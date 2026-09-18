"""
Portfolio Service - Discover FDA-cleared device portfolios via Exa agent API.

Usage:
    from services.portfolio_service import search_portfolio_via_exa
    portfolio = await search_portfolio_via_exa(company_name="Acme Corp")
"""

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def search_portfolio_via_exa(company: str, timeout: int = 540) -> Dict[str, Any]:
    """
    Search for all FDA-cleared devices for a company using Exa agent API.

    Args:
        company: Company name (e.g., "Medtronic", "Siemens Healthineers")
        timeout: Maximum seconds to wait for Exa run completion (default 540s = 9min)

    Returns:
        Dictionary with structure:
        {
            "items": [
                {
                    "company": str,
                    "device": str,
                    "intended_use": str (optional),
                    "device_description": str (optional),
                    "primary_product_code": str (optional),
                    "panel": str (optional),
                    "submission_number": str (optional),
                    "submission_type": str enum (optional),
                },
                ...
            ]
        }

    Raises:
        ValueError: If Exa API key not set or response malformed
        TimeoutError: If Exa run does not complete within timeout
    """
    try:
        from exa_py import Exa
    except ImportError:
        raise ValueError("exa_py not installed. Run: pip install exa_py")

    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError("EXA_API_KEY environment variable not set")

    exa = Exa(api_key=api_key)

    logger.info(f"🔍 [Portfolio] Searching for devices: {company}")

    # Define output schema for Exa agent
    output_schema = {
        "items": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "company": {"type": "string"},
                "device": {"type": "string"},
                "intended_use": {"type": "string"},
                "device_description": {"type": "string"},
                "primary_product_code": {"type": "string"},
                "panel": {"type": "string"},
                "submission_number": {"type": "string"},
                "submission_type": {
                    "type": "string",
                    "enum": ["510(k)", "PMA", "De Novo", "HDE", "IDE"],
                },
            },
            "required": ["company", "device"],
            "type": "object",
        },
        "type": "object",
    }

    try:
        # Create Exa agent run
        run = exa.agent.runs.create(
            query=f"Find all distinct FDA-cleared devices for company {company}",
            output_schema=output_schema,
        )
        
        logger.info(f"  [Portfolio] Exa run created: {run.id}")

        # Wait for run to complete with timeout
        start_time = asyncio.get_event_loop().time()
        while True:
            run = exa.agent.runs.retrieve(run.id)
            
            if run.status == "completed":
                logger.info(f"  [Portfolio] Exa run completed successfully")
                break
            elif run.status == "failed":
                error_msg = getattr(run, "error", "Unknown error")
                raise ValueError(f"Exa run failed: {error_msg}")
            elif run.status in ("pending", "running"):
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > timeout:
                    raise TimeoutError(
                        f"Exa run did not complete within {timeout}s. "
                        f"Run ID: {run.id}"
                    )
                # Wait 2 seconds before checking again
                await asyncio.sleep(2)
            else:
                raise ValueError(f"Unknown Exa run status: {run.status}")

        # Extract result
        result = getattr(run, "result", None)
        if not result:
            logger.warning(f"  [Portfolio] No result returned by Exa")
            return {"items": []}

        # Ensure result is dict with 'items' key
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError as e:
                logger.error(f"  [Portfolio] Failed to parse Exa result as JSON: {e}")
                logger.error(f"  [Portfolio] Raw result: {result[:500]}")
                raise ValueError(f"Exa result is not valid JSON: {str(e)}")

        if not isinstance(result, dict):
            raise ValueError(f"Exa result is not a dict: {type(result)}")

        # Normalize: ensure 'items' key exists and is a list
        if "items" not in result:
            logger.warning(f"  [Portfolio] Exa result missing 'items' key. Creating empty items list.")
            result = {"items": []}
        elif not isinstance(result["items"], list):
            logger.warning(
                f"  [Portfolio] Exa result 'items' is not a list: {type(result['items'])}. "
                f"Converting to list."
            )
            # If items is a dict, wrap it; if single object, wrap it
            items_val = result["items"]
            if isinstance(items_val, dict):
                result["items"] = [items_val]
            else:
                result["items"] = []

        # Clean up items: ensure each has required fields
        cleaned_items = []
        for idx, item in enumerate(result.get("items", [])):
            if not isinstance(item, dict):
                logger.warning(f"  [Portfolio] Item {idx} is not a dict: {type(item)}. Skipping.")
                continue

            # Ensure required fields
            if "company" not in item or "device" not in item:
                logger.warning(
                    f"  [Portfolio] Item {idx} missing required fields (company, device). Skipping: {item}"
                )
                continue

            cleaned_items.append(item)

        result["items"] = cleaned_items

        logger.info(f"  [Portfolio] Found {len(result['items'])} FDA-cleared devices")
        return result

    except Exception as e:
        logger.error(f"  ❌ [Portfolio] Exa search failed: {str(e)}", exc_info=True)
        raise


async def batch_search_portfolios(
    org_names: list[str],
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Batch search portfolios for multiple organizations.

    Args:
        org_names: List of organization names
        dry_run: If True, log what would happen but don't update database

    Returns:
        Summary dict: {total, success, failed, errors: {org_name: error_msg, ...}}
    """
    summary = {"total": len(org_names), "success": 0, "failed": 0, "errors": {}}

    for org_name in org_names:
        try:
            logger.info(f"🔍 [Batch Portfolio] Processing: {org_name}")
            portfolio = await search_portfolio_via_exa(org_name)
            
            if dry_run:
                logger.info(f"  [DRY-RUN] Would update {org_name} with {len(portfolio['items'])} devices")
            else:
                logger.info(f"  [Portfolio] Found {len(portfolio['items'])} devices for {org_name}")
            
            summary["success"] += 1
        except Exception as e:
            logger.error(f"  ❌ [Batch Portfolio] Failed for {org_name}: {str(e)}")
            summary["failed"] += 1
            summary["errors"][org_name] = str(e)

    logger.info(
        f"✅ [Batch Portfolio] Complete: {summary['success']} success, "
        f"{summary['failed']} failed out of {summary['total']}"
    )
    return summary
