# Rule Code UPSERT Fix

## Problem

When a user runs a predefined rule from the YAML (e.g., `run PATTERN_IN_EPISODE`), the backend would always INSERT a new rule record instead of updating the existing rule. This meant:
- Running `PATTERN_IN_EPISODE` twice created duplicate entries
- The rule_code column had a unique constraint violation
- Users couldn't update the SQL for an existing rule

## Root Cause

The backend was:
1. Generating a new `rule_name` from the natural language logic
2. Using that `rule_name` as the unique key for inserts
3. Losing the connection to the stable `rule_code` from the YAML

## Solution

Changed the data model and backend logic to use `rule_code` (stable YAML identifier) as the unique key:

### YAML Structure
```yaml
RULES:
  - rule_code: PATTERN_IN_EPISODE          ← Stable identifier (unique key)
    name: "Patterns in Episodes"           ← Display name
    description: "..."                     ← Display description
    logic: "natural language..."           ← User-facing description
```

### Database Structure
```
rules table:
- id (primary key)
- name (text) - Display name from YAML
- rule_code (text) - UNIQUE CONSTRAINT - Stable identifier from YAML
- description (text) - Description from YAML
- sql (text) - Generated SQL
- created_at, updated_at
```

### Backend Flow

**Before:**
```
User runs: "run PATTERN_IN_EPISODE"
    ↓
Supervisor receives rule_code="PATTERN_IN_EPISODE"
    ↓
Generates rule_name from logic (e.g., "find_all_patterns")
    ↓
Inserts INTO rules (name=rule_name, rule_code=logic, ...)
    ↓
Problem: rule_code is the NATURAL LANGUAGE, not the YAML key!
```

**After:**
```
User runs: "run PATTERN_IN_EPISODE"
    ↓
Supervisor receives rule_code="PATTERN_IN_EPISODE", rule_id="PATTERN_IN_EPISODE"
    ↓
Passes rule_code_key="PATTERN_IN_EPISODE" to RegisterRuleTool
    ↓
UPSERT INTO rules
WHERE rule_code="PATTERN_IN_EPISODE"
SET name, description, sql, updated_at
    ↓
Result: Existing rule updated, no duplicates ✅
```

## Code Changes

### supervisor.py

Changed `_process_single_rule()` to accept `rule_code_key`:
```python
# Before
rule_name=rule_id or self._auto_rule_name(rule_code)

# After
rule_code_key=rule_id  # Stable identifier from YAML
```

Now passes to tools:
```python
rule_reg = await self.tool_registry.execute(
    "register_rule",
    rule_code_key=rule_code_key,    # ← YAML identifier
    rule_name=display_name,         # ← Display name for views
    logic=logic,
    sql_query=sql_query
)
```

### tools.py

**RegisterRuleTool:**
```python
# Before
ON CONFLICT (name)

# After
ON CONFLICT (rule_code)
DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    sql = EXCLUDED.sql,
    updated_at = CURRENT_TIMESTAMP
```

**RegisterViewTool:**
```python
# Before
SELECT id FROM rules WHERE name=$1

# After
SELECT id FROM rules WHERE rule_code=$1
```

## Testing

### Test 1: Insert new rule
```bash
run NEW_CUSTOM_RULE
```
Expected: New entry created in `rules` table with rule_code='NEW_CUSTOM_RULE'

### Test 2: Update existing rule
```bash
# First run
run PATTERN_IN_EPISODE
# Check: row count = 42, SQL = SELECT ... 

# Second run (SQL may change, generated again)
run PATTERN_IN_EPISODE
# Check: SAME row, id=1, updated_at is NOW
```

### Test 3: Verify no duplicates
```sql
SELECT rule_code, COUNT(*) 
FROM rules 
GROUP BY rule_code 
HAVING COUNT(*) > 1;

-- Should return 0 rows (no duplicates)
```

## Compatibility

- **Existing predefined rules**: Will now UPDATE instead of INSERT
- **New ad-hoc rules**: Will INSERT with auto-generated rule_code
- **YAML rules**: Can now be re-run without duplicates

## Impact

- ✅ Users can run predefined rules repeatedly without duplicates
- ✅ SQL updates when rules are re-executed
- ✅ Stable rule tracking across multiple executions
- ✅ Respects the YAML rule_code as the source of truth

---

**Status**: ✅ IMPLEMENTED  
**Date**: November 24, 2025  
**Related**: `rule_code` is now the unique key for rules table
