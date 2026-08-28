#!/usr/bin/env python3
"""
Merge taxonomy countermeasures into production database.

PAT-330: SAFE MERGE—adds ~125 taxonomy countermeasures alongside 359 production ones.
Uses INSERT ... ON CONFLICT (name) to avoid duplicates.

Preserves:
  - All 359 production countermeasures
  - All threat classifications
  - countermeasure_class table
"""

import json
import asyncpg
import os
from pathlib import Path
from typing import Dict, Tuple

async def load_taxonomy() -> Dict[str, dict]:
    """Load taxonomy-countermeasures-v3.json."""
    taxonomy_path = Path(__file__).parent / 'taxonomy-countermeasures-v3.json'
    if not taxonomy_path.exists():
        raise FileNotFoundError(f'Taxonomy file not found: {taxonomy_path}')
    
    with open(taxonomy_path, 'r') as f:
        return json.load(f)

async def get_db_connection() -> asyncpg.Connection:
    """Get asyncpg connection to pattern-factory database."""
    return await asyncpg.connect(
        database='pattern-factory',
        host=os.getenv('DB_HOST', 'localhost'),
        user=os.getenv('DB_USER', 'pattern_factory'),
        password=os.getenv('DB_PASSWORD', ''),
    )

async def fetch_class_map(conn: asyncpg.Connection) -> Dict[str, int]:
    """Fetch {class_name: class_id} mapping."""
    rows = await conn.fetch(
        "SELECT id, class FROM threat.countermeasure_class"
    )
    return {row['class']: row['id'] for row in rows}

async def merge_taxonomy_countermeasures(
    conn: asyncpg.Connection,
    class_map: Dict[str, int],
) -> Tuple[int, int, int]:
    """
    Merge countermeasures from taxonomy with production data.
    INSERT ... ON CONFLICT (name) to handle duplicates gracefully.
    
    Returns: (total_inserted, duplicates_skipped, errors)
    """
    taxonomy = await load_taxonomy()
    total_inserted = 0
    duplicates_skipped = 0
    errors = 0
    
    for class_name, class_info in taxonomy.items():
        class_id = class_map.get(class_name)
        if not class_id:
            print(f'⚠ Class not found: {class_name}')
            continue
        
        countermeasures = class_info.get('countermeasures', [])
        
        for cm in countermeasures:
            cm_name = cm.get('name')
            cm_desc = cm.get('description')
            cm_type = cm.get('type')
            impl_notes = cm.get('implementation_notes')
            residual_risk = cm.get('residual_risk')
            
            if not cm_name:
                continue
            
            try:
                result = await conn.execute(
                    '''INSERT INTO threat.countermeasures 
                       (name, description, class_id, model_id)
                       VALUES ($1, $2, $3, 1)
                       ON CONFLICT (model_id, name) DO NOTHING''',
                    cm_name, cm_desc, class_id
                )
                
                # Check if insert happened or conflict occurred
                if 'INSERT' in result:
                    total_inserted += 1
                    print(f'  ✓ Inserted: {cm_name} (class_id={class_id})')
                else:
                    duplicates_skipped += 1
                    print(f'  ⊘ Duplicate (skipped): {cm_name}')
                    
            except Exception as e:
                errors += 1
                print(f'  ✗ Error inserting {cm_name}: {e}')
    
    return total_inserted, duplicates_skipped, errors

async def main():
    """Main entry point."""
    print('\n=== PAT-330: Merge Taxonomy Countermeasures (SAFE MODE) ===\n')
    
    conn = await get_db_connection()
    try:
        # Step 1: Get current state
        print('Step 1: Current state...')
        prod_count = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NULL'
        )
        taxonomy_count = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NOT NULL'
        )
        print(f'  Production countermeasures (class_id IS NULL): {prod_count}')
        print(f'  Taxonomy countermeasures (class_id IS NOT NULL): {taxonomy_count}\n')
        
        # Step 2: Fetch class map
        print('Step 2: Fetching countermeasure classes...')
        class_map = await fetch_class_map(conn)
        print(f'✓ Loaded {len(class_map)} classes\n')
        
        # Step 3: Merge taxonomy countermeasures
        print('Step 3: Merging taxonomy countermeasures...')
        inserted, duplicates, errors = await merge_taxonomy_countermeasures(conn, class_map)
        print(f'\n✓ Inserted: {inserted}, Duplicates skipped: {duplicates}, Errors: {errors}\n')
        
        # Step 4: Verify final state
        total = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures'
        )
        prod_final = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NULL'
        )
        taxonomy_final = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NOT NULL'
        )
        classifications = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.threat_countermeasure_classes'
        )
        
        print(f'Step 4: Final verification')
        print(f'  Total countermeasures: {total}')
        print(f'  Production (class_id IS NULL): {prod_final}')
        print(f'  Taxonomy (class_id IS NOT NULL): {taxonomy_final}')
        print(f'  Threat classifications preserved: {classifications}')
        
        # Show class distribution
        by_class = await conn.fetch(
            '''SELECT cc.class, COUNT(*) as count 
               FROM threat.countermeasures cm
               JOIN threat.countermeasure_class cc ON cm.class_id = cc.id
               GROUP BY cc.id, cc.class
               ORDER BY count DESC
               LIMIT 5'''
        )
        
        print(f'\n  Top 5 taxonomy classes:')
        for row in by_class:
            print(f'    {row["class"]}: {row["count"]}')
        
        print(f'\n✅ Merge complete (SAFE MODE)!\n')
    
    finally:
        await conn.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
