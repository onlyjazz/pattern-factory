"""
Threat Selector Service - Select and bulk-copy threats from canonical basis set.

Loads all canonical threats (model_id=35) into memory, uses LLM to score
threats against device profiles, and copies selected threats to target models.

Usage:
    service = ThreatSelectorService(db_url, dry_run=False)
    await service.initialize()
    try:
        result = await service.select_threats_for_device(
            target_model_id=2,
            device_id=5,
            threat_count=10
        )
        print(result)
    finally:
        await service.cleanup()
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
import yaml
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

logger = logging.getLogger("threat_selector_service")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

DEFAULT_CANONICAL_MODEL_ID = 37
DEFAULT_THREAT_COUNT = 10
MIN_THREAT_COUNT = 8
MAX_THREAT_COUNT = 12
_PROMPT_CONFIG_CACHE: Optional[Dict[str, Any]] = None


def load_selthreat_prompts() -> Dict[str, Any]:
    """Load and cache SELTHREAT prompt configuration from BASIS_THREATS.yaml."""
    global _PROMPT_CONFIG_CACHE
    if _PROMPT_CONFIG_CACHE is not None:
        return _PROMPT_CONFIG_CACHE

    path = Path(__file__).resolve().parents[2] / "prompts" / "rules" / "BASIS_THREATS.yaml"
    with path.open(encoding="utf-8") as prompt_file:
        yaml_data = yaml.safe_load(prompt_file)

    config = yaml_data.get("SELTHREAT") if isinstance(yaml_data, dict) else None
    if not isinstance(config, dict):
        raise RuntimeError(f"Invalid SELTHREAT configuration in: {path}")

    _PROMPT_CONFIG_CACHE = config
    logger.info("Loaded SELTHREAT prompts from: %s (version: %s)", path, config.get("version"))
    return config


class ThreatSelectorService:
    """Select and copy threats from canonical basis set to target models."""

    def __init__(
        self,
        db_url: str,
        dry_run: bool = False,
        llm_model: str = "gpt-4o-mini",
        canonical_model_id: int = DEFAULT_CANONICAL_MODEL_ID,
    ):
        self.db_url = db_url
        self.dry_run = dry_run
        self.llm_model = llm_model
        self.canonical_model_id = canonical_model_id
        self.pool: Optional[asyncpg.Pool] = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.canonical_threats: List[Dict[str, Any]] = []
        self.canonical_threats_loaded = False

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=3,
            command_timeout=120,
        )
        logger.info("Database pool initialized")

    async def cleanup(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    async def create_model(self, product_name: str, suffix: str = "SELTHREAT") -> int:
        """Create a new threat model for test isolation.
        
        Args:
            product_name: Name of the product or test identifier
            suffix: Suffix to append (default: SELTHREAT for selthreat, GENTHREAT for genthreat)
        
        Returns:
            The created model ID
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")
        
        model_name = f"{product_name}+{suffix}"
        
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO threat.models (name, created_at, updated_at)
                VALUES ($1, NOW(), NOW())
                RETURNING id
                """,
                model_name,
            )
        
        if not row:
            raise RuntimeError(f"Failed to create model with name: {model_name}")
        
        model_id = int(row["id"])
        logger.info("Created new threat model: name=%s id=%d", model_name, model_id)
        print(f"\n✓ Created new threat model: {model_name} (id={model_id})")
        return model_id

    async def load_canonical_threats(self, panel: Optional[str] = None) -> None:
        """Load canonical threats, optionally filtered by panel via provenance.
        
        If panel is provided, loads only threats with provenance from products in that panel.
        This eliminates cross-domain hallucination (e.g., bone density vs. breast imaging threats).
        """
        if not self.pool:
            raise RuntimeError("Service not initialized")

        if self.canonical_threats_loaded:
            logger.info("Canonical threats already loaded (%d threats)", len(self.canonical_threats))
            return

        async with self.pool.acquire() as conn:
            if panel:
                # Load threats with provenance from same panel
                rows = await conn.fetch(
                    """
                    SELECT DISTINCT 
                        t.id, t.model_id, t.tag, t.name, t.description, t.domain, t.probability,
                        t.damage_description, t.spoofing, t.tampering, t.repudiation,
                        t.information_disclosure, t.denial_of_service, t.elevation_of_privilege,
                        t.mitigation_level, t.disabled, t.created_at, t.updated_at, t.card_id, t.version
                    FROM threat.threats t
                    INNER JOIN threat.threat_provenance tp ON t.id = tp.threat_id
                    INNER JOIN public.products p ON tp.product_id = p.id
                    WHERE t.model_id = $1 AND p.panel = $2
                    ORDER BY t.id
                    """,
                    self.canonical_model_id,
                    panel,
                )
                logger.info("Loaded canonical threats for panel: %s", panel)
            else:
                # Load all threats
                rows = await conn.fetch(
                    """
                    SELECT 
                        id, model_id, tag, name, description, domain, probability,
                        damage_description, spoofing, tampering, repudiation,
                        information_disclosure, denial_of_service, elevation_of_privilege,
                        mitigation_level, disabled, created_at, updated_at, card_id, version
                    FROM threat.threats
                    WHERE model_id = $1
                    ORDER BY id
                    """,
                    self.canonical_model_id,
                )

        # Convert rows to dicts and normalize datetime fields
        threats_list = []
        for row in rows:
            threat = dict(row)
            # Ensure datetime fields are datetime objects
            if threat.get('created_at') and isinstance(threat['created_at'], str):
                from datetime import datetime
                threat['created_at'] = datetime.fromisoformat(threat['created_at'])
            if threat.get('updated_at') and isinstance(threat['updated_at'], str):
                from datetime import datetime
                threat['updated_at'] = datetime.fromisoformat(threat['updated_at'])
            threats_list.append(threat)
        
        self.canonical_threats = threats_list
        self.canonical_threats_loaded = True
        logger.info("Loaded %d canonical threats from model_id=%d", len(self.canonical_threats), self.canonical_model_id)

    async def get_device_profile(self, device_id: int) -> Dict[str, Any]:
        """Fetch device profile from products table."""
        if not self.pool:
            raise RuntimeError("Service not initialized")

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    id, device, company, indicated_use, device_description,
                    indications_for_use, panel, primary_product_code, submission_number
                FROM public.products
                WHERE id = $1
                """,
                device_id,
            )

        if not row:
            raise ValueError(f"Device (product) id {device_id} not found")

        return dict(row)

    async def _filter_threats_by_device_profile(
        self,
        device_profile: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Semantically filter threats by matching descriptions to device profile.
        
        Uses LLM to determine which threats are relevant based on threat description
        and damage_description vs. device intended_use, indications_for_use, and device_description.
        """
        if not self.canonical_threats:
            return []
        
        # Build threat list with descriptions for filtering
        threat_summaries = [
            f"ID {t['id']}: {t['name']}\n  Description: {t['description'][:150] if t['description'] else 'N/A'}\n  Damage: {t['damage_description'][:150] if t['damage_description'] else 'N/A'}"
            for t in self.canonical_threats
        ]
        
        device_summary = f"""
Device: {device_profile.get('device', 'N/A')}
Intended Use: {device_profile.get('indicated_use') or device_profile.get('indications_for_use') or 'N/A'}
Device Description: {device_profile.get('device_description', 'N/A')[:300] or 'N/A'}
Company: {device_profile.get('company', 'N/A')}
Panel: {device_profile.get('panel', 'N/A')}
"""
        
        system_prompt = """
You are a medical device security expert.
Given a device profile and a list of threats with descriptions, identify which threats are RELEVANT to this specific device.
Return ONLY a JSON array of threat IDs that are applicable to this device's intended use and function."""
        
        user_prompt = f"""{device_summary}

Candidate Threats:
{chr(10).join(threat_summaries)}

Task: For each threat, carefully read its description and damage description.
Determine if this threat could occur in or affect this device based on its intended use.

RETAIN threats about:
- The device's specific clinical function or indication
- Data processing specific to the device's modality (e.g., radiograph analysis)
- The device's target population or anatomy
- Model behavior affecting the device's output

REJECT threats about:
- Different imaging modalities (e.g., ultrasound threats for a radiography device)
- Different clinical procedures or specialties
- Different anatomical areas not relevant to device function
- Different patient populations or age groups not relevant to device
- Completely unrelated clinical scenarios

Return ONLY a JSON array of threat IDs to keep:
[<id1>, <id2>, ...]
No explanation."""
        
        try:
            create_kwargs = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "timeout": 45.0,  # Longer timeout for filtering task
            }
            # Only add temperature if model supports it (not gpt-5.6-terra)
            if "gpt-5.6" not in self.llm_model.lower():
                create_kwargs["temperature"] = 0.1  # Low temperature for deterministic filtering
            
            response = self.openai_client.chat.completions.create(**create_kwargs)
            response_text = response.choices[0].message.content.strip()
            kept_ids = json.loads(response_text)
            if not isinstance(kept_ids, list):
                kept_ids = []
        except Exception as e:
            logger.warning("Threat filtering failed: %s, keeping all threats", str(e))
            kept_ids = [t["id"] for t in self.canonical_threats]
        
        # Filter threats by kept IDs
        filtered = [t for t in self.canonical_threats if t["id"] in kept_ids]
        logger.info("Semantic filter: %d of %d threats retained", len(filtered), len(self.canonical_threats))
        
        return filtered

    def _build_threat_selection_prompt(
        self,
        device_profile: Dict[str, Any],
        threat_count: int,
    ) -> tuple[str, str]:
        """Build LLM prompt for threat selection using optimized threat summaries."""
        # Prioritize intended_use, fall back to indications_for_use
        intended_use = device_profile.get('indicated_use') or device_profile.get('indications_for_use') or 'Not specified'
        device_text = f"""
Device Profile:
- Device: {device_profile.get('device', 'N/A')}
- Company: {device_profile.get('company', 'N/A')}
- Intended Use: {intended_use}
- Device Description: {device_profile.get('device_description', 'N/A')}
- Panel/Specialty: {device_profile.get('panel', 'N/A')}
- Submission Number: {device_profile.get('submission_number', 'N/A')}
- Primary Product Code: {device_profile.get('primary_product_code', 'N/A')}
"""

        # Create compact threat summaries to reduce token count
        threat_summaries = [
            f"{t['id']}|{t['tag']}|{t['name']}|{t['domain']}"
            for t in self.canonical_threats
        ]

        system_prompt = """You are a medical device security expert specializing in AI/ML-enabled medical devices.
Your task is to select the most plausible threat scenarios for a given FDA-cleared medical device.

Given a device profile and a list of canonical threat IDs with names, rate each threat's relevance.
Return a JSON array of the top threats with scores based on threat names and domains only."""

        threats_text = "\n".join(threat_summaries)
        user_prompt = f"""{device_text}

Canonical Threat List ({len(self.canonical_threats)} threats in format: ID|TAG|NAME|DOMAIN):
{threats_text}

Task:
1. Review each threat's name and domain against the device profile
2. Rate each threat's plausibility on a scale of 1-10 (10 = highly plausible, 1 = not plausible)
3. Select the top {threat_count} most plausible threats
4. Return ONLY a valid JSON array (no markdown, no explanation) with structure:
   [
     {{"id": <int>, "tag": "<str>", "name": "<str>", "score": <float>}},
     ...
   ]

Prioritize threats that match:
- The device's clinical domain and indication
- AI/ML-specific risks (training data, model degradation, adversarial inputs)
- Integration risks (interfaces, data exchange)
- Patient safety impact scenarios
- Regulatory compliance risks

Output only valid JSON array. Do not include explanations."""

        return system_prompt, user_prompt

    async def _validate_threats_with_descriptions(
        self,
        device_profile: Dict[str, Any],
        borderline_threats: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Validate borderline-scored threats by checking descriptions against device profile.
        
        Filters out threats whose descriptions indicate they're not applicable to this device.
        """
        if not borderline_threats:
            return []
        
        # Build validation prompt with threat descriptions
        device_summary = f"""Device: {device_profile['device']}
Intended Use: {device_profile.get('indicated_use') or device_profile.get('indications_for_use') or 'N/A'}
Device Description: {device_profile.get('device_description', 'N/A')[:250] or 'N/A'}
Company: {device_profile.get('company', 'N/A')}
Panel: {device_profile.get('panel', 'N/A')}"""
        
        threat_list_with_desc = [
            f"ID {t['id']}: {t['name']} ({t['domain']}) - {t['description'][:150] if t['description'] else 'N/A'}"
            for t in borderline_threats
        ]
        
        system_prompt = """You are a medical device security expert.
You are given a device profile and a list of threats with full descriptions.
Determine which threats are genuinely applicable to this device based on their descriptions.
Return ONLY a JSON array of threat IDs that should be kept (NOT rejected)."""
        
        user_prompt = f"""{device_summary}

Borderline Threats (score 7-8):
{chr(10).join(threat_list_with_desc)}

Task: For each threat, read its description carefully and decide if it applies to this DEPLOYED DEVICE at runtime.
Return ONLY a valid JSON array of threat IDs to KEEP:
[<id1>, <id2>, ...]

REJECT (do NOT include) threats about:
- Surgical/procedural blood loss (unless device performs surgery)
- Anesthesia-related risks (unless device involves anesthesia)
- Specific medical procedures (unless device performs/screens for them)
- Specific medical conditions (unless device screens/treats them)

KEEP threats about:
- Data input/output risks
- Model behavior (bias, drift, calibration)
- Clinical decision support risks
- Cybersecurity at runtime
- Data integrity and transmission

Output only JSON array of IDs. No explanation."""
        
        try:
            # gpt-5.6-terra requires temperature=1.0 (no parameter control)
            create_kwargs = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "timeout": 15.0,
            }
            # Only add temperature if model supports it (not gpt-5.6-terra)
            if "gpt-5.6" not in self.llm_model.lower():
                create_kwargs["temperature"] = 0.0  # Deterministic validation
            
            response = self.openai_client.chat.completions.create(**create_kwargs)
            response_text = response.choices[0].message.content.strip()
            kept_ids = json.loads(response_text)
            if not isinstance(kept_ids, list):
                kept_ids = []
        except Exception as e:
            logger.warning("Threat validation failed: %s, keeping all borderline threats", str(e))
            kept_ids = [t["id"] for t in borderline_threats]
        
        validated = [t for t in borderline_threats if t["id"] in kept_ids]
        if len(validated) < len(borderline_threats):
            rejected = len(borderline_threats) - len(validated)
            logger.info("Validation rejected %d borderline threat(s)", rejected)
        
        return validated

    async def select_threats_for_device(
        self,
        target_model_id: int,
        device_id: int,
        threat_count: int = DEFAULT_THREAT_COUNT,
    ) -> Dict[str, Any]:
        """Select and optionally copy threats for a device.
        
        Two-stage filtering:
        1. Load panel-based candidate threats (eliminates cross-specialty hallucination)
        2. Semantically filter by matching threat descriptions to device profile
        3. Score remaining threats for selection
        """
        if threat_count < MIN_THREAT_COUNT or threat_count > MAX_THREAT_COUNT:
            raise ValueError(
                f"Threat count must be between {MIN_THREAT_COUNT} and {MAX_THREAT_COUNT}, got {threat_count}"
            )

        # Fetch device profile (includes panel)
        device_profile = await self.get_device_profile(device_id)
        logger.info("Fetched device profile: %s (id=%d, panel=%s)", 
                   device_profile["device"], device_id, device_profile.get("panel", "N/A"))
        
        # Load canonical threats filtered by panel (or all if panel is None)
        panel = device_profile.get("panel")
        if not self.canonical_threats_loaded:
            await self.load_canonical_threats(panel=panel)
        
        if not self.canonical_threats:
            raise ValueError(f"No canonical threats found for panel: {panel}")
        
        # Semantically filter threats based on device profile
        logger.info("Filtering %d candidate threats by device profile", len(self.canonical_threats))
        filtered_threats = await self._filter_threats_by_device_profile(device_profile)
        logger.info("Retained %d relevant threats after semantic filtering", len(filtered_threats))
        
        if len(filtered_threats) < threat_count:
            logger.warning(
                "Only %d relevant threats found (requested %d). Proceeding with available threats.",
                len(filtered_threats), threat_count
            )
        
        # Temporarily swap threat list for scoring
        original_threats = self.canonical_threats
        self.canonical_threats = filtered_threats

        # Build and execute LLM prompt
        system_prompt, user_prompt = self._build_threat_selection_prompt(device_profile, threat_count)

        try:
            # gpt-5.6-terra requires temperature=1.0 (no parameter control)
            create_kwargs = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "timeout": 30.0,
            }
            # Only add temperature if model supports it (not gpt-5.6-terra)
            if "gpt-5.6" not in self.llm_model.lower():
                create_kwargs["temperature"] = 0.2
            
            response = self.openai_client.chat.completions.create(**create_kwargs)
            response_text = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM selection failed: %s", str(e))
            raise RuntimeError(f"LLM threat selection failed: {str(e)}")

        # Parse LLM response
        try:
            scored_threats = json.loads(response_text)
            if not isinstance(scored_threats, list):
                raise ValueError("LLM response is not a JSON array")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response: %s\nResponse:\n%s", str(e), response_text)
            raise RuntimeError(f"Failed to parse LLM threat selection response: {str(e)}")

        logger.info("LLM selected %d threats for device %d", len(scored_threats), device_id)

        # Fetch full threat data for selected threats
        threat_by_id = {t["id"]: t for t in self.canonical_threats}

        selected_threats = []
        borderline_threats = []  # Score 7-8: validate with descriptions
        
        for scored in scored_threats:
            threat_id = scored["id"]
            if threat_id not in threat_by_id:
                logger.warning("Threat id %d not found in canonical set, skipping", threat_id)
                continue
            threat = dict(threat_by_id[threat_id])
            threat["score"] = scored["score"]
            
            # Flag borderline threats for validation
            if 7.0 <= scored["score"] <= 8.0:
                borderline_threats.append(threat)
            else:
                selected_threats.append(threat)
        
        # Validate borderline threats by checking descriptions
        if borderline_threats:
            logger.info("Validating %d borderline threats (score 7-8) against descriptions", len(borderline_threats))
            validated_threats = await self._validate_threats_with_descriptions(
                device_profile, borderline_threats
            )
            selected_threats.extend(validated_threats)
            logger.info("Validation complete: %d of %d borderline threats kept", 
                       len(validated_threats), len(borderline_threats))

        logger.info("Resolved %d threats from canonical set", len(selected_threats))

        # Insert threats into target model
        inserted_count = 0
        if not self.dry_run:
            inserted_count = await self._insert_selected_threats(target_model_id, selected_threats)
        
        # Restore original threat list
        self.canonical_threats = original_threats

        return {
            "device_id": device_id,
            "device_name": device_profile["device"],
            "target_model_id": target_model_id,
            "threat_count_requested": threat_count,
            "threat_count_selected": len(selected_threats),
            "threat_count_inserted": inserted_count,
            "dry_run": self.dry_run,
            "threats": [
                {
                    "id": t["id"],
                    "tag": t["tag"],
                    "name": t["name"],
                    "domain": t["domain"],
                    "score": t["score"],
                }
                for t in selected_threats
            ],
        }

    async def _insert_selected_threats(
        self,
        target_model_id: int,
        threats: List[Dict[str, Any]],
    ) -> int:
        """Insert selected threats into target model."""
        if not self.pool:
            raise RuntimeError("Service not initialized")

        if not threats:
            return 0

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                inserted = 0
                for threat in threats:
                    try:
                        await conn.execute(
                            """
                            INSERT INTO threat.threats (
                                model_id, tag, name, description, domain, probability,
                                damage_description, spoofing, tampering, repudiation,
                                information_disclosure, denial_of_service, elevation_of_privilege,
                                mitigation_level, disabled, created_at, updated_at, card_id, version
                            )
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18::uuid, $19)
                            ON CONFLICT (model_id, tag) DO NOTHING
                            """,
                            target_model_id,
                            threat["tag"],
                            threat["name"],
                            threat["description"],
                            threat["domain"],
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
                            threat["created_at"],  # asyncpg handles datetime objects
                            threat["updated_at"],  # asyncpg handles datetime objects
                            threat["card_id"],
                            threat["version"],
                        )
                        inserted += 1
                        logger.info("Inserted threat %s (%s) into model %d", threat["tag"], threat["name"], target_model_id)
                    except asyncpg.UniqueViolationError:
                        logger.debug("Threat %s already exists in model %d, skipping", threat["tag"], target_model_id)
                    except Exception as e:
                        logger.error("Failed to insert threat %s: %s", threat["tag"], str(e))
                        raise

        return inserted

    async def list_selected_threats(
        self,
        device_id: int,
        threat_count: int = DEFAULT_THREAT_COUNT,
    ) -> Dict[str, Any]:
        """Preview selected threats without inserting them.
        
        Uses panel-based threat filtering for consistency.
        """
        # Fetch device profile (includes panel)
        device_profile = await self.get_device_profile(device_id)
        logger.info("Fetched device profile: %s (id=%d, panel=%s)", 
                   device_profile["device"], device_id, device_profile.get("panel", "N/A"))
        
        # Load canonical threats filtered by panel
        panel = device_profile.get("panel")
        if not self.canonical_threats_loaded:
            await self.load_canonical_threats(panel=panel)
        
        if not self.canonical_threats:
            raise ValueError(f"No canonical threats found for panel: {panel}")

        # Build and execute LLM prompt
        system_prompt, user_prompt = self._build_threat_selection_prompt(device_profile, threat_count)

        try:
            # gpt-5.6-terra requires temperature=1.0 (no parameter control)
            create_kwargs = {
                "model": self.llm_model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "timeout": 30.0,
            }
            # Only add temperature if model supports it (not gpt-5.6-terra)
            if "gpt-5.6" not in self.llm_model.lower():
                create_kwargs["temperature"] = 0.2
            
            response = self.openai_client.chat.completions.create(**create_kwargs)
            response_text = response.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM selection failed: %s", str(e))
            raise RuntimeError(f"LLM threat selection failed: {str(e)}")

        # Parse LLM response
        try:
            scored_threats = json.loads(response_text)
            if not isinstance(scored_threats, list):
                raise ValueError("LLM response is not a JSON array")
        except json.JSONDecodeError as e:
            logger.error("Failed to parse LLM response: %s\nResponse:\n%s", str(e), response_text)
            raise RuntimeError(f"Failed to parse LLM threat selection response: {str(e)}")

        # Fetch full threat data for selected threats
        threat_by_id = {t["id"]: t for t in self.canonical_threats}
        selected_threats = []
        for scored in scored_threats:
            threat_id = scored["id"]
            if threat_id not in threat_by_id:
                logger.warning("Threat id %d not found in canonical set, skipping", threat_id)
                continue
            threat = dict(threat_by_id[threat_id])
            threat["score"] = scored["score"]
            selected_threats.append(threat)

        return {
            "device_id": device_id,
            "device_name": device_profile["device"],
            "threat_count_requested": threat_count,
            "threat_count_selected": len(selected_threats),
            "threats": [
                {
                    "id": t["id"],
                    "tag": t["tag"],
                    "name": t["name"],
                    "description": t["description"],
                    "domain": t["domain"],
                    "score": t["score"],
                }
                for t in selected_threats
            ],
        }
