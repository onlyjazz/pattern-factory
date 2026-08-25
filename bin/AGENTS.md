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
