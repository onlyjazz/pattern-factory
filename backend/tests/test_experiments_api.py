"""
Hermetic tests for the PAT-380 experiments CRUD, activation and runs endpoints.

No database, OpenAI, or network access: the pool is the in-memory fake from
conftest.py and the Close/Sanity service calls are patched with AsyncMocks.
"""
import pytest


EXP_ROW = {
    "id": 1,
    "name": "Exp",
    "description": None,
    "hypothesis": "Stories beat abstract risk talk",
    "target": "AI-guided surgery and imaging startups",
    "arm": "social",
    "email_header": None,
    "email_header_status": "draft",
    "created_at": "2026-06-30T00:00:00",
    "updated_at": "2026-06-30T00:00:00",
}


@pytest.fixture
def patched_services(monkeypatch):
    """Patch Close + Sanity seams so activation never touches the network."""
    import backend.services.close_service as close_service
    import backend.services.sanity_service as sanity_service

    async def fake_find_or_create_company(name, custom_fields=None):
        return "lead_123"

    async def fake_create_contact(company_id, person, custom_fields=None):
        return f"contact_{person.get('id')}"

    async def fake_create_smart_view(name, query):
        return "sv_1"

    monkeypatch.setattr(close_service, "find_or_create_company", fake_find_or_create_company)
    monkeypatch.setattr(close_service, "create_contact", fake_create_contact)
    monkeypatch.setattr(close_service, "create_smart_view", fake_create_smart_view)
    monkeypatch.setattr(
        close_service, "build_company_custom_field_payload", lambda *a, **k: {"cf_x": "y"}
    )
    monkeypatch.setattr(
        close_service, "build_experiment_smart_view_query", lambda name: f'custom.cf_x:"{name}"'
    )
    monkeypatch.setattr(
        sanity_service,
        "get_brief",
        lambda content_id: {"_rev": "r1", "status": "approved", "approved": True},
    )
    monkeypatch.setattr(
        sanity_service, "is_approved", lambda brief: bool(brief and brief.get("approved"))
    )
    return close_service, sanity_service


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------
def test_list_experiments_nested(client, mock_pool, fake_conn):
    fake_conn.fetch.side_effect = [
        [EXP_ROW],
        [{"experiment_id": 1, "position": 1, "channel": "email", "content_id": "c1", "content_rev": "r1"}],
        [{"experiment_id": 1, "product_id": 5}],
    ]
    r = client.get("/experiments")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body[0]["id"] == 1
    assert body[0]["steps"] == [
        {"position": 1, "channel": "email", "content_id": "c1", "content_rev": "r1"}
    ]
    assert body[0]["product_ids"] == [5]
    assert body[0]["hypothesis"] == EXP_ROW["hypothesis"]
    assert body[0]["target"] == EXP_ROW["target"]


