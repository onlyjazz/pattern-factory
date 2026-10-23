"""
Hermetic tests for GET /model-risk/{model_id}.

Regression guard: the model-risk page used to read public."THRIM", which is
pinned to the single row in public.active_models, so it reported whichever model
happened to be active instead of the one being viewed. The page header (model
158) and its threat rows (the active model) disagreed, in both the page and the
exported PDF. The endpoint must resolve the model from its path argument.
"""


def _sql(mock_call) -> str:
    """Return the first positional SQL string from an asyncpg mock call."""
    return str(mock_call.args[0])


def test_model_risk_resolves_the_model_from_the_path(client, mock_pool, fake_conn):
    fake_conn.fetchval.return_value = 158  # the model exists
    fake_conn.fetch.return_value = [
        {
            "threat_id": 5831,
            "model_id": 158,
            "threat_tag": "PROD-103-01",
            "threat_name": "Segmentation error",
            "gross_sle": 22500000,
            "sle": 1125000,
            "sle_after_mitigation": 56250,
        }
    ]

    r = client.get("/model-risk/158")
    assert r.status_code == 200, r.text
    assert r.json()[0]["threat_name"] == "Segmentation error"

    sql = _sql(fake_conn.fetch.call_args)
    assert "threat.threat_impact" in sql, "must read the model-scoped function"
    assert "THRIM" not in sql, "THRIM is pinned to the active model"
    # The model from the path is the argument the function is called with.
    assert fake_conn.fetch.call_args.args[1] == 158


def test_model_risk_missing_model_returns_404(client, mock_pool, fake_conn):
    fake_conn.fetchval.return_value = None
    r = client.get("/model-risk/999999")
    assert r.status_code == 404
