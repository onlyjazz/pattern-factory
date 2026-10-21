"""
Close CRM integration service (PAT-380: Send to Close).

Thin async client over the Close CRM REST API (httpx). Configuration is loaded
at runtime from ``prompts/rules/CLOSE.yaml`` using the same loader pattern as
the SEARCH.yaml loader in ``backend/pitboss/competitors.py``:

* The API ``base_url``, ``api_key_env`` and timeout come from CLOSE.yaml, so no
  endpoint/base URL is hard-coded here.
* Close custom-field ids are read from ``CLOSE.company_field_map`` and are never
  hard-coded in Python.

The API key (``CLOSE_API_KEY``) is read from the environment at call time and is
never logged.
"""

from __future__ import annotations

import logging
import os
from decimal import Decimal
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Close REST resource paths.
#
# These are the Close API surface (resource paths), not configuration. The API
# base URL, key env var, timeout and custom-field ids all come from CLOSE.yaml.
# ---------------------------------------------------------------------------
_LEAD_PATH = "/lead/"
_CONTACT_PATH = "/contact/"
_SAVED_SEARCH_PATH = "/saved_search/"

# Cache for the parsed CLOSE.yaml config.
_CLOSE_CONFIG_CACHE: Optional[Dict[str, Any]] = None


class CloseConfigError(RuntimeError):
    """Raised when CLOSE.yaml is missing required configuration or the API key is unset."""


class CloseAPIError(RuntimeError):
    """Raised when Close returns an HTTP error or a non-JSON response."""


def _load_close_config() -> Dict[str, Any]:
    """Load and cache the CLOSE section from prompts/rules/CLOSE.yaml.

    Mirrors ``_load_search_config`` in ``backend/pitboss/competitors.py``.
    """
    global _CLOSE_CONFIG_CACHE
    if _CLOSE_CONFIG_CACHE is not None:
        return _CLOSE_CONFIG_CACHE
    try:
        import yaml

        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "rules", "CLOSE.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        _CLOSE_CONFIG_CACHE = (yaml_data.get("CLOSE") or {}) if isinstance(yaml_data, dict) else {}
        logger.info("  ✓ Loaded CLOSE.yaml config")
    except Exception as e:  # pragma: no cover - defensive, config is in-repo
        logger.warning(f"  Could not load CLOSE.yaml: {e}")
        _CLOSE_CONFIG_CACHE = {}
    return _CLOSE_CONFIG_CACHE


def _api_config() -> Dict[str, Any]:
    """Return the ``CLOSE.api`` config block, validating ``base_url``."""
    api = _load_close_config().get("api") or {}
    base_url = (api.get("base_url") or "").strip()
    if not base_url:
        raise CloseConfigError("CLOSE.yaml is missing CLOSE.api.base_url")
    return api


def _api_key() -> str:
    """Read the Close API key from the environment variable named in CLOSE.yaml."""
    env_name = (_api_config().get("api_key_env") or "CLOSE_API_KEY").strip()
    key = os.getenv(env_name)
    if not key:
        raise CloseConfigError(f"{env_name} environment variable is not set")
    return key


def _escape(value: str) -> str:
    """Escape double quotes for a Close search query literal."""
    return str(value).replace('"', '\\"')


def _first_result(payload: Any) -> Optional[Dict[str, Any]]:
    """Return the first element of a Close list response, if any."""
    if not isinstance(payload, dict):
        return None
    data = payload.get("data")
    if isinstance(data, list) and data:
        first = data[0]
        return first if isinstance(first, dict) else None
    return None


