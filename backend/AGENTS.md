# Backend API, Pydantic Models & System Logging

## Adding a New Verb (Clean Architecture Pattern)

The system follows a clean, generic `VERB OBJECT` pattern:
```
User: "VERB OBJECT"  (e.g., "portfolio Medtronic", "enrich Acme Corp", "feelgood 42")
  ↓
LanguageCapo: Validates verb exists, returns (decision, confidence, reason, verb)
  ↓
Supervisor: Routes to workflow (no special cases, pure routing)
  ↓
Agent Flow: Extracts object using _extract_verb_object(raw_text), processes, returns result
  ↓
Terminal/HITL: Returns to chat or awaits user approval
```

### To Add a New Verb (5 Steps)

1. **Add to Verb enum** (`backend/pitboss/envelope.py`, lines 34-45):
   ```python
   class Verb(str, Enum):
       # ... existing verbs ...
       MYVERB = "MYVERB"  # Description of what MYVERB does
   ```

2. **Add workflow to WorkflowEngine** (`backend/pitboss/workflow.py`):
   ```python
   myverb_workflow = {
       "model.Capo": WorkflowNode(...),
       # ... other nodes in your agent flow ...
   }
   self.workflows["MYVERB"] = myverb_workflow
   ```

3. **Create agent files** (`backend/pitboss/myverb.py`):
   - Agents extract object using: `from .agents import _extract_verb_object`
   - Object extraction: `obj = _extract_verb_object(raw_text)`
   - Each agent returns: `(decision, confidence, reason)`

4. **Register agents** in `backend/pitboss/agents.py`:
   ```python
   # Import
   from .myverb import agent_name1, agent_name2
   
   # Register in AGENT_REGISTRY
   AGENT_REGISTRY = {
       # ...
       "agent.name1": agent_name1,
       "agent.name2": agent_name2,
   }
   
   # Add routing in _get_agent_for_verb()
   case "MYVERB":
       match agent_name:
           case "model.Capo":
               return agent_capo_rule
           case _:
               return AGENT_REGISTRY.get(agent_name)
   ```

5. **Done** — No supervisor changes needed. The generic flow handles all verbs.

### Key Rules

- **NEVER extract object in supervisor** — Leave raw_text untouched
- **ALWAYS use `_extract_verb_object(raw_text)`** in agents — Splits on first space, returns everything after
- **NEVER add special cases to supervisor** — It only routes, agents own business logic
- **Each agent returns `(decision, confidence, reason)`** — Supervisor handles yes/no/HITL

## Agent Continuity Rule (CRITICAL)

Do not cd to the root directory of the project while you're working since it breaks the reference to AGENTS.md in the working directory.

Specifically if you run psql or git commands do not cd to the project root - pattern-factory

**When you return from the terminal or paste test output, treat it as a continuation of active work, not a new interaction.** If context is unclear from the message alone, immediately call `search_conversation_history` to recover prior task context instead of asking the user to repeat themselves. This prevents losing mid-task progress when developers escape to run tests, check logs, or verify output. Treat pasted query results, error messages, and command output as signals that the user is mid-stream, working on the branch specified in their git HEAD.

See `backend/db/AGENTS.MD` for comprehensive database schema maintenance and Pydantic model sync rules (consolidated source of truth for DB/API coordination).

## System Logging (Single Source of Truth)

**All system logging MUST use** `backend/pitboss/logging_util.py:log_event()` — this is the ONLY correct way to log events.

### Correct Usage

```python
from pitboss.logging_util import log_event

# In async code:
await log_event(
    db,  # asyncpg connection or pool
    "EVENT_NAME",
    {"field1": value1, "field2": value2}  # optional context dict
)
```

### Signature

```python
async def log_event(
    db,  # asyncpg connection/pool
    event: str,  # Event name (e.g., "FEELGOOD_COMPLETE", "ENRICH_COMPLETE")
    context: Optional[Dict[str, Any]] = None  # Optional context data
) -> bool:  # Returns True on success, False on failure
```

### Database Schema

Table: `public.system_log`
- `id`: UUID (auto-generated)
- `event`: TEXT (event name)
- `context`: JSONB (context dict, auto-serialized)
- `created_at`: TIMESTAMP (auto-generated)

### Examples

```python
# FEELGOOD batch completion
await log_event(pool, "FEELGOOD_BATCH_COMPLETE", {
    "total": 100,
    "success": 95,
    "failed": 5
})

# ENRICH agent completion
await log_event(db, "ENRICH_COMPLETE", {
    "org_id": 42,
    "org_name": "Acme Corp",
    "estimated_annual_sales": 1000000,
    "total_funding": 5000000
})
```

### Never Do This

❌ **DO NOT** write raw SQL inserts:
```python
# WRONG - bypasses logging utility
await db.execute(
    "INSERT INTO public.system_log (event, context) VALUES ($1, $2)",
    "MY_EVENT",
    json.dumps(data)
)
```

❌ **DO NOT** use `backend/db/log.py` (file is deleted, wrong schema)

## Database Timestamp Defaults

**CRITICAL: Do NOT pass `created_at` and `updated_at` from Python code to INSERT statements.**

All tables in the threat schema (and most application tables) define these fields with `DEFAULT now()`:
- `created_at TIMESTAMP DEFAULT now()`
- `updated_at TIMESTAMP DEFAULT now()`

When building INSERT payloads:
- **OMIT** `created_at` and `updated_at` from the INSERT column list
- **OMIT** these fields from the VALUES clause
- Let PostgreSQL automatically populate them via DEFAULT
- This avoids timezone-aware/naive datetime mismatch errors

**Example**:
```python
# ❌ WRONG - causes type mismatch with PostgreSQL naive timestamps
await conn.execute(
    "INSERT INTO threat.threats (model_id, name, created_at, updated_at, ...) "
    "VALUES ($1, $2, $3, $4, ...)",
    model_id, name, datetime.now(timezone.utc), datetime.now(timezone.utc)
)

# ✅ CORRECT - let database handle timestamps
await conn.execute(
    "INSERT INTO threat.threats (model_id, name, ...) VALUES ($1, $2, ...)",
    model_id, name
)
```
