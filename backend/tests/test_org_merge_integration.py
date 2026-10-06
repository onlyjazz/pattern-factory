"""
Integration tests for POST /orgs/merge against the real PostgreSQL database.

Unlike the hermetic suite in this directory, these tests exercise the merge
endpoint end-to-end against the live ``pattern-factory`` database: a real
asyncpg pool is patched into the FastAPI app, fixture rows are inserted, and the
endpoint's transaction is verified against the actual schema (foreign keys,
``competitors`` UNIQUE constraint, and the ``update_product_competitors``
trigger).

Each test creates uniquely tagged fixtures and removes them in a ``finally``
block, so the database is left as it was found.

When PostgreSQL is not reachable the whole module skips, so environments
without a database can still run the hermetic suite. To run only the hermetic
tests:  ``python -m pytest -m "not integration"``
"""
from __future__ import annotations

import uuid

import asyncpg
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.services.api import POSTGRES_DSN

pytestmark = pytest.mark.integration

# An org id that cannot exist, used to exercise the 404 path.
MISSING_ORG_ID = 999_999_999_999


@pytest_asyncio.fixture
async def pool():
    """A real asyncpg pool, or skip the test when Postgres is unreachable."""
    try:
        pool = await asyncpg.create_pool(dsn=POSTGRES_DSN, min_size=1, max_size=2)
    except Exception as exc:  # pragma: no cover - depends on the local environment
        pytest.skip(f"PostgreSQL not reachable at {POSTGRES_DSN}: {exc}")

    try:
        yield pool
    finally:
        await pool.close()


