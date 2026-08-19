"""
Basis Threats Service - Generate orthogonal dimensionless threats from FDA devices.

Generate mode samples treatment-arm products, asks an LLM to extract canonical
threat objects from product profile text, removes duplicate threat names,
and inserts the resulting rows.

Validate mode samples holdout products, extracts threats without inserting
them, compares them to a generated basis version, and reports coverage.
"""

import argparse
import asyncio
import hashlib
import json
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import yaml
from dotenv import load_dotenv
from openai import OpenAI

from pitboss.logging_util import log_event


load_dotenv()

logger = logging.getLogger("basis_threats_service")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

CARD_ID = "7513ebae-a266-49b1-a088-3afacec21a02"
_PROMPT_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def load_basis_threats_prompt_config() -> Dict[str, Any]:
    """Load and cache the versioned BASIS_THREATS prompt configuration."""
    global _PROMPT_CONFIG_CACHE
    if _PROMPT_CONFIG_CACHE is not None:
        return _PROMPT_CONFIG_CACHE

    path = Path(__file__).resolve().parents[2] / "prompts" / "rules" / "BASIS_THREATS.yaml"
    with path.open(encoding="utf-8") as prompt_file:
        yaml_data = yaml.safe_load(prompt_file)

    config = yaml_data.get("BASIS_THREATS") if isinstance(yaml_data, dict) else None
    required_keys = {"version", "task", "system_prompt", "output_contract", "dedupe_examples"}
    if not isinstance(config, dict) or not required_keys.issubset(config):
        raise RuntimeError(f"Invalid basis threat prompt configuration: {path}")

    _PROMPT_CONFIG_CACHE = config
    logger.info("Loaded basis threat prompt configuration: %s", path)
    return config


