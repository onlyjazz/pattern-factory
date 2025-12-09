# UPSERT Logic Bug Fix for Rules and Views Registry

## Problem
When a rule was executed multiple times (e.g., after adding a new column to the SELECT statement), the system had incorrect upsert logic:

1. **RegisterRuleTool** (lines 173-201 in `backend/pitboss/tools.py`):
   - ✅ Already had correct UPSERT on `rule_code` (the stable identifier)
   - This preserves the `rule.id` when re-running the same rule code
   - Maintains referential integrity with `views_registry.rule_id`

2. **RegisterViewTool** (lines 207-241 in `backend/pitboss/tools.py`):
   - ❌ Was doing INSERT ONLY - no UPSERT
   - On re-execution, it tried to insert a new row for the same `table_name`
   - This created duplicate entries or failed due to duplicate keys

## Why This Matters
The database schema has:
- `rules.rule_code` → UNIQUE (stable identifier across executions)
- `views_registry.rule_id` → Foreign key to `rules.id`

When a user updates a rule (e.g., adds a description column), the workflow:
1. Drops the old view
2. Creates a new view with updated columns
3. Needs to update the `rules` table with new SQL
4. Needs to update the `views_registry` entry

Without proper UPSERT in RegisterViewTool, step 4 would fail because it tries to insert a duplicate `table_name`.

## Solution Implemented

### 1. Added UNIQUE constraint on `table_name` in schema
**File**: `backend/db/pattern_factory_schema.sql`
```sql
CREATE TABLE IF NOT EXISTS views_registry (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES rules(id) ON DELETE SET NULL,
    table_name TEXT NOT NULL UNIQUE,  -- allows UPSERT
    summary VARCHAR,
    ...
);
```

**Migration**: `backend/db/add-table-name-unique.sql`
```sql
ALTER TABLE views_registry
ADD CONSTRAINT views_registry_table_name_key UNIQUE (table_name);
```

### 2. Updated RegisterViewTool to use UPSERT
**File**: `backend/pitboss/tools.py` (lines 207-254)

Changed from INSERT-only to INSERT...ON CONFLICT:
```python
await conn.execute("""
    INSERT INTO views_registry (rule_id, table_name, summary)
    VALUES ($1, $2, $3)
    ON CONFLICT (table_name) DO UPDATE SET
        rule_id     = EXCLUDED.rule_id,
        summary     = EXCLUDED.summary,
        updated_at  = CURRENT_TIMESTAMP
""", rule_id, table_name, summary)
```

## Flow Example: Re-executing LIST_ORGS with added column

**Initial execution:**
```
Rule: LIST_ORGS
Logic: "show me the orgs with funding stage, name, date founded, and date funded"

1. SQL generated: SELECT stage, name, date_founded, date_funded FROM orgs
2. View created: pattern_orgs
3. rules INSERT: INSERT INTO rules (rule_code, sql, ...) VALUES ('LIST_ORGS', '...')
   → rules.id = 42, rules.rule_code = 'LIST_ORGS'
4. views_registry INSERT: INSERT INTO views_registry (rule_id, table_name, summary)
   → views_registry.rule_id = 42, table_name = 'pattern_orgs'
```

**Re-execution with added column (description):**
```
Logic: "show me the orgs with name, description, date founded, date funded, and funding stage"

1. SQL generated (updated): SELECT name, description, date_founded, date_funded, stage FROM orgs
2. View dropped and recreated: DROP VIEW pattern_orgs; CREATE VIEW pattern_orgs AS ...
3. rules UPSERT: ON CONFLICT (rule_code) UPDATE SET sql = '...'
   → rules.id stays 42 (unchanged), rules.rule_code = 'LIST_ORGS' (unchanged)
4. views_registry UPSERT: ON CONFLICT (table_name) UPDATE SET rule_id = 42, summary = '...'
   → Same row in views_registry updated (id stays same, rule_id unchanged)
```

## Benefits
1. **Referential Integrity Preserved**: `views_registry.rule_id` always points to the correct `rules.id`
2. **Idempotency**: Re-running the same rule updates existing entries instead of creating duplicates
3. **View Updates**: Adding/removing columns from a rule now works correctly
4. **Traceable History**: The `updated_at` timestamp reflects when the view was last modified
