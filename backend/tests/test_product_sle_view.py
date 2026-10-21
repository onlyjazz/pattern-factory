"""
Stability tests for the ``public.product_sle_after_mitigation`` logical view.

Two layers:

* **Hermetic contract tests** (no database). They parse the migration that
  defines the view and assert the published shape -- the view name, the seven
  output columns in order, and the invariants that make the SLE arithmetic
  correct (the products->orgs and models->products join paths, the
  countermeasure mitigation rollup, the A1-A8 core-asset filter, the 5% residual
  floor, and the soft-delete filters). These run everywhere, including CI
  without PostgreSQL.

* **Integration tests** against the live ``pattern-factory`` database. They
  assert the deployed view matches the contract and -- most importantly -- that
  every row reconciles with ``threat.threat_impact(model_id)``, the independent
  PAT-399 implementation of the same arithmetic. When PostgreSQL is not
  reachable these tests skip, matching
  ``backend/tests/test_org_merge_integration.py``.

The reconciliation test is the one that matters most: the view duplicates the
mitigation math rather than calling the PAT-399 function (the function is ~7x
slower because it re-aggregates ``countermeasure_threat`` per model). That
duplication is a deliberate trade, and this test is what keeps the two copies
from drifting apart.

Run everything:               ``python -m pytest``
Run only the hermetic tests:  ``python -m pytest -m "not integration"``
"""
from __future__ import annotations

import re
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio

from backend.services.api import POSTGRES_DSN

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "db"

VIEW_NAME = "public.product_sle_after_mitigation"

# The published column contract, in order. `name` is orgs.name and `size` is
# orgs.size; both are unqualified in the view's output. `product_id` (products.id)
# is appended last so the view stays CREATE OR REPLACE-able, and lets products
# join the view back to their own row.
EXPECTED_COLUMNS = [
    "device",
    "panel",
    "superiority",
    "name",
    "size",
    "sle_after_mitigation",
    "product_id",
]

EXPECTED_TYPES = {
    "product_id": "bigint",
    "device": "text",
    "panel": "text",
    "superiority": "text",
    "name": "text",
    "size": "bigint",
    "sle_after_mitigation": "bigint",
}

# Each entry is a semantic invariant the view must preserve. If someone rewrites
# the view and drops one of these, the numbers silently change, so they are
# pinned individually rather than as one blob.
INVARIANTS = {
    "products joined to orgs on products.org_id": (
        r"FROM\s+products\s+p\s+INNER\s+JOIN\s+orgs\s+o\s+ON\s+o\.id\s*=\s*p\.org_id"
    ),
    "models reached through threat.models.product_id": (
        r"FROM\s+threat\.models\s+m\s+INNER\s+JOIN\s+threat_sle\s+ts\s+ON\s+ts\.model_id\s*=\s*m\.id"
    ),
    "only models carrying a product are rolled up": r"WHERE\s+m\.product_id\s+IS\s+NOT\s+NULL",
    "threats joined to assets through asset_threat": (
        r"INNER\s+JOIN\s+threat\.asset_threat\s+at\s+ON\s+at\.threat_id\s*=\s*t\.id"
        r"\s+AND\s+at\.model_id\s*=\s*t\.model_id"
    ),
    "assets joined on both id and model_id": (
        r"INNER\s+JOIN\s+threat\.assets\s+a\s+ON\s+a\.id\s*=\s*at\.asset_id"
        r"\s+AND\s+a\.model_id\s*=\s*at\.model_id"
    ),
    "asset damage applied to asset sle_value": (
        r"COALESCE\(a\.sle_value,\s*0\)\s*\*\s*\(at\.damage\s*/\s*100\.0\)"
    ),
    "threat probability applied": r"COALESCE\(t\.probability,\s*0\)\s*/\s*100\.0",
    "mitigation rolled up from countermeasure_threat": (
        r"FROM\s+threat\.countermeasure_threat\s+ct\s+INNER\s+JOIN\s+threat\.countermeasures\s+c"
        r"\s+ON\s+c\.id\s*=\s*ct\.countermeasure_id"
    ),
    "only included, enabled countermeasures count": (
        r"ct\.included_in_mitigation\s*=\s*true\s+AND\s+c\.disabled\s*=\s*false"
    ),
    "residual multiplier floored at 5%": r"GREATEST\(\s*0\.05",
    "mitigation level clamped to 0..95": (
        r"LEAST\(\s*GREATEST\(COALESCE\(ct\.mitigation_level,\s*0\),\s*0\),\s*95\s*\)"
    ),
    "core asset tags A1-A8": (
        r"a\.tag\s+IN\s*\('A1',\s*'A2',\s*'A3',\s*'A4',\s*'A5',\s*'A6',\s*'A7',\s*'A8'\)"
    ),
    "disabled threats excluded": r"t\.disabled\s*=\s*false",
    "disabled assets excluded": r"a\.disabled\s*=\s*false",
    "soft-deleted products excluded": r"p\.deleted_at\s+IS\s+NULL",
}

