#!/usr/bin/env python3
"""
Load countermeasures from taxonomy-countermeasures-v3.json with correct class_id assignment.

PAT-330: SAFE loader—deletes only countermeasures added in this session.
Preserves all other production data.

Strategy:
  1. Find countermeasures with class_id (PAT-330 test data)
  2. Delete only those (by id list)
  3. Load fresh from taxonomy with correct class_id
  4. All other countermeasures left untouched
"""

import json
import asyncpg
import os
from pathlib import Path
from typing import Dict, List, Tuple

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

async def find_test_countermeasures(conn: asyncpg.Connection) -> List[int]:
    """Find countermeasures added in this PAT-330 run (those with class_id IS NOT NULL).
    
    Returns: List of IDs to delete
    """
    rows = await conn.fetch(
        "SELECT id FROM threat.countermeasures WHERE class_id IS NOT NULL"
    )
    return [row['id'] for row in rows]

async def delete_test_countermeasures(
    conn: asyncpg.Connection,
    ids_to_delete: List[int]
) -> int:
    """Delete only the PAT-330 test countermeasures. Returns count deleted."""
    if not ids_to_delete:
        print('  No test countermeasures to delete')
        return 0
    
    # Build parameterized query
    placeholders = ','.join(f'${i+1}' for i in range(len(ids_to_delete)))
    query = f"DELETE FROM threat.countermeasures WHERE id IN ({placeholders})"
    
    result = await conn.execute(query, *ids_to_delete)
    # Parse result string: "DELETE N"
    deleted = int(result.split()[-1])
    return deleted

async def load_countermeasures_from_taxonomy(
    conn: asyncpg.Connection,
    class_map: Dict[str, int],
) -> Tuple[int, int]:
    """
    Load countermeasures from taxonomy with correct class_id assignment.
    
    Returns: (total_inserted, skipped_count)
    """
    taxonomy = await load_taxonomy()
    total_inserted = 0
    skipped = 0
    
    for class_name, class_info in taxonomy.items():
        class_id = class_map.get(class_name)
        if not class_id:
            print(f'⚠ Class not found: {class_name}')
            continue
        
        countermeasures = class_info.get('countermeasures', [])
        
        for cm in countermeasures:
            cm_name = cm.get('name')
            cm_desc = cm.get('description')
            
            if not cm_name:
                skipped += 1
                continue
            
            # INSERT countermeasure with class_id
            try:
                await conn.execute(
                    '''INSERT INTO threat.countermeasures 
                       (name, description, class_id, model_id)
                       VALUES ($1, $2, $3, 1)''',
                    cm_name, cm_desc, class_id
                )
                total_inserted += 1
            except Exception as e:
                print(f'  ⚠ Failed to insert {cm_name}: {e}')
                skipped += 1
    
    return total_inserted, skipped

async def main():
    """Main entry point."""
    print('\n=== PAT-330: Load Countermeasures from Taxonomy (SAFE MODE) ===\n')
    
    conn = await get_db_connection()
    try:
        # Step 1: Fetch class map
        print('Step 1: Fetching countermeasure classes...')
        class_map = await fetch_class_map(conn)
        print(f'✓ Loaded {len(class_map)} classes\n')
        
        # Step 2: Find test countermeasures
        print('Step 2: Finding PAT-330 test countermeasures (with class_id)...')
        ids_to_delete = await find_test_countermeasures(conn)
        print(f'  Found {len(ids_to_delete)} test countermeasures to clean up\n')
        
        # Step 3: Delete only test data
        print('Step 3: Deleting only PAT-330 test countermeasures...')
        deleted = await delete_test_countermeasures(conn, ids_to_delete)
        print(f'✓ Deleted {deleted} test countermeasures\n')
        
        # Step 4: Load fresh from taxonomy
        print('Step 4: Loading countermeasures from taxonomy...')
        total, skipped = await load_countermeasures_from_taxonomy(conn, class_map)
        print(f'✓ Inserted {total} countermeasures, skipped {skipped}\n')
        
        # Step 5: Verify
        total_count = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures'
        )
        test_count = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NOT NULL'
        )
        by_class = await conn.fetch(
            '''SELECT cc.class, COUNT(*) as count 
               FROM threat.countermeasures cm
               JOIN threat.countermeasure_class cc ON cm.class_id = cc.id
               GROUP BY cc.class
               ORDER BY count DESC
               LIMIT 5'''
        )
        
        print(f'Step 5: Verification')
        print(f'  Total countermeasures (all): {total_count}')
        print(f'  PAT-330 countermeasures (with class_id): {test_count}')
        print(f'  Top 5 classes:')
        for row in by_class:
            print(f'    {row["class"]}: {row["count"]}')
        
        print(f'\n✅ Countermeasures loaded successfully (SAFE MODE)!\n')
    
    finally:
        await conn.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
