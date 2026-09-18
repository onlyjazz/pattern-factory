#!/usr/bin/env python
"""
Batch Org Portfolio Discovery Script

Discovers FDA-cleared device portfolios for organizations using Exa's agent API.
Stores portfolio as JSON in orgs.portfolio column.

Usage:
    python backend/scripts/batch_org_portfolio.py --org-ids 1-50
    python backend/scripts/batch_org_portfolio.py --org-ids 1,5,10
    python backend/scripts/batch_org_portfolio.py --org-names "Medtronic,Siemens"
    python backend/scripts/batch_org_portfolio.py --org-ids 1-10 --dry-run

Environment:
    EXA_API_KEY: Exa API key for agent.runs.create() calls
    DATABASE_URL: PostgreSQL connection string (optional, uses pattern-factory)
"""

import argparse
import asyncio
import logging
import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from services.portfolio_service import batch_search_portfolios
from pitboss.logging_util import log_event

logger = logging.getLogger(__name__)


def setup_logging():
    """Configure logging."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )


def parse_org_ids(spec: str) -> list[int]:
    """Parse org ID specification: '1,5,10' or '1-50'."""
    org_ids = []
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            try:
                start, end = part.split('-')
                org_ids.extend(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError as e:
                logger.error(f"Invalid range spec: {part} - {e}")
                sys.exit(1)
        else:
            try:
                org_ids.append(int(part))
            except ValueError as e:
                logger.error(f"Invalid org ID: {part} - {e}")
                sys.exit(1)
    return org_ids


async def get_org_names_by_ids(org_ids: list[int]) -> list[str]:
    """Query database for org names by IDs."""
    try:
        import asyncpg
    except ImportError:
        logger.error("asyncpg not installed. Run: pip install asyncpg")
        sys.exit(1)

    db_url = os.getenv("DATABASE_URL") or "postgresql://localhost/pattern-factory"
    try:
        conn = await asyncpg.connect(db_url)
        try:
            rows = await conn.fetch(
                "SELECT id, name FROM public.orgs WHERE id = ANY($1::int[]) ORDER BY id",
                org_ids,
            )
            return [row['name'] for row in rows]
        finally:
            await conn.close()
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        sys.exit(1)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Batch discover FDA-cleared device portfolios for organizations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python backend/scripts/batch_org_portfolio.py --org-ids 1-50
  python backend/scripts/batch_org_portfolio.py --org-ids 1,5,10
  python backend/scripts/batch_org_portfolio.py --org-names "Medtronic,Siemens"
  python backend/scripts/batch_org_portfolio.py --org-ids 1-10 --dry-run
        """,
    )
    
    parser.add_argument(
        "--org-ids",
        type=str,
        help="Organization IDs: comma-separated or range (e.g., '1,5,10' or '1-50')",
    )
    parser.add_argument(
        "--org-names",
        type=str,
        help="Comma-separated organization names (e.g., 'Medtronic,Siemens')",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would happen but don't update database",
    )
    
    args = parser.parse_args()
    setup_logging()
    
    # Validate API key
    if not os.getenv("EXA_API_KEY"):
        logger.error("❌ EXA_API_KEY environment variable not set")
        sys.exit(1)
    
    # Determine org names
    org_names = []
    
    if args.org_names:
        org_names = [name.strip() for name in args.org_names.split(',') if name.strip()]
    elif args.org_ids:
        org_ids = parse_org_ids(args.org_ids)
        logger.info(f"🔍 Querying database for {len(org_ids)} organization names...")
        org_names = await get_org_names_by_ids(org_ids)
        if not org_names:
            logger.error(f"❌ No organizations found with IDs: {org_ids}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)
    
    logger.info(f"🚀 Starting batch portfolio discovery for {len(org_names)} organizations")
    if args.dry_run:
        logger.info("   (DRY-RUN MODE - no database updates)")
    
    # Run batch search
    summary = await batch_search_portfolios(org_names, dry_run=args.dry_run)
    
    # Print summary
    print("\n" + "=" * 70)
    print(f"📊 BATCH PORTFOLIO DISCOVERY SUMMARY")
    print("=" * 70)
    print(f"  Total:    {summary['total']}")
    print(f"  Success:  {summary['success']} ✅")
    print(f"  Failed:   {summary['failed']} ❌")
    if summary['errors']:
        print(f"\n  Errors:")
        for org_name, error in summary['errors'].items():
            print(f"    - {org_name}: {error}")
    print("=" * 70)
    
    sys.exit(0 if summary['failed'] == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
