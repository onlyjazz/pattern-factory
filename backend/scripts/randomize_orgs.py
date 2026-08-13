#!/usr/bin/env python3
"""
Pattern Factory: Stratified Randomization of Organizations to Study Arms

Purpose:
    Randomize ~1,500 FDA-cleared medical device manufacturers into three
    balanced study arms (Control, Treatment Arm 1, Treatment Arm 2) using
    stratified randomization by market tier (Tier 1, 2, 3).

Algorithm:
    1. For each tier (1, 2, 3):
       - Count orgs in tier
       - Allocate: control = count/3, treatment_1 = count/3, treatment_2 = count/3
       - Distribute remainder orgs round-robin (control, treat1, treat2)
       - Shuffle orgs in tier deterministically using seed
       - Assign first N_control → 'control', next N_treat1 → 'treatment_1', rest → 'treatment_2'
    2. All orgs assigned to exactly one arm
    3. Distribution balanced within ±1 org per tier

Usage:
    # Randomize all orgs with auto-generated seed
    python randomize_orgs.py
    
    # Randomize with specific seed (for reproducibility)
    python randomize_orgs.py --seed 1234567890
    
    # Randomize only specific tiers
    python randomize_orgs.py --tiers 1,2
    
    # Dry-run (show allocation without writing to DB)
    python randomize_orgs.py --dry-run
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple
import random
import json
from datetime import datetime

# Database connection
try:
    import asyncpg
    import asyncio
except ImportError:
    print("Error: asyncpg required. Install with: pip install asyncpg")
    sys.exit(1)


@dataclass
class RandomizationConfig:
    """Configuration for randomization run."""
    seed: Optional[int] = None
    tiers: List[int] = None  # None = all tiers
    dry_run: bool = False
    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "pattern_factory"
    db_user: str = "postgres"
    db_password: Optional[str] = None

    def __post_init__(self):
        if self.tiers is None:
            self.tiers = [1, 2, 3]


@dataclass
class TierAllocation:
    """Allocation for a single tier."""
    tier: int
    total_orgs: int
    control_count: int
    treatment_1_count: int
    treatment_2_count: int
    remainder: int


def parse_args() -> RandomizationConfig:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Stratified randomization of organizations to study arms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (default: auto-generated from timestamp)"
    )
    
    parser.add_argument(
        "--tiers",
        type=str,
        default="1,2,3",
        help="Comma-separated list of tiers to randomize (default: 1,2,3)"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show allocation without writing to database"
    )
    
    parser.add_argument(
        "--db-host",
        default=os.getenv("DB_HOST", "localhost"),
        help="Database host (env: DB_HOST)"
    )
    
    parser.add_argument(
        "--db-port",
        type=int,
        default=int(os.getenv("DB_PORT", "5432")),
        help="Database port (env: DB_PORT)"
    )
    
    parser.add_argument(
        "--db-name",
        default=os.getenv("DB_NAME", "pattern_factory"),
        help="Database name (env: DB_NAME)"
    )
    
    parser.add_argument(
        "--db-user",
        default=os.getenv("DB_USER", "postgres"),
        help="Database user (env: DB_USER)"
    )
    
    parser.add_argument(
        "--db-password",
        default=os.getenv("DB_PASSWORD"),
        help="Database password (env: DB_PASSWORD, optional)"
    )
    
    args = parser.parse_args()
    
    # Parse tiers
    try:
        tiers = [int(t.strip()) for t in args.tiers.split(",")]
        if not all(t in [1, 2, 3] for t in tiers):
            parser.error("Tiers must be 1, 2, or 3")
    except ValueError:
        parser.error("Tiers must be comma-separated integers")
    
    return RandomizationConfig(
        seed=args.seed,
        tiers=tiers,
        dry_run=args.dry_run,
        db_host=args.db_host,
        db_port=args.db_port,
        db_name=args.db_name,
        db_user=args.db_user,
        db_password=args.db_password,
    )


async def get_db_connection(config: RandomizationConfig):
    """Create asyncpg database connection."""
    return await asyncpg.connect(
        host=config.db_host,
        port=config.db_port,
        database=config.db_name,
        user=config.db_user,
        password=config.db_password,
    )


async def fetch_tier_orgs(conn, tier: int) -> List[Dict]:
    """Fetch all non-deleted orgs for a given tier."""
    rows = await conn.fetch("""
        SELECT id, name, tier, size
        FROM public.orgs
        WHERE deleted_at IS NULL AND tier = $1
        ORDER BY id
    """, tier)
    
    return [dict(row) for row in rows]


async def fetch_all_tier_counts(conn) -> Dict[int, int]:
    """Fetch org counts by tier."""
    rows = await conn.fetch("""
        SELECT tier, COUNT(*) as count
        FROM public.orgs
        WHERE deleted_at IS NULL
        GROUP BY tier
        ORDER BY tier
    """)
    
    return {row['tier']: row['count'] for row in rows}


def compute_tier_allocation(tier_count: int) -> TierAllocation:
    """Compute balanced arm allocation for a tier."""
    control = tier_count // 3
    remainder = tier_count % 3
    
    treatment_1 = tier_count // 3
    treatment_2 = tier_count // 3
    
    # Distribute remainder round-robin: control, treatment_1, treatment_2
    if remainder >= 1:
        control += 1
    if remainder >= 2:
        treatment_1 += 1
    
    return TierAllocation(
        tier=0,  # Set by caller
        total_orgs=tier_count,
        control_count=control,
        treatment_1_count=treatment_1,
        treatment_2_count=treatment_2,
        remainder=remainder,
    )


def randomize_tier_assignments(
    orgs: List[Dict],
    seed: int,
) -> Dict[int, str]:
    """
    Randomize org assignments for a tier using deterministic seed.
    
    Returns: {org_id: arm_name, ...}
    """
    # Deterministic shuffle using seed
    rng = random.Random(seed)
    shuffled_orgs = orgs.copy()
    rng.shuffle(shuffled_orgs)
    
    # Compute allocation
    count = len(shuffled_orgs)
    allocation = compute_tier_allocation(count)
    
    # Assign arms
    assignments = {}
    for idx, org in enumerate(shuffled_orgs):
        org_id = org['id']
        
        if idx < allocation.control_count:
            arm = 'control'
        elif idx < allocation.control_count + allocation.treatment_1_count:
            arm = 'treatment_1'
        else:
            arm = 'treatment_2'
        
        assignments[org_id] = arm
    
    return assignments


def print_allocation_summary(
    tier_counts: Dict[int, int],
    allocations: Dict[int, TierAllocation],
    seed: int,
):
    """Print human-readable allocation summary."""
    print("\n" + "="*70)
    print("STRATIFIED RANDOMIZATION ALLOCATION SUMMARY")
    print("="*70)
    print(f"Randomization Seed: {seed}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()
    
    total_control = 0
    total_treatment_1 = 0
    total_treatment_2 = 0
    total_orgs = 0
    
    for tier in [1, 2, 3]:
        if tier not in allocations:
            continue
        
        alloc = allocations[tier]
        tier_name = {1: "Tier 1 (Enterprise > $500M)", 2: "Tier 2 (Mid-Market $50M–$500M)", 3: "Tier 3 (Startup < $50M)"}[tier]
        
        print(f"{tier_name}:")
        print(f"  Total Orgs:        {alloc.total_orgs:5d}")
        print(f"  → Control:         {alloc.control_count:5d} ({100*alloc.control_count/alloc.total_orgs:5.1f}%)")
        print(f"  → Treatment Arm 1: {alloc.treatment_1_count:5d} ({100*alloc.treatment_1_count/alloc.total_orgs:5.1f}%)")
        print(f"  → Treatment Arm 2: {alloc.treatment_2_count:5d} ({100*alloc.treatment_2_count/alloc.total_orgs:5.1f}%)")
        print()
        
        total_control += alloc.control_count
        total_treatment_1 += alloc.treatment_1_count
        total_treatment_2 += alloc.treatment_2_count
        total_orgs += alloc.total_orgs
    
    print("-"*70)
    print("TOTAL (All Tiers):")
    print(f"  Total Orgs:        {total_orgs:5d}")
    print(f"  → Control:         {total_control:5d} ({100*total_control/total_orgs:5.1f}%)")
    print(f"  → Treatment Arm 1: {total_treatment_1:5d} ({100*total_treatment_1/total_orgs:5.1f}%)")
    print(f"  → Treatment Arm 2: {total_treatment_2:5d} ({100*total_treatment_2/total_orgs:5.1f}%)")
    print("="*70 + "\n")


async def execute_randomization(
    conn,
    config: RandomizationConfig,
    all_assignments: Dict[int, Dict[int, str]],
    allocations: Dict[int, TierAllocation],
) -> bool:
    """Write randomization assignments to database."""
    
    if config.dry_run:
        print("DRY-RUN MODE: No database writes executed\n")
        return True
    
    try:
        print("Writing assignments to database...\n")
        
        # Begin transaction
        async with conn.transaction():
            # Clear existing assignments (safety check)
            await conn.execute("""
                UPDATE public.orgs
                SET study_arm = NULL, randomization_seed = NULL, randomized_at = NULL
                WHERE deleted_at IS NULL
            """)
            
            # Bulk insert assignments
            now = datetime.utcnow()
            seed_int = config.seed if config.seed else int(time.time() * 1000000)
            
            for tier, org_assignments in all_assignments.items():
                for org_id, arm in org_assignments.items():
                    await conn.execute("""
                        UPDATE public.orgs
                        SET
                            study_arm = $1,
                            randomization_seed = $2,
                            randomized_at = $3
                        WHERE id = $4
                    """, arm, seed_int, now, org_id)
            
            # Log event
            counts = {
                'control': sum(1 for assignments in all_assignments.values() for arm in assignments.values() if arm == 'control'),
                'treatment_1': sum(1 for assignments in all_assignments.values() for arm in assignments.values() if arm == 'treatment_1'),
                'treatment_2': sum(1 for assignments in all_assignments.values() for arm in assignments.values() if arm == 'treatment_2'),
            }
            
            await conn.execute("""
                INSERT INTO public.system_log (event, context)
                VALUES ($1, $2)
            """, 'stratified_randomization_completed', json.dumps({
                'timestamp': now.isoformat(),
                'seed': seed_int,
                'arms': counts,
                'tiers_randomized': config.tiers,
            }))
        
        print("✓ Randomization completed successfully")
        print(f"  Seed used: {seed_int}")
        print(f"  Total assignments: {sum(len(a) for a in all_assignments.values())}\n")
        return True
        
    except Exception as e:
        print(f"✗ Error writing to database: {e}\n", file=sys.stderr)
        return False


async def main():
    """Main entry point."""
    config = parse_args()
    
    # Generate seed if not provided
    if config.seed is None:
        config.seed = int(time.time() * 1000000)
    
    print(f"\nPattern Factory: Stratified Randomization")
    print(f"Seed: {config.seed}")
    print(f"Tiers to randomize: {config.tiers}")
    print(f"Mode: {'DRY-RUN' if config.dry_run else 'WRITE'}\n")
    
    # Connect to database
    try:
        conn = await get_db_connection(config)
        print("✓ Connected to database\n")
    except Exception as e:
        print(f"✗ Failed to connect to database: {e}", file=sys.stderr)
        sys.exit(1)
    
    try:
        # Fetch tier counts
        tier_counts = await fetch_all_tier_counts(conn)
        print("Organization counts by tier:")
        for tier in [1, 2, 3]:
            count = tier_counts.get(tier, 0)
            tier_name = {1: "Tier 1 (Enterprise)", 2: "Tier 2 (Mid-Market)", 3: "Tier 3 (Startup)"}[tier]
            print(f"  {tier_name}: {count:5d} orgs")
        print()
        
        # Compute allocations and assignments for each tier
        all_assignments: Dict[int, Dict[int, str]] = {}
        allocations: Dict[int, TierAllocation] = {}
        
        for tier in config.tiers:
            # Fetch orgs for this tier
            orgs = await fetch_tier_orgs(conn, tier)
            
            if not orgs:
                print(f"  No orgs in tier {tier}, skipping\n")
                continue
            
            # Compute allocation
            alloc = compute_tier_allocation(len(orgs))
            alloc.tier = tier
            allocations[tier] = alloc
            
            # Randomize assignments
            tier_seed = config.seed + tier * 1000  # Vary seed per tier
            assignments = randomize_tier_assignments(orgs, tier_seed)
            all_assignments[tier] = assignments
            
            print(f"✓ Tier {tier}: {len(orgs)} orgs → {alloc.control_count} control, {alloc.treatment_1_count} treat1, {alloc.treatment_2_count} treat2")
        
        print()
        
        # Print summary
        print_allocation_summary(tier_counts, allocations, config.seed)
        
        # Execute write to database
        success = await execute_randomization(conn, config, all_assignments, allocations)
        
        if not success:
            sys.exit(1)
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
