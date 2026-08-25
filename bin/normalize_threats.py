#!/usr/bin/env python3
"""
Normalize threats in model_id=37 to remove device/anatomy/modality/disease-specific context.

This tool:
1. Batch-processes threats in chunks (50-100 per batch)
2. Uses GPT-4o with deterministic system prompt (temperature=0.0)
3. Preserves causal failure mechanisms
4. Stores original threat snapshots for audit
5. Logs all changes to system_log

Usage:
    python backend/cli/normalize_threats.py --model-id 37 --batch-size 50 --max-batches 36 --dry-run false

Environment:
    OPENAI_API_KEY - OpenAI API key (required)
    DATABASE_URL - PostgreSQL connection string (from .env)
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import asyncpg
from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
from pitboss.logging_util import log_event

load_dotenv()

logger = logging.getLogger("normalize_threats")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

NORMALIZATION_SYSTEM_PROMPT = (
    "You are a threat model normalization expert for FDA-regulated medical devices.\n"
    "\n"
    "Your task: rewrite each threat to remove device-specific, anatomy-specific, "
    "modality-specific, disease-specific, and workflow-specific details UNLESS "
    "they are essential to the threat's causal failure mechanism.\n"
    "\n"
    "Preserve:\n"
    "- The core failure mechanism (what can go wrong)\n"
    "- Patient/clinical impact\n"
    "- AI model failure modes\n"
    "- Security/safety failure modes\n"
    "\n"
    "Remove:\n"
    '- References to specific organs/anatomies (e.g., "bone density", "cardiac", "pulmonary")\n'
    '- References to specific imaging modalities (e.g., "DICOM", "ultrasound", "CT", "MRI", "X-ray")\n'
    '- References to specific diseases (e.g., "osteoporosis", "sepsis", "myocardial infarction")\n'
    '- References to specific workflows (e.g., "triage", "screening", "surgical planning", "monitoring")\n'
    "- References to specific product names or vendors\n"
    '- Device-specific features (e.g., "integrated PACS", "mobile app integration")\n'
    "\n"
    "The rewritten threat should be portable across all medical device categories.\n"
    "\n"
    "For each threat, return a JSON object with:\n"
    '{"normalized_name": "string (rewritten threat name, or null if unchanged)", '
    '"normalized_description": "string (rewritten description)", '
    '"normalized_damage_description": "string (rewritten damage description)", '
    '"changed": boolean, "confidence": 0.0-1.0, '
    '"notes": "brief explanation of changes (or null if unchanged)"}'
)


class ThreatNormalizer:
    """Normalize threats by removing device-specific context via LLM."""

    def __init__(
        self,
        db_url: str,
        model_id: int = 37,
        batch_size: int = 50,
        dry_run: bool = False,
    ):
        self.db_url = db_url
        self.model_id = model_id
        self.batch_size = batch_size
        self.dry_run = dry_run
        self.pool: Optional[asyncpg.Pool] = None
        self.openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    async def initialize(self) -> None:
        """Initialize database connection pool."""
        self.pool = await asyncpg.create_pool(
            self.db_url,
            min_size=1,
            max_size=3,
            command_timeout=120,
        )
        logger.info(f"Initialized connection pool for {self.db_url}")

    async def cleanup(self) -> None:
        """Close database connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("Closed connection pool")

    async def get_unnormalized_threats(self, limit: int) -> List[Dict[str, Any]]:
        """Fetch threats that haven't been normalized yet."""
        if not self.pool:
            raise RuntimeError("Pool not initialized")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    id,
                    name,
                    description,
                    damage_description,
                    domain,
                    tag
                FROM threat.threats
                WHERE model_id = $1 AND normalization_version = 0
                ORDER BY id
                LIMIT $2
                """,
                self.model_id,
                limit,
            )

        return [dict(row) for row in rows]

    def _normalize_threat_batch(self, threats: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
        """Call OpenAI to normalize a batch of threats."""
        # Build prompt with all threats in batch
        threat_list = "\n\n".join(
            [
                f"Threat #{i + 1}: {t['name']}\n"
                f"Description: {t['description']}\n"
                f"Damage: {t['damage_description']}"
                for i, t in enumerate(threats)
            ]
        )

        user_message = f"Normalize the following {len(threats)} threats:\n\n{threat_list}\n\nReturn a JSON array with {len(threats)} objects, one per threat, in the same order."

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            temperature=0.0,
            timeout=300,
            messages=[
                {"role": "system", "content": NORMALIZATION_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
        )

        try:
            # Extract JSON from response
            content = response.choices[0].message.content.strip()
            # Try to parse as array
            if content.startswith("["):
                normalized_list = json.loads(content)
            else:
                # Try to extract JSON from markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                normalized_list = json.loads(content)

            # Map back to threat IDs
            result = {}
            for i, threat in enumerate(threats):
                if i < len(normalized_list):
                    result[threat["id"]] = normalized_list[i]
                else:
                    logger.warning(f"Missing normalization result for threat {threat['id']}")

            return result
        except (json.JSONDecodeError, IndexError, KeyError) as e:
            logger.error(f"Failed to parse LLM response: {e}\n{response.choices[0].message.content}")
            raise

    async def update_threat(
        self,
        conn: asyncpg.Connection,
        threat_id: int,
        normalized: Dict[str, Any],
        original: Dict[str, Any],
    ) -> bool:
        """Update a single threat with normalized values."""
        try:
            # Store original snapshot
            snapshot = {
                "original_name": original["name"],
                "original_description": original["description"],
                "original_damage_description": original["damage_description"],
                "normalized_at_version": 1,
                "normalized_by": "PAT-317",
            }

            await conn.execute(
                """
                UPDATE threat.threats
                SET
                    name = $1,
                    description = $2,
                    damage_description = $3,
                    normalization_version = 1,
                    normalized_at = $4,
                    normalization_confidence = $5,
                    original_threat_snapshot = $6
                WHERE id = $7 AND model_id = $8
                """,
                normalized.get("normalized_name") or original["name"],
                normalized["normalized_description"],
                normalized["normalized_damage_description"],
                datetime.now(timezone.utc),
                normalized.get("confidence"),
                json.dumps(snapshot),
                threat_id,
                self.model_id,
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update threat {threat_id}: {e}")
            return False

    async def process_batch(self, batch_num: int, threats: List[Dict[str, Any]]) -> int:
        """Process one batch of threats."""
        logger.info(
            f"Batch {batch_num}: normalizing {len(threats)} threats "
            f"(IDs {threats[0]['id']}-{threats[-1]['id']})"
        )

        # Call LLM to normalize batch
        try:
            normalized_map = self._normalize_threat_batch(threats)
        except Exception as e:
            logger.error(f"Batch {batch_num} LLM call failed: {e}")
            return 0

        # Update database
        if self.dry_run:
            logger.info(f"DRY RUN: Would update {len(normalized_map)} threats")
            for threat in threats:
                if threat["id"] in normalized_map:
                    normalized = normalized_map[threat["id"]]
                    logger.info(
                        f"  {threat['id']}: "
                        f"changed={normalized.get('changed')}, "
                        f"confidence={normalized.get('confidence')}"
                    )
            return len(normalized_map)

        # Real update
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                updated_count = 0
                for threat in threats:
                    if threat["id"] in normalized_map:
                        normalized = normalized_map[threat["id"]]
                        success = await self.update_threat(
                            conn, threat["id"], normalized, threat
                        )
                        if success:
                            updated_count += 1

        logger.info(f"Batch {batch_num}: updated {updated_count} threats")
        return updated_count

    async def run(self, max_batches: Optional[int] = None) -> None:
        """Run normalization process."""
        logger.info(f"Starting normalization for model_id={self.model_id}")

        total_updated = 0
        batch_num = 0

        while True:
            batch_num += 1

            if max_batches and batch_num > max_batches:
                logger.info(f"Reached max batches limit ({max_batches})")
                break

            # Fetch batch
            threats = await self.get_unnormalized_threats(self.batch_size)
            if not threats:
                logger.info("No more threats to normalize")
                break

            # Process batch
            updated = await self.process_batch(batch_num, threats)
            total_updated += updated

            # Log progress
            if not self.dry_run:
                await log_event(
                    self.pool,
                    "THREAT_NORMALIZATION_BATCH_COMPLETE",
                    {
                        "batch_num": batch_num,
                        "threats_in_batch": len(threats),
                        "updated": updated,
                        "total_updated": total_updated,
                        "model_id": self.model_id,
                    },
                )

        logger.info(f"Normalization complete. Total updated: {total_updated}")


async def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Normalize threats for Cycle-3")
    parser.add_argument(
        "--model-id",
        type=int,
        default=37,
        help="Model ID to normalize (default: 37)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Threats per batch (default: 50)",
    )
    parser.add_argument(
        "--max-batches",
        type=int,
        default=None,
        help="Max batches to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=False,
        help="Don't update database (default: false)",
    )

    args = parser.parse_args()

    # Get database URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set in environment")
        sys.exit(1)

    # Check API key
    if not os.getenv("OPENAI_API_KEY"):
        logger.error("OPENAI_API_KEY not set in environment")
        sys.exit(1)

    # Run normalization
    normalizer = ThreatNormalizer(
        db_url=db_url,
        model_id=args.model_id,
        batch_size=args.batch_size,
        dry_run=args.dry_run,
    )

    await normalizer.initialize()
    try:
        await normalizer.run(max_batches=args.max_batches)
    finally:
        await normalizer.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