@pytest_asyncio.fixture
async def api(pool, monkeypatch):
    """An httpx client bound to the real FastAPI app, backed by the real pool."""
    import backend.services.api as api_module

    monkeypatch.setattr(api_module, "get_pg_pool", lambda: pool)
    transport = ASGITransport(app=api_module.app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest_asyncio.fixture
async def scenario(pool):
    """Build a duplicate-org scenario covering every table the merge touches.

    Layout (``other`` is an unrelated org used as a competitor endpoint):

    - target   : 1 product, competitor row (target, other)
    - source   : 1 product, 1 person, 1 pattern link, competitor row (source, other)
    - source2  : 1 product, 1 person, 1 pattern link, competitor row (source2, target)

    After merging ``source`` and ``source2`` into ``target``:

    - all three products and both people belong to ``target``
    - the two pattern links collapse into a single ``(pattern, target)`` link
    - the (source, other) competitor collapses onto the existing (target, other)
      row, and (source2, target) would become self-referential so it is dropped
    """
    tag = f"itmerge-{uuid.uuid4().hex[:10]}"
    submission_numbers = [f"{tag}-T", f"{tag}-S", f"{tag}-S2"]
    person_names = [f"{tag}-person-s", f"{tag}-person-s2"]

    async with pool.acquire() as conn:
        pattern_id = await conn.fetchval("SELECT id FROM public.patterns ORDER BY id LIMIT 1")
        if pattern_id is None:
            pytest.skip("No patterns exist to create pattern_org_link fixtures")

        target_id = await conn.fetchval(
            "INSERT INTO public.orgs (name) VALUES ($1) RETURNING id", f"{tag}-target"
        )
        source_id = await conn.fetchval(
            "INSERT INTO public.orgs (name) VALUES ($1) RETURNING id", f"{tag}-source"
        )
        source2_id = await conn.fetchval(
            "INSERT INTO public.orgs (name) VALUES ($1) RETURNING id", f"{tag}-source2"
        )
        other_id = await conn.fetchval(
            "INSERT INTO public.orgs (name) VALUES ($1) RETURNING id", f"{tag}-other"
        )
        org_ids = [target_id, source_id, source2_id, other_id]

        product_ids = [
            await conn.fetchval(
                "INSERT INTO public.products (submission_number, device, org_id) VALUES ($1, $2, $3) RETURNING id",
                submission_numbers[0], "target device", target_id,
            ),
            await conn.fetchval(
                "INSERT INTO public.products (submission_number, device, org_id) VALUES ($1, $2, $3) RETURNING id",
                submission_numbers[1], "source device", source_id,
            ),
            await conn.fetchval(
                "INSERT INTO public.products (submission_number, device, org_id) VALUES ($1, $2, $3) RETURNING id",
                submission_numbers[2], "source2 device", source2_id,
            ),
        ]

        await conn.execute(
            "INSERT INTO public.people (name, org_id) VALUES ($1, $2)", person_names[0], source_id
        )
        await conn.execute(
            "INSERT INTO public.people (name, org_id) VALUES ($1, $2)", person_names[1], source2_id
        )

        await conn.execute(
            "INSERT INTO public.pattern_org_link (pattern_id, org_id) VALUES ($1, $2)",
            pattern_id, source_id,
        )
        await conn.execute(
            "INSERT INTO public.pattern_org_link (pattern_id, org_id) VALUES ($1, $2)",
            pattern_id, source2_id,
        )

        # Colliding competitor pair + one that becomes self-referential.
        await conn.execute(
            "INSERT INTO public.competitors (company_id, competitor_id, product_id, rank) VALUES ($1, $2, $3, $4)",
            target_id, other_id, product_ids[0], 1,
        )
        await conn.execute(
            "INSERT INTO public.competitors (company_id, competitor_id, product_id, rank) VALUES ($1, $2, $3, $4)",
            source_id, other_id, product_ids[0], 2,
        )
        await conn.execute(
            "INSERT INTO public.competitors (company_id, competitor_id, product_id, rank) VALUES ($1, $2, $3, $4)",
            source2_id, target_id, product_ids[0], 3,
        )

    data = {
        "tag": tag,
        "pattern_id": pattern_id,
        "org_ids": org_ids,
        "target_id": target_id,
        "source_ids": [source_id, source2_id],
        "other_id": other_id,
        "product_ids": product_ids,
        "submission_numbers": submission_numbers,
        "person_names": person_names,
    }

    try:
        yield data
    finally:
        async with pool.acquire() as conn:
            # Order matters: competitors reference both orgs and products.
            await conn.execute(
                "DELETE FROM public.competitors WHERE company_id = ANY($1::bigint[]) OR competitor_id = ANY($1::bigint[])",
                org_ids,
            )
            await conn.execute(
                "DELETE FROM public.products WHERE submission_number = ANY($1::text[])",
                submission_numbers,
            )
            await conn.execute(
                "DELETE FROM public.pattern_org_link WHERE org_id = ANY($1::bigint[])", org_ids
            )
            await conn.execute(
                "DELETE FROM public.people WHERE name = ANY($1::text[])", person_names
            )
            await conn.execute("DELETE FROM public.orgs WHERE id = ANY($1::bigint[])", org_ids)


@pytest.mark.asyncio
async def test_merge_reassigns_all_references_and_deletes_sources(api, pool, scenario):
    response = await api.post(
        "/orgs/merge",
        json={
            "target_org_id": scenario["target_id"],
            "source_org_ids": scenario["source_ids"],
        },
    )
    assert response.status_code == 200, response.text

    body = response.json()
    assert body["status"] == "ok"
    assert body["target_org_id"] == scenario["target_id"]
    assert sorted(body["merged_org_ids"]) == sorted(scenario["source_ids"])
    assert body["updated"]["products"] == 2
    assert body["updated"]["people"] == 2
    assert body["updated"]["pattern_org_link"] == 1

    target_id = scenario["target_id"]
    source_ids = scenario["source_ids"]

    async with pool.acquire() as conn:
        # products: every fixture product now points at the target
        for product_id in scenario["product_ids"]:
            org_id = await conn.fetchval(
                "SELECT org_id FROM public.products WHERE id = $1", product_id
            )
            assert org_id == target_id

        # people: every fixture person now points at the target
        people_orgs = await conn.fetch(
            "SELECT DISTINCT org_id FROM public.people WHERE name = ANY($1::text[])",
            scenario["person_names"],
        )
        assert [row["org_id"] for row in people_orgs] == [target_id]

        # pattern_org_link: sources collapsed into a single (pattern, target) link
        link_orgs = await conn.fetch(
            "SELECT org_id FROM public.pattern_org_link WHERE pattern_id = $1 AND org_id = ANY($2::bigint[])",
            scenario["pattern_id"], scenario["org_ids"],
        )
        assert [row["org_id"] for row in link_orgs] == [target_id]

        # competitors: the duplicate collapsed and the self-reference was dropped
        competitor_rows = await conn.fetch(
            "SELECT company_id, competitor_id FROM public.competitors WHERE product_id = $1",
            scenario["product_ids"][0],
        )
        assert [(row["company_id"], row["competitor_id"]) for row in competitor_rows] == [
            (target_id, scenario["other_id"])
        ]

        # source orgs are gone
        remaining_sources = await conn.fetchval(
            "SELECT COUNT(*) FROM public.orgs WHERE id = ANY($1::bigint[])", source_ids
        )
        assert remaining_sources == 0

        # the target survived
        target_exists = await conn.fetchval(
            "SELECT COUNT(*) FROM public.orgs WHERE id = $1", target_id
        )
        assert target_exists == 1

        # the merge was recorded in system_log
        logged = await conn.fetchval(
            "SELECT COUNT(*) FROM public.system_log WHERE event = 'ORG_MERGE' AND context->>'target_org_id' = $1",
            str(target_id),
        )
        assert logged >= 1


@pytest.mark.asyncio
async def test_merge_rejects_empty_source_list(api, scenario):
    response = await api.post(
        "/orgs/merge", json={"target_org_id": scenario["target_id"], "source_org_ids": []}
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "source_org_ids must not be empty"


@pytest.mark.asyncio
async def test_merge_rejects_target_inside_sources(api, scenario):
    response = await api.post(
        "/orgs/merge",
        json={
            "target_org_id": scenario["target_id"],
            "source_org_ids": [scenario["target_id"], scenario["source_ids"][0]],
        },
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "target_org_id must not be one of source_org_ids"


@pytest.mark.asyncio
async def test_merge_missing_source_org_returns_404(api, scenario):
    response = await api.post(
        "/orgs/merge",
        json={"target_org_id": scenario["target_id"], "source_org_ids": [MISSING_ORG_ID]},
    )
    assert response.status_code == 404
    assert str(MISSING_ORG_ID) in response.json()["detail"]


@pytest.mark.asyncio
async def test_merge_rolls_back_when_a_source_is_missing(api, pool, scenario):
    """A missing org must abort before any write happens."""
    response = await api.post(
        "/orgs/merge",
        json={
            "target_org_id": scenario["target_id"],
            "source_org_ids": [scenario["source_ids"][0], MISSING_ORG_ID],
        },
    )
    assert response.status_code == 404

    async with pool.acquire() as conn:
        # The valid source org and its product are untouched.
        source_exists = await conn.fetchval(
            "SELECT COUNT(*) FROM public.orgs WHERE id = $1", scenario["source_ids"][0]
        )
        assert source_exists == 1

        product_org = await conn.fetchval(
            "SELECT org_id FROM public.products WHERE id = $1", scenario["product_ids"][1]
        )
        assert product_org == scenario["source_ids"][0]