RECONCILIATION_SQL = """
WITH view_rows AS (
    SELECT
        row_number() OVER (ORDER BY sle_after_mitigation DESC, device) AS rn,
        device,
        sle_after_mitigation
    FROM public.product_sle_after_mitigation
    WHERE sle_after_mitigation IS NOT NULL
),
function_rows AS (
    SELECT
        row_number() OVER (ORDER BY total DESC, device) AS rn,
        device,
        total
    FROM (
        SELECT
            p.id,
            p.device,
            SUM(f.sle_after_mitigation)::BIGINT AS total
        FROM public.products p
        JOIN public.orgs o ON o.id = p.org_id
        JOIN threat.models m ON m.product_id = p.id
        CROSS JOIN LATERAL threat.threat_impact(m.id::integer) f
        WHERE p.deleted_at IS NULL
        GROUP BY p.id, p.device
    ) rolled
)
SELECT
    (SELECT count(*) FROM view_rows)     AS view_rows,
    (SELECT count(*) FROM function_rows) AS function_rows,
    count(*) FILTER (WHERE v.device IS DISTINCT FROM f.device)              AS device_diffs,
    count(*) FILTER (WHERE v.sle_after_mitigation IS DISTINCT FROM f.total) AS value_diffs
FROM view_rows v
FULL OUTER JOIN function_rows f ON f.rn = v.rn
"""

TOTALS_SQL = """
SELECT
    (SELECT sum(sle_after_mitigation) FROM public.product_sle_after_mitigation) AS view_total,
    (SELECT sum(f.sle_after_mitigation)
       FROM public.products p
       JOIN public.orgs o ON o.id = p.org_id
       JOIN threat.models m ON m.product_id = p.id
       CROSS JOIN LATERAL threat.threat_impact(m.id::integer) f
      WHERE p.deleted_at IS NULL) AS function_total
"""


# ---------------------------------------------------------------------------
# Hermetic contract tests -- no database required
# ---------------------------------------------------------------------------


def _published_columns(sql: str) -> list[str]:
    """Return the view's output column names, in order.

    Reads the SELECT list that immediately precedes the view's
    ``FROM products p``, taking the last SELECT keyword before it so the CTE
    subqueries earlier in the file are not picked up.
    """
    marker = re.search(r"FROM\s+products\s+p\b", sql, re.IGNORECASE)
    assert marker, "view definition never selects FROM products p"

    selects = list(re.finditer(r"\bSELECT\b", sql[: marker.start()], re.IGNORECASE))
    assert selects, "no SELECT keyword found before FROM products p"

    body = sql[selects[-1].end() : marker.start()]
    columns = []
    for raw in body.split(","):
        name = raw.strip()
        # Reduce `p.id AS product_id` to its alias before the table prefix is
        # stripped, so the alias is what gets compared.
        alias = re.search(r"\bAS\s+(\w+)\s*$", name, re.IGNORECASE)
        if alias:
            name = alias.group(1)
        # Reduce `p.device` / `ps.sle_after_mitigation` to the bare name.
        columns.append(re.sub(r"^.*\.", "", name).lower())
    return columns


@pytest.fixture(scope="module")
def migration_sql() -> str:
    """The migration that defines the view, located by suffix not exact name."""
    matches = sorted(MIGRATIONS_DIR.glob("*product-sle-after-mitigation-view.sql"))
    assert len(matches) == 1, (
        "expected exactly one product SLE view migration in "
        f"{MIGRATIONS_DIR}, found {[m.name for m in matches]}"
    )
    return matches[0].read_text()


