# DSL Loading Mechanism

## Overview

The Pattern Factory uses a YAML-based Domain Specific Language (DSL) stored in `prompts/rules/pattern-factory.yaml`. This document explains how the DSL is loaded and used by the Pitboss supervisor.

## DSL File Location

```
/pattern-factory/
├── prompts/
│   └── rules/
│       └── pattern-factory.yaml  ← DSL file
├── backend/
│   ├── services/
│   │   └── api.py
│   └── pitboss/
│       ├── supervisor.py
│       └── context_builder.py    ← Loads DSL
```

## DSL Structure

The `pattern-factory.yaml` contains three main sections:

### 1. SYSTEM Section
Instructions for the LLM (GPT-4o) on how to generate SQL.

```yaml
SYSTEM:
  rev: 0.1
  date: 2025-11-24
  author: D. Lieberman
  prompt: |
    You are the `model_rule_agent`.
    Your task is to take natural-language data rules
    and generate valid ANSI SQL...
```

### 2. DATA Section
Complete database schema (tables and columns).

```yaml
DATA:
  tables:
    patterns:
      - id
      - name
      - description
      - kind
      - created_at
      - updated_at
    episodes:
      - id
      - name
      - description
      - published_at
```

### 3. RULES Section
Predefined rules as examples (optional).

```yaml
RULES:
  - rule_code: PATTERN_IN_EPISODE
    name: "Patterns in Episodes"
    description: "Show patterns that appear in podcast episodes"
    logic: "show me the patterns in podcast episodes..."
```

## Loading Flow

### 1. Backend Startup

```
uvicorn services/api.py:app
    ↓
FastAPI initializes
    ↓
WebSocket endpoint /ws is ready
```

### 2. First WebSocket Connection

```
User clicks chat icon (frontend)
    ↓
Frontend connects to ws://localhost:8000/ws
    ↓
api.py:websocket_endpoint() is called
    ↓
Creates Pitboss instance:
    pitboss = Pitboss(db_connection, websocket)
    ↓
Pitboss.__init__() initializes:
    self.context_builder = ContextBuilder(db_connection)
    ↓
ContextBuilder.__init__() runs
    ↓
self._load_yaml() is called
    ↓
DSL is loaded from pattern-factory.yaml
```

### 3. DSL Path Resolution

The `ContextBuilder` now uses intelligent path resolution:

```python
# In context_builder.py
def __init__(self, db_connection=None, rules_yaml_path: str = None):
    if rules_yaml_path:
        # Use provided path
        self.rules_yaml_path = rules_yaml_path
    else:
        # Auto-resolve relative to backend directory
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        # File: backend/pitboss/context_builder.py
        # __file__ = /project/backend/pitboss/context_builder.py
        # dirname(__file__) = /project/backend/pitboss
        # dirname(dirname(__file__)) = /project/backend
        # dirname(backend_root) = /project
        
        project_root = os.path.dirname(backend_root)
        self.rules_yaml_path = os.path.join(
            project_root, "prompts", "rules", "pattern-factory.yaml"
        )
```

### Path Resolution Examples

| Working Directory | Resolved Path |
|---|---|
| `/project` | `/project/prompts/rules/pattern-factory.yaml` ✅ |
| `/project/backend` | `/project/prompts/rules/pattern-factory.yaml` ✅ |
| `/project/backend/pitboss` | `/project/prompts/rules/pattern-factory.yaml` ✅ |
| Any directory | Works correctly ✅ |

## Context Building Flow

### 1. User Sends Message

```
User types: "run Find all patterns"
Frontend sends: {"type": "run_rule", "rule_code": "Find all patterns"}
```

### 2. Backend Receives Request

```python
# api.py:websocket_endpoint()
data = await websocket.receive_text()
msg = json.loads(data)

if msg.get("type") == "run_rule":
    await pitboss.process_rule_request(
        rule_code=msg.get("rule_code"),
        rule_id=msg.get("rule_id")
    )
```

### 3. Pitboss Processes Rule

```python
# supervisor.py:process_rule_request()
async def process_rule_request(self, rule_code: str, rule_id: str):
    return await self._process_single_rule(
        rule_name=rule_id,
        logic=rule_code
    )
```

### 4. Context Builder Creates LLM Context

```python
# supervisor.py:_process_single_rule()
context = self.context_builder.build_context(
    rule_code=logic,  # "Find all patterns"
    include_examples=False,
    dsl=None
)
```

### 5. Context is Built

```python
# context_builder.py:build_context()
def build_context(self, rule_code: str):
    system_prompt = self._assemble_system_block()
    user_prompt = rule_code
    
    return {
        "system": system_prompt,
        "user": user_prompt
    }
```

### 6. System Block Contains

```python
# context_builder.py:_assemble_system_block()
# Returns: SYSTEM.prompt + DATA section

# Example output:
"""
You are the `model_rule_agent`.
Your task is to take a natural-language rule
and generate valid ANSI SQL...

# DATA
Available Tables:
  - patterns (id, name, description, kind, created_at, updated_at)
  - episodes (id, name, description, published_at, created_at, updated_at)
  - pattern_episode_link (pattern_id, episode_id)
  ...
"""
```

### 7. LLM Generation

```python
# tools.py:sql_pitboss()
messages = [
    {"role": "system", "content": context["system"]},
    {"role": "user", "content": context["user"]}
]

response = openai_client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    temperature=0
)

sql = response.choices[0].message.content
```