def test_get_experiment_returns_nested(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = EXP_ROW
    fake_conn.fetch.side_effect = [
        [{"experiment_id": 1, "position": 1, "channel": "buffer", "content_id": "c1", "content_rev": None}],
        [{"experiment_id": 1, "product_id": 7}],
    ]
    r = client.get("/experiments/1")
    assert r.status_code == 200, r.text
    assert r.json()["product_ids"] == [7]
    assert r.json()["hypothesis"] == EXP_ROW["hypothesis"]
    assert r.json()["target"] == EXP_ROW["target"]


def test_get_experiment_missing_returns_404(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = None
    r = client.get("/experiments/999")
    assert r.status_code == 404


def test_create_experiment_returns_nested(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = [{"id": 5}]  # product exists
    fake_conn.fetchrow.return_value = EXP_ROW
    r = client.post(
        "/experiments",
        json={
            "name": "Exp",
            "hypothesis": "Stories beat abstract risk talk",
            "target": "AI-guided surgery and imaging startups",
            "arm": "social",
            "steps": [{"position": 1, "channel": "email", "content_id": "c1"}],
            "product_ids": [5],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == 1
    assert body["product_ids"] == [5]
    assert body["steps"][0]["position"] == 1

    # The new fields reach the INSERT, in column order after name/description.
    insert = fake_conn.fetchrow.call_args_list[0]
    assert "hypothesis, target" in str(insert.args[0])
    assert insert.args[3] == "Stories beat abstract risk talk"
    assert insert.args[4] == "AI-guided surgery and imaging startups"


def test_create_experiment_missing_product_returns_400(client, mock_pool, fake_conn):
    fake_conn.fetch.return_value = []  # none of the requested products exist
    r = client.post(
        "/experiments",
        json={"name": "Exp", "arm": "social", "product_ids": [999]},
    )
    assert r.status_code == 400
    assert "999" in r.json()["detail"]


def test_create_experiment_invalid_arm_returns_422(client):
    r = client.post("/experiments", json={"name": "Exp", "arm": "bogus"})
    assert r.status_code == 422


def test_update_experiment_replaces_children(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {**EXP_ROW, "name": "Exp2"}
    fake_conn.fetch.side_effect = [
        [{"id": 5}],  # product validation
        [{"experiment_id": 1, "position": 1, "channel": "email", "content_id": "c1", "content_rev": "r1"}],
        [{"experiment_id": 1, "product_id": 5}],
    ]
    r = client.put(
        "/experiments/1",
        json={
            "name": "Exp2",
            "hypothesis": "Sharper hook",
            "target": "Imaging startups",
            "steps": [{"position": 1, "channel": "email", "content_id": "c1"}],
            "product_ids": [5],
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Exp2"
    assert r.json()["product_ids"] == [5]

    # The new fields are in the UPDATE's SET list and its parameter list.
    update = fake_conn.fetchrow.call_args_list[0]
    assert "hypothesis = COALESCE($3, hypothesis)" in str(update.args[0])
    assert "target = COALESCE($4, target)" in str(update.args[0])
    assert update.args[3] == "Sharper hook"
    assert update.args[4] == "Imaging startups"


def test_update_experiment_missing_returns_404(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = None
    r = client.put("/experiments/999", json={"name": "Exp2"})
    assert r.status_code == 404


def test_delete_experiment_soft_deletes(client, mock_pool, fake_conn):
    fake_conn.execute.return_value = "UPDATE 1"
    r = client.delete("/experiments/1")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "deleted_id": 1}


def test_delete_experiment_missing_returns_404(client, mock_pool, fake_conn):
    fake_conn.execute.return_value = "UPDATE 0"
    r = client.delete("/experiments/999")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Activation
# ---------------------------------------------------------------------------
def test_start_experiment_success(client, mock_pool, fake_conn, patched_services):
    fake_conn.fetchrow.side_effect = [
        {"id": 1, "name": "Exp", "arm": "social"},  # experiment
        {
            "id": 5, "device": "d", "competitors": "A", "superiority": None,
            "intended_use": None, "date_of_final_decision": None, "org_id": 9,
            "org_name": "Acme", "estimated_annual_sales": None, "size": None, "arm": 2,
        },  # product + org
        {"id": 77},  # model
        {"id": 300},  # experiment_run
    ]
    fake_conn.fetch.side_effect = [
        [{"position": 1, "channel": "email", "content_id": "c1", "content_rev": None}],  # steps
        [{"id": 5}],  # existing products
        [{"id": 11, "name": "Jane", "email": "j@x.com", "linkedin_url": None, "job_description": None}],
    ]
    r = client.post("/experiments/1/start", json={"product_ids": [5]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] == 1
    assert body["failed"] == 0
    assert body["companies"] == 1
    assert body["contacts"] == 1
    assert body["smart_view_id"] == "sv_1"
    result = body["results"][0]
    assert result["run_id"] == 300
    assert result["model_id"] == 77
    assert result["steps_pinned"] == 1
    assert result["targets"] == 1

    # Close send tracking stamped on product / org / people.
    sqls = [str(call.args[0]) for call in fake_conn.execute.call_args_list]
    assert any("close_sent = true" in sql for sql in sqls)
    assert any("close_mail_sent = true" in sql for sql in sqls)


def _product_and_org_row():
    """The product/org row _activate_product loads for a product of org 9."""
    return {
        "id": 5, "device": "d", "competitors": None, "superiority": None,
        "intended_use": None, "date_of_final_decision": None, "org_id": 9,
        "org_name": "Acme", "estimated_annual_sales": None, "size": None, "arm": 2,
    }


def _activation_fetch_rows():
    """The step, existing-product and people rows a single-product run loads."""
    return [
        [{"position": 1, "channel": "email", "content_id": "c1", "content_rev": None}],
        [{"id": 5}],
        [{"id": 11, "name": "Jane", "email": "j@x.com", "linkedin_url": None, "job_description": None}],
    ]


def test_start_experiment_persists_the_smart_view_on_first_run(
    client, mock_pool, fake_conn, patched_services
):
    """The first activation records the view it created, so later runs can reuse it."""
    fake_conn.fetchrow.side_effect = [
        {"id": 1, "name": "Exp", "arm": "social"},  # no close_smart_view_id yet
        _product_and_org_row(),
        {"id": 77},   # model
        {"id": 300},  # experiment_run
    ]
    fake_conn.fetch.side_effect = _activation_fetch_rows()

    r = client.post("/experiments/1/start", json={"product_ids": [5]})
    assert r.status_code == 200, r.text
    assert r.json()["smart_view_id"] == "sv_1"

    persisted = [
        call.args for call in fake_conn.execute.call_args_list
        if "SET close_smart_view_id" in str(call.args[0])
    ]
    assert len(persisted) == 1, "the created view id must be written back once"
    assert persisted[0][1] == "sv_1"


def test_start_experiment_reuses_the_smart_view_on_rerun(
    client, mock_pool, fake_conn, patched_services, monkeypatch
):
    """Re-running an experiment must not create a second Close smart view.

    Regression: every activation used to POST a new saved search, so running the
    same experiment repeatedly piled up duplicate views in Close.
    """
    close_service, _ = patched_services
    created = []

    async def fake_create_smart_view(name, query):
        created.append(name)
        return "sv_new"

    monkeypatch.setattr(close_service, "create_smart_view", fake_create_smart_view)

    fake_conn.fetchrow.side_effect = [
        {"id": 1, "name": "Exp", "arm": "social", "close_smart_view_id": "sv_existing"},
        _product_and_org_row(),
        {"id": 77},
        {"id": 300},
    ]
    fake_conn.fetch.side_effect = _activation_fetch_rows()

    r = client.post("/experiments/1/start", json={"product_ids": [5]})
    assert r.status_code == 200, r.text
    assert r.json()["smart_view_id"] == "sv_existing"
    assert created == [], "a re-run must not reach Close to create another view"

    sqls = [str(call.args[0]) for call in fake_conn.execute.call_args_list]
    assert not any("SET close_smart_view_id" in sql for sql in sqls)


def test_start_experiment_dedupes_close_work_per_org(
    client, mock_pool, fake_conn, patched_services
):
    """Several products of one org must yield one company and one contact set.

    Regression for the per-product fan-out: two products of org 9 used to create
    two targets (and two pending sends) for the same person and report
    two companies / two contacts.
    """
    product = {
        "device": "d", "competitors": None, "superiority": None,
        "intended_use": None, "date_of_final_decision": None, "org_id": 9,
        "org_name": "Acme", "estimated_annual_sales": None, "size": None, "arm": 2,
    }
    fake_conn.fetchrow.side_effect = [
        {"id": 1, "name": "Exp", "arm": "social"},  # experiment
        {**product, "id": 5},  # product 5 of org 9
        {"id": 77},  # model for product 5
        {"id": 300},  # run for product 5
        {**product, "id": 6},  # product 6 of the same org
        {"id": 78},  # model for product 6
        {"id": 301},  # run for product 6
    ]
    fake_conn.fetch.side_effect = [
        [{"position": 1, "channel": "email", "content_id": "c1", "content_rev": None}],
        [{"id": 5}, {"id": 6}],  # existing products
        # People are loaded once, for the org's first product only.
        [{"id": 11, "name": "Jane", "email": "j@x.com", "linkedin_url": None, "job_description": None}],
    ]

    r = client.post("/experiments/1/start", json={"product_ids": [5, 6]})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["success"] == 2
    assert body["companies"] == 1
    assert body["contacts"] == 1

    first, second = body["results"]
    assert first["company_id"] == "lead_123"
    assert first["targets"] == 1
    assert second["company_id"] is None
    assert second["targets"] == 0

    sqls = [str(call.args[0]) for call in fake_conn.execute.call_args_list]
    # The org's Close work happens once...
    assert sum("INSERT INTO public.experiment_run_target" in sql for sql in sqls) == 1
    assert sum("UPDATE public.orgs SET close_sent" in sql for sql in sqls) == 1
    assert sum("UPDATE public.people SET close_mail_sent" in sql for sql in sqls) == 1
    # ...while every product still gets its own run, stamp and send seeding.
    run_sqls = [str(call.args[0]) for call in fake_conn.fetchrow.call_args_list]
    assert sum("INSERT INTO public.experiment_run " in sql for sql in run_sqls) == 2
    assert sum("UPDATE public.products SET close_sent" in sql for sql in sqls) == 2
    assert sum("INSERT INTO public.experiment_run_send" in sql for sql in sqls) == 2


def test_start_experiment_refuses_unapproved_step(
    client, mock_pool, fake_conn, patched_services, monkeypatch
):
    _, sanity_service = patched_services
    monkeypatch.setattr(sanity_service, "is_approved", lambda brief: False)

    fake_conn.fetchrow.side_effect = [
        {"id": 1, "name": "Exp", "arm": "social"},
        {
            "id": 5, "device": "d", "competitors": None, "superiority": None,
            "intended_use": None, "date_of_final_decision": None, "org_id": 9,
            "org_name": "Acme", "estimated_annual_sales": None, "size": None, "arm": None,
        },
        {"id": 77},
        {"id": 300},
    ]
    fake_conn.fetch.side_effect = [
        [{"position": 1, "channel": "email", "content_id": "draft-c1", "content_rev": None}],
        [{"id": 5}],
        [],
    ]
    r = client.post("/experiments/1/start", json={"product_ids": [5]})
    assert r.status_code == 200, r.text
    result = r.json()["results"][0]
    assert result["steps_pinned"] == 0
    assert result["steps_refused"] == 1
    assert result["status"] == "success"


def test_start_experiment_missing_experiment_returns_404(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = None
    r = client.post("/experiments/999/start", json={"product_ids": [5]})
    assert r.status_code == 404


def test_start_experiment_empty_products_returns_400(client):
    r = client.post("/experiments/1/start", json={"product_ids": []})
    assert r.status_code == 400
    assert r.json()["detail"] == "product_ids must not be empty"


def test_start_experiment_no_steps_returns_400(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Exp", "arm": "social"}
    fake_conn.fetch.return_value = []  # no steps
    r = client.post("/experiments/1/start", json={"product_ids": [5]})
    assert r.status_code == 400


def test_start_experiment_missing_product_returns_400(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1, "name": "Exp", "arm": "social"}
    fake_conn.fetch.side_effect = [
        [{"position": 1, "channel": "email", "content_id": "c1", "content_rev": None}],
        [],  # requested product does not exist
    ]
    r = client.post("/experiments/1/start", json={"product_ids": [999]})
    assert r.status_code == 400
    assert "999" in r.json()["detail"]


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------
def test_get_experiment_runs_nested(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = {"id": 1}
    fake_conn.fetch.side_effect = [
        [{
            "id": 300, "experiment_id": 1, "product_id": 5, "model_id": 77,
            "email_header_sent": False, "created_at": "2026-06-30T00:00:00",
        }],
        [{"run_id": 300, "position": 1, "content_id": "c1", "content_rev": "r1"}],
        [{"id": 900, "run_id": 300, "person_id": 11, "company_id": "lead_1", "contact_id": "con_1"}],
        [{"target_id": 900, "position": 1, "state": "pending", "external_id": None,
          "handed_off_at": None, "sent_at": None}],
    ]
    r = client.get("/experiments/1/runs")
    assert r.status_code == 200, r.text
    run = r.json()[0]
    assert run["id"] == 300
    assert run["model_id"] == 77
    assert run["steps"] == [{"position": 1, "content_id": "c1", "content_rev": "r1"}]
    assert run["targets"][0]["contact_id"] == "con_1"
    assert run["targets"][0]["sends"][0]["state"] == "pending"


def test_get_experiment_runs_missing_returns_404(client, mock_pool, fake_conn):
    fake_conn.fetchrow.return_value = None
    r = client.get("/experiments/999/runs")
    assert r.status_code == 404
