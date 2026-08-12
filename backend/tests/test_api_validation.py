"""
Request-body validation regression tests.

A 422 response is returned by FastAPI BEFORE any endpoint code (or DB access)
runs, so these tests prove the Pydantic models imported into api.py still act
as request validators without needing a database. Only the `client` fixture
is required; `mock_pool` is intentionally not used.
"""


def test_post_patterns_missing_name_returns_422(client):
    r = client.post("/patterns", json={"description": "x", "kind": "pattern"})
    assert r.status_code == 422


def test_post_patterns_missing_kind_returns_422(client):
    r = client.post("/patterns", json={"name": "n", "description": "x"})
    assert r.status_code == 422


def test_post_patterns_empty_body_returns_422(client):
    r = client.post("/patterns", json={})
    assert r.status_code == 422


def test_post_cards_missing_pattern_id_returns_422(client):
    r = client.post("/cards", json={"name": "n", "description": "d"})
    assert r.status_code == 422


def test_post_threats_missing_name_returns_422(client):
    r = client.post("/threats", json={"description": "d"})
    assert r.status_code == 422


def test_post_models_missing_name_returns_422(client):
    r = client.post("/models", json={"version": "1"})
    assert r.status_code == 422


def test_post_products_missing_submission_number_returns_422(client):
    r = client.post("/products", json={"device": "d"})
    assert r.status_code == 422


def test_post_products_missing_device_returns_422(client):
    r = client.post("/products", json={"submission_number": "K123"})
    assert r.status_code == 422


def test_post_assets_invalid_fixed_value_type_returns_422(client):
    # fixed_value is float; a non-numeric string cannot be coerced -> 422
    r = client.post(
        "/assets",
        json={"name": "n", "description": "d", "fixed_value": "not-a-number"},
    )
    assert r.status_code == 422