def test_migration_defines_an_ordinary_view(migration_sql: str) -> None:
    """A logical view, not a materialized one, created inside a transaction."""
    assert re.search(
        r"CREATE\s+OR\s+REPLACE\s+VIEW\s+public\.product_sle_after_mitigation\b",
        migration_sql,
        re.IGNORECASE,
    ), "migration does not create public.product_sle_after_mitigation"
    assert not re.search(r"MATERIALIZED\s+VIEW", migration_sql, re.IGNORECASE), (
        "the view must stay logical (a materialized view would go stale)"
    )
    assert re.search(r"\bBEGIN\b", migration_sql) and re.search(r"\bCOMMIT\b", migration_sql)


def test_published_columns_are_exactly_the_contract(migration_sql: str) -> None:
    assert _published_columns(migration_sql) == EXPECTED_COLUMNS


@pytest.mark.parametrize("label", sorted(INVARIANTS))
def test_view_preserves_arithmetic_invariant(migration_sql: str, label: str) -> None:
    pattern = INVARIANTS[label]
    assert re.search(pattern, migration_sql, re.IGNORECASE | re.DOTALL), (
        f"the view no longer {label}; the SLE figure will not match "
        f"threat.threat_impact. Expected to find /{pattern}/"
    )


# ---------------------------------------------------------------------------
# Integration tests -- skipped when PostgreSQL is unreachable
# ---------------------------------------------------------------------------


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


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deployed_view_is_a_logical_view(pool) -> None:
    async with pool.acquire() as conn:
        # relkind is "char", which asyncpg hands back as bytes; cast to text.
        relkind = await conn.fetchval(
            "SELECT c.relkind::text FROM pg_class c "
            "JOIN pg_namespace n ON n.oid = c.relnamespace "
            "WHERE n.nspname = 'public' AND c.relname = 'product_sle_after_mitigation'"
        )
    assert relkind == "v", f"expected an ordinary view (relkind 'v'), got {relkind!r}"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_deployed_view_column_contract(pool) -> None:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'product_sle_after_mitigation' "
            "ORDER BY ordinal_position"
        )
    assert [row["column_name"] for row in rows] == EXPECTED_COLUMNS
    assert {row["column_name"]: row["data_type"] for row in rows} == EXPECTED_TYPES


@pytest.mark.integration
@pytest.mark.asyncio
async def test_one_row_per_product_that_has_an_org(pool) -> None:
    """The rollup must not fan out across models, threats or assets."""
    async with pool.acquire() as conn:
        view_rows = await conn.fetchval(
            "SELECT count(*) FROM public.product_sle_after_mitigation"
        )
        expected_rows = await conn.fetchval(
            "SELECT count(*) FROM public.products p "
            "JOIN public.orgs o ON o.id = p.org_id "
            "WHERE p.deleted_at IS NULL"
        )
    assert view_rows == expected_rows


@pytest.mark.integration
@pytest.mark.asyncio
async def test_products_without_an_org_are_excluded(pool) -> None:
    """orgs.name/orgs.size cannot be rendered for a product with no org."""
    async with pool.acquire() as conn:
        view_rows = await conn.fetchval(
            "SELECT count(*) FROM public.product_sle_after_mitigation"
        )
        total_products = await conn.fetchval(
            "SELECT count(*) FROM public.products WHERE deleted_at IS NULL"
        )
        products_without_org = await conn.fetchval(
            "SELECT count(*) FROM public.products p "
            "LEFT JOIN public.orgs o ON o.id = p.org_id "
            "WHERE p.deleted_at IS NULL AND o.id IS NULL"
        )
    assert view_rows == total_products - products_without_org


@pytest.mark.integration
@pytest.mark.asyncio
async def test_every_row_reconciles_with_threat_impact_function(pool) -> None:
    """Row-level agreement with the independent PAT-399 implementation.

    Compares the multiset of (device, sle_after_mitigation) pairs, so it catches
    a drifted formula even when the two sides still agree on row count.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(RECONCILIATION_SQL)

    assert row["view_rows"] == row["function_rows"], (
        "the view and threat.threat_impact(model_id) disagree on how many "
        f"products have a non-null SLE: {row['view_rows']} vs {row['function_rows']}"
    )
    assert row["value_diffs"] == 0, (
        f"{row['value_diffs']} products have a different sle_after_mitigation "
        "than threat.threat_impact(model_id)"
    )
    assert row["device_diffs"] == 0, (
        f"{row['device_diffs']} products are present on only one side"
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_totals_reconcile_with_threat_impact_function(pool) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(TOTALS_SQL)

    assert row["view_total"] == row["function_total"], (
        "total SLE across the view differs from the sum over "
        f"threat.threat_impact(model_id): {row['view_total']} vs {row['function_total']}"
    )
