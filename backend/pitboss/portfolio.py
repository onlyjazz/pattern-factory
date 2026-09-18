"""
Portfolio Agents - Discover and store FDA-cleared device portfolios.

Workflow: PORTFOLIO
- model.validateOrgName: Verify org exists (shared with ENRICH)
- model.searchPortfolio: Call Exa agent API to discover devices
- model.verifyPortfolioPayload: Validate Exa response structure
- tool.upsertPortfolio: UPDATE orgs.portfolio with JSON
"""

import json
import logging
from typing import Tuple, Dict, Any

from services.portfolio_service import search_portfolio_via_exa
from pitboss.logging_util import log_event

logger = logging.getLogger(__name__)


async def agent_search_portfolio(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchPortfolio (PORTFOLIO flow)
    Call Exa agent API to discover FDA-cleared devices for the organization.
    
    Input:
    - message_body["org_id"]: Organization ID (from validateOrgName)
    - message_body["org_name"]: Organization name
    
    Output:
    - Stores message_body["portfolio"]: {items: [{company, device, ...}, ...]}
    """
    logger.info("🤖 [model.searchPortfolio] Searching for organization portfolio...")
    
    org_name = (message_body.get("org_name") or "").strip()
    if not org_name:
        reason = "No organization name provided"
        logger.warning(f"  Decision: no (confidence: 0.95) - {reason}")
        return ("no", 0.95, reason)
    
    try:
        portfolio = await search_portfolio_via_exa(org_name)
        message_body["portfolio"] = portfolio
        
        device_count = len(portfolio.get("items", []))
        reason = f"Found {device_count} FDA-cleared devices for {org_name}"
        logger.info(f"  Decision: yes (confidence: 0.96) - {reason}")
        return ("yes", 0.96, reason)
    
    except Exception as e:
        reason = f"Failed to search portfolio: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.85) - {reason}", exc_info=True)
        return ("no", 0.85, reason)


async def agent_verify_portfolio_payload(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyPortfolioPayload (PORTFOLIO flow)
    Validate Exa response structure before database upsert.
    
    Input:
    - message_body["portfolio"]: Portfolio dict from Exa
    
    Checks:
    1. portfolio is dict with 'items' key
    2. 'items' is a list
    3. Each item has required fields: company, device
    """
    logger.info("🤖 [model.verifyPortfolioPayload] Validating portfolio payload...")
    
    portfolio = message_body.get("portfolio")
    if not isinstance(portfolio, dict):
        reason = f"Portfolio is not a dict: {type(portfolio)}"
        logger.warning(f"  Decision: no (confidence: 0.92) - {reason}")
        return ("no", 0.92, reason)
    
    items = portfolio.get("items", [])
    if not isinstance(items, list):
        reason = f"Portfolio items is not a list: {type(items)}"
        logger.warning(f"  Decision: no (confidence: 0.92) - {reason}")
        return ("no", 0.92, reason)
    
    # Validate each item has required fields
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            reason = f"Item {idx} is not a dict: {type(item)}"
            logger.warning(f"  Decision: no (confidence: 0.92) - {reason}")
            return ("no", 0.92, reason)
        
        if "company" not in item or "device" not in item:
            reason = f"Item {idx} missing required fields (company, device)"
            logger.warning(f"  Decision: no (confidence: 0.92) - {reason}")
            return ("no", 0.92, reason)
    
    reason = f"Portfolio validation passed: {len(items)} devices"
    logger.info(f"  Decision: yes (confidence: 0.96) - {reason}")
    return ("yes", 0.96, reason)


async def tool_upsert_portfolio(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.upsertPortfolio (PORTFOLIO flow) - Terminal Agent
    Update orgs.portfolio with the discovered portfolio JSON.
    
    Input:
    - message_body["org_id"]: Organization ID
    - message_body["org_name"]: Organization name
    - message_body["portfolio"]: Portfolio dict to store
    """
    logger.info("🤖 [tool.upsertPortfolio] Upserting portfolio to database...")
    
    org_id = message_body.get("org_id")
    org_name = message_body.get("org_name", "Unknown")
    portfolio = message_body.get("portfolio", {})
    
    if not org_id:
        reason = "No org_id provided for upsert"
        logger.error(f"  Decision: no (confidence: 0.0) - {reason}")
        return ("no", 0.0, reason)
    
    try:
        # Import here to avoid circular imports
        from pitboss.workflow import get_tool_registry
        
        tool_registry = get_tool_registry()
        if not tool_registry:
            raise ValueError("ToolRegistry not available")
        
        # Prepare upsert payload
        portfolio_json = json.dumps(portfolio)
        
        # Execute upsert via SQL (pattern: UPDATE orgs SET portfolio = ... WHERE id = ...)
        result = await tool_registry.execute(
            "upsert_org_portfolio",
            org_id=org_id,
            portfolio_json=portfolio_json,
        )
        
        device_count = len(portfolio.get("items", []))
        
        # Log completion
        await log_event(
            tool_registry.db,
            "PORTFOLIO_COMPLETE",
            {
                "org_id": org_id,
                "org_name": org_name,
                "device_count": device_count,
            },
        )
        
        reason = f"Portfolio upserted for {org_name}: {device_count} devices stored"
        logger.info(f"  Decision: yes (confidence: 0.97) - {reason}")
        return ("yes", 0.97, reason)
    
    except Exception as e:
        reason = f"Portfolio upsert failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.0) - {reason}", exc_info=True)
        return ("no", 0.0, reason)
