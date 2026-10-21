"""
Unit tests for the PAT-380 Close field mapping helper and the Sanity stub.

These are pure and hermetic: no network, no database. They verify that Close
field ids come from CLOSE.yaml (never hard-coded) and that the Sanity stub is
deterministic and correctly reports approval state.
"""
import pytest

from backend.services import close_service, sanity_service


def test_company_custom_field_payload_uses_yaml_field_ids():
    field_map = close_service._load_close_config()["company_field_map"]

    payload = close_service.build_company_custom_field_payload(
        experiment={"name": "Exp1"},
        product={"device": "Dev", "competitors": "A, B", "superiority": None},
        org={"estimated_annual_sales": 100, "size": 5, "arm": 2},
    )

    assert payload[field_map["experiment.name"]["field_id"]] == "Exp1"
    assert payload[field_map["products.device"]["field_id"]] == "Dev"
    assert payload[field_map["products.competitors"]["field_id"]] == "A, B"
    assert payload[field_map["orgs.arm"]["field_id"]] == 2
    # None / blank values are skipped.
    assert field_map["products.superiority"]["field_id"] not in payload


def test_company_custom_field_payload_serializes_datetimes():
    import datetime

    field_map = close_service._load_close_config()["company_field_map"]
    payload = close_service.build_company_custom_field_payload(
        product={"date_of_final_decision": datetime.datetime(2026, 6, 30, 0, 0, 0)},
    )
    assert payload[field_map["products.date_of_final_decision"]["field_id"]] == "2026-06-30T00:00:00"


def test_company_custom_field_payload_serializes_decimals():
    import decimal
    import json

    field_map = close_service._load_close_config()["company_field_map"]
    payload = close_service.build_company_custom_field_payload(
        org={
            "estimated_annual_sales": decimal.Decimal("1000000"),
            "size": decimal.Decimal("5000000"),
        }
    )
    assert payload[field_map["orgs.estimated_annual_sales"]["field_id"]] == 1000000
    assert payload[field_map["orgs.size"]["field_id"]] == 5000000
    json.dumps(payload)  # must not raise: the payload is sent as JSON to Close


def test_find_contact_in_lead_matches_email_then_name():
    contacts = [
        {"id": "c1", "name": "Mary", "emails": [{"email": "mary@contentbegin.org"}]},
        {"id": "c2", "name": "James Moon", "emails": [{"email": "ceo@mycardium.com"}]},
    ]
    # Email match wins.
    assert close_service._find_contact_in_lead(contacts, "ceo@mycardium.com", "James Moon")["id"] == "c2"
    # Falls back to name when there is no email.
    assert close_service._find_contact_in_lead(contacts, "", "Mary")["id"] == "c1"
    # No match returns None (so a new contact is created on the correct lead).
    assert close_service._find_contact_in_lead(contacts, "nope@example.com", "Nobody") is None


def test_experiment_smart_view_query_uses_yaml_field_id():
    field_map = close_service._load_close_config()["company_field_map"]
    query = close_service.build_experiment_smart_view_query("Exp1")
    assert field_map["experiment.name"]["field_id"] in query
    assert "Exp1" in query


def test_close_config_base_url_from_yaml():
    api = close_service._load_close_config()["api"]
    assert api["base_url"].startswith("https://")
    assert api["api_key_env"] == "CLOSE_API_KEY"


def test_sanity_stub_is_deterministic_and_approved():
    brief = sanity_service.get_brief("content-1")
    assert brief["_id"] == "content-1"
    assert brief["_rev"].startswith("stub-")
    assert sanity_service.is_approved(brief) is True
    assert sanity_service.get_brief("content-1") == brief


def test_sanity_stub_draft_is_not_approved():
    brief = sanity_service.get_brief("draft-1")
    assert brief["status"] == "draft"
    assert sanity_service.is_approved(brief) is False


def test_sanity_stub_none_content_id():
    assert sanity_service.get_brief(None) is None
    assert sanity_service.is_approved(None) is False


def test_find_or_create_company_updates_existing_lead(monkeypatch):
    import asyncio

    calls = []

    async def fake_request(method, path, *, json=None, params=None):
        calls.append((method, path, json))
        if method == "GET":
            return {"data": [{"id": "lead_1", "name": "Acme"}]}
        return {}

    monkeypatch.setattr(close_service, "_request", fake_request)
    lead_id = asyncio.run(close_service.find_or_create_company("Acme", {"cf_x": "y"}))

    assert lead_id == "lead_1"
    # Existing lead is refreshed (PUT) instead of only being read.
    assert any(
        method == "PUT" and path == "/lead/lead_1/" and body and body.get("custom") == {"cf_x": "y"}
        for method, path, body in calls
    )
    assert not any(method == "POST" for method, _path, _body in calls)


def test_find_or_create_company_creates_when_absent(monkeypatch):
    import asyncio

    calls = []

    async def fake_request(method, path, *, json=None, params=None):
        calls.append((method, path, json))
        if method == "GET":
            return {"data": []}
        if method == "POST":
            return {"id": "lead_new"}
        return {}

    monkeypatch.setattr(close_service, "_request", fake_request)
    lead_id = asyncio.run(close_service.find_or_create_company("Acme", {"cf_x": "y"}))

    assert lead_id == "lead_new"
    assert any(method == "POST" for method, _path, _body in calls)


def test_sle_after_mitigation_is_mapped_not_unmapped():
    """products.sle_after_mitigation is sent, not left in unmapped_fields."""
    config = close_service._load_close_config()
    assert "products.sle_after_mitigation" in config["company_field_map"]
    assert "products.sle_after_mitigation" not in (config.get("unmapped_fields") or {})


def test_company_custom_field_payload_sends_sle_after_mitigation():
    import decimal

    field_map = close_service._load_close_config()["company_field_map"]
    payload = close_service.build_company_custom_field_payload(
        product={"device": "Dev", "sle_after_mitigation": decimal.Decimal("1500000")},
    )
    # The SLE field is declared `format: currency_compact` in CLOSE.yaml, so the
    # NUMERIC column arrives at Close as an abbreviated dollar string.
    assert payload[field_map["products.sle_after_mitigation"]["field_id"]] == "$1.5M"


@pytest.mark.parametrize(
    "raw, expected",
    [
        (0, "$0"),
        (410, "$410"),
        (410000, "$410K"),
        (1000000, "$1M"),
        (4100000, "$4.1M"),
        (485925000, "$485.9M"),
        (5037422500, "$5,037.4M"),
        (-410000, "-$410K"),
    ],
)
def test_format_compact_currency(raw, expected):
    assert close_service._format_compact_currency(raw) == expected


def test_currency_compact_format_is_declared_in_yaml():
    """The formatter is wired to the SLE field from config, not by column name."""
    field_map = close_service._load_close_config()["company_field_map"]
    assert field_map["products.sle_after_mitigation"]["format"] == "currency_compact"