class BasisThreatsService:
    """Generate and persist a basis set of threats for sampled products."""

    def __init__(
        self,
        db_url: str,
        model_name: str,
        dry_run: bool = False,
        sample_per_arm: int = 10,
        card_id: str = CARD_ID,
        target_model_id: Optional[int] = None,
    ):
        self.db_url = db_url
        self.model_name = model_name
        self.dry_run = dry_run
        self.sample_per_arm = sample_per_arm
        self.card_id = card_id
        self.target_model_id = target_model_id
        self.pool: Optional[asyncpg.Pool] = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.prompt_config = load_basis_threats_prompt_config()
        self.prompt_version = str(self.prompt_config["version"])

    async def initialize(self) -> None:
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=3,
            command_timeout=120,
        )

    async def cleanup(self) -> None:
        if self.pool:
            await self.pool.close()

    async def get_active_model_id(self) -> int:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT model_id
                FROM public.active_models
                ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
                LIMIT 1
                """
            )

        if not row:
            raise RuntimeError("No active model_id found in public.active_models")

        return int(row["model_id"])

    async def validate_card_id(self) -> None:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM public.cards
                    WHERE id = $1::uuid
                ) AS card_exists
                """,
                self.card_id,
            )

        if not row or not row["card_exists"]:
            raise RuntimeError(f"Card id {self.card_id} does not exist in public.cards")

    async def get_next_run_version(self, model_id: int) -> int:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM threat.threats
                WHERE model_id = $1 AND card_id = $2::uuid
                """,
                model_id,
                self.card_id,
            )

        return int(row["next_version"])

    async def get_latest_run_version(self, model_id: int) -> int:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT MAX(version) AS latest_version
                FROM threat.threats
                WHERE model_id = $1 AND card_id = $2::uuid
                """,
                model_id,
                self.card_id,
            )

        if not row or row["latest_version"] is None:
            raise RuntimeError("No generated basis threat version found for the active model/card")

        return int(row["latest_version"])

    async def get_single_product(self, product_id: int) -> Dict[str, Any]:
        """Fetch a single product by ID."""
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    p.id,
                    p.submission_number,
                    p.device,
                    p.company,
                    p.intended_use,
                    p.indications_for_use,
                    p.device_description,
                    p.org_id,
                    o.name AS org_name,
                    o.arm
                FROM public.products p
                JOIN public.orgs o ON o.id = p.org_id
                WHERE p.id = $1
                  AND p.deleted_at IS NULL
                  AND o.deleted_at IS NULL
                  AND (
                      NULLIF(p.intended_use, '') IS NOT NULL
                      OR NULLIF(p.indications_for_use, '') IS NOT NULL
                      OR NULLIF(p.device_description, '') IS NOT NULL
                  )
                """,
                product_id,
            )

        if not row:
            raise ValueError(f"Product {product_id} not found or missing device profile")
        return dict(row)

    async def sample_products(self, arms: List[int]) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Service not initialized")
        if not arms:
            raise ValueError("At least one arm must be specified")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH ranked_products AS (
                    SELECT
                        p.id,
                        p.submission_number,
                        p.device,
                        p.company,
                        p.intended_use,
                        p.indications_for_use,
                        p.device_description,
                        p.org_id,
                        o.name AS org_name,
                        o.arm,
                        ROW_NUMBER() OVER (PARTITION BY o.arm ORDER BY random()) AS arm_rank
                    FROM public.products p
                    JOIN public.orgs o ON o.id = p.org_id
                    WHERE p.deleted_at IS NULL
                      AND p.process_flag = false
                      AND o.deleted_at IS NULL
                      AND o.arm = ANY($1::int[])
                      AND (
                          NULLIF(p.intended_use, '') IS NOT NULL
                          OR NULLIF(p.indications_for_use, '') IS NOT NULL
                          OR NULLIF(p.device_description, '') IS NOT NULL
                      )
                )
                SELECT *
                FROM ranked_products
                WHERE arm_rank <= $2
                ORDER BY arm, arm_rank
                """,
                arms,
                self.sample_per_arm,
            )

        return [dict(row) for row in rows]

    async def create_basis_run(
        self,
        model_id: int,
        arms: List[int],
        existing_basis_threat_count: int,
    ) -> int:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            run_id = await conn.fetchval(
                """
                INSERT INTO threat.basis_runs (
                    model_id,
                    card_id,
                    arms,
                    sample_per_arm,
                    llm_model,
                    prompt_version,
                    existing_basis_threat_count
                )
                VALUES ($1, $2::uuid, $3::integer[], $4, $5, $6, $7)
                RETURNING id
                """,
                model_id,
                self.card_id,
                arms,
                self.sample_per_arm,
                self.model_name,
                self.prompt_version,
                existing_basis_threat_count,
            )

        return int(run_id)

    async def complete_basis_run(
        self,
        run_id: int,
        candidate_threat_count: int,
        run_unique_candidate_threat_count: int,
        new_basis_threat_count: int,
    ) -> None:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE threat.basis_runs
                SET status = 'completed',
                    candidate_threat_count = $2,
                    run_unique_candidate_threat_count = $3,
                    new_basis_threat_count = $4,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                run_id,
                candidate_threat_count,
                run_unique_candidate_threat_count,
                new_basis_threat_count,
            )

    async def fail_basis_run(self, run_id: int, error: str) -> None:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE threat.basis_runs
                SET status = 'failed',
                    error = $2,
                    finished_at = CURRENT_TIMESTAMP
                WHERE id = $1
                """,
                run_id,
                error[:4000],
            )

    async def fetch_threats_by_tags(
        self,
        model_id: int,
        tags: List[str],
    ) -> List[Dict[str, Any]]:
        if not self.pool or not tags:
            return []

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tag, name
                FROM threat.threats
                WHERE model_id = $1
                  AND tag = ANY($2::text[])
                """,
                model_id,
                tags,
            )

        return [dict(row) for row in rows]

    async def insert_threat_provenance(self, records: List[Dict[str, Any]]) -> int:
        if not self.pool or not records or self.dry_run:
            return 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                await conn.executemany(
                    """
                    INSERT INTO threat.threat_provenance (
                        run_id,
                        threat_id,
                        product_id,
                        model_id,
                        basis_version,
                        generated_name,
                        generated_payload,
                        match_type,
                        match_score,
                        llm_model,
                        prompt_version,
                        source_profile_hash,
                        source_token_estimate,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9,
                        $10, $11, $12, $13, $14, $15, $16
                    )
                    ON CONFLICT (run_id, product_id, generated_name) DO NOTHING
                    """,
                    [
                        (
                            record["run_id"],
                            record["threat_id"],
                            record["product_id"],
                            record["model_id"],
                            record["basis_version"],
                            record["generated_name"],
                            json.dumps(record["generated_payload"]),
                            record["match_type"],
                            record["match_score"],
                            self.model_name,
                            self.prompt_version,
                            record["source_profile_hash"],
                            record["source_token_estimate"],
                            record["prompt_tokens"],
                            record["completion_tokens"],
                            record["total_tokens"],
                        )
                        for record in records
                    ],
                )

        return len(records)

    async def mark_product_processed(self, product_id: int) -> None:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE public.products
                SET process_flag = true,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $1
                  AND process_flag = false
                """,
                product_id,
            )

    async def fetch_basis_threats(self, model_id: int, version: int) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, tag, name, description, domain
                FROM threat.threats
                WHERE model_id = $1
                  AND card_id = $2::uuid
                  AND version = $3
                  AND disabled = false
                ORDER BY name
                """,
                model_id,
                self.card_id,
                version,
            )

        return [dict(row) for row in rows]

    async def fetch_existing_basis_threats(self, model_id: int) -> List[Dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id,
                    model_id,
                    tag,
                    name,
                    description,
                    probability,
                    damage_description,
                    spoofing,
                    tampering,
                    repudiation,
                    information_disclosure,
                    denial_of_service,
                    elevation_of_privilege,
                    mitigation_level,
                    disabled,
                    card_id::text AS card_id,
                    version,
                    domain,
                    created_at,
                    updated_at
                FROM threat.threats
                WHERE model_id = $1
                  AND card_id = $2::uuid
                  AND disabled = false
                ORDER BY name
                """,
                model_id,
                self.card_id,
            )

        return [dict(row) for row in rows]

    async def extract_threats_for_product(
        self,
        product: Dict[str, Any],
        model_id: int,
        version: int,
    ) -> Dict[str, Any]:
        source_profile_text = self.build_source_profile_text(product)
        source_token_estimate = self.estimate_token_count(source_profile_text)
        source_profile_hash = hashlib.sha256(source_profile_text.encode("utf-8")).hexdigest()
        system_prompt = str(self.prompt_config["system_prompt"]).strip()
        user_payload = {
            "task": self.prompt_config["task"],
            "required_output_shape": self.prompt_config["output_contract"],
            "fixed_attributes": {
                "model_id": model_id,
                "card_id": self.card_id,
                "version": version,
            },
            "dedupe_examples": self.prompt_config["dedupe_examples"],
            "device": {
                "id": product["id"],
                "submission_number": product.get("submission_number"),
                "device": product.get("device"),
                "company": product.get("company"),
                "org_name": product.get("org_name"),
                "org_arm": product.get("arm"),
                "intended_use": product.get("intended_use"),
                "indications_for_use": product.get("indications_for_use"),
                "device_description": product.get("device_description"),
            },
        }

        def _call_openai() -> tuple[str, Dict[str, Optional[int]]]:
            # gpt-5.5 and newer gpt-5.6 variants require temperature=1.0
            temperature = 1.0 if self.model_name in {"gpt-5.5", "gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna"} else 0.0
            response = self.openai_client.chat.completions.create(
                model=self.model_name,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
                response_format={"type": "json_object"},
                timeout=60.0,
            )
            usage = getattr(response, "usage", None)
            usage_dict = {
                "prompt_tokens": getattr(usage, "prompt_tokens", None),
                "completion_tokens": getattr(usage, "completion_tokens", None),
                "total_tokens": getattr(usage, "total_tokens", None),
            }
            return response.choices[0].message.content, usage_dict

        raw_response, usage = await asyncio.to_thread(_call_openai)
        parsed = json.loads(raw_response)
        threats = parsed.get("threats", [])
        if not isinstance(threats, list):
            threats = []

        normalized_threats = self.normalize_threats(threats, model_id, version, product["id"])
        return {
            "threats": normalized_threats,
            "source_profile_hash": source_profile_hash,
            "source_profile_tokens_estimate": source_token_estimate,
            "openai_usage": usage,
        }

    def normalize_threats(
        self,
        threats: List[Any],
        model_id: int,
        version: int,
        product_id: int,
    ) -> List[Dict[str, Any]]:
        canonical_by_name: Dict[str, Dict[str, Any]] = {}

        for raw_threat in threats:
            if not isinstance(raw_threat, dict):
                continue

            name = self.clean_text(raw_threat.get("name"))
            if not name:
                continue
            now_iso = datetime.utcnow().isoformat()

            candidate = {
                "model_id": model_id,
                "name": name,
                "description": self.clean_text(raw_threat.get("description")),
                "probability": self.clamp_int(raw_threat.get("probability"), minimum=1, maximum=5, default=3),
                "damage_description": self.clean_text(raw_threat.get("damage_description")),
                "spoofing": self.parse_bool(raw_threat.get("spoofing")),
                "tampering": self.parse_bool(raw_threat.get("tampering")),
                "repudiation": self.parse_bool(raw_threat.get("repudiation")),
                "information_disclosure": self.parse_bool(raw_threat.get("information_disclosure")),
                "denial_of_service": self.parse_bool(raw_threat.get("denial_of_service")),
                "elevation_of_privilege": self.parse_bool(raw_threat.get("elevation_of_privilege")),
                "mitigation_level": self.clamp_int(raw_threat.get("mitigation_level"), minimum=0, maximum=5, default=0),
                "disabled": self.parse_bool(raw_threat.get("disabled")),
                "created_at": now_iso,
                "updated_at": now_iso,
                "card_id": self.card_id,
                "version": version,
                "domain": self.clean_text(raw_threat.get("domain")) or "clinical",
                "tag": "",
            }

            key = self.name_key(name)
            existing = canonical_by_name.get(key)
            if existing is None or len(candidate["name"]) < len(existing["name"]):
                canonical_by_name[key] = candidate

        normalized = list(canonical_by_name.values())
        normalized.sort(key=lambda item: item["name"].lower())

        for index, threat in enumerate(normalized, 1):
            threat["tag"] = f"BASIS-{version}-{product_id}-{index:02d}"

        return normalized

    @staticmethod
    def clean_text(value: Any) -> str:
        if value is None:
            return ""
        return re.sub(r"\s+", " ", str(value)).strip()

    @staticmethod
    def build_source_profile_text(product: Dict[str, Any]) -> str:
        fields = [
            ("device_description", product.get("device_description")),
            ("intended_use", product.get("intended_use")),
            ("indications_for_use", product.get("indications_for_use")),
        ]
        return "\n\n".join(
            f"{field_name}: {BasisThreatsService.clean_text(value)}"
            for field_name, value in fields
            if BasisThreatsService.clean_text(value)
        )

    @staticmethod
    def estimate_token_count(text: str) -> int:
        if not text:
            return 0
        word_like_tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        character_estimate = max(1, round(len(text) / 4))
        return max(len(word_like_tokens), character_estimate)

    @staticmethod
    def name_key(name: str) -> str:
        key = name.lower()
        key = re.sub(r"\b(third[- ]party|external)\b", "", key)
        key = re.sub(r"\b(the|a|an|is|are|to|of|or|and)\b", "", key)
        key = re.sub(r"[^a-z0-9]+", " ", key)
        return re.sub(r"\s+", " ", key).strip()
    @staticmethod
    def parse_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "t", "yes", "y", "1"}
        return False

    @staticmethod
    def clamp_int(value: Any, minimum: int, maximum: int, default: int) -> int:
        try:
            parsed = int(float(value))
        except (TypeError, ValueError):
            return default
        return max(minimum, min(maximum, parsed))

    def find_basis_match(
        self,
        validation_threat: Dict[str, Any],
        basis_threats: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        validation_key = self.name_key(validation_threat.get("name", ""))
        validation_tokens = set(validation_key.split())

        if not validation_key or not validation_tokens:
            return None

        best_match: Optional[Dict[str, Any]] = None
        best_score = 0.0

        for basis_threat in basis_threats:
            basis_key = self.name_key(basis_threat.get("name", ""))
            basis_tokens = set(basis_key.split())
            if not basis_key or not basis_tokens:
                continue

            if validation_key == basis_key:
                return {**basis_threat, "match_type": "normalized_name", "score": 1.0}

            intersection = validation_tokens & basis_tokens
            containment = len(intersection) / min(len(validation_tokens), len(basis_tokens))
            jaccard = len(intersection) / len(validation_tokens | basis_tokens)
            score = max(containment, jaccard)
            if score > best_score:
                best_score = score
                best_match = {**basis_threat, "match_type": "token_overlap", "score": round(score, 3)}

        if best_match and best_score >= 0.8:
            return best_match

        return None

    def dedupe_basis_threats(self, threats: List[Dict[str, Any]], version: int) -> List[Dict[str, Any]]:
        canonical_by_name: Dict[str, Dict[str, Any]] = {}

        for threat in threats:
            name = self.clean_text(threat.get("name"))
            if not name:
                continue
            key = self.name_key(name)
            if not key:
                continue

            candidate = dict(threat)
            candidate["name"] = name
            existing = canonical_by_name.get(key)
            if existing is None or len(candidate["name"]) < len(existing["name"]):
                canonical_by_name[key] = candidate

        deduped = sorted(canonical_by_name.values(), key=lambda item: item["name"].lower())
        for index, threat in enumerate(deduped, 1):
            threat["tag"] = f"BASIS-{version}-{index:03d}"

        return deduped

    def select_novel_basis_threats(
        self,
        candidate_threats: List[Dict[str, Any]],
        existing_basis_threats: List[Dict[str, Any]],
        version: int,
    ) -> List[Dict[str, Any]]:
        novel_threats = []

        for candidate in candidate_threats:
            if self.find_basis_match(candidate, existing_basis_threats):
                continue
            novel_threats.append(dict(candidate))

        return self.dedupe_basis_threats(novel_threats, version)

    async def insert_threats(self, threats_json: Dict[str, Any]) -> int:
        if not self.pool:
            raise RuntimeError("Service not initialized")

        threats = threats_json.get("threats", [])
        if not threats:
            return 0

        if self.dry_run:
            return len(threats)

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                inserted = 0
                for threat in threats:
                    await conn.execute(
                        """
                        INSERT INTO threat.threats (
                            model_id,
                            tag,
                            name,
                            description,
                            probability,
                            damage_description,
                            spoofing,
                            tampering,
                            repudiation,
                            information_disclosure,
                            denial_of_service,
                            elevation_of_privilege,
                            mitigation_level,
                            disabled,
                            created_at,
                            updated_at,
                            card_id,
                            version,
                            domain
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15::timestamp,
                            $16::timestamp, $17::uuid, $18, $19
                        )
                        ON CONFLICT (model_id, tag) DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            probability = EXCLUDED.probability,
                            damage_description = EXCLUDED.damage_description,
                            spoofing = EXCLUDED.spoofing,
                            tampering = EXCLUDED.tampering,
                            repudiation = EXCLUDED.repudiation,
                            information_disclosure = EXCLUDED.information_disclosure,
                            denial_of_service = EXCLUDED.denial_of_service,
                            elevation_of_privilege = EXCLUDED.elevation_of_privilege,
                            mitigation_level = EXCLUDED.mitigation_level,
                            disabled = EXCLUDED.disabled,
                            card_id = EXCLUDED.card_id,
                            domain = EXCLUDED.domain,
                            updated_at = EXCLUDED.updated_at
                        """,
                        threat["model_id"],
                        threat["tag"],
                        threat["name"],
                        threat["description"],
                        threat["probability"],
                        threat["damage_description"],
                        threat["spoofing"],
                        threat["tampering"],
                        threat["repudiation"],
                        threat["information_disclosure"],
                        threat["denial_of_service"],
                        threat["elevation_of_privilege"],
                        threat["mitigation_level"],
                        threat["disabled"],
                        datetime.fromisoformat(threat["created_at"]),
                        datetime.fromisoformat(threat["updated_at"]),
                        threat["card_id"],
                        threat["version"],
                        threat["domain"],
                    )
                    inserted += 1

        return inserted

    async def process_generate_single_product(self, product_id: int, target_model_id: Optional[int] = None) -> Dict[str, Any]:
        """Generate threats for a single product and insert into target model.
        
        Args:
            product_id: Product ID to process
            target_model_id: Target threat model ID for insertion. If not provided, uses active model.
        """
        if target_model_id is not None:
            model_id = target_model_id
        elif self.target_model_id is not None:
            model_id = self.target_model_id
        else:
            model_id = await self.get_active_model_id()
        await self.validate_card_id()
        version = await self.get_next_run_version(model_id)
        existing_basis_threats = await self.fetch_existing_basis_threats(model_id)
        product = await self.get_single_product(product_id)
        products = [product]

        results: Dict[str, Any] = {
            "mode": "generate",
            "model_id": model_id,
            "product_id": product_id,
            "product_name": product["device"],
            "card_id": self.card_id,
            "version": version,
            "dry_run": self.dry_run,
            "existing_basis_threat_count": len(existing_basis_threats),
            "processed": [],
        }
        candidate_threats: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []

        print(f"\nGenerating threats for {product['device']} (product_id={product_id})")
        threats_json = await self.extract_threats_for_product(product, model_id, version)
        unique_count = len(threats_json["threats"])
        candidate_threats.extend(threats_json["threats"])
        usage = threats_json["openai_usage"]
        for threat in threats_json["threats"]:
            observations.append(
                {
                    "product_id": product["id"],
                    "generated_threat": threat,
                    "source_profile_hash": threats_json["source_profile_hash"],
                    "source_token_estimate": threats_json["source_profile_tokens_estimate"],
                    "prompt_tokens": usage.get("prompt_tokens"),
                    "completion_tokens": usage.get("completion_tokens"),
                    "total_tokens": usage.get("total_tokens"),
                }
            )
        print(f"{product['device']}: {unique_count} unique threats found")
        self.print_token_usage(threats_json)

        results["processed"].append(
            {
                "product_id": product["id"],
                "device": product["device"],
                "arm": product["arm"],
                "unique_threats": unique_count,
                "inserted_threats": 0,
                "source_profile_tokens_estimate": threats_json["source_profile_tokens_estimate"],
                "openai_usage": threats_json["openai_usage"],
                "threats": threats_json["threats"],
            }
        )
        deduped_candidate_threats = self.dedupe_basis_threats(candidate_threats, version)
        matched_observations = []
        unmatched_observations = []
        for observation in observations:
            match = self.find_basis_match(
                observation["generated_threat"],
                existing_basis_threats,
            )
            if match:
                matched_observations.append(
                    {
                        **observation,
                        "threat_id": match["id"],
                        "match_type": match["match_type"],
                        "match_score": match["score"],
                    }
                )
            else:
                unmatched_observations.append(observation)

        novel_threats = self.dedupe_basis_threats(
            [observation["generated_threat"] for observation in unmatched_observations],
            version,
        )
        inserted_count = await self.insert_threats({"threats": novel_threats})
        inserted_threats = await self.fetch_threats_by_tags(
            model_id,
            [threat["tag"] for threat in novel_threats],
        )
        new_threat_ids_by_name_key = {
            self.name_key(threat["name"]): threat["id"]
            for threat in inserted_threats
        }
        for observation in unmatched_observations:
            threat_key = self.name_key(observation["generated_threat"]["name"])
            threat_id = new_threat_ids_by_name_key.get(threat_key)
            if threat_id is None:
                raise RuntimeError(
                    f"Could not resolve inserted basis threat for {observation['generated_threat']['name']}"
                )
            matched_observations.append(
                {
                    **observation,
                    "threat_id": threat_id,
                    "match_type": "new",
                    "match_score": 1.0,
                }
            )

        results["candidate_threat_count"] = len(candidate_threats)
        results["run_unique_candidate_threat_count"] = len(deduped_candidate_threats)
        results["new_basis_threat_count"] = len(novel_threats)
        results["final_inserted_threats"] = inserted_count
        results["threat_names_found"] = [threat["name"] for threat in novel_threats]
        results["deduped_candidate_threats"] = deduped_candidate_threats
        results["new_basis_threats"] = novel_threats
        results["matched_observations"] = matched_observations

        return results

    async def process_generate(self, arms: List[int]) -> Dict[str, Any]:
        model_id = await self.get_active_model_id()
        await self.validate_card_id()
        version = await self.get_next_run_version(model_id)
        existing_basis_threats = await self.fetch_existing_basis_threats(model_id)
        products = await self.sample_products(arms)
        run_id = None
        if not self.dry_run:
            run_id = await self.create_basis_run(
                model_id,
                arms,
                len(existing_basis_threats),
            )

        if len(products) < self.sample_per_arm * len(arms):
            logger.warning(
                "Sample contains %s products; expected %s.",
                len(products),
                self.sample_per_arm * len(arms),
            )

        results: Dict[str, Any] = {
            "mode": "generate",
            "model_id": model_id,
            "card_id": self.card_id,
            "version": version,
            "arms": arms,
            "sample_size": len(products),
            "dry_run": self.dry_run,
            "run_id": run_id,
            "existing_basis_threat_count": len(existing_basis_threats),
            "processed": [],
        }
        candidate_threats: List[Dict[str, Any]] = []
        observations: List[Dict[str, Any]] = []

        for index, product in enumerate(products, 1):
            print(f"\n[{index}/{len(products)}] {product['device']} (arm {product['arm']})")
            threats_json = await self.extract_threats_for_product(product, model_id, version)
            unique_count = len(threats_json["threats"])
            candidate_threats.extend(threats_json["threats"])
            usage = threats_json["openai_usage"]
            for threat in threats_json["threats"]:
                observations.append(
                    {
                        "product_id": product["id"],
                        "generated_threat": threat,
                        "source_profile_hash": threats_json["source_profile_hash"],
                        "source_token_estimate": threats_json["source_profile_tokens_estimate"],
                        "prompt_tokens": usage.get("prompt_tokens"),
                        "completion_tokens": usage.get("completion_tokens"),
                        "total_tokens": usage.get("total_tokens"),
                    }
                )
            print(f"{product['device']}: {unique_count} unique threats found")
            self.print_token_usage(threats_json)

            results["processed"].append(
                {
                    "product_id": product["id"],
                    "device": product["device"],
                    "arm": product["arm"],
                    "unique_threats": unique_count,
                    "inserted_threats": 0,
                    "source_profile_tokens_estimate": threats_json["source_profile_tokens_estimate"],
                    "openai_usage": threats_json["openai_usage"],
                    "threats": threats_json["threats"],
                }
            )
        deduped_candidate_threats = self.dedupe_basis_threats(candidate_threats, version)
        matched_observations = []
        unmatched_observations = []
        for observation in observations:
            match = self.find_basis_match(
                observation["generated_threat"],
                existing_basis_threats,
            )
            if match:
                matched_observations.append(
                    {
                        **observation,
                        "threat_id": match["id"],
                        "match_type": match["match_type"],
                        "match_score": match["score"],
                    }
                )
            else:
                unmatched_observations.append(observation)

        novel_threats = self.dedupe_basis_threats(
            [observation["generated_threat"] for observation in unmatched_observations],
            version,
        )
        inserted_count = await self.insert_threats({"threats": novel_threats})
        inserted_threats = await self.fetch_threats_by_tags(
            model_id,
            [threat["tag"] for threat in novel_threats],
        )
        new_threat_ids_by_name_key = {
            self.name_key(threat["name"]): threat["id"]
            for threat in inserted_threats
        }
        for observation in unmatched_observations:
            threat_key = self.name_key(observation["generated_threat"]["name"])
            threat_id = new_threat_ids_by_name_key.get(threat_key)
            if threat_id is None:
                raise RuntimeError(
                    f"Could not resolve inserted basis threat for {observation['generated_threat']['name']}"
                )
            matched_observations.append(
                {
                    **observation,
                    "threat_id": threat_id,
                    "match_type": "new",
                    "match_score": 1.0,
                }
            )

        provenance_count = 0
        if run_id is not None:
            provenance_count = await self.insert_threat_provenance(
                [
                    {
                        "run_id": run_id,
                        "threat_id": observation["threat_id"],
                        "product_id": observation["product_id"],
                        "model_id": model_id,
                        "basis_version": version,
                        "generated_name": observation["generated_threat"]["name"],
                        "generated_payload": observation["generated_threat"],
                        "match_type": observation["match_type"],
                        "match_score": observation["match_score"],
                        "source_profile_hash": observation["source_profile_hash"],
                        "source_token_estimate": observation["source_token_estimate"],
                        "prompt_tokens": observation["prompt_tokens"],
                        "completion_tokens": observation["completion_tokens"],
                        "total_tokens": observation["total_tokens"],
                    }
                    for observation in matched_observations
                ]
            )
            for product in results["processed"]:
                await self.mark_product_processed(product["product_id"])
            await self.complete_basis_run(
                run_id,
                len(candidate_threats),
                len(deduped_candidate_threats),
                len(novel_threats),
            )

        results["candidate_threat_count"] = len(candidate_threats)
        results["run_unique_candidate_threat_count"] = len(deduped_candidate_threats)
        results["new_basis_threat_count"] = len(novel_threats)
        results["final_inserted_threats"] = inserted_count
        results["provenance_count"] = provenance_count
        results["threat_names_found"] = [threat["name"] for threat in novel_threats]
        results["deduped_candidate_threats"] = deduped_candidate_threats
        results["new_basis_threats"] = novel_threats

        print(f"\nCandidate threats found before global dedupe: {len(candidate_threats)}")
        print(f"Existing basis threats for active model/card: {len(existing_basis_threats)}")
        print(f"Run-unique candidate threats after global dedupe: {len(deduped_candidate_threats)}")
        print(f"New basis threats after existing-basis dedupe: {len(novel_threats)}")
        print(f"Threat provenance records: {provenance_count}")
        if self.dry_run:
            print(f"Dry run: {inserted_count} new basis threats not inserted")
        else:
            print(f"Inserted new basis threats: {inserted_count}")
        print("\nNew threat names found")
        for threat_name in results["threat_names_found"]:
            print(f"- {threat_name}")

        token_summary = self.print_run_token_summary(results["processed"])
        results["model"] = self.model_name
        results["openai_usage_total"] = token_summary

        if self.pool and not self.dry_run:
            await log_event(self.pool, "BASIS_THREATS_COMPLETE", results)

        return results

    async def process_validate(self, arms: List[int], version: Optional[int]) -> Dict[str, Any]:
        model_id = await self.get_active_model_id()
        await self.validate_card_id()
        basis_version = version if version is not None else await self.get_latest_run_version(model_id)
        basis_threats = await self.fetch_basis_threats(model_id, basis_version)
        if not basis_threats:
            raise RuntimeError(f"No basis threats found for version {basis_version}")

        products = await self.sample_products(arms)
        expected = self.sample_per_arm * len(arms)
        if len(products) < expected:
            logger.warning("Sample contains %s products; expected %s.", len(products), expected)

        results: Dict[str, Any] = {
            "mode": "validate",
            "model_id": model_id,
            "card_id": self.card_id,
            "version": basis_version,
            "arms": arms,
            "basis_threat_count": len(basis_threats),
            "sample_size": len(products),
            "total_extracted_threats": 0,
            "matched_threats": 0,
            "coverage": 0.0,
            "processed": [],
        }

        for index, product in enumerate(products, 1):
            print(f"\n[{index}/{len(products)}] {product['device']} (arm {product['arm']})")
            threats_json = await self.extract_threats_for_product(product, model_id, basis_version)
            validation_threats = threats_json["threats"]
            matches = []
            unmatched = []

            for threat in validation_threats:
                match = self.find_basis_match(threat, basis_threats)
                if match:
                    matches.append({"validation_threat": threat["name"], "basis_threat": match["name"], "match_type": match["match_type"], "score": match["score"]})
                else:
                    unmatched.append(threat["name"])

            total_count = len(validation_threats)
            matched_count = len(matches)
            device_coverage = matched_count / total_count if total_count else 0.0
            results["total_extracted_threats"] += total_count
            results["matched_threats"] += matched_count

            print(f"{product['device']}: {matched_count}/{total_count} threats matched")
            print(f"Coverage: {device_coverage:.1%}")
            self.print_token_usage(threats_json)
            if unmatched:
                print("Unmatched threats:")
                for threat_name in unmatched:
                    print(f"  - {threat_name}")

            results["processed"].append(
                {
                    "product_id": product["id"],
                    "device": product["device"],
                    "arm": product["arm"],
                    "extracted_threats": total_count,
                    "matched_threats": matched_count,
                    "coverage": device_coverage,
                    "source_profile_tokens_estimate": threats_json["source_profile_tokens_estimate"],
                    "openai_usage": threats_json["openai_usage"],
                    "matches": matches,
                    "unmatched": unmatched,
                }
            )

        total = results["total_extracted_threats"]
        matched = results["matched_threats"]
        results["coverage"] = matched / total if total else 0.0
        print("\nValidation summary")
        print(f"Basis version: {basis_version}")
        print(f"Basis threats: {len(basis_threats)}")
        print(f"Matched threats: {matched}/{total}")
        print(f"Coverage: {results['coverage']:.1%}")

        token_summary = self.print_run_token_summary(results["processed"])
        results["model"] = self.model_name
        results["openai_usage_total"] = token_summary

        return results


    @staticmethod
    def summarize_token_usage(processed: List[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        saw_usage = False

        for item in processed:
            usage = item.get("openai_usage") or {}
            if not usage:
                continue
            saw_usage = True
            prompt_tokens += int(usage.get("prompt_tokens") or 0)
            completion_tokens += int(usage.get("completion_tokens") or 0)
            total_tokens += int(usage.get("total_tokens") or 0)

        if not saw_usage:
            return {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
            }

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    def print_run_token_summary(self, processed: List[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        usage = self.summarize_token_usage(processed)
        print(f"\nModel: {self.model_name}")
        if usage["total_tokens"] is None:
            print("Total tokens consumed: unavailable")
        else:
            print(
                "Total tokens consumed: "
                f"{usage['total_tokens']} "
                f"(prompt={usage['prompt_tokens']}, completion={usage['completion_tokens']})"
            )
        return usage

    @staticmethod
    def print_token_usage(threats_json: Dict[str, Any]) -> None:
        usage = threats_json.get("openai_usage") or {}
        print(
            "Source profile tokens (estimate): "
            f"{threats_json.get('source_profile_tokens_estimate', 0)}"
        )
        if usage.get("total_tokens") is not None:
            print(
                "OpenAI tokens: "
                f"prompt={usage.get('prompt_tokens')} "
                f"completion={usage.get('completion_tokens')} "
                f"total={usage.get('total_tokens')}"
            )


def parse_args(argv: List[str]) -> argparse.Namespace:
    if argv and argv[0] not in {"generate", "validate", "-h", "--help"}:
        argv = ["generate", *argv]
    elif not argv:
        argv = ["generate"]
    parser = argparse.ArgumentParser(
        description="Generate a basis set of orthogonal dimensionless threats from sampled products.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Build the basis threat set from treatment arms.",
    )
    generate_parser.add_argument(
        "--arms",
        default="2,3",
        help="Comma-separated org arms used for basis generation (default: 2,3).",
    )
    generate_parser.add_argument(
        "--sample-per-arm",
        type=int,
        default=10,
        help="Number of devices sampled from each org arm (default: 10).",
    )
    generate_parser.add_argument(
        "--card-id",
        default=CARD_ID,
        help=f"Card UUID to assign to generated threats (default: {CARD_ID}).",
    )
    generate_parser.add_argument(
        "--model",
        default=os.getenv("BASIS_THREATS_MODEL", "gpt-5.6-terra"),
        help="OpenAI model used for threat extraction (default: BASIS_THREATS_MODEL or gpt-5.6-terra).",
    )
    generate_parser.add_argument(
        "--product-id",
        type=int,
        default=None,
        help="Product ID for single-product threat generation (alternative to --arms). Used for validation.",
    )
    generate_parser.add_argument(
        "--model-id",
        type=int,
        default=None,
        help="Target threat model ID for insertion (default: uses active model).",
    )
    generate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print counts without inserting threats.",
    )

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a generated basis set against holdout arms.",
    )
    validate_parser.add_argument(
        "--arms",
        default="1",
        help="Comma-separated holdout org arms used for validation (default: 1).",
    )
    validate_parser.add_argument(
        "--sample-per-arm",
        type=int,
        default=10,
        help="Number of devices sampled from each holdout arm (default: 10).",
    )
    validate_parser.add_argument(
        "--card-id",
        default=CARD_ID,
        help=f"Card UUID for the basis threats (default: {CARD_ID}).",
    )
    validate_parser.add_argument(
        "--model",
        default=os.getenv("BASIS_THREATS_MODEL", "gpt-5.6-terra"),
        help="OpenAI model used for validation threat extraction (default: BASIS_THREATS_MODEL or gpt-5.6-terra).",
    )
    validate_parser.add_argument(
        "--version",
        default="latest",
        help="Basis threat version to validate against (default: latest).",
    )
    return parser.parse_args(argv)


def parse_arms(value: str) -> List[int]:
    try:
        arms = [int(item.strip()) for item in value.split(",") if item.strip()]
    except ValueError as exc:
        raise ValueError(f"Invalid arms list: {value}") from exc

    invalid = [arm for arm in arms if arm not in {1, 2, 3}]
    if invalid:
        raise ValueError(f"Arms must be 1, 2, or 3; got {invalid}")
    if not arms:
        raise ValueError("At least one arm must be specified")

    return arms


def validate_sample_per_arm(value: int) -> int:
    if value < 1:
        raise ValueError("sample-per-arm must be at least 1")
    return value

def parse_version(value: str) -> Optional[int]:
    if value.strip().lower() == "latest":
        return None
    try:
        version = int(value)
    except ValueError as exc:
        raise ValueError(f"Invalid version: {value}") from exc
    if version < 1:
        raise ValueError("Version must be a positive integer or latest")
    return version


async def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
        # Handle single product mode
        if args.mode == "generate" and hasattr(args, "product_id") and args.product_id:
            arms = None
            sample_per_arm = None
        else:
            arms = parse_arms(args.arms)
            sample_per_arm = validate_sample_per_arm(args.sample_per_arm)
        validation_version = parse_version(args.version) if args.mode == "validate" else None
    except ValueError as exc:
        logger.error(str(exc))
        sys.exit(1)

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL environment variable not set")
        sys.exit(1)

    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY environment variable not set")
        sys.exit(1)

    service = BasisThreatsService(
        db_url=db_url,
        model_name=args.model,
        dry_run=getattr(args, "dry_run", False),
        sample_per_arm=sample_per_arm,
        card_id=args.card_id,
        target_model_id=getattr(args, "model_id", None),
    )

    try:
        await service.initialize()
        if args.mode == "generate":
            if hasattr(args, "product_id") and args.product_id:
                target_model_id = getattr(args, "model_id", None)
                await service.process_generate_single_product(args.product_id, target_model_id=target_model_id)
            else:
                await service.process_generate(arms)
        else:
            await service.process_validate(arms, validation_version)
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
