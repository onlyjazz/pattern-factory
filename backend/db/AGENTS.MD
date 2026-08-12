# FOLLOW THIS RULES FOR maintaining this database

## Always do when updating the db schema
- When adding or altering tables, always update the TypeScript Models in src/lib/types/models.ts
- When adding or altering tables, always update the Pydantic models in backend/services/models.py

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