### 8. Generated SQL Example

```sql
-- For rule: "Find all patterns"
SELECT 
    p.id,
    p.name,
    p.description,
    p.kind,
    p.created_at
FROM patterns p
ORDER BY p.created_at DESC
```

### 9. Results Flow Back

```
SQL executed on database
    ↓
Materialized view created
    ↓
Results sent to frontend
    ↓
Frontend displays: "Rule find_all_patterns → 15 rows → rule_find_all_patterns_..."
```

## DSL Usage in Pitboss Pipeline

```
rule_code (natural language)
    ↓
[1. Build Context]
    SYSTEM.prompt (how to generate SQL)
    +
    DATA.tables (database schema)
    +
    rule_code (the specific rule)
    ↓
[2. Call sql_pitboss Tool]
    OpenAI GPT-4o converts to SQL
    ↓
[3. Call data_table Tool]
    Execute SQL
    Create materialized view
    ↓
[4. Register Results]
    Save rule metadata
    Record view in registry
    ↓
[5. Send to Frontend]
    Result message with table name and row count
```

## How DSL is Accessed

### During Initialization
- ✅ Loaded once when `ContextBuilder` is created
- ✅ Parsed and stored in `self.yaml_data`
- ✅ Logging shows what was loaded

### For Each Rule Request
- ✅ `SYSTEM.prompt` extracted from DSL
- ✅ `DATA.tables` formatted into context
- ✅ Schema information sent to LLM
- ✅ LLM uses schema to generate correct SQL

### Path Resolution Algorithm

```python
# File location: /project/backend/pitboss/context_builder.py
__file__ = "/project/backend/pitboss/context_builder.py"

# Step 1: Get directory of this file
dir1 = os.path.dirname(__file__)
     = "/project/backend/pitboss"

# Step 2: Get parent directory (backend/)
backend_root = os.path.dirname(dir1)
              = "/project/backend"

# Step 3: Get project root
project_root = os.path.dirname(backend_root)
             = "/project"

# Step 4: Build final path
dsl_path = os.path.join(project_root, "prompts", "rules", "pattern-factory.yaml")
         = "/project/prompts/rules/pattern-factory.yaml"
```

## Testing DSL Loading

A test script is provided to verify DSL loading:

```bash
# From project root
python backend/test_dsl_loading.py

# From backend directory
cd backend && python test_dsl_loading.py

# Expected output:
# ✅ DSL loaded successfully!
# DSL path: /path/to/pattern-factory/prompts/rules/pattern-factory.yaml
# SYSTEM sections: rev, date, author, prompt
# DATA tables: 18
# Available tables: [...]
# RULES defined: 8
```

## Troubleshooting

### Issue: "DSL file not found"

**Symptoms**:
- Error in logs: "Failed to load YAML file"
- Backend won't process rules

**Diagnosis**:
```python
logger.error(f"DSL file not found: {self.rules_yaml_path}")
logger.error(f"Current working directory: {os.getcwd()}")
```

**Solutions**:
1. Verify file exists: `ls prompts/rules/pattern-factory.yaml`
2. Check path permissions: `ls -la prompts/rules/`
3. Run from project root: `cd /path/to/pattern-factory`
4. Test with: `python backend/test_dsl_loading.py`

### Issue: Empty or Corrupted DSL

**Symptoms**:
- DSL loads but has 0 tables
- No SYSTEM prompt

**Check**:
```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('prompts/rules/pattern-factory.yaml'))"

# Should produce no errors
```

### Issue: LLM Gets Wrong Schema

**Symptoms**:
- SQL references non-existent columns
- "Unknown column" errors

**Solution**:
1. Update `pattern-factory.yaml` with correct schema
2. Restart backend to reload DSL
3. Test with: `python backend/test_dsl_loading.py`

## Configuration

### Custom DSL Path

You can provide a custom DSL path:

```python
# In api.py or wherever ContextBuilder is created
context_builder = ContextBuilder(
    db_connection=pool,
    rules_yaml_path="/custom/path/to/dsl.yaml"
)
```

### DSL Format Requirements

The DSL YAML must contain:

```yaml
SYSTEM:
  prompt: |
    Instructions for LLM...

DATA:
  tables:
    table_name:
      - column1
      - column2

RULES: []  # Can be empty
```

## DSL Update Process

1. **Edit** `prompts/rules/pattern-factory.yaml`
2. **Restart** the backend: `Ctrl+C` then `uvicorn ...`
3. **Verify** DSL loaded: Check logs for "✅ Loaded Pattern Factory DSL"
4. **Test** with chat: Send a new rule to verify it works

No database changes needed - just update the YAML!

## Performance Notes

- DSL loaded once at startup (~10ms)
- No repeated file I/O during rule processing
- Schema cached in memory
- Updated YAML requires backend restart

## Related Files

- `prompts/rules/pattern-factory.yaml` - DSL definition
- `backend/pitboss/context_builder.py` - DSL loader
- `backend/pitboss/supervisor.py` - DSL consumer
- `backend/services/api.py` - Pitboss instantiation
- `backend/test_dsl_loading.py` - DSL testing tool

---

**Last Updated**: November 24, 2025  
**Status**: ✅ DSL Loading Verified and Tested
