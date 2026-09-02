#!/usr/bin/env python3
"""
Load countermeasure taxonomy from JSON and update threat.countermeasures.

This service reads a JSON taxonomy file (e.g., taxonomy-countermeasures-v4.json)
with structured countermeasure definitions and updates the database with:
  - implementation_notes
  - effectiveness
  - mitigation_level (numeric 0-100)

The loader performs exact-match name lookups to ensure data integrity and
provides comprehensive diagnostics for unmatched or duplicate names.

Usage:
    python load_countermeasure_taxonomy.py <json_file> [options]

Options:
    --model-id ID         Model ID to filter countermeasures (default: all)
    --dry-run            Validate without writing
    --limit N            Process at most N countermeasures (default: no limit)
    -v, --verbose        Detailed diagnostics

Environment:
    DATABASE_URL: PostgreSQL connection string
"""

import asyncio
import asyncpg
import json
import logging
import os
import sys
from collections import defaultdict
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class TaxonomyLoader:
    """Load and validate countermeasure taxonomy before database writes."""

    def __init__(self, json_path: str, model_id: int | None = None, dry_run: bool = False, limit: int | None = None, verbose: bool = False):
        self.json_path = json_path
        self.model_id = model_id
        self.dry_run = dry_run
        self.limit = limit
        self.verbose = verbose

        # Tracking
        self.taxonomy_records = []  # All loaded countermeasures from JSON
        self.db_countermeasures = {}  # name -> {id, model_id, ...} from database
        self.matched = []  # Successfully matched records
        self.unmatched = []  # From JSON but not in DB
        self.duplicates = defaultdict(list)  # Multiple matches in DB

    async def load_json(self) -> bool:
        """Load and parse taxonomy JSON file."""
        try:
            with open(self.json_path, 'r') as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"❌ Failed to load JSON: {e}")
            return False

        # Flatten taxonomy structure: each category -> countermeasures
        for category, category_data in data.items():
            if not isinstance(category_data, dict) or 'countermeasures' not in category_data:
                logger.warning(f"⚠️  Category '{category}' has no 'countermeasures' key, skipping")
                continue

            for cm in category_data['countermeasures']:
                if not isinstance(cm, dict) or 'name' not in cm:
                    logger.warning(f"⚠️  Record in '{category}' missing 'name' field, skipping")
                    continue

                # Normalize record
                record = {
                    'name': cm['name'].strip(),
                    'category': category,
                    'type': cm.get('type', ''),
                    'description': cm.get('description', ''),
                    'implementation_notes': cm.get('implementation_notes', ''),
                    'effectiveness': cm.get('effectiveness', ''),
                    'mitigation_level': cm.get('mitigation_level', None),
                }

                # Validate mitigation_level
                if record['mitigation_level'] is not None:
                    if not isinstance(record['mitigation_level'], int):
                        logger.warning(f"⚠️  '{record['name']}': mitigation_level is not an integer, skipping")
                        continue
                    if not (0 <= record['mitigation_level'] <= 100):
                        logger.warning(f"⚠️  '{record['name']}': mitigation_level {record['mitigation_level']} out of range [0-100], skipping")
                        continue

                self.taxonomy_records.append(record)

        logger.info(f"📖 Loaded {len(self.taxonomy_records)} countermeasure records from taxonomy")
        return len(self.taxonomy_records) > 0

    async def fetch_database_countermeasures(self, pool: asyncpg.Pool) -> bool:
        """Fetch countermeasure names from database for matching."""
        try:
            async with pool.acquire() as conn:
                # Build query: filter by model_id if specified
                query = "SELECT id, name, model_id FROM threat.countermeasures"
                params = []

                if self.model_id is not None:
                    query += " WHERE model_id = $1"
                    params.append(self.model_id)

                rows = await conn.fetch(query, *params)

                # Build lookup: name -> list of records (to detect duplicates)
                for row in rows:
                    name = row['name'].strip()
                    if name not in self.db_countermeasures:
                        self.db_countermeasures[name] = []
                    self.db_countermeasures[name].append({
                        'id': row['id'],
                        'model_id': row['model_id'],
                    })

                logger.info(f"📊 Database has {len(self.db_countermeasures)} unique countermeasure names")
                return True

        except Exception as e:
            logger.error(f"❌ Failed to fetch database countermeasures: {e}")
            return False

    async def validate_matches(self) -> bool:
        """Match taxonomy records to database records and report diagnostics."""
        logger.info("\n🔍 Matching taxonomy records to database...")

        # Match each taxonomy record
        for cm in self.taxonomy_records:
            name = cm['name']
            if name in self.db_countermeasures:
                matches = self.db_countermeasures[name]
                if len(matches) == 1:
                    # Unique match
                    self.matched.append({
                        'taxonomy': cm,
                        'db_id': matches[0]['id'],
                        'model_id': matches[0]['model_id'],
                    })
                else:
                    # Multiple matches in DB for this name
                    self.duplicates[name] = matches
                    if self.verbose:
                        logger.warning(f"⚠️  '{name}': {len(matches)} matches in database")
            else:
                # No match in DB
                self.unmatched.append(cm)
                if self.verbose:
                    logger.info(f"   No match for '{name}'")

        # Report diagnostics
        logger.info(f"\n📈 Match Report:")
        logger.info(f"   ✅ Matched:    {len(self.matched)}")
        logger.info(f"   ❌ Unmatched:  {len(self.unmatched)}")
        logger.info(f"   ⚠️  Duplicates: {len(self.duplicates)}")

        if self.unmatched and not self.verbose:
            logger.info(f"\n   Use --verbose to see unmatched names")

        if self.duplicates:
            logger.warning(f"\n   ⚠️  Duplicate names in database (cannot update safely):")
            for name, matches in self.duplicates.items():
                ids = [str(m['id']) for m in matches]
                logger.warning(f"      '{name}': IDs {', '.join(ids)}")

        return True

    async def apply_updates(self, pool: asyncpg.Pool) -> bool:
        """Apply updates to matched countermeasures."""
        if not self.matched:
            logger.warning("❌ No matched records to update")
            return False

        if self.dry_run:
            logger.info(f"\n🔍 [DRY RUN] Would update {len(self.matched)} countermeasures")
            for m in self.matched[:5]:  # Show first 5
                cm = m['taxonomy']
                logger.info(f"   '{cm['name']}':")
                if cm['implementation_notes']:
                    logger.info(f"      implementation_notes: {cm['implementation_notes'][:60]}...")
                if cm['effectiveness']:
                    logger.info(f"      effectiveness: {cm['effectiveness'][:60]}...")
                if cm['mitigation_level'] is not None:
                    logger.info(f"      mitigation_level: {cm['mitigation_level']}")
            if len(self.matched) > 5:
                logger.info(f"   ... and {len(self.matched) - 5} more")
            return True

        # Apply update limit if specified
        updates = self.matched
        if self.limit is not None and len(updates) > self.limit:
            logger.warning(f"⚠️  Limiting to {self.limit} updates (--limit)")
            updates = updates[:self.limit]

        logger.info(f"\n💾 Updating {len(updates)} countermeasures...")

        # Batch update in transaction
        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    updated = 0
                    for match in updates:
                        cm = match['taxonomy']
                        db_id = match['db_id']

                        # Update only non-empty fields
                        update_fields = []
                        params = []
                        param_idx = 1

                        if cm['implementation_notes']:
                            update_fields.append(f"implementation_notes = ${param_idx}")
                            params.append(cm['implementation_notes'])
                            param_idx += 1

                        if cm['effectiveness']:
                            update_fields.append(f"effectiveness = ${param_idx}")
                            params.append(cm['effectiveness'])
                            param_idx += 1

                        if cm['mitigation_level'] is not None:
                            update_fields.append(f"mitigation_level = ${param_idx}")
                            params.append(cm['mitigation_level'])
                            param_idx += 1

                        if update_fields:
                            update_fields.append(f"updated_at = now()")
                            query = f"UPDATE threat.countermeasures SET {', '.join(update_fields)} WHERE id = ${param_idx}"
                            params.append(db_id)

                            await conn.execute(query, *params)
                            updated += 1

                    logger.info(f"✅ Updated {updated} countermeasures in database")

                    # Log to system_log
                    await conn.execute(
                        """
                        INSERT INTO public.system_log (event, context)
                        VALUES ($1, $2)
                        """,
                        'countermeasure_taxonomy_load',
                        json.dumps({
                            'taxonomy_file': os.path.basename(self.json_path),
                            'model_id': self.model_id,
                            'taxonomy_total': len(self.taxonomy_records),
                            'matched': len(self.matched),
                            'unmatched': len(self.unmatched),
                            'duplicates': len(self.duplicates),
                            'updated': updated,
                        })
                    )

                    return True

        except Exception as e:
            logger.error(f"❌ Update failed: {e}")
            return False


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Load countermeasure taxonomy from JSON and update database'
    )
    parser.add_argument('json_file', help='Path to taxonomy JSON file')
    parser.add_argument('--model-id', type=int, help='Filter by model ID')
    parser.add_argument('--dry-run', action='store_true', help='Validate without writing')
    parser.add_argument('--limit', type=int, help='Process at most N records')
    parser.add_argument('-v', '--verbose', action='store_true', help='Detailed diagnostics')

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.json_file):
        logger.error(f"❌ JSON file not found: {args.json_file}")
        sys.exit(1)

    # Validate database connection
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    # Initialize loader
    loader = TaxonomyLoader(
        json_path=args.json_file,
        model_id=args.model_id,
        dry_run=args.dry_run,
        limit=args.limit,
        verbose=args.verbose,
    )

    # Load JSON
    if not await loader.load_json():
        sys.exit(1)

    # Connect to database
    logger.info("📦 Connecting to database...")
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5, command_timeout=300)
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    try:
        # Fetch database state
        if not await loader.fetch_database_countermeasures(pool):
            sys.exit(1)

        # Validate matches
        if not await loader.validate_matches():
            sys.exit(1)

        # Apply updates
        if not await loader.apply_updates(pool):
            sys.exit(1)

        logger.info("\n✅ Taxonomy load complete")

    finally:
        await pool.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n⏹️  Interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
