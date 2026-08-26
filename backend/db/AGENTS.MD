# Database Schema & Backend API Maintenance

## Agent Continuity Rule (CRITICAL)

**When you return from the terminal or paste test output, treat it as a continuation of active work, not a new interaction.** If context is unclear from the message alone, immediately call `search_conversation_history` to recover prior task context instead of asking the user to repeat themselves. This prevents losing mid-task progress when developers escape to run tests, check logs, or verify output. Treat pasted query results, error messages, and command output as signals that the user is mid-stream, working on the branch specified in their git HEAD.

#  Always note - pay attention to this first
- the database is called pattern-factory
- to understand and when altering the schema - always query with psql don't use migration scripts

## Always Do When Updating DB Schema

- Update prompts/rules/DATA.yaml - in the tables section
- When adding or altering tables, always update the TypeScript Models in `src/lib/types/models.ts`
- When adding or altering tables, always update the Pydantic models in `backend/services/models.py`
- Ensure Pydantic model fields match all database columns being queried and returned in API responses
- Failure to sync causes `UndefinedColumnError` exceptions

## Pydantic Model Sync Pattern

For any new database field:
- Add the field to the corresponding Pydantic `Create` class with appropriate default
- Add the field to the corresponding Pydantic `Update` class with optional type
- Update all API endpoints that return the entity to include the new field in SELECT statements
- Test that the field is properly persisted and retrieved
- Run `python -m pytest` from the repo root to verify the API contract still holds

Example (`backend/services/models.py`):
```python
# ❌ WRONG - missing fields in Pydantic model
class AssetCreate(BaseModel):
    name: str
    description: str

# ✅ CORRECT - all fields in Pydantic model
class AssetCreate(BaseModel):
    name: str
    description: str
    fixed_value: float = 0
    fixed_value_period: int = 12
    recurring_value: float = 0
    include_fixed_value: bool = True
    include_recurring_value: bool = True
```

## Pydantic request models location (refactor pat-306)
All FastAPI request-body Pydantic models (the `*Create` / `*Update` classes
for patterns, cards, paths, threats, models, assets, vulnerabilities,
countermeasures, and products, plus `PathNode` / `PathEdge`) live in
`backend/services/models.py`.

`backend/services/api.py` imports these models from `backend.services.models`
and must NOT re-define them inline. When adding a new endpoint request body:
1. Add the model class to `backend/services/models.py`.
2. Import it into `backend/services/api.py` via the existing
   `from backend.services.models import (...)` block.
3. Do not add `class XxxCreate(BaseModel):` blocks back into `api.py`.

## Running the API test suite
A hermetic pytest suite (no PostgreSQL or OpenAI connection required) lives
in `backend/tests/` and guards the API contract, request-body validation,
and core CRUD flows.

```bash
# One-time: install test dependencies (pytest; httpx already in requirements.txt)
pip install -r backend/requirements-dev.txt

# Run the full suite from the repo root
python -m pytest

# Verbose, per-test output
python -m pytest -v
```

`pytest.ini` at the repo root sets `pythonpath = .` and
`testpaths = backend/tests`, so always invoke pytest from the repo root.

The suite uses `fastapi.testclient.TestClient` without entering the app
lifespan, so the real Postgres pool and OpenAI diagnostics never start.
Database access in routes is short-circuited by patching
`backend.services.api.get_pg_pool` with an in-memory fake (see
`backend/tests/conftest.py`). Run `python -m pytest` before committing any
schema or model change.

## Database Timestamp Defaults (CRITICAL)

**Do NOT pass `created_at` and `updated_at` from Python to INSERT statements.**

All tables define these fields with `DEFAULT now()`:
```sql
CREATE TABLE threat.threats (
    ...,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now(),
    ...
);
```

PostgreSQL `now()` returns a naive (timezone-unaware) timestamp. Python's `datetime.now(timezone.utc)` returns timezone-aware. Passing timezone-aware objects causes:
```
can't subtract offset-naive and offset-aware datetimes
```

**Fix**: Omit timestamp fields from INSERT and let PostgreSQL use DEFAULT:
```python
# ❌ WRONG
for threat in threats:
    await conn.execute(
        "INSERT INTO threat.threats (..., created_at, updated_at) "
        "VALUES (..., $N::timestamp, $M::timestamp)",
        ...,
        datetime.now(timezone.utc),  # timezone-aware
        datetime.now(timezone.utc)   # timezone-aware
    )

# ✅ CORRECT
for threat in threats:
    await conn.execute(
        "INSERT INTO threat.threats (...) VALUES (...)",  # omit created_at, updated_at
        ...
    )
```

PostgreSQL will call `now()` server-side (naive timestamp in UTC), matching the schema definition.
