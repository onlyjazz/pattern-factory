# DSL Loading Fix - Summary

## What You Caught

You correctly identified that the DSL (`prompts/rules/pattern-factory.yaml`) was using a relative path in `context_builder.py`. This could fail if the backend was run from different working directories.

## The Fix

### Before (Fragile)
```python
self.rules_yaml_path = rules_yaml_path or os.path.join(
    "prompts", "rules", "pattern-factory.yaml"
)
```

Only works if running from project root: `cd /project && uvicorn backend/services/api.py`

### After (Robust)
```python
if rules_yaml_path:
    self.rules_yaml_path = rules_yaml_path
else:
    # Auto-resolve relative to the backend directory
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # __file__ = /project/backend/pitboss/context_builder.py
    # dirname(__file__) = /project/backend/pitboss
    # dirname(dirname(__file__)) = /project/backend
    
    project_root = os.path.dirname(backend_root)
    # project_root = /project
    
    self.rules_yaml_path = os.path.join(
        project_root, "prompts", "rules", "pattern-factory.yaml"
    )
```

Now works from ANY working directory!

## How It Works

The fix uses Python's `__file__` attribute to locate the current file, then traverses up the directory structure to find the project root:

```
/project/backend/pitboss/context_builder.py  ← This is __file__
   ↓
/project/backend/pitboss                      ← dirname(__file__)
   ↓
/project/backend                              ← dirname(dirname(__file__))
   ↓
/project                                      ← dirname(backend_root)
   ↓
/project/prompts/rules/pattern-factory.yaml   ← Final DSL path
```

## Testing

Created `backend/test_dsl_loading.py` to verify the fix works:

```bash
# Test from project root
cd /Users/dl/code/pattern-factory && python backend/test_dsl_loading.py
# ✅ PASSED

# Test from backend directory
cd /Users/dl/code/pattern-factory/backend && python test_dsl_loading.py
# ✅ PASSED

# Test from any directory
cd /tmp && python /Users/dl/code/pattern-factory/backend/test_dsl_loading.py
# ✅ PASSED
```

## Verification Output

```
✅ DSL loaded successfully!
DSL path: /Users/dl/code/pattern-factory/prompts/rules/pattern-factory.yaml

DSL Content Summary:
  - SYSTEM sections: rev, date, author, prompt
  - SYSTEM.prompt length: 618
  - DATA.tables: 18
  - Available tables: categories, episodes, guests, orgs, pattern_episode_link... (18 total)
  - RULES defined: 8
  - First rule: Patterns in Episodes

✅ Testing context building...
  - System prompt length: 654 chars
  - User prompt: 'Find all patterns'

✅ All tests passed!
```

## Enhanced Logging

Added informative logging to `context_builder.py`:

```python
logger.info(f"✅ Loaded Pattern Factory DSL: {self.rules_yaml_path}")
logger.info(f"   SYSTEM sections: {system_keys}")
logger.info(f"   DATA tables: {data_tables}")
logger.info(f"   Predefined RULES: {rules_count}")
```

When backend starts, you'll see:
```
context_builder.py - INFO - ✅ Loaded Pattern Factory DSL: /project/prompts/rules/pattern-factory.yaml
context_builder.py - INFO -    SYSTEM sections: rev, date, author, prompt
context_builder.py - INFO -    DATA tables: 18
context_builder.py - INFO -    Predefined RULES: 8
```

## DSL Loading Flow (Now Clear)

```
User sends chat message
    ↓
WebSocket receives: {"type": "run_rule", "rule_code": "..."}
    ↓
api.py:websocket_endpoint() routes to Pitboss
    ↓
Pitboss.__init__() creates ContextBuilder
    ↓
ContextBuilder.__init__() loads DSL:
    ├─ Resolves absolute path (works from any directory)
    ├─ Reads prompts/rules/pattern-factory.yaml
    ├─ Parses SYSTEM, DATA, RULES sections
    ├─ Logs what was loaded
    └─ Caches in self.yaml_data
    ↓
For each rule request:
    ├─ Extract SYSTEM.prompt from DSL
    ├─ Format DATA.tables into context
    ├─ Combine with user's rule_code
    ├─ Send to OpenAI GPT-4o
    ├─ Receive SQL
    ├─ Execute SQL
    └─ Return results to frontend
```

## Files Modified

- ✅ `backend/pitboss/context_builder.py` - Fixed path resolution, added logging
- ✅ `backend/test_dsl_loading.py` - Created test script
- ✅ `DSL_LOADING.md` - Created comprehensive documentation

## Files Unchanged (Already Correct)

- `prompts/rules/pattern-factory.yaml` - DSL already well-structured
- `backend/pitboss/supervisor.py` - Already correctly calls `context_builder.build_context()`
- `backend/services/api.py` - Already correctly creates Pitboss instance

## DSL Structure Verified

The DSL has exactly what Pitboss needs:

### SYSTEM Section
```yaml
SYSTEM:
  prompt: |
    You are the model_rule_agent...
    [Instructions for LLM]
```

### DATA Section
```yaml
DATA:
  tables:
    patterns: [id, name, description, kind, ...]
    episodes: [id, name, description, ...]
    guests: [id, name, job_description, ...]
    [... 18 tables total ...]
```

### RULES Section
```yaml
RULES:
  - rule_code: PATTERN_IN_EPISODE
    name: "Patterns in Episodes"
    logic: "show me patterns in podcast episodes..."
  [... 8 predefined rules ...]
```

## Flow Diagram

```
Chat Message (Frontend)
    ↓
WebSocket (/ws)
    ↓
api.py::websocket_endpoint()
    ↓
Pitboss(db, websocket)
    ↓
ContextBuilder(db) 
    ├─ _load_yaml()
    │   └─ Loads /project/prompts/rules/pattern-factory.yaml ✅
    └─ Stores self.yaml_data
    ↓
process_rule_request(rule_code)
    ↓
build_context(rule_code)
    ├─ SYSTEM.prompt from DSL
    ├─ DATA.tables from DSL
    └─ user_prompt = rule_code
    ↓
Messages to OpenAI
    ↓
SQL Generated
    ↓
Database Results
    ↓
Frontend Response
```

## Confidence Level

✅ **HIGH** - The fix has been:
- Tested from multiple working directories
- Verified with automated test script
- Logged with clear debug output
- Documented with comprehensive guide

The DSL loading mechanism is now robust and works correctly regardless of where the backend is run from.

---

**Status**: ✅ RESOLVED - DSL loading fixed and verified  
**Date**: November 24, 2025  
**Impact**: Critical fix ensuring Pitboss always loads the DSL correctly
