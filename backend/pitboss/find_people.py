"""
Find People in Organizations via Exa Agent (FIND_PEOPLE Workflow)

Discovers names and emails of key people (e.g., CEOs) at organizations
using the Exa agent API (structured web research) and persists them to
public.people.

Flow (invoked directly, not via model.LanguageCapo / the supervisor):
  model.validateOrgId   → model.findPeopleViaExa   → tool.upsertPeople

Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)

The `run_find_people_flow` helper orchestrates the three steps for a single
org and is shared by the batch CLI (bin/find-people) and potentially
the API endpoint (future: POST /orgs/find-people).
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import asyncpg

from .logging_util import log_event

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

logger = logging.getLogger(__name__)

# Exa agent polling budget (milliseconds). Overridable via EXA_AGENT_TIMEOUT_MS.
EXA_AGENT_TIMEOUT_MS = int(os.getenv("EXA_AGENT_TIMEOUT_MS", "120000"))

# Structured output contract for the Exa agent (find people).
EXA_OUTPUT_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "people": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string"},
                    "job_description": {"type": "string"},
                },
                "required": ["name"],
            },
        },
    },
    "required": ["people"],
    "additionalProperties": False,
}

# mtime-cached SEARCH.yaml config (hot-reload without restart).
_FIND_PEOPLE_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_FIND_PEOPLE_CONFIG_MTIME: Optional[float] = None


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


def _load_find_people_config() -> Dict[str, Any]:
    """
    Load the FIND_PEOPLE section from prompts/rules/SEARCH.yaml, refreshing
    whenever the file's mtime changes so prompt edits take effect without a
    process restart. Falls back to inline defaults when the file/key is absent.
    """
    global _FIND_PEOPLE_CONFIG_CACHE, _FIND_PEOPLE_CONFIG_MTIME

    yaml_path = _search_yaml_path()
    try:
        mtime = os.path.getmtime(yaml_path)
    except OSError:
        mtime = None

    if mtime is not None and mtime == _FIND_PEOPLE_CONFIG_MTIME:
        return _FIND_PEOPLE_CONFIG_CACHE or {}

    config: Dict[str, Any] = {}
    try:
        import yaml

        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f) or {}
        search_section = yaml_data.get("SEARCH") or {}
        config = search_section.get("find_people") or {}
    except Exception as e:
        logger.warning(f"  Could not load SEARCH.yaml find_people config, using defaults: {e}")
        config = {}

    _FIND_PEOPLE_CONFIG_CACHE = config
    _FIND_PEOPLE_CONFIG_MTIME = mtime
    return config


def _build_agent_query(org: Dict[str, Any]) -> Tuple[str, str]:
    """
    Build the Exa agent research query for one organization.
    Returns (user_prompt, system_prompt).
    """
    config = _load_find_people_config()
    user_template = config.get("user_prompt") or "find the name and email of the CEO of {company_name}"
    system_prompt = config.get("system_prompt") or "You are an expert market researcher looking for the email of the CEO of a medical device company"
    
    company_name = (org.get("name") or "").strip()
    user_prompt = user_template.format(company_name=company_name)
    
    return user_prompt, system_prompt


async def model_validate_org_id(
    db: asyncpg.Pool, org_id: int
) -> Tuple[str, float, str, Optional[Dict[str, Any]]]:
    """
    Agent: model.validateOrgId
    Verify organization exists in database.
    
    Returns: (decision, confidence, reason, org_record)
    """
    try:
        org = await db.fetchrow("SELECT * FROM public.orgs WHERE id = $1", org_id)
        if org:
            logger.info(f"  Decision: yes (confidence: 1.0) - Org {org_id} ({org['name']}) found")
            return ("yes", 1.0, f"Org {org_id} exists", dict(org))
        else:
            logger.warning(f"  Decision: no (confidence: 1.0) - Org {org_id} not found")
            return ("no", 1.0, f"Org {org_id} not found in database", None)
    except Exception as e:
        logger.error(f"  Decision: no (confidence: 0.0) - Database error: {e}")
        return ("no", 0.0, f"Database error: {e}", None)


async def model_find_people_via_exa(
    db: asyncpg.Pool,
    org: Dict[str, Any],
    exa_client: Optional[Exa] = None,
) -> Tuple[str, float, str, Optional[Dict[str, Any]]]:
    """
    Agent: model.findPeopleViaExa
    Search for people at the organization using Exa agent with structured extraction.
    
    Returns: (decision, confidence, reason, extracted_people_dict)
    """
    if not EXA_AVAILABLE or exa_client is None:
        reason = "Exa not available or not initialized"
        logger.error(f"  Decision: no (confidence: 0.0) - {reason}")
        return ("no", 0.0, reason, None)

    org_id = org.get("id")
    org_name = org.get("name", "").strip()

    try:
        user_prompt, system_prompt = _build_agent_query(org)
        
        logger.info(f"  Exa agent research for org {org_id} ({org_name})...")
        
        # Call Exa agent with structured output schema
        run = exa_client.search_and_contents(
            query=user_prompt,
            type="agent",
            use_autoprompt=False,
            num_results=5,
            contents={
                "text": {
                    "max_characters": 4000,
                },
            },
        )
        
        # Extract the agent result (structured JSON response)
        if hasattr(run, "agent_result"):
            result = run.agent_result
        else:
            logger.warning(f"  No agent_result in Exa response for org {org_id}")
            return ("no", 0.2, "Exa agent returned no result", None)
        
        # Validate the result is a dict with 'people' key
        if not isinstance(result, dict) or "people" not in result:
            logger.warning(f"  Exa agent result missing 'people' key for org {org_id}")
            return ("no", 0.3, "Exa agent result missing 'people' key", None)
        
        people = result.get("people", [])
        if not isinstance(people, list):
            logger.warning(f"  Exa agent 'people' is not a list for org {org_id}")
            return ("no", 0.3, "Exa agent 'people' is not a list", None)
        
        # Validate at least one person was found
        if not people:
            logger.warning(f"  Decision: no (confidence: 0.4) - No people found for org {org_id}")
            return ("no", 0.4, f"Exa agent found no people for {org_name}", None)
        
        # Validate each person has at least a name
        valid_people = []
        for person in people:
            if isinstance(person, dict) and "name" in person and person["name"].strip():
                valid_people.append(person)
        
        if not valid_people:
            logger.warning(f"  Decision: no (confidence: 0.4) - No valid people (missing names) for org {org_id}")
            return ("no", 0.4, "No valid people with names found", None)
        
        confidence = min(0.95, 0.5 + len(valid_people) * 0.15)  # Confidence grows with number of people found
        logger.info(f"  Decision: yes (confidence: {confidence:.2f}) - Found {len(valid_people)} people for org {org_id}")
        
        return (
            "yes",
            confidence,
            f"Found {len(valid_people)} people for {org_name}",
            {"people": valid_people}
        )
    
    except asyncio.TimeoutError:
        logger.error(f"  Decision: no (confidence: 0.1) - Exa agent timeout for org {org_id}")
        return ("no", 0.1, f"Exa agent timeout searching for {org_name}", None)
    except Exception as e:
        logger.error(f"  Decision: no (confidence: 0.0) - Exa agent error: {e}")
        return ("no", 0.0, f"Exa agent error: {e}", None)


async def tool_upsert_people(
    db: asyncpg.Pool,
    org_id: int,
    extracted_people: Dict[str, Any],
) -> Tuple[str, float, str]:
    """
    Terminal agent: tool.upsertPeople
    Insert or update people records in public.people, linked to org_id.
    
    Returns: (decision, confidence, reason)
    """
    people_list = extracted_people.get("people", [])
    if not people_list:
        logger.warning("  No people to upsert")
        return ("no", 0.5, "No people provided to upsert")
    
    try:
        upserted_count = 0
        for person in people_list:
            name = person.get("name", "").strip()
            email = person.get("email", "").strip() or None
            job_desc = person.get("job_description", "").strip() or None
            
            if not name:
                logger.debug(f"  Skipping person with empty name")
                continue
            
            # Upsert: insert or update on unique key (name, org_id)
            # If the person already exists with this name+org_id, update their email/job_description
            await db.execute(
                """
                INSERT INTO public.people (name, email, job_description, org_id, content_source)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (name) WHERE org_id = $4
                DO UPDATE SET
                    email = COALESCE($2, people.email),
                    job_description = COALESCE($3, people.job_description),
                    updated_at = NOW()
                """,
                name,
                email,
                job_desc,
                org_id,
                "exa_agent",
            )
            upserted_count += 1
            logger.debug(f"  Upserted person: {name} (org_id={org_id})")
        
        logger.info(f"  Decision: yes (confidence: 0.96) - Upserted {upserted_count} people for org_id={org_id}")
        return ("yes", 0.96, f"Upserted {upserted_count} people for org_id={org_id}")
    
    except Exception as e:
        logger.error(f"  Decision: no (confidence: 0.0) - Database upsert error: {e}")
        return ("no", 0.0, f"Upsert error: {e}")


async def run_find_people_flow(
    db: asyncpg.Pool,
    org_id: int,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrate the find-people flow for a single organization.
    
    Returns a result dict with keys:
      - status: "updated", "skipped", "error", "unknown"
      - org_id, org_name
      - decision, confidence, reason (from final step)
      - people_count (number upserted, or 0 if dry_run or error)
      - elapsed_s (elapsed time)
      - error (if status='error')
    """
    start_time = time.time()
    result = {
        "org_id": org_id,
        "org_name": None,
        "status": "unknown",
        "decision": None,
        "confidence": None,
        "reason": None,
        "people_count": 0,
        "elapsed_s": None,
        "dry_run": dry_run,
    }
    
    try:
        # Step 1: Validate org exists
        logger.info(f"[Org {org_id}] Step 1: Validating org...")
        decision, confidence, reason, org_record = await model_validate_org_id(db, org_id)
        
        if decision != "yes":
            result["status"] = "error"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            result["elapsed_s"] = time.time() - start_time
            return result
        
        result["org_name"] = org_record.get("name")
        logger.info(f"[Org {result['org_name']}] Step 2: Searching for people via Exa...")
        
        # Step 2: Search for people via Exa agent
        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            logger.error("EXA_API_KEY not set")
            result["status"] = "error"
            result["reason"] = "EXA_API_KEY not set"
            result["elapsed_s"] = time.time() - start_time
            return result
        
        exa_client = Exa(api_key=exa_api_key)
        decision, confidence, reason, extracted_people = await model_find_people_via_exa(
            db, org_record, exa_client
        )
        
        if decision != "yes":
            result["status"] = "skipped"
            result["decision"] = decision
            result["confidence"] = confidence
            result["reason"] = reason
            result["elapsed_s"] = time.time() - start_time
            return result
        
        logger.info(f"[Org {result['org_name']}] Step 3: Upserting people...")
        
        # Step 3: Upsert people to database
        if dry_run:
            logger.info(f"[DRY RUN] Would upsert {len(extracted_people.get('people', []))} people for org_id={org_id}")
            result["status"] = "dry_run"
            result["decision"] = "yes"
            result["confidence"] = confidence
            result["reason"] = reason
            result["people_count"] = len(extracted_people.get("people", []))
        else:
            decision, confidence, reason = await tool_upsert_people(db, org_id, extracted_people)
            
            if decision == "yes":
                result["status"] = "updated"
                result["decision"] = decision
                result["confidence"] = confidence
                result["reason"] = reason
                result["people_count"] = len(extracted_people.get("people", []))
            else:
                result["status"] = "error"
                result["decision"] = decision
                result["confidence"] = confidence
                result["reason"] = reason
        
        result["elapsed_s"] = time.time() - start_time
        return result
    
    except Exception as e:
        logger.exception(f"[Org {org_id}] Unhandled exception in find-people flow: {e}")
        result["status"] = "error"
        result["reason"] = f"Unhandled exception: {e}"
        result["elapsed_s"] = time.time() - start_time
        return result
