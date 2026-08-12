"""
Pytest fixtures for the Pattern Factory API test suite.

No PostgreSQL or OpenAI connection is required. The FastAPI startup events
that normally create a database pool and call OpenAI are NOT run (TestClient
is used without entering its lifespan context manager). Database access in
routes is short-circuited by patching `backend.services.api.get_pg_pool` to
return an in-memory fake pool whose connections return canned asyncpg-like
results.
"""
from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


class FakeAsyncpgConn:
    """Minimal asyncpg-like connection.

    Default return values are chosen to avoid accidentally tripping 404/400
    error paths in CRUD endpoints (truthy fetchrow, truthy fetchval, a
    successful execute string). Override per test via
    `fake_conn.fetch.return_value = ...` etc.
    """

    def __init__(self) -> None:
        self.fetch = AsyncMock(return_value=[])
        self.fetchrow = AsyncMock(return_value={"id": 1, "name": "test"})
        self.fetchval = AsyncMock(return_value=1)
        self.execute = AsyncMock(return_value="DELETE 1")


class FakeAsyncpgPool:
    """asyncpg.Pool-like object whose acquire() yields a FakeAsyncpgConn."""

    def __init__(self, conn: FakeAsyncpgConn) -> None:
        self._conn = conn

    @contextlib.asynccontextmanager
    async def acquire(self):
        yield self._conn


@pytest.fixture
def fake_conn() -> FakeAsyncpgConn:
    return FakeAsyncpgConn()


@pytest.fixture
def client():
    """FastAPI TestClient without running the app's lifespan/startup events."""
    from backend.services.api import app
    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture
def mock_pool(fake_conn: FakeAsyncpgConn, monkeypatch) -> FakeAsyncpgPool:
    """Patch get_pg_pool to return a fake pool backed by fake_conn."""
    import backend.services.api as api_module
    pool = FakeAsyncpgPool(fake_conn)
    monkeypatch.setattr(api_module, "get_pg_pool", lambda: pool)
    return pool