async def _request(
    method: str,
    path: str,
    *,
    json: Optional[Dict[str, Any]] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Issue a Close API request, raising clear exceptions on failure.

    The Authorization header (which contains the API key) is never included in
    log messages or exception text.
    """
    api = _api_config()
    base_url = api["base_url"].rstrip("/")
    timeout = float(api.get("timeout_seconds", 30) or 30)
    url = f"{base_url}{path}"
    # Close authenticates with HTTP Basic auth: the API key is the username and
    # the password is empty (curl equivalent: -u "$CLOSE_API_KEY:"). A Bearer
    # token returns HTTP 401.
    auth = httpx.BasicAuth(_api_key(), "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method, url, json=json, params=params, headers=headers, auth=auth
            )
    except httpx.HTTPError as e:
        raise CloseAPIError(f"Close API {method} {path} request failed: {e}") from e

    if response.status_code >= 400:
        # Body may help debugging; it never contains our Authorization header.
        raise CloseAPIError(
            f"Close API {method} {path} returned HTTP {response.status_code}: {response.text[:500]}"
        )
    try:
        return response.json()
    except ValueError as e:
        raise CloseAPIError(f"Close API {method} {path} returned a non-JSON response") from e


# ---------------------------------------------------------------------------
# Custom-field payload helpers (field ids and formats come from CLOSE.yaml)
# ---------------------------------------------------------------------------
def _format_compact_currency(value: Any) -> str:
    """Render a dollar amount the way the Close SLE field expects.

    The amount is read in thousands and abbreviated: below 1,000 dollars it is a
    plain dollar figure, below 1,000,000 it is $410K, above that $4.1M. One
    decimal is kept and a trailing .0 dropped, so 410000 -> "$410K" and
    4100000 -> "$4.1M". The thousands inside an M figure keep their separators
    (5037422500 -> "$5,037.4M").
    """
    amount = float(value)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)

    if amount < 1000:
        return f"{sign}${amount:,.0f}"

    thousands = amount / 1000.0
    if thousands < 1000:
        scaled, suffix = thousands, "K"
    else:
        scaled, suffix = thousands / 1000.0, "M"

    text = f"{scaled:,.1f}"
    if text.endswith(".0"):
        text = text[:-2]
    return f"{sign}${text}{suffix}"


# CLOSE.yaml `format` name -> formatter. Unknown names are ignored, so a field
# with a typo'd format is sent as-is rather than dropped.
_FIELD_FORMATTERS = {
    "currency_compact": _format_compact_currency,
}


def build_company_custom_field_payload(
    experiment: Optional[Dict[str, Any]] = None,
    product: Optional[Dict[str, Any]] = None,
    org: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a Close lead ``custom`` payload from ``CLOSE.company_field_map``.

    Each map key is a Pattern Factory ``table.column`` (e.g. ``products.device``).
    The matching value is read from ``experiment`` / ``product`` / ``org`` and
    keyed by the Close ``field_id`` from CLOSE.yaml. Empty/None values are
    skipped, and datetime values are serialized to ISO-8601 strings.
    """
    field_map = _load_close_config().get("company_field_map") or {}
    sources = {
        "experiment": experiment or {},
        "products": product or {},
        "orgs": org or {},
    }
    payload: Dict[str, Any] = {}
    for key, spec in field_map.items():
        if not isinstance(spec, dict):
            continue
        field_id = spec.get("field_id")
        if not field_id:
            continue
        try:
            table, column = str(key).split(".", 1)
        except ValueError:
            continue
        value = sources.get(table, {}).get(column)
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        # A declared format wins: it renders the raw value into the string the
        # Close field expects. A value that cannot be rendered is skipped rather
        # than sent half-converted.
        formatter = _FIELD_FORMATTERS.get(str(spec.get("format") or "").strip().lower())
        if formatter is not None:
            try:
                value = formatter(value)
            except (TypeError, ValueError) as e:
                logger.warning(f"  Could not format {key} for Close: {e}")
                continue
        # asyncpg returns NUMERIC columns as Decimal, which is not JSON
        # serializable; coerce to int/float for the Close payload.
        elif isinstance(value, Decimal):
            value = int(value) if value == value.to_integral_value() else float(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        payload[field_id] = value
    return payload


def build_experiment_smart_view_query(experiment_name: str) -> str:
    """Build a Close saved-search query scoped to the experiment custom field.

    Uses the ``experiment.name`` field id from CLOSE.yaml so the smart view
    surfaces exactly the companies created for this experiment.
    """
    field_map = _load_close_config().get("company_field_map") or {}
    spec = field_map.get("experiment.name") or {}
    field_id = spec.get("field_id") if isinstance(spec, dict) else None
    escaped = _escape(experiment_name or "")
    if field_id:
        return f'custom.{field_id}:"{escaped}"'
    return f'"{escaped}"'


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def find_or_create_company(
    name: str,
    custom_fields: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Return the Close lead (company) id for ``name``, creating it if absent.

    Searches Close first to avoid creating duplicate leads; only when no lead
    matches does it create one via ``POST /lead/``. Returns the Close lead id.
    """
    if not name or not str(name).strip():
        raise CloseConfigError("A company name is required to find or create a Close lead")

    query = f'name:"{_escape(name)}"'
    found = _first_result(await _request("GET", _LEAD_PATH, params={"query": query}))
    if found is not None:
        lead_id = found.get("id")
        # Refresh the existing lead's custom fields so a rerun reflects the
        # latest product/org data instead of the values from first creation.
        if lead_id and custom_fields:
            await _request(
                "PUT",
                f"{_LEAD_PATH}{lead_id}/",
                json={"name": name, "custom": custom_fields},
            )
        return lead_id

    payload: Dict[str, Any] = {"name": name}
    if custom_fields:
        payload["custom"] = custom_fields
    created = await _request("POST", _LEAD_PATH, json=payload)
    if not isinstance(created, dict) or not created.get("id"):
        raise CloseAPIError("Close did not return a lead id when creating a company")
    return created.get("id")


async def _list_lead_contacts(company_id: str) -> list[Dict[str, Any]]:
    """List the contacts that belong to a Close lead (company).

    Close's ``/contact/`` endpoint ignores a ``query`` filter (it returns every
    contact in the org), so contacts are filtered by ``lead_id`` server-side and
    matched by email/name in Python.
    """
    payload = await _request(
        "GET",
        _CONTACT_PATH,
        params={"lead_id": company_id, "_fields": "id,name,emails", "_limit": 100},
    )
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    return [c for c in data if isinstance(c, dict)]


def _find_contact_in_lead(
    contacts: list[Dict[str, Any]], email: str, name: str
) -> Optional[Dict[str, Any]]:
    """Return the first lead contact matching ``email`` (preferred) or ``name``."""
    email_l = (email or "").strip().lower()
    if email_l:
        for contact in contacts:
            for entry in contact.get("emails") or []:
                if isinstance(entry, dict) and (entry.get("email") or "").strip().lower() == email_l:
                    return contact
    name_l = (name or "").strip().lower()
    if name_l:
        for contact in contacts:
            if (contact.get("name") or "").strip().lower() == name_l:
                return contact
    return None


async def create_contact(
    company_id: str,
    person: Dict[str, Any],
    custom_fields: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """Return the Close contact id for ``person``, linked to ``company_id``.

    Dedupes only against contacts already on the same lead (company), matched by
    email when available and otherwise by name, before creating the contact with
    ``POST /contact/``. This keeps a person from being attached to an unrelated
    lead's contact.
    """
    if not company_id:
        raise CloseConfigError("A Close company id is required to create a contact")

    person = person or {}
    name = (person.get("name") or "").strip()
    email = (person.get("email") or "").strip()

    existing = _find_contact_in_lead(await _list_lead_contacts(company_id), email, name)
    if existing is not None:
        return existing.get("id")

    payload: Dict[str, Any] = {"lead_id": company_id}
    if name:
        payload["name"] = name
    if email:
        payload["emails"] = [{"email": email, "type": "office"}]
    title = (person.get("job_description") or "").strip()
    if title:
        payload["title"] = title
    if custom_fields:
        payload["custom"] = custom_fields

    created = await _request("POST", _CONTACT_PATH, json=payload)
    if not isinstance(created, dict) or not created.get("id"):
        raise CloseAPIError("Close did not return a contact id when creating a contact")
    return created.get("id")


async def create_smart_view(name: str, query: str) -> Optional[str]:
    """Create a Close smart view (saved search) for an experiment, return its id."""
    if not name or not str(name).strip():
        raise CloseConfigError("A name is required to create a Close smart view")
    payload = {"name": name, "type": "lead", "query": query}
    created = await _request("POST", _SAVED_SEARCH_PATH, json=payload)
    if not isinstance(created, dict) or not created.get("id"):
        raise CloseAPIError("Close did not return a smart view id when creating a saved search")
    return created.get("id")
