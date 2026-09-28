"""
Organization Status Agent Flow (ORG_STATUS Workflow)

Resolves the lifecycle status of an organization using the Exa agent API
(structured web research) and persists it to public.orgs.status_id.

Flow (invoked directly, not via model.LanguageCapo / the supervisor):
  model.validateOrgId   → model.resolveOrgStatus   → tool.updateOrgStatus

Statuses map to public.statuses: active, closed, acquired, duplicate, renamed.

Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)

The `run_org_status_flow` helper orchestrates the three steps for a single
org and is shared by the batch CLI (scripts/batch_orgs_update_status.py) and
the API endpoint (POST /orgs/update-status).
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import asyncpg

from .logging_util import log_event

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

logger = logging.getLogger(__name__)

# Statuses the resolver is allowed to return (mirrors public.statuses values).
VALID_STATUSES = ["active", "closed", "acquired", "duplicate", "renamed"]

# Exa agent polling budget (milliseconds). 120s matches the competitors flow.
EXA_AGENT_TIMEOUT_MS = 120000

# Resolver confidence at or below which (or an Exa timeout) we treat the result
# as a signal that the company no longer exists, and mark it closed.
EXA_LOW_CONFIDENCE = 0.10

# Structured output contract for the Exa agent. Every key is required so the
# agent always returns a fully-populated object; empty string means "n/a".
EXA_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": VALID_STATUSES + ["unknown"]},
        "confidence": {"type": "number"},
        "reason": {"type": "string"},
        "current_name": {"type": "string"},
        "acquirer": {"type": "string"},
        "duplicate_of": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "status",
        "confidence",
        "reason",
        "current_name",
        "acquirer",
        "duplicate_of",
        "sources",
    ],
    "additionalProperties": False,
}

_DEFAULT_AGENT_QUERY = (
    "Investigate the current operating status of the company \"{name}\". "
    "Context: {description}. Headquarters: {headquarters}. "
    "Determine whether the company is: active (still operating independently), "
    "closed (ceased operations / shut down / dissolved / bankrupt with no successor), "
    "acquired (acquired by or merged into another company), "
    "renamed (still operating but now under a different legal or brand name), or "
    "duplicate (this record appears to duplicate another company already tracked). "
    "Return a structured JSON object."
)

# mtime-cached SEARCH.yaml config (hot-reload without restart).
_ORG_STATUS_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_ORG_STATUS_CONFIG_MTIME: Optional[float] = None

# Cache of status name -> status_id loaded from public.statuses.
_STATUS_ID_CACHE: Dict[str, int] = {}


def _search_yaml_path() -> str:
    """Absolute path to prompts/rules/SEARCH.yaml, resolved from this file."""
    return os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "prompts",
            "rules",
            "SEARCH.yaml",
        )
    )


def _load_org_status_config() -> Dict[str, Any]:
    """
    Load the ORG_STATUS section from prompts/rules/SEARCH.yaml, refreshing
    whenever the file's mtime changes so prompt edits take effect without a
    process restart. Falls back to inline defaults when the file/key is absent.
    """
    global _ORG_STATUS_CONFIG_CACHE, _ORG_STATUS_CONFIG_MTIME

    yaml_path = _search_yaml_path()
    try:
        mtime = os.path.getmtime(yaml_path)
    except OSError:
        mtime = None

    if mtime is not None and mtime == _ORG_STATUS_CONFIG_MTIME:
        return _ORG_STATUS_CONFIG_CACHE or {}

    config: Dict[str, Any] = {}
    try:
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
        search_section = yaml_data.get("SEARCH") or {}
        config = search_section.get("org_status") or {}
    except Exception as e:
        logger.warning(f"  Could not load SEARCH.yaml org_status config, using defaults: {e}")
        config = {}

    _ORG_STATUS_CONFIG_CACHE = config
    _ORG_STATUS_CONFIG_MTIME = mtime
    return config


def _build_agent_query(org: Dict[str, Any]) -> str:
    """Format the Exa agent research query for one organization."""
    template = _load_org_status_config().get("agent_query") or _DEFAULT_AGENT_QUERY
    description = (org.get("description") or "no description on file").strip()
    headquarters = (org.get("headquarters") or "unknown").strip()
    return template.format(
        name=(org.get("name") or "").strip(),
        description=description,
        headquarters=headquarters,
    )


def _looks_like_timeout(exc: BaseException) -> bool:
    """Heuristically detect an Exa polling timeout (the 2-minute poll budget)."""
    text = f"{type(exc).__name__}: {exc}".lower()
    return "timeout" in text or "timed out" in text


def _inferred_closed_resolution(reason: str) -> Dict[str, Any]:
    """Build a resolution that marks the org closed because of an Exa failure."""
    return {
        "status": "closed",
        "confidence": EXA_LOW_CONFIDENCE,
        "reason": f"Inferred closed: {reason}",
        "current_name": None,
        "acquirer": None,
        "duplicate_of": None,
        "sources": [],
        "inferred_closed": True,
    }


def _mark_inferred_closed(
    message_body: Dict[str, Any], reason: str
) -> Tuple[str, float, str]:
    """
    Record an inferred 'closed' resolution when the Exa agent times out or
    returns confidence <= EXA_LOW_CONFIDENCE, which we treat as a signal that
    the company no longer exists.
    """
    resolution = _inferred_closed_resolution(reason)
    message_body["status_resolution"] = resolution
    logger.warning(
        f"  Decision: yes (confidence: {EXA_LOW_CONFIDENCE:.2f}) - {resolution['reason']}"
    )
    return ("yes", EXA_LOW_CONFIDENCE, resolution["reason"])


# ============================================================================
# model.validateOrgId - Verify org exists in database
# ============================================================================

async def agent_validate_org_id(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.validateOrgId (ORG_STATUS flow)

    RESPONSIBILITY: Confirm the org exists in public.orgs and stash its
    identity fields on message_body for the resolver.

    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.validateOrgId] Validating org in database...")

    try:
        org_id = message_body.get("org_id")
        if not org_id:
            reason = "No org_id provided"
            logger.warning(f"  Decision: no (confidence: 0.95) - {reason}")
            return ("no", 0.95, reason)

        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)

        try:
            row = await db.fetchrow(
                """
                SELECT id, name, name_before_acquisition, description, headquarters,
                       content_url, linkedin_company_url, status_id
                FROM public.orgs
                WHERE id = $1 AND deleted_at IS NULL
                """,
                int(org_id),
            )
        except Exception as e:
            reason = f"Database query failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)

        if not row:
            reason = f"Organization id={org_id} not found"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)

        org = dict(row)
        message_body["org"] = org
        message_body["org_id"] = org["id"]
        message_body["org_name"] = org["name"]
        message_body["current_status_id"] = org["status_id"]

        reason = f"Organization {org['id']} found: {org['name']}"
        logger.info(f"  Decision: yes (confidence: 0.99) - {reason}")
        return ("yes", 0.99, reason)

    except Exception as e:
        reason = f"Validation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# model.resolveOrgStatus - Exa agent structured classification
# ============================================================================

async def agent_resolve_org_status(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.resolveOrgStatus (ORG_STATUS flow)

    RESPONSIBILITY: Ask the Exa agent to determine the org's lifecycle status
    and return a structured result. Stores it on message_body['status_resolution'].

    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.resolveOrgStatus] Resolving org status via Exa agent...")

    try:
        org = message_body.get("org")
        if not org:
            reason = "Org context not available (validateOrgId must run first)"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)

        if not EXA_AVAILABLE:
            reason = "exa_py package not installed"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)

        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            reason = "EXA_API_KEY environment variable not set"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)

        query = _build_agent_query(org)
        logger.info(f"  Exa agent query: {query}")

        def _call_exa_agent():
            exa = Exa(api_key=exa_api_key)
            run = exa.agent.runs.create(query=query, output_schema=EXA_OUTPUT_SCHEMA)
            return exa.agent.runs.poll_until_finished(
                run.id, timeout_ms=EXA_AGENT_TIMEOUT_MS
            )

        try:
            completed_run = await asyncio.to_thread(_call_exa_agent)
        except Exception as e:
            if _looks_like_timeout(e):
                logger.warning(
                    f"  Exa agent timed out after {EXA_AGENT_TIMEOUT_MS} ms; "
                    f"treating as closed"
                )
                return _mark_inferred_closed(
                    message_body,
                    f"Exa agent timed out after {EXA_AGENT_TIMEOUT_MS} ms",
                )
            reason = f"Exa agent call failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)

        if not completed_run or not completed_run.output or not completed_run.output.structured:
            # The poll finished without usable output — the same effective signal
            # as a timeout: no evidence the company is still operating.
            logger.warning("  Exa agent returned no structured output; treating as closed")
            return _mark_inferred_closed(
                message_body, "Exa agent returned no structured output"
            )

        raw = completed_run.output.structured
        resolution = _normalize_resolution(raw)

        # A near-zero confidence is, in practice, Exa telling us it could not find
        # an operating company. Treat that as 'closed'.
        if resolution["confidence"] <= EXA_LOW_CONFIDENCE:
            logger.warning(
                f"  Exa confidence {resolution['confidence']:.2f} <= "
                f"{EXA_LOW_CONFIDENCE:.2f}; treating as closed"
            )
            return _mark_inferred_closed(
                message_body,
                f"Exa confidence {resolution['confidence']:.2f} <= {EXA_LOW_CONFIDENCE:.2f}",
            )

        message_body["status_resolution"] = resolution

        logger.info(f"  Resolved: status={resolution['status']} "
                    f"confidence={resolution['confidence']:.2f}")

        confidence = resolution["confidence"] or 0.5
        reason = (
            f"Exa agent resolved status '{resolution['status']}' "
            f"(confidence {confidence:.2f}): {resolution['reason'][:200]}"
        )
        # A structured result is always a success for this stage; the
        # orchestrator decides whether to write based on status/confidence.
        logger.info(f"  Decision: yes (confidence: {confidence:.2f}) - {reason}")
        return ("yes", confidence, reason)

    except Exception as e:
        reason = f"Status resolution failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


def _normalize_resolution(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce the Exa agent's structured output into a predictable shape."""
    status = str(raw.get("status") or "").strip().lower()
    if status not in VALID_STATUSES:
        status = "unknown"

    try:
        confidence = float(raw.get("confidence") or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    sources = raw.get("sources") or []
    if isinstance(sources, str):
        sources = [sources] if sources else []
    elif not isinstance(sources, list):
        sources = []
    sources = [str(s) for s in sources if s]

    def _clean(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    return {
        "status": status,
        "confidence": confidence,
        "reason": _clean(raw.get("reason")) or "",
        "current_name": _clean(raw.get("current_name")),
        "acquirer": _clean(raw.get("acquirer")),
        "duplicate_of": _clean(raw.get("duplicate_of")),
        "sources": sources,
        "inferred_closed": False,
    }


# ============================================================================
# tool.updateOrgStatus - Persist status_id + audit blob
# ============================================================================

async def _get_status_id(db, status_name: str) -> Optional[int]:
    """Resolve a status name to public.statuses.id (cached in-process)."""
    if status_name in _STATUS_ID_CACHE:
        return _STATUS_ID_CACHE[status_name]

    rows = await db.fetch("SELECT id, name FROM public.statuses")
    for row in rows:
        _STATUS_ID_CACHE[str(row["name"]).strip().lower()] = row["id"]
    return _STATUS_ID_CACHE.get(status_name)


async def tool_update_org_status(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.updateOrgStatus (ORG_STATUS flow, terminal agent)

    RESPONSIBILITY: Write the resolved status to public.orgs.status_id and
    record the resolution evidence under orgs.portfolio.status.

    Confidence gating and dry-run are handled by `run_org_status_flow`; this
    tool writes whenever it is called with a valid, non-unknown status.

    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [tool.updateOrgStatus] Updating org status...")

    try:
        db = message_body.get("_db")
        org = message_body.get("org")
        resolution = message_body.get("status_resolution")

        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)

        if not org or not resolution:
            reason = "Missing org context or resolution"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)

        status_name = resolution.get("status")
        if status_name not in VALID_STATUSES:
            reason = f"Refusing to write non-terminal status '{status_name}'"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)

        try:
            status_id = await _get_status_id(db, status_name)
        except Exception as e:
            reason = f"Could not resolve status id for '{status_name}': {e}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)

        if status_id is None:
            reason = f"Status '{status_name}' not present in public.statuses"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)

        org_id = org["id"]
        old_name = (org.get("name") or "").strip()
        current_status_id = message_body.get("current_status_id", org.get("status_id"))

        # When Exa reports the company now operating under a newer name (e.g. after
        # one or more acquisitions), rename the org to that latest operating name
        # and preserve the pre-acquisition name.
        latest_name = None
        rename_conflict_with = None
        if status_name in ("acquired", "renamed"):
            candidate = resolution.get("current_name") or (
                resolution.get("acquirer") if status_name == "acquired" else None
            )
            candidate = (candidate or "").strip()
            if candidate and candidate.lower() != old_name.lower():
                try:
                    rename_conflict_with = await db.fetchval(
                        """
                        SELECT id FROM public.orgs
                        WHERE lower(name) = lower($1) AND id <> $2 AND deleted_at IS NULL
                        """,
                        candidate,
                        org_id,
                    )
                except Exception as e:
                    logger.warning(f"  Could not pre-check rename conflict: {e}")
                    rename_conflict_with = None

                if rename_conflict_with:
                    logger.warning(
                        f"  Skipping rename to '{candidate}': org id={rename_conflict_with} "
                        f"already uses that name"
                    )
                else:
                    latest_name = candidate

        portfolio_status = {
            "status": status_name,
            "confidence": resolution.get("confidence"),
            "reason": resolution.get("reason"),
            "current_name": resolution.get("current_name"),
            "acquirer": resolution.get("acquirer"),
            "duplicate_of": resolution.get("duplicate_of"),
            "sources": resolution.get("sources") or [],
            "latest_name": latest_name,
            "name_before_acquisition": old_name if latest_name else None,
            "rename_conflict_with": rename_conflict_with,
            "inferred_closed": bool(resolution.get("inferred_closed")),
            "resolved_at": datetime.utcnow().isoformat(),
        }

        # name / name_before_acquisition reference old row values on the RHS, so
        # COALESCE(name_before_acquisition, ...) preserves the earliest name across
        # successive acquisitions (7D Surgical -> SeaSpine -> Orthofix keeps 7D).
        update_sql = """
            UPDATE public.orgs
            SET status_id = $1,
                name = CASE WHEN $4::text IS NOT NULL THEN $4::text ELSE name END,
                name_before_acquisition = CASE
                    WHEN $4::text IS NOT NULL
                        THEN COALESCE(name_before_acquisition, $5::text)
                    ELSE name_before_acquisition
                END,
                portfolio = jsonb_set(
                    COALESCE(portfolio, '{}'::jsonb), '{status}', $2::jsonb
                ),
                updated_at = now()
            WHERE id = $3 AND deleted_at IS NULL
            RETURNING id, name, status_id, name_before_acquisition
        """

        try:
            row = await db.fetchrow(
                update_sql,
                status_id,
                json.dumps(portfolio_status),
                org_id,
                latest_name,
                old_name,
            )
        except asyncpg.UniqueViolationError:
            # Another org already owns the target name; keep the existing name.
            logger.warning(
                f"  Name '{latest_name}' already used by another org; keeping '{old_name}'"
            )
            latest_name = None
            rename_conflict_with = rename_conflict_with or -1
            portfolio_status["latest_name"] = None
            portfolio_status["name_before_acquisition"] = None
            portfolio_status["rename_conflict_with"] = rename_conflict_with
            row = await db.fetchrow(
                update_sql,
                status_id,
                json.dumps(portfolio_status),
                org_id,
                None,
                old_name,
            )
        except Exception as e:
            reason = f"Database update failed: {e}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)

        if not row:
            reason = f"Organization id={org_id} not found for update"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)

        message_body["latest_name"] = latest_name
        message_body["name_before_acquisition"] = row["name_before_acquisition"]

        try:
            await log_event(
                db,
                "ORG_STATUS_COMPLETE",
                {
                    "org_id": org_id,
                    "org_name": row["name"],
                    "previous_name": old_name,
                    "name_before_acquisition": row["name_before_acquisition"],
                    "latest_name": latest_name,
                    "previous_status_id": current_status_id,
                    "new_status_id": status_id,
                    "status": status_name,
                    "confidence": resolution.get("confidence"),
                    "reason": resolution.get("reason"),
                    "current_name": resolution.get("current_name"),
                    "acquirer": resolution.get("acquirer"),
                    "duplicate_of": resolution.get("duplicate_of"),
                    "rename_conflict_with": rename_conflict_with,
                    "inferred_closed": bool(resolution.get("inferred_closed")),
                    "sources": resolution.get("sources") or [],
                },
            )
        except Exception as e:
            logger.warning(f"  Failed to log event: {e}")

        if latest_name and latest_name != old_name:
            reason = (
                f"Updated {old_name} → {row['name']} (id={org_id}) status → "
                f"{status_name} (status_id={status_id})"
            )
        else:
            reason = (
                f"Updated {row['name']} (id={org_id}) status → "
                f"{status_name} (status_id={status_id})"
            )
        logger.info(f"  Decision: yes (confidence: 0.98) - {reason}")
        return ("yes", 0.98, reason)

    except Exception as e:
        reason = f"Status update failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# Orchestrator (shared by the batch CLI and the API endpoint)
