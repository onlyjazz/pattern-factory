# Views Registry Consolidation

## Overview
The `rules` and `views_registry` tables have been consolidated into a single `views_registry` table. This eliminates unnecessary complexity and redundant foreign key relationships while maintaining all necessary metadata.

## Schema Changes

### Before (Two-Table Design)
```sql
-- rules table
CREATE TABLE rules (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    rule_code TEXT NOT NULL UNIQUE,
    sql TEXT NOT NULL,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- views_registry table (with foreign key to rules)
CREATE TABLE views_registry (
    id BIGSERIAL PRIMARY KEY,
    rule_id BIGINT REFERENCES rules(id) ON DELETE SET NULL,
    table_name TEXT NOT NULL UNIQUE,
    summary VARCHAR,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**Problems with this design:**
- Two tables to maintain the same logical unit
- Unnecessary foreign key relationship
- Synchronization issues when rules changed
- Extra join required to get complete rule + view metadata

### After (Single-Table Design)
```sql
CREATE TABLE views_registry (
    id BIGSERIAL PRIMARY KEY,
    name VARCHAR,                       -- YAML rule name
    table_name TEXT NOT NULL UNIQUE,    -- YAML rule_code (stable identifier)
    sql TEXT NOT NULL,                  -- generated SQL
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);
```

**Advantages:**
- Single source of truth for rule and view metadata
- No foreign key synchronization issues
- Simpler upsert logic (single table, no joins needed)
- `table_name` is UNIQUE, enabling idempotent UPSERT operations
- Cleaner codebase (fewer tool classes and database interactions)

## Code Changes

### 1. Removed RegisterRuleTool
**File**: `backend/pitboss/tools.py`

- Deleted the `RegisterRuleTool` class entirely
- Removed registration from `ToolRegistry._register_default_tools()`

### 2. Updated RegisterViewTool
**File**: `backend/pitboss/tools.py` (lines 163-211)

**Before:**
```python
async def execute(self, rule_code_key: str, table_name: str, summary: str, **kwargs):
    # Looked up rule_id from rules table
    row = await conn.fetchrow("SELECT id FROM rules WHERE rule_code=$1", rule_code_key)
    rule_id = row["id"] if row else None
    
    # Inserted into views_registry
    await conn.execute("""
        INSERT INTO views_registry (rule_id, table_name, summary)
        VALUES ($1, $2, $3)
        ON CONFLICT (table_name) DO UPDATE SET
            rule_id = EXCLUDED.rule_id,
            summary = EXCLUDED.summary,
            updated_at = CURRENT_TIMESTAMP
    """, rule_id, table_name, summary)
```

**After:**
```python
async def execute(self, table_name: str, name: str, sql_query: str, **kwargs):
    # Direct UPSERT into consolidated views_registry
    await conn.execute("""
        INSERT INTO views_registry (name, table_name, sql)
        VALUES ($1, $2, $3)
        ON CONFLICT (table_name) DO UPDATE SET
            name = EXCLUDED.name,
            sql = EXCLUDED.sql,
            updated_at = CURRENT_TIMESTAMP
    """, name, table_name, sql_query)
```

### 3. Updated agent_execute_sql
**File**: `backend/pitboss/agents.py` (lines 465-547)

**Before:**
```python
# Step 2: Register rule metadata
await tool_registry.execute(
    "register_rule",
    rule_code_key=rule_code,
    rule_name=rule_name,
    logic=rule_logic,
    sql_query=sql_query
)

# Step 3: Register view in views_registry
await tool_registry.execute(
    "register_view",
    rule_code_key=rule_code,
    table_name=table_name,
    summary=rule_name
)
```

**After:**
```python
# Step 2: Register view metadata in views_registry (consolidated)
await tool_registry.execute(
    "register_view",
    table_name=table_name,
    name=rule_name,
    sql_query=sql_query
)
```

### 4. Updated Database Schema
**File**: `backend/db/pattern_factory_schema.sql`

- Removed `rules` table
- Updated `views_registry` to include `name` and `sql` columns
- Added UNIQUE constraint on `table_name` for idempotent UPSERTs

### 5. Updated YAML Configuration
**File**: `prompts/rules/pattern-factory.yaml`

- Removed `rules` table from DATA.tables section
- Updated `views_registry` schema definition:
  ```yaml
  views_registry:
    - id
    - name
    - table_name
    - sql
    - created_at
    - updated_at
  ```

## Execution Flow

### Rule Execution Workflow

```
User Input: "show me the orgs with name, description, date founded, date funded, and funding stage"

1. LanguageCapo classifies as RULE
2. Capo validates rule
3. verifyRequest validates semantics against YAML rules (no DB query)
4. ruleToSQL converts to SQL via LLM
5. verifySQL checks SQL safety
6. executeSQL:
   a. Create materialized view (DROP IF EXISTS, CREATE VIEW)
   b. Count rows
   c. UPSERT into views_registry (single operation):
      - INSERT INTO views_registry (name, table_name, sql)
      - ON CONFLICT (table_name) DO UPDATE SET
      - Updates: name, sql, updated_at
```

### Example: Re-executing LIST_ORGS with added column

**First execution:**
```sql
INSERT INTO views_registry (name, table_name, sql)
VALUES (
    'Organizations who were on the podcast',
    'LIST_ORGS',
    'SELECT stage, name, date_founded, date_funded FROM orgs'
);
-- Creates: id=1, name='...', table_name='LIST_ORGS', sql='...', created_at=now()
```

**Re-execution with updated SQL (description column added):**
```sql
INSERT INTO views_registry (name, table_name, sql)
VALUES (
    'Organizations who were on the podcast',
    'LIST_ORGS',
    'SELECT name, description, date_founded, date_funded, stage FROM orgs'
)
ON CONFLICT (table_name) DO UPDATE SET
    name = EXCLUDED.name,
    sql = EXCLUDED.sql,
    updated_at = CURRENT_TIMESTAMP;
-- Updates: same row (id=1), sql updated, updated_at updated
```

## Benefits

1. **Simplified Schema**: Single table instead of two, no foreign key management
2. **Atomic Operations**: Rule + view metadata updated together, no sync issues
3. **Idempotency**: UPSERT on `table_name` ensures re-running rules is safe
4. **Cleaner Code**: One less tool class, simpler agent flow
5. **Better Performance**: No joins needed to retrieve rule + view metadata
6. **Maintainability**: Single source of truth for all rule and view data

## Migration Path

For existing databases with the two-table design:

1. Run migration to create new `views_registry` table structure:
   ```sql
   -- New views_registry with consolidated schema
   CREATE TABLE views_registry_new (
       id BIGSERIAL PRIMARY KEY,
       name VARCHAR,
       table_name TEXT NOT NULL UNIQUE,
       sql TEXT NOT NULL,
       created_at TIMESTAMP DEFAULT now(),
       updated_at TIMESTAMP DEFAULT now()
   );
   
   -- Migrate data from old tables
   INSERT INTO views_registry_new (name, table_name, sql, created_at, updated_at)
   SELECT r.name, v.table_name, r.sql, v.created_at, v.updated_at
   FROM views_registry v
   LEFT JOIN rules r ON v.rule_id = r.id;
   
   -- Drop old tables
   DROP TABLE IF EXISTS views_registry CASCADE;
   DROP TABLE IF EXISTS rules CASCADE;
   
   -- Rename new table
   ALTER TABLE views_registry_new RENAME TO views_registry;
   ```

2. Update application code (already done in this PR)
3. Deploy and test
