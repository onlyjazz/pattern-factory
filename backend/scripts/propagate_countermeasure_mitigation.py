#!/usr/bin/env python3
"""
Propagate countermeasure mitigation_level to countermeasure_threat pairs.

Updates threat.countermeasure_threat.mitigation_level from
threat.countermeasures.mitigation_level WHERE countermeasure_threat.countermeasure_id = countermeasures.id.

Large dataset (241K pairs) is processed in batches with progress reporting,
dry-run support, and configurable limits for testing.

Usage:
    python propagate_countermeasure_mitigation.py [options]

Options:
    --model-id ID         Filter by model ID (optional)
    --batch-size N        Batch size for updates (default: 1000)
    --limit N            Process at most N pairs (default: no limit)
    --dry-run            Validate without writing
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
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class PairPropagator:
    """Propagate countermeasure metadata to threat-countermeasure pairs."""

    def __init__(self, model_id: int | None = None, batch_size: int = 1000, limit: int | None = None, dry_run: bool = False, verbose: bool = False):
        self.model_id = model_id
        self.batch_size = batch_size
        self.limit = limit
        self.dry_run = dry_run
        self.verbose = verbose

        # Statistics
        self.total_pairs = 0
        self.pairs_with_mitigation = 0
        self.pairs_without_mitigation = 0
        self.updated = 0
        self.skipped = 0
        self.errors = 0

    async def fetch_countermeasure_mitigation(self, pool: asyncpg.Pool) -> dict[int, int]:
        """Fetch countermeasure ID -> mitigation_level mapping for classified countermeasures.
        
        Only fetch countermeasures that have class_id IS NOT NULL (the 125 classified ones)
        and mitigation_level set.
        """
        try:
            async with pool.acquire() as conn:
                query = "SELECT id, mitigation_level FROM threat.countermeasures WHERE mitigation_level IS NOT NULL AND class_id IS NOT NULL"
                rows = await conn.fetch(query)

                mapping = {row['id']: row['mitigation_level'] for row in rows}
                logger.info(f"📊 Loaded {len(mapping)} classified countermeasures with mitigation_level")
                return mapping

        except Exception as e:
            logger.error(f"❌ Failed to fetch countermeasure mitigation levels: {e}")
            return {}

    async def count_pairs(self, pool: asyncpg.Pool) -> int:
        """Count total countermeasure_threat pairs."""
        try:
            async with pool.acquire() as conn:
                query = "SELECT COUNT(*) as cnt FROM threat.countermeasure_threat"
                params = []

                if self.model_id is not None:
                    query += " WHERE model_id = $1"
                    params.append(self.model_id)

                row = await conn.fetchrow(query, *params)
                return row['cnt'] if row else 0

        except Exception as e:
            logger.error(f"❌ Failed to count pairs: {e}")
            return 0

    async def get_pair_batches(self, pool: asyncpg.Pool, cm_mapping: dict[int, int]):
        """Stream countermeasure_threat pairs in batches.
        
        If model_id is specified, fetch pairs where threat.model_id = model_id.
        Only include classified countermeasures (class_id IS NOT NULL).
        """
        try:
            async with pool.acquire() as conn:
                if self.model_id is not None:
                    # Filter by threat.model_id and classified countermeasures
                    query = """
                        SELECT 
                            ct.model_id,
                            ct.countermeasure_id,
                            ct.threat_id,
                            cm.mitigation_level
                        FROM threat.countermeasure_threat ct
                        INNER JOIN threat.threats t ON ct.threat_id = t.id
                        INNER JOIN threat.countermeasures cm ON ct.countermeasure_id = cm.id
                        WHERE t.model_id = $1 AND cm.mitigation_level IS NOT NULL AND cm.class_id IS NOT NULL
                        ORDER BY ct.countermeasure_id, ct.threat_id
                    """
                    rows = await conn.fetch(query, self.model_id)
                else:
                    # Fetch all pairs with classified countermeasures that have mitigation_level
                    query = """
                        SELECT 
                            ct.model_id,
                            ct.countermeasure_id,
                            ct.threat_id,
                            cm.mitigation_level
                        FROM threat.countermeasure_threat ct
                        INNER JOIN threat.countermeasures cm ON ct.countermeasure_id = cm.id
                        WHERE cm.mitigation_level IS NOT NULL AND cm.class_id IS NOT NULL
                        ORDER BY ct.countermeasure_id, ct.threat_id
                    """
                    rows = await conn.fetch(query)

                # Stream results in batches
                for i in range(0, len(rows), self.batch_size):
                    batch = rows[i:i + self.batch_size]
                    yield batch

        except Exception as e:
            logger.error(f"❌ Failed to fetch pair batches: {e}")

    async def apply_updates(self, pool: asyncpg.Pool, cm_mapping: dict[int, int]) -> bool:
        """Apply mitigation_level updates to pairs in batches."""
        if not cm_mapping:
            logger.warning("❌ No countermeasures with mitigation_level found")
            return False

        self.total_pairs = await self.count_pairs(pool)
        logger.info(f"📊 Total countermeasure_threat pairs: {self.total_pairs:,}")

        if self.dry_run:
            logger.info(f"\n🔍 [DRY RUN] Would process {len(cm_mapping)} classified countermeasures")
            # Count pairs that would be updated
            try:
                async with pool.acquire() as conn:
                    if self.model_id is not None:
                        query = """
                            SELECT COUNT(*) as cnt FROM threat.countermeasure_threat ct
                            INNER JOIN threat.threats t ON ct.threat_id = t.id
                            INNER JOIN threat.countermeasures cm ON ct.countermeasure_id = cm.id
                            WHERE t.model_id = $1 AND cm.mitigation_level IS NOT NULL AND cm.class_id IS NOT NULL
                        """
                        row = await conn.fetchrow(query, self.model_id)
                    else:
                        query = """
                            SELECT COUNT(*) as cnt FROM threat.countermeasure_threat ct
                            INNER JOIN threat.countermeasures cm ON ct.countermeasure_id = cm.id
                            WHERE cm.mitigation_level IS NOT NULL AND cm.class_id IS NOT NULL
                        """
                        row = await conn.fetchrow(query)

                    would_update = row['cnt'] if row else 0
                    logger.info(f"   Would update: {would_update:,} pairs")
            except Exception as e:
                logger.warning(f"   (Could not estimate update count: {e})")
            return True

        logger.info(f"\n💾 Propagating mitigation_level to pairs...")

        batch_num = 0
        total_updated = 0

        try:
            async with pool.acquire() as conn:
                async with conn.transaction():
                    async for batch in self.get_pair_batches(pool, cm_mapping):
                        batch_num += 1
                        batch_size = len(batch)

                        # Apply update limit if specified
                        if self.limit is not None and total_updated >= self.limit:
                            logger.info(f"⏹️  Limit of {self.limit} pairs reached")
                            break

                        if self.limit is not None:
                            remaining = self.limit - total_updated
                            if batch_size > remaining:
                                batch = batch[:remaining]
                                batch_size = len(batch)

                        # Update this batch
                        for pair in batch:
                            cm_id = pair['countermeasure_id']
                            threat_id = pair['threat_id']
                            model_id = pair['model_id']
                            mitigation_level = pair['mitigation_level']

                            try:
                                await conn.execute(
                                    """
                                    UPDATE threat.countermeasure_threat
                                    SET mitigation_level = $1
                                    WHERE countermeasure_id = $2 AND threat_id = $3 AND model_id = $4
                                    """,
                                    mitigation_level,
                                    cm_id,
                                    threat_id,
                                    model_id,
                                )
                                self.updated += 1
                                total_updated += 1

                                if self.verbose and self.updated % 5000 == 0:
                                    logger.info(f"   Updated {self.updated:,} pairs...")

                            except Exception as e:
                                logger.error(f"❌ Error updating pair ({cm_id}, {threat_id}): {e}")
                                self.errors += 1

                        if self.limit is not None and total_updated >= self.limit:
                            break

                    # Log summary
                    logger.info(f"\n✅ Propagation complete")
                    logger.info(f"   Updated: {self.updated:,} pairs")
                    logger.info(f"   Errors:  {self.errors:,}")

                    # Log to system_log
                    await conn.execute(
                        """
                        INSERT INTO public.system_log (event, context)
                        VALUES ($1, $2)
                        """,
                        'countermeasure_threat_mitigation_propagate',
                        json.dumps({
                            'model_id': self.model_id,
                            'total_pairs': self.total_pairs,
                            'updated': self.updated,
                            'errors': self.errors,
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
        description='Propagate countermeasure mitigation_level to countermeasure_threat pairs'
    )
    parser.add_argument('--model-id', type=int, help='Filter by model ID')
    parser.add_argument('--batch-size', type=int, default=1000, help='Batch size (default: 1000)')
    parser.add_argument('--limit', type=int, help='Process at most N pairs')
    parser.add_argument('--dry-run', action='store_true', help='Validate without writing')
    parser.add_argument('-v', '--verbose', action='store_true', help='Detailed diagnostics')

    args = parser.parse_args()

    # Validate database connection
    db_url = os.getenv('DATABASE_URL')
    if not db_url:
        logger.error("❌ DATABASE_URL environment variable not set")
        sys.exit(1)

    # Initialize propagator
    propagator = PairPropagator(
        model_id=args.model_id,
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Connect to database
    logger.info("📦 Connecting to database...")
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=5, command_timeout=300)
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
        sys.exit(1)

    try:
        # Fetch countermeasure mitigation mapping
        cm_mapping = await propagator.fetch_countermeasure_mitigation(pool)
        if not cm_mapping:
            logger.warning("❌ No countermeasures with mitigation_level found")
            sys.exit(1)

        # Apply updates
        if not await propagator.apply_updates(pool, cm_mapping):
            sys.exit(1)

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
