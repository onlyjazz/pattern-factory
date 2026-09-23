#!/usr/bin/env python3
"""
Backfill views_registry.description from the YAML rule definitions.

Rules are authored in prompts/rules/RULES.yaml with a stable `rule_code` and a
human-readable `description`. When a rule runs, the supervisor passes that
description through to the register_view tool, which persists it in
public.views_registry.description. Rows created before that column existed
therefore have a NULL description.

This script reconciles existing rows by matching views_registry.table_name
(the rule_code) against the YAML `rule_code` values and updating only the
description. It never inserts or deletes registry rows, and it leaves rows that
do not correspond to a YAML rule untouched.

Usage:
    python backend/scripts/backfill_view_descriptions.py [--dry-run]

Environment:
    DATABASE_URL: PostgreSQL connection string
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import asyncpg
import yaml
from dotenv import load_dotenv

# Load environment (.env in project root)
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RULES_PATH = Path(__file__).resolve().parents[2] / "prompts" / "rules" / "RULES.yaml"


def load_rule_descriptions() -> dict[str, str]:
    """Return {rule_code: description} for rules that define both fields."""
    with open(RULES_PATH, "r") as f:
        data = yaml.safe_load(f) or {}

    descriptions: dict[str, str] = {}
    for rule in data.get("RULES", []):
        rule_code = (rule.get("rule_code") or "").strip()
        description = (rule.get("description") or "").strip()
        if rule_code and description:
            descriptions[rule_code] = description
    return descriptions


async def backfill(pool: asyncpg.Pool, descriptions: dict[str, str], dry_run: bool) -> int:
    """Update matching registry rows; return the number of rows updated."""
    updated = 0
    async with pool.acquire() as conn:
        for rule_code, description in descriptions.items():
            exists = await conn.fetchval(
                "SELECT 1 FROM public.views_registry WHERE table_name = $1",
                rule_code,
            )
            if not exists:
                logger.info(f"⏭️  {rule_code}: no matching registry row, skipping")
                continue

            if dry_run:
                logger.info(f"🔍 [DRY RUN] {rule_code}: would set description to '{description}'")
                updated += 1
                continue

            result = await conn.execute(
                """
                UPDATE public.views_registry
                SET description = $1, updated_at = now()
                WHERE table_name = $2
                  AND description IS DISTINCT FROM $1
                """,
                description,
                rule_code,
            )
            if result == "UPDATE 1":
                logger.info(f"✅ {rule_code}: description set to '{description}'")
                updated += 1
            else:
                logger.info(f"➖ {rule_code}: description already up to date")
    return updated


async def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill views_registry.description from RULES.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing")
    args = parser.parse_args()

    if not RULES_PATH.exists():
        logger.error(f"❌ Rules file not found: {RULES_PATH}")
        sys.exit(1)

    descriptions = load_rule_descriptions()
    if not descriptions:
        logger.error("❌ No rule descriptions found in RULES.yaml")
        sys.exit(1)
    logger.info(f"📖 Loaded {len(descriptions)} rule descriptions from {RULES_PATH.name}")

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5, command_timeout=60)
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    try:
        updated = await backfill(pool, descriptions, args.dry_run)
        verb = "would update" if args.dry_run else "updated"
        logger.info(f"\n✅ Backfill complete: {verb} {updated} view descriptions")
    finally:
        await pool.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
