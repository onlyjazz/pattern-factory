"""
Products Threats Service - Generate threats per-product with isolated models.

Extract threats for individual products and create a separate threat model
for each product. No deduping across products—each product gets its own
isolated model containing its extracted threats.

Supports:
1. Single product mode (--product-id <id>)
2. Product range mode (--product-id-range <start>-<end>)
3. Arm sampling mode (--arms <list> --sample-per-arm <n>)
4. All-in-arms mode (--arms <list> --all-in-arms)
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

logger = logging.getLogger("products_threats_service")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

CARD_ID = "7513ebae-a266-49b1-a088-3afacec21a02"
_PROMPT_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def load_product_threats_prompt_config() -> Dict[str, Any]:
    """Load and cache the versioned BASIS_THREATS prompt configuration."""
    global _PROMPT_CONFIG_CACHE
    if _PROMPT_CONFIG_CACHE is not None:
        return _PROMPT_CONFIG_CACHE

    path = Path(__file__).resolve().parents[2] / "prompts" / "rules" / "BASIS_THREATS.yaml"
    with path.open(encoding="utf-8") as prompt_file:
        yaml_data = yaml.safe_load(prompt_file)

    config = yaml_data.get("BASIS_THREATS") if isinstance(yaml_data, dict) else None
    required_keys = {"version", "task", "system_prompt", "output_contract"}
    if not isinstance(config, dict) or not required_keys.issubset(config):
        raise RuntimeError(f"Invalid threat prompt configuration: {path}")

    _PROMPT_CONFIG_CACHE = config
    logger.info("Loaded threat prompt configuration: %s", path)
    return config


class ProductsThreatsService:
    """Generate and persist threats for individual products with isolated models."""

    def __init__(
        self,
        db_url: str,
        model_name: str,
        dry_run: bool = False,
        sample_per_arm: int = 10,
        card_id: str = CARD_ID,
        all_in_arms: bool = False,
    ):
        self.db_url = db_url
        self.model_name = model_name
        self.dry_run = dry_run
        self.sample_per_arm = sample_per_arm
        self.card_id = card_id
        self.all_in_arms = all_in_arms
        self.pool: Optional[asyncpg.Pool] = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.prompt_config = load_product_threats_prompt_config()
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

    async def get_or_create_model_for_submission(self, submission_number: str, device_name: str, product_id: int, suffix: str = "PRODUCT") -> int:
        """Get existing model for submission_number or create new one.
        
        Prevents duplicate models for products with same submission_number.
        Sets product_id in threat.models to track which product the model is for.
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        model_name = f"{device_name}+{suffix}"
        
        async with self.pool.acquire() as conn:
            # Try to find existing model by submission_number in name
            if submission_number:
                existing_id = await conn.fetchval(
                    """
                    SELECT id FROM threat.models
                    WHERE name LIKE $1
                    LIMIT 1
                    """,
                    f"%{submission_number}%"
                )
                if existing_id:
                    logger.info("Model already exists for submission_number=%s: id=%d, product_id=%d", submission_number, existing_id, product_id)
                    return existing_id
            
            # Create new model with product_id
            row = await conn.fetchrow(
                """
                INSERT INTO threat.models (name, product_id, created_at, updated_at)
                VALUES ($1, $2, NOW(), NOW())
                RETURNING id
                """,
                model_name,
                product_id,
            )
        
        if not row:
            raise RuntimeError(f"Failed to create model with name: {model_name}")
        
        model_id = int(row["id"])
        logger.info("Created new threat model: name=%s id=%d product_id=%d", model_name, model_id, product_id)
        return model_id

    async def get_single_product(self, product_id: int) -> Dict[str, Any]:
        """Fetch a single product by ID.
        
        Requires product to exist. If device_description is empty, creates a fallback
        from company + device name to ensure LLM has context for threat extraction.
        """
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
                """,
                product_id,
            )

        if not row:
            raise ValueError(f"Product {product_id} not found")
        
        result = dict(row)
        
        # If device_description is empty, create fallback from company + device
        if not result.get("device_description"):
            company = result.get("company", "Unknown") or "Unknown"
            device = result.get("device", "Device") or "Device"
            result["device_description"] = f"{company} {device}"
            logger.info(f"Product {product_id}: Using fallback device_description: {result['device_description']}")
        
        return result

    async def get_products_in_range(self, start_id: int, end_id: int) -> List[Dict[str, Any]]:
        """Fetch all products within a given ID range.
        
        Returns products with fallback device_description if needed.
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        if start_id > end_id:
            raise ValueError(f"Invalid range: start_id ({start_id}) > end_id ({end_id})")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
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
                WHERE p.id >= $1
                  AND p.id <= $2
                  AND p.deleted_at IS NULL
                  AND o.deleted_at IS NULL
                ORDER BY p.id
                """,
                start_id,
                end_id,
            )

        if not rows:
            raise ValueError(f"No products found in range {start_id}-{end_id}")
        
        # Apply fallback device_description for products missing it
        results = []
        for row in rows:
            result = dict(row)
            if not result.get("device_description"):
                company = result.get("company", "Unknown") or "Unknown"
                device = result.get("device", "Device") or "Device"
                result["device_description"] = f"{company} {device}"
            results.append(result)
        
        return results

    async def sample_products(self, arms: List[int], all_in_arms: bool = False) -> List[Dict[str, Any]]:
        """Sample products from specified arms.
        
        Returns products with fallback device_description if needed.
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        if not arms:
            raise ValueError("At least one arm must be specified")

        async with self.pool.acquire() as conn:
            if all_in_arms:
                # Fetch ALL products in the specified arms, ordered by product ID
                rows = await conn.fetch(
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
                    WHERE p.deleted_at IS NULL
                      AND o.deleted_at IS NULL
                      AND o.arm = ANY($1::int[])
                    ORDER BY p.id
                    """,
                    arms,
                )
            else:
                # Sample up to sample_per_arm from each arm
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
                          AND o.deleted_at IS NULL
                          AND o.arm = ANY($1::int[])
                    )
                    SELECT *
                    FROM ranked_products
                    WHERE arm_rank <= $2
                    ORDER BY arm, id
                    """,
                    arms,
                    self.sample_per_arm,
                )

        # Apply fallback device_description for products missing it
        results = []
        for row in rows:
            result = dict(row)
            if not result.get("device_description"):
                company = result.get("company", "Unknown") or "Unknown"
                device = result.get("device", "Device") or "Device"
                result["device_description"] = f"{company} {device}"
            results.append(result)
        
        return results

    async def extract_threats_for_product(
        self,
        product: Dict[str, Any],
        model_id: int,
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
                "version": 1,
            },
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

        normalized_threats = self.normalize_threats(threats, model_id, product["id"])
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
        product_id: int,
    ) -> List[Dict[str, Any]]:
        """Normalize threats without deduping—keep all as-extracted."""
        normalized = []

        for index, raw_threat in enumerate(threats, 1):
            if not isinstance(raw_threat, dict):
                continue

            name = self.clean_text(raw_threat.get("name"))
            if not name:
                continue

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
                "card_id": self.card_id,
                "version": 1,
                "domain": self.clean_text(raw_threat.get("domain")) or "clinical",
                "tag": f"PROD-{product_id}-{index:02d}",
            }
            normalized.append(candidate)

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
            f"{field_name}: {ProductsThreatsService.clean_text(value)}"
            for field_name, value in fields
            if ProductsThreatsService.clean_text(value)
        )

    @staticmethod
    def estimate_token_count(text: str) -> int:
        if not text:
            return 0
        word_like_tokens = re.findall(r"\w+|[^\w\s]", text, flags=re.UNICODE)
        character_estimate = max(1, round(len(text) / 4))
        return max(len(word_like_tokens), character_estimate)

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
                            model_id, tag, name, description, probability,
                            damage_description, spoofing, tampering, repudiation,
                            information_disclosure, denial_of_service,
                            elevation_of_privilege, mitigation_level, disabled,
                            card_id, version, domain
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15::uuid, $16, $17
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
                            domain = EXCLUDED.domain
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
                        threat["card_id"],
                        threat["version"],
                        threat["domain"],
                    )
                    inserted += 1

        return inserted

    async def process_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single product: get/create model, extract threats, insert."""
        product_id = product["id"]
        device_name = product["device"]
        submission_number = product.get("submission_number", "")
        
        # Get or reuse existing model for this submission_number
        model_id = await self.get_or_create_model_for_submission(submission_number, device_name, product_id, suffix="PRODUCT")
        print(f"  Model ID: {model_id}")
        
        threats_json = await self.extract_threats_for_product(product, model_id)
        threat_count = len(threats_json["threats"])
        
        inserted_count = await self.insert_threats(threats_json)
        
        self.print_token_usage(threats_json)
        
        result = {
            "product_id": product_id,
            "device": device_name,
            "arm": product["arm"],
            "model_id": model_id,
            "threats_extracted": threat_count,
            "threats_inserted": inserted_count,
            "source_profile_tokens_estimate": threats_json["source_profile_tokens_estimate"],
            "openai_usage": threats_json["openai_usage"],
            "threats": threats_json["threats"],
        }
        
        print(f"  {device_name}: {threat_count} threats extracted and inserted")
        
        return result

    async def process_products(
        self,
        arms: Optional[List[int]] = None,
        product_id: Optional[int] = None,
        product_id_range: Optional[tuple[int, int]] = None,
    ) -> Dict[str, Any]:
        """Process products: single, range, or arm-based sampling."""
        await self.validate_card_id()
        
        if product_id is not None:
            products = [await self.get_single_product(product_id)]
            mode_desc = f"single product (id={product_id})"
        elif product_id_range is not None:
            start_id, end_id = product_id_range
            products = await self.get_products_in_range(start_id, end_id)
            mode_desc = f"product range ({start_id}-{end_id})"
        elif arms:
            products = await self.sample_products(arms, all_in_arms=self.all_in_arms)
            if self.all_in_arms:
                mode_desc = f"all products in arms {arms}"
            else:
                mode_desc = f"{self.sample_per_arm} products per arm from arms {arms}"
        else:
            raise ValueError("Either --product-id, --product-id-range, or --arms must be specified")
        
        if not products:
            raise ValueError("No products found to process")
        
        print(f"\nProcessing {len(products)} products in {mode_desc}")
        
        results: Dict[str, Any] = {
            "mode": "products",
            "card_id": self.card_id,
            "dry_run": self.dry_run,
            "mode_description": mode_desc,
            "product_count": len(products),
            "processed": [],
            "total_threats_extracted": 0,
            "total_threats_inserted": 0,
        }
        
        for index, product in enumerate(products, 1):
            print(f"\n[{index}/{len(products)}] {product['device']} (arm {product['arm']})")
            try:
                product_result = await self.process_product(product)
                results["processed"].append(product_result)
                results["total_threats_extracted"] += product_result["threats_extracted"]
                results["total_threats_inserted"] += product_result["threats_inserted"]
            except Exception as e:
                logger.error("Failed to process product %d: %s", product["id"], str(e))
                results["processed"].append({
                    "product_id": product["id"],
                    "device": product["device"],
                    "error": str(e),
                })
        
        token_summary = self.print_run_token_summary(results["processed"])
        results["model"] = self.model_name
        results["openai_usage_total"] = token_summary
        
        print(f"\n=== Summary ===")
        print(f"Products processed: {len(products)}")
        print(f"Total threats extracted: {results['total_threats_extracted']}")
        print(f"Total threats inserted: {results['total_threats_inserted']}")
        
        if self.pool and not self.dry_run:
            await log_event(self.pool, "PRODUCTS_THREATS_COMPLETE", results)
        
        return results

    @staticmethod
    def summarize_token_usage(processed: List[Dict[str, Any]]) -> Dict[str, Optional[int]]:
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0
        saw_usage = False

        for item in processed:
            if "error" in item:
                continue
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
            "  Source profile tokens (estimate): "
            f"{threats_json.get('source_profile_tokens_estimate', 0)}"
        )
        if usage.get("total_tokens") is not None:
            print(
                "  OpenAI tokens: "
                f"prompt={usage.get('prompt_tokens')} "
                f"completion={usage.get('completion_tokens')} "
                f"total={usage.get('total_tokens')}"
            )


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract threats for individual products with isolated models.",
    )
    
    parser.add_argument(
        "--product-id",
        type=int,
        default=None,
        help="Product ID for single-product threat generation.",
    )
    parser.add_argument(
        "--product-id-range",
        default=None,
        help="Product ID range for batch threat generation (e.g., 1-1525).",
    )
    parser.add_argument(
        "--arms",
        default=None,
        help="Comma-separated org arms to sample products from (e.g., 1,2,3).",
    )
    parser.add_argument(
        "--all-in-arms",
        action="store_true",
        help="Process ALL products in specified arms (ignores --sample-per-arm).",
    )
    parser.add_argument(
        "--sample-per-arm",
        type=int,
        default=10,
        help="Number of products to sample per arm when --all-in-arms is not set (default: 10).",
    )
    parser.add_argument(
        "--card-id",
        default=CARD_ID,
        help=f"Card UUID to assign to generated threats (default: {CARD_ID}).",
    )
    parser.add_argument(
        "--model",
        default=os.getenv("PRODUCTS_THREATS_MODEL", "gpt-5.6-terra"),
        help="OpenAI model used for threat extraction (default: PRODUCTS_THREATS_MODEL or gpt-5.6-terra).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and print counts without inserting threats.",
    )
    
    return parser.parse_args(argv)


def parse_product_id_range(value: str) -> tuple[int, int]:
    """Parse product ID range from string like '1-1525'."""
    try:
        parts = value.split("-")
        if len(parts) != 2:
            raise ValueError(f"Invalid range format: {value}. Use 'START-END'")
        start_id = int(parts[0].strip())
        end_id = int(parts[1].strip())
    except ValueError as exc:
        raise ValueError(f"Invalid product ID range: {value}") from exc

    if start_id < 1:
        raise ValueError(f"Start ID must be >= 1; got {start_id}")
    if end_id < 1:
        raise ValueError(f"End ID must be >= 1; got {end_id}")
    if start_id > end_id:
        raise ValueError(f"Start ID ({start_id}) must be <= End ID ({end_id})")

    return start_id, end_id


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


async def main() -> None:
    try:
        args = parse_args(sys.argv[1:])
        
        mode_count = sum([
            args.product_id is not None,
            args.product_id_range is not None,
            args.arms is not None,
        ])
        if mode_count == 0:
            raise ValueError("Either --product-id, --product-id-range, or --arms must be specified")
        if mode_count > 1:
            raise ValueError("Only one of --product-id, --product-id-range, or --arms can be specified")
        
        # Initialize all variables upfront to avoid UnboundLocalError
        product_id_range = None
        arms = None
        sample_per_arm = 1
        
        if args.product_id_range is not None:
            product_id_range = parse_product_id_range(args.product_id_range)
        elif args.arms is not None:
            arms = parse_arms(args.arms)
            sample_per_arm = validate_sample_per_arm(args.sample_per_arm)
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

    service = ProductsThreatsService(
        db_url=db_url,
        model_name=args.model,
        dry_run=args.dry_run,
        sample_per_arm=sample_per_arm,
        card_id=args.card_id,
        all_in_arms=args.all_in_arms,
    )

    try:
        await service.initialize()
        await service.process_products(
            arms=arms,
            product_id=args.product_id,
            product_id_range=product_id_range,
        )
    finally:
        await service.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
