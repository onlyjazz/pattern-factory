# Directory of batch scripts to run backend services

## General rules
Services run in the ./backend/services directory
Batch scripts run in ./bin/

## Agent Continuity Rule (CRITICAL)

**When you return from the terminal or paste test output, treat it as a continuation of active work, not a new interaction.** If context is unclear from the message alone, immediately call `search_conversation_history` to recover prior task context instead of asking the user to repeat themselves. This prevents losing mid-task progress when developers escape to run tests, check logs, or verify output. Treat pasted query results, error messages, and command output as signals that the user is mid-stream, working on the branch specified in their git HEAD.

See `backend/db/AGENTS.MD` for comprehensive database schema maintenance and Pydantic model sync rules (consolidated source of truth for DB/API coordination).

## System Logging (Single Source of Truth) in backend services code

**All system logging MUST use** `backend/pitboss/logging_util.py:log_event()` — this is the ONLY correct way to log events.

### Correct Usage for loggin

```python
from pitboss.logging_util import log_event

# In async code:
await log_event(
    db,  # asyncpg connection or pool
    "EVENT_NAME",
    {"field1": value1, "field2": value2}  # optional context dict
)
```

### Signature for logging

```python
async def log_event(
    db,  # asyncpg connection/pool
    event: str,  # Event name (e.g., "FEELGOOD_COMPLETE", "ENRICH_COMPLETE")
    context: Optional[Dict[str, Any]] = None  # Optional context data
) -> bool:  # Returns True on success, False on failure
```

### Database Schema for logging

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