# ============================================================================

async def run_org_status_flow(
    db,
    org_id: int,
    confidence_threshold: float = 0.70,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Run validate → resolve → update for a single organization.

    Args:
        db: asyncpg connection or pool.
        org_id: Organization ID.
        confidence_threshold: Minimum resolver confidence required to write.
        dry_run: When True, resolve but do not write to the database.

    Returns:
        Result dict describing the outcome (status, decision, confidence,
        resolved fields, error).
    """
    result: Dict[str, Any] = {
        "org_id": org_id,
        "org_name": None,
        "status": "unknown",
        "stage": None,
        "decision": None,
        "confidence": None,
        "resolved_status": None,
        "current_status_id": None,
        "new_status_id": None,
        "reason": None,
        "current_name": None,
        "latest_name": None,
        "name_before_acquisition": None,
        "acquirer": None,
        "duplicate_of": None,
        "sources": [],
        "inferred_closed": False,
        "error": None,
    }

    message_body: Dict[str, Any] = {"org_id": org_id, "_db": db}

    try:
        # Stage 1: validate
        result["stage"] = "validateOrgId"
        decision, confidence, reason = await agent_validate_org_id(message_body)
        if decision != "yes":
            result["status"] = "skipped"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            return result

        result["org_name"] = message_body.get("org_name")
        result["current_status_id"] = message_body.get("current_status_id")

        # Stage 2: resolve
        result["stage"] = "resolveOrgStatus"
        decision, confidence, reason = await agent_resolve_org_status(message_body)
        if decision != "yes":
            result["status"] = "unresolved"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            return result

        resolution = message_body.get("status_resolution", {})
        resolved_status = resolution.get("status")
        resolved_confidence = float(resolution.get("confidence") or 0.0)

        result["decision"] = decision
        result["confidence"] = resolved_confidence
        result["resolved_status"] = resolved_status
        result["reason"] = resolution.get("reason")
        result["current_name"] = resolution.get("current_name")
        result["latest_name"] = resolution.get("current_name")
        result["acquirer"] = resolution.get("acquirer")
        result["duplicate_of"] = resolution.get("duplicate_of")
        result["sources"] = resolution.get("sources") or []
        result["inferred_closed"] = bool(resolution.get("inferred_closed"))

        if resolved_status not in VALID_STATUSES:
            result["status"] = "unknown"
            result["reason"] = result["reason"] or "Resolver returned no conclusive status"
            return result

        # An inferred 'closed' (Exa timeout or near-zero confidence) is written
        # regardless of the confidence threshold: the low confidence IS the signal.
        if result["inferred_closed"]:
            if dry_run:
                result["status"] = "dry_run"
                return result
            result["stage"] = "updateOrgStatus"
            decision, confidence, reason = await tool_update_org_status(message_body)
            if decision == "yes":
                result["status"] = "updated"
                result["new_status_id"] = _STATUS_ID_CACHE.get(resolved_status)
                result["reason"] = reason
            else:
                result["status"] = "write_failed"
                result["reason"] = reason
            return result

        if resolved_confidence < confidence_threshold:
            result["status"] = "below_threshold"
            result["reason"] = (
                f"Confidence {resolved_confidence:.2f} below threshold "
                f"{confidence_threshold:.2f}"
            )
            return result

        if dry_run:
            result["status"] = "dry_run"
            return result

        # Stage 3: write
        result["stage"] = "updateOrgStatus"
        decision, confidence, reason = await tool_update_org_status(message_body)
        if decision == "yes":
            result["status"] = "updated"
            result["new_status_id"] = _STATUS_ID_CACHE.get(resolved_status)
            result["latest_name"] = message_body.get("latest_name")
            result["name_before_acquisition"] = message_body.get("name_before_acquisition")
            result["reason"] = reason
        else:
            result["status"] = "write_failed"
            result["reason"] = reason
        return result

    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        logger.exception(f"  Exception during org status flow: {e}")
        return result
