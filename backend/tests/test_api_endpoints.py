"""
Endpoint-level regression tests with a mocked Postgres pool.

These tests exercise the real FastAPI routes end-to-end but substitute the
database pool with an in-memory fake (see conftest.mock_pool). They prove
that after the Pydantic-model refactor, request models are still accepted
and responses are still produced for the core CRUD flows. No real database
or OpenAI connection is used.
"""


def test_root_returns_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "timestamp" in body


def test_get_patterns_returns_list(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [{"id": 1, "name": "Branding", "kind": "pattern"}]
    r = client.get("/patterns")
    assert r.status_code == 200
    assert r.json() == [{"id": 1, "name": "Branding", "kind": "pattern"}]


def test_search_patterns_returns_list(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [{"id": 1, "name": "Branding", "kind": "pattern"}]
    r = client.get("/patterns/search?q=brand")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_pattern_returns_200(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Branding", "kind": "pattern"}
    r = client.post(
        "/patterns",
        json={"name": "Branding", "description": "d", "kind": "pattern"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["id"] == 1


def test_update_pattern_returns_200(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Branding", "kind": "pattern"}
    r = client.put("/patterns/1", json={"name": "Branding2"})
    assert r.status_code == 200, r.text


def test_delete_pattern_returns_200(client, mock_pool, fake_conn):
    fake_conn.execute.return_value = "DELETE 1"
    r = client.delete("/patterns/1")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "deleted_id": 1}


def test_delete_pattern_not_found_returns_404(client, mock_pool, fake_conn):
    fake_conn.execute.return_value = "DELETE 0"
    r = client.delete("/patterns/1")
    assert r.status_code == 404


def test_create_card_returns_200(client, mock_pool, fake_conn):
    # fetchval default is truthy (pattern exists), fetchrow default is truthy
    fake_conn.fetchrow.return_value = {"id": 1, "name": "c", "pattern_id": 1}
    r = client.post("/cards", json={"name": "c", "description": "d", "pattern_id": 1})
    assert r.status_code == 200, r.text


def test_create_card_pattern_not_found_returns_400(client, mock_pool, fake_conn):
    fake_conn.fetchval.return_value = None  # pattern existence check fails
    r = client.post("/cards", json={"name": "c", "description": "d", "pattern_id": 999})
    assert r.status_code == 400
    assert r.json()["detail"] == "Pattern not found"


def test_create_product_returns_200(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {
        "id": 1, "submission_number": "K1", "device": "d",
    }
    r = client.post("/products", json={"submission_number": "K1", "device": "d"})
    assert r.status_code == 200, r.text


def test_create_product_org_not_found_returns_400(client, mock_pool, fake_conn):
    fake_conn.fetchval.return_value = None  # org existence check fails
    r = client.post(
        "/products",
        json={"submission_number": "K1", "device": "d", "org_id": 999},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Organization not found"


def test_views_invalid_mode_returns_400(client):
    # 400 is raised before get_pg_pool() is called, so no mock_pool needed
    r = client.get("/views?mode=bogus")
    assert r.status_code == 400


def test_views_explore_returns_list(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [
        {"id": 1, "name": "LIST_ORGS", "table_name": "LIST_ORGS", "mode": "explore"}
    ]
    r = client.get("/views?mode=explore")
    assert r.status_code == 200
    assert r.json()[0]["mode"] == "explore"


def test_query_invalid_table_name_returns_400(client, mock_pool):
    # get_pg_pool() runs before sanitization, so mock_pool is required here
    r = client.get("/query/tables;%20DROP%20TABLE%20users")
    assert r.status_code == 400


def test_query_valid_table_returns_rows(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [{"id": 1}]
    r = client.get("/query/LIST_ORGS")
    assert r.status_code == 200
    assert r.json() == [{"id": 1}]
