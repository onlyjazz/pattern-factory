#!/usr/bin/env python3
"""
Load countermeasure classes from taxonomy-countermeasures-v3.json
and assign to existing countermeasures table.

PAT-330: Threat Classification with Countermeasure Classes
"""

import json
import re
import asyncpg
import os
from pathlib import Path
from typing import Dict, Tuple

async def generate_tag(class_name: str) -> str:
    """Generate a unique tag from class name."""
    # Uppercase, replace non-alphanumeric with underscore, collapse runs
    tag = re.sub(r'[^A-Za-z0-9]+', '_', class_name)
    tag = tag.upper()
    tag = re.sub(r'^_+|_+$', '', tag)  # Strip leading/trailing underscores
    return tag

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

async def load_countermeasure_classes(conn: asyncpg.Connection) -> Dict[str, int]:
    """Load class taxonomy into threat.countermeasure_class.
    
    Returns: {class_name: class_id} mapping
    """
    taxonomy = await load_taxonomy()
    class_map = {}
    
    for class_name in taxonomy.keys():
        tag = await generate_tag(class_name)
        
        # Upsert: insert or ignore duplicate
        row = await conn.fetchrow(
            '''INSERT INTO threat.countermeasure_class (class, tag)
               VALUES ($1, $2)
               ON CONFLICT (class) DO UPDATE SET tag = EXCLUDED.tag
               RETURNING id, class, tag''',
            class_name, tag
        )
        class_map[class_name] = row['id']
        print(f'✓ Class: {class_name} (tag={tag}, id={row["id"]})')
    
    return class_map

async def populate_countermeasure_class_ids(
    conn: asyncpg.Connection,
    class_map: Dict[str, int]
) -> Tuple[int, int]:
    """Assign class_id to all countermeasures.
    
    Strategy: Assign all unclassified countermeasures to UNDEFINED by default.
    Future: Create optional mapping file to assign by pattern matching.
    
    Returns: (total_updated, skipped_count)
    """
    # Get UNDEFINED class_id
    undefined_id = class_map.get('UNDEFINED')
    if not undefined_id:
        raise ValueError('UNDEFINED class not found in class_map')
    
    # Assign all countermeasures without class_id to UNDEFINED
    result = await conn.execute(
        '''UPDATE threat.countermeasures
           SET class_id = $1
           WHERE class_id IS NULL''',
        undefined_id
    )
    
    # Parse result string: "UPDATE N" -> extract N
    total_updated = int(result.split()[-1])
    
    if total_updated > 0:
        print(f'  ✓ Assigned {total_updated} countermeasures to UNDEFINED class')
    
    return total_updated, 0

async def main():
    """Main entry point."""
    print('\n=== PAT-330: Load Countermeasure Classes ===\n')
    
    conn = await get_db_connection()
    try:
        # Step 1: Load class taxonomy
        print('Step 1: Loading countermeasure classes...')
        class_map = await load_countermeasure_classes(conn)
        print(f'\n✓ Loaded {len(class_map)} countermeasure classes\n')
        
        # Step 2: Populate countermeasure.class_id
        print('Step 2: Assigning class_id to countermeasures...')
        total, skipped = await populate_countermeasure_class_ids(conn, class_map)
        print(f'\n✓ Updated {total} countermeasures, skipped {skipped}\n')
        
        # Step 3: Verify
        count = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures WHERE class_id IS NOT NULL'
        )
        total_cms = await conn.fetchval(
            'SELECT COUNT(*) FROM threat.countermeasures'
        )
        print(f'Step 3: Verification')
        print(f'  Countermeasures with class_id: {count} / {total_cms}')
        
        if count == total_cms:
            print(f'\n✅ All countermeasures successfully assigned to classes!\n')
        else:
            print(f'\n⚠ {total_cms - count} countermeasures still unassigned.\n')
    
    finally:
        await conn.close()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
