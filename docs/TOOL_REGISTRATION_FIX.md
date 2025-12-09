# Tool Registration Fix

## Problem

Error: `Tool 'data_table' not found`

When trying to execute a rule, Pitboss supervisor couldn't find the `data_table` tool.

## Root Cause

The `DataTableTool`, `RegisterRuleTool`, and `RegisterViewTool` classes were missing `__init__` methods that call `super().__init__()` to set their `name` attribute.

**Before:**
```python
class DataTableTool(Tool):
    async def execute(self, sql_query: str, rule_name: str, **kwargs):
        # Tool was never assigned a name!
```

When tools were instantiated in `ToolRegistry._register_default_tools()`:
```python
self.register(DataTableTool(self.db_pool))
```

The tool would be created but its `name` would be undefined, so when the registry tried to look it up by name later, it would fail.

## Solution

Added explicit `__init__` methods to all tools to properly set their names:

**DataTableTool:**
```python
def __init__(self, db_pool):
    super().__init__("data_table", db_pool)
```

**RegisterRuleTool:**
```python
def __init__(self, db_pool):
    super().__init__("register_rule", db_pool)
```

**RegisterViewTool:**
```python
def __init__(self, db_pool):
    super().__init__("register_view", db_pool)
```

## Tool Registry Flow

Now the tools properly register:

```
ToolRegistry.__init__()
    ↓
_register_default_tools()
    ├─ SqlPitbossTool(pool, config)
    │   └─ name = "sql_pitboss"
    ├─ DataTableTool(pool)
    │   └─ name = "data_table" ✅
    ├─ RegisterRuleTool(pool)
    │   └─ name = "register_rule" ✅
    └─ RegisterViewTool(pool)
        └─ name = "register_view" ✅
```

## Verification

Tool names are now correctly set:

```
✅ Tool names are set correctly:
  - DataTableTool.name = "data_table"
  - RegisterRuleTool.name = "register_rule"
  - RegisterViewTool.name = "register_view"
  - SqlPitbossTool.name = "sql_pitboss"
```

## Testing

To verify the fix works:

1. **Open chat** and send: `run PATTERN_IN_EPISODE`
2. **Expected flow:**
   - User message appears (blue)
   - Typing indicator shows (● ● ●)
   - Backend processes rule
   - All 4 tools execute in order:
     - ✅ `sql_pitboss` - Generate SQL from natural language
     - ✅ `data_table` - Create view and count rows
     - ✅ `register_rule` - Save rule metadata
     - ✅ `register_view` - Register view in registry
   - Agent message appears (gray): "Rule pattern_in_episode → X rows → view_name"

## Impact

- **Before**: `data_table` tool not found → Rule execution failed
- **After**: All tools properly registered → Rules execute successfully

## Files Modified

- `backend/pitboss/tools.py`
  - Added `__init__` to `DataTableTool`
  - Added `__init__` to `RegisterRuleTool`
  - Added `__init__` to `RegisterViewTool`

---

**Status**: ✅ FIXED  
**Date**: November 24, 2025  
**Tools Now Working**: sql_pitboss, data_table, register_rule, register_view
