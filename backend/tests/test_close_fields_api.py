"""
PAT-380 close_* column round-trip tests for orgs / products / people.

These are hermetic: the Postgres pool is replaced by the in-memory fake from
conftest.py, so no database or network is touched. They assert that the new
close columns are present in the SQL the endpoints issue (SELECT / INSERT /
UPDATE ... RETURNING) and that they are surfaced in responses.
"""


def _sql(mock_call) -> str:
    """Return the first positional SQL string from an asyncpg mock call."""
    return str(mock_call.args[0])


# ---------------------------------------------------------------------------
# orgs
# ---------------------------------------------------------------------------
def test_get_orgs_select_includes_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [
        {"id": 1, "name": "Acme", "close_send_date": None, "close_sent": False}
    ]
    r = client.get("/orgs")
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetch.call_args)
    assert "close_send_date" in sql
    assert "close_sent" in sql
    assert r.json()[0]["close_sent"] is False


def test_create_org_round_trips_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {
        "id": 1, "name": "Acme", "close_send_date": None, "close_sent": False
    }
    r = client.post("/orgs", json={"name": "Acme", "close_sent": False})
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_send_date" in sql
    assert "close_sent" in sql
    assert r.json()["close_sent"] is False


def test_get_org_includes_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Acme", "close_sent": True}
    r = client.get("/orgs/1")
    assert r.status_code == 200, r.text
    assert "close_sent" in _sql(fake_conn.fetchrow.call_args)


def test_update_org_sets_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Acme", "close_sent": True}
    r = client.put("/orgs/1", json={"close_sent": True})
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_send_date = COALESCE" in sql
    assert "close_sent = COALESCE" in sql


# ---------------------------------------------------------------------------
# products
# ---------------------------------------------------------------------------
def test_get_products_select_includes_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [
        {"id": 1, "device": "d", "close_send_date": None, "close_sent": False}
    ]
    r = client.get("/products")
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetch.call_args)
    assert "p.close_send_date" in sql
    assert "p.close_sent" in sql


def test_create_product_round_trips_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {
        "id": 1, "submission_number": "K1", "device": "d",
        "close_send_date": None, "close_sent": False,
    }
    r = client.post(
        "/products",
        json={"submission_number": "K1", "device": "d", "close_sent": False},
    )
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_send_date" in sql
    assert "close_sent" in sql


def test_get_product_includes_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "device": "d", "close_sent": True}
    r = client.get("/products/1")
    assert r.status_code == 200, r.text
    assert "p.close_sent" in _sql(fake_conn.fetchrow.call_args)


def test_update_product_sets_close_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "device": "d", "close_sent": True}
    r = client.put("/products/1", json={"close_sent": True})
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_send_date = COALESCE" in sql
    assert "close_sent = COALESCE" in sql


# ---------------------------------------------------------------------------
# people
# ---------------------------------------------------------------------------
def test_get_people_select_includes_close_mail_fields(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [
        {"id": 1, "name": "Jane", "close_mail_send_date": None, "close_mail_sent": False}
    ]
    r = client.get("/people")
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetch.call_args)
    assert "close_mail_send_date" in sql
    assert "close_mail_sent" in sql


def test_create_person_round_trips_close_mail_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {
        "id": 1, "name": "Jane", "close_mail_send_date": None, "close_mail_sent": False
    }
    r = client.post("/people", json={"name": "Jane", "close_mail_sent": False})
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_mail_send_date" in sql
    assert "close_mail_sent" in sql


def test_get_person_includes_close_mail_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Jane", "close_mail_sent": True}
    r = client.get("/people/1")
    assert r.status_code == 200, r.text
    assert "close_mail_sent" in _sql(fake_conn.fetchrow.call_args)


def test_update_person_sets_close_mail_fields(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Jane", "close_mail_sent": True}
    r = client.put("/people/1", json={"close_mail_sent": True})
    assert r.status_code == 200, r.text
    sql = _sql(fake_conn.fetchrow.call_args)
    assert "close_mail_send_date = COALESCE" in sql
    assert "close_mail_sent = COALESCE" in sql
