"""
Product Competitors Agent Flow (COMPETITORS Workflow)

COMPETITORS Workflow:
  model.validateProductId → model.searchForCompetitors → tool.upsertCompetitors

Discovers top 3 competing products for a given device using Exa search,
then upserts competitor relationships and missing products/orgs to the database.

Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
"""

import logging
import re
from typing import Tuple, Dict, Any, Optional, List
import json
from datetime import datetime
import os
from .logging_util import log_event

# Cache for SEARCH.yaml config
_SEARCH_CONFIG_CACHE: Optional[Dict[str, Any]] = None

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from openai import OpenAI

logger = logging.getLogger(__name__)


def _load_search_config() -> Dict[str, Any]:
    """Load and cache the SEARCH section from prompts/rules/SEARCH.yaml."""
    global _SEARCH_CONFIG_CACHE
    if _SEARCH_CONFIG_CACHE is not None:
        return _SEARCH_CONFIG_CACHE
    try:
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "rules", "SEARCH.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        _SEARCH_CONFIG_CACHE = (yaml_data.get("SEARCH") or {}) if isinstance(yaml_data, dict) else {}
        logger.info("  ✓ Loaded SEARCH.yaml competitors config")
    except Exception as e:
        logger.warning(f"  Could not load SEARCH.yaml, using defaults: {e}")
        _SEARCH_CONFIG_CACHE = {}
    return _SEARCH_CONFIG_CACHE


# ============================================================================
# Model.searchForCompetitors - Search Exa for competing products
# ============================================================================

async def agent_search_for_competitors(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchForCompetitors (COMPETITORS flow)
    
    RESPONSIBILITY: Use Exa agent API to find top 3 competing products based on
    the product's name. The Exa agent handles
    search, analysis, and structured JSON extraction in one step.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchForCompetitors] Searching for competing products via Exa agent...")
    
    try:
        product = message_body.get("product")
        if not product:
            reason = "Product data not available"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        # Extract search parameters
        device = (product.get("device") or "").strip()
        company = (product.get("company") or "").strip()
        intended_use = (product.get("intended_use") or "").strip()
        
        if not device:
            reason = f"Product missing device name"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)
        
        # Check Exa availability
        if not EXA_AVAILABLE:
            reason = "Exa Python SDK not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            reason = "EXA_API_KEY environment variable not set"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        try:
            exa = Exa(api_key=exa_api_key)
            
            # Build agent query to find competitors
            # Prompt: find the top 3 competitors to {products.device} device from {orgs.name}. return a json object with up to 3 strings (names of companies/products)
            query = f"find the top 3 competitors to {device} device from {company}. return a json object with up to 3 strings (names of companies/products)"
            
            logger.info(f"  Exa agent query: {query}")
            
            # Call Exa agent API with structured output schema
            import asyncio
            
            def _call_exa_agent():
                run = exa.agent.runs.create(
                    query=query,
                    output_schema={
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "company": {"type": "string"},
                                "product": {"type": "string"},
                            },
                            "required": ["company", "product"],
                            "additionalProperties": False,
                        },
                    },
                )
                # Poll until finished (timeout_ms is in milliseconds; 120000 ms = 120 seconds)
                completed_run = exa.agent.runs.poll_until_finished(run.id, timeout_ms=120000)
                return completed_run
            
            completed_run = await asyncio.to_thread(_call_exa_agent)
            
            # Extract structured output
            if not completed_run or not completed_run.output:
                reason = "Exa agent returned no output"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            structured_output = completed_run.output.structured
            if not structured_output:
                reason = "Exa agent returned no structured data"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            logger.info(f"  Raw structured output: {structured_output}")
            logger.info(f"  Output type: {type(structured_output)}")
            
            # Format output into competitor list
            competitors_found = _format_exa_agent_output(
                structured_output=structured_output,
                source_company=company
            )
            
            if not competitors_found:
                reason = "No valid competitors extracted from Exa agent output"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            # Store results for next agent
            message_body["competitors_found"] = competitors_found
            
            # Generate human-readable competitors string
            competitors_str = _unravel_competitors_to_string(competitors_found)
            message_body["competitors_string"] = competitors_str
            logger.info(f"  Competitors string: {competitors_str}")
            
            reason = f"Found {len(competitors_found)} competitor(s) via Exa agent"
            logger.info(f"  Decision: yes (confidence: 0.92) - {reason}")
            return ("yes", 0.92, reason)
            
        except Exception as e:
            reason = f"Exa agent call failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Search failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


def _unravel_competitors_to_string(competitors_found: List[Dict[str, Any]]) -> str:
    """
    Convert list of competitor objects into a human-readable string.
    Example: "Agada Medical Ltd. - Auto-Seg (Spine Auto-Seg), Materialise NV - Mimics Medical and Mighty Oak Medical - Acorn 3D Software"
    """
    if not competitors_found:
        return ""
    
    parts = []
    for comp in competitors_found[:3]:
        company = (comp.get("company") or "").strip()
        device = (comp.get("device") or "").strip()
        if company and device:
            parts.append(f"{company} - {device}")
    
    if len(parts) == 0:
        return ""
    elif len(parts) == 1:
        return parts[0]
    elif len(parts) == 2:
        return f"{parts[0]} and {parts[1]}"
    else:  # 3 parts
        return f"{parts[0]}, {parts[1]} and {parts[2]}"


def _format_exa_agent_output(
    structured_output: Dict[str, Any],
    source_company: str
) -> List[Dict[str, Any]]:
    """
    Format Exa agent structured output into competitor list.
    Exa agent returns an array of {company: str, product: str} objects.
    
    Returns: List of {company: str, device: str, description: str, rank: int}
    """
    logger.info("  Processing Exa agent output...")
    
    try:
        if not structured_output:
            logger.warning("  No structured output from Exa agent")
            return []
        
        logger.info(f"  Raw output: {structured_output}")
        
        # Exa agent returns an array of competitor objects
        competitor_list = []
        if isinstance(structured_output, list):
            competitor_list = structured_output
        else:
            logger.warning(f"  Unexpected output format (expected array): {structured_output}")
            return []
        
        if not competitor_list:
            logger.warning(f"  No competitors in Exa output: {structured_output}")
            return []
        
        competitors_ranked = []
        source_company_lower = source_company.lower()
        
        for comp_data in competitor_list:
            if not isinstance(comp_data, dict):
                continue
            
            comp_company = (comp_data.get("company") or "").strip()
            comp_product = (comp_data.get("product") or "").strip()
            
            if not comp_company or not comp_product:
                logger.warning(f"  Skipping incomplete entry: {comp_data}")
                continue
            
            # Skip if same company as source
            if comp_company.lower() == source_company_lower:
                logger.info(f"  Skipping same company: {comp_company}")
                continue
            
            competitors_ranked.append({
                "company": comp_company,
                "device": comp_product,
                "description": comp_product,
                "rank": len(competitors_ranked) + 1
            })
            
            # Only keep top 3
            if len(competitors_ranked) >= 3:
                break
        
        logger.info(f"  Extracted {len(competitors_ranked)} competitors from Exa output")
        return competitors_ranked
        
    except Exception as e:
        logger.error(f"  Failed to process Exa output: {e}", exc_info=True)
        return []


async def _call_openai_async(
    *, 
    client: OpenAI,
    system_prompt: str,
    user_message: str,
    model: str,
    temperature: float,
    timeout: float
) -> str:
    """Call OpenAI chat.completions in a background thread, return JSON content."""
    import asyncio
    
    def _call_sync() -> str:
        resp = client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            response_format={"type": "json_object"},
            timeout=timeout,
        )
        return resp.choices[0].message.content
    
    return await asyncio.to_thread(_call_sync)


# ============================================================================
# Tool.upsertCompetitors - Upsert competitor relationships to database
# ============================================================================

async def agent_upsert_competitors(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.upsertCompetitors (COMPETITORS flow, terminal agent)
    
    RESPONSIBILITY: For each competitor found, verify/create the org and product
    records if missing, then upsert the competitor relationship to the database.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [tool.upsertCompetitors] Upserting competitor relationships...")
    
    try:
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        product = message_body.get("product")
        product_id = message_body.get("product_id")
        competitors_found = message_body.get("competitors_found", [])
        competitors_string = message_body.get("competitors_string", "")
        
        if not product_id or not product:
            reason = "Product or product_id not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        if not competitors_found:
            reason = "No competitors found to upsert"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)
        
        # Get or create org for the product (company_id)
        company_name = (product.get("company") or "").strip()
        company_org_id = None
        
        if company_name:
            try:
                # Look up company org
                company_org = await db.fetchrow(
                    "SELECT id FROM public.orgs WHERE name = $1 AND deleted_at IS NULL",
                    company_name
                )
                if company_org:
                    company_org_id = company_org["id"]
                else:
                    # Create new org for company
                    logger.info(f"  Creating new org for company: {company_name}")
                    company_org_id = await db.fetchval(
                        """INSERT INTO public.orgs (name, status_id) 
                           VALUES ($1, 1) 
                           RETURNING id""",
                        company_name
                    )
            except Exception as e:
                logger.warning(f"  Could not get/create company org: {e}")
        
        if not company_org_id:
            reason = f"Could not identify company organization"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)
        
        # Process each competitor
        upserted_count = 0
        for competitor in competitors_found[:3]:  # Top 3 only
            try:
                competitor_company = (competitor.get("company") or "").strip()
                competitor_device = (competitor.get("device") or "").strip()
                competitor_rank = competitor.get("rank", 0)
                
                if not competitor_company:
                    logger.warning(f"  Skipping competitor with no company name")
                    continue
                
                # Look up or create competitor org
                competitor_org = await db.fetchrow(
                    "SELECT id FROM public.orgs WHERE name = $1 AND deleted_at IS NULL",
                    competitor_company
                )
                
                if competitor_org:
                    competitor_org_id = competitor_org["id"]
                else:
                    # Create new org for competitor company
                    logger.info(f"  Creating new org for competitor: {competitor_company}")
                    competitor_org_id = await db.fetchval(
                        """INSERT INTO public.orgs (name, status_id) 
                           VALUES ($1, 1) 
                           RETURNING id""",
                        competitor_company
                    )
                
                # Try to find competitor product in database
                competitor_product_id = None
                competitor_device = (competitor.get("device") or "").strip()
                
                if competitor_device:
                    competitor_product = await db.fetchrow(
                        """SELECT id FROM public.products 
                           WHERE device = $1 AND deleted_at IS NULL""",
                        competitor_device
                    )
                    
                    if competitor_product:
                        competitor_product_id = competitor_product["id"]
                    else:
                        # Create new product record for competitor device
                        # Use 'UNK-{uuid}' for submission_number (unique placeholder)
                        # PROFILE agent can find real submission numbers later
                        import uuid
                        placeholder_submission = f"UNK-{uuid.uuid4().hex[:8].upper()}"
                        try:
                            logger.info(f"  Creating new competitor product: {competitor_device}")
                            competitor_product_id = await db.fetchval(
                                """INSERT INTO public.products (device, company, org_id, submission_number, process_flag) 
                                   VALUES ($1, $2, $3, $4, false) 
                                   RETURNING id""",
                                competitor_device,
                                competitor_company,
                                competitor_org_id,
                                placeholder_submission
                            )
                            logger.info(f"  ✓ Created competitor product {competitor_product_id}: {competitor_device} (submission: {placeholder_submission})")
                        except Exception as e:
                            logger.error(f"  ERROR creating competitor product '{competitor_device}' for org {competitor_org_id}: {str(e)}", exc_info=True)
                            # Continue anyway - we'll insert with competitor_product_id=NULL
                            competitor_product_id = None
                
                # Upsert competitor relationship
                await db.execute(
                    """INSERT INTO public.competitors (company_id, competitor_id, product_id, competitor_product_id, rank, rationale)
                       VALUES ($1, $2, $3, $4, $5, $6)
                       ON CONFLICT (company_id, competitor_id, product_id)
                       DO UPDATE SET rank = $5, competitor_product_id = $4, rationale = $6, updated_at = NOW()""",
                    company_org_id,
                    competitor_org_id,
                    product_id,
                    competitor_product_id,
                    competitor_rank,
                    competitor.get("description", "")
                )
                
                logger.info(f"  ✓ Upserted competitor: {competitor_company} (rank {competitor_rank})")
                if competitor_product_id:
                    logger.info(f"    → Competitor product ID: {competitor_product_id}")
                upserted_count += 1
                
            except Exception as e:
                logger.error(f"  Failed to upsert competitor: {e}", exc_info=True)
                continue
        
        # Update products.competitors with the unraveled competitors string
        if competitors_string and upserted_count > 0:
            try:
                await db.execute(
                    "UPDATE public.products SET competitors = $1, updated_at = NOW() WHERE id = $2",
                    competitors_string,
                    product_id
                )
                logger.info(f"  ✓ Updated products.competitors for product {product_id}")
            except Exception as e:
                logger.warning(f"  Failed to update products.competitors: {e}")
        
        # Build human-readable output message
        device_name = (product.get("device") or "this device").strip()
        competitor_messages = []
        
        for i, (competitor, idx) in enumerate(zip(competitors_found[:3], range(1, 4)), 1):
            comp_company = (competitor.get("company") or "").strip()
            comp_device = (competitor.get("device") or "").strip()
            
            if comp_company and comp_device:
                if upserted_count >= idx:
                    # This competitor was successfully upserted
                    msg = f"#{idx}: {comp_company} with '{comp_device}'"
                else:
                    msg = f"#{idx}: {comp_company} with '{comp_device}' (lookup failed)"
                competitor_messages.append(msg)
        
        if competitor_messages:
            comp_list = " | ".join(competitor_messages)
            if upserted_count == 1:
                reason = f"Found 1 competitor to {device_name}: {comp_list}"
            elif upserted_count > 1:
                reason = f"Found {upserted_count} competitors to {device_name}: {comp_list}"
            else:
                reason = f"No competitors could be stored for {device_name}"
        else:
            reason = f"Could not extract competitor information for {device_name}"
        
        # Log completion
        try:
            await log_event(
                db,
                "COMPETITORS_COMPLETE",
                {
                    "product_id": product_id,
                    "product_device": product.get("device"),
                    "product_company": product.get("company"),
                    "competitors_found": len(competitors_found),
                    "competitors_upserted": upserted_count
                }
            )
        except Exception as e:
            logger.warning(f"  Failed to log event: {e}")
        
        confidence = 0.92 if upserted_count > 0 else 0.50
        decision = "yes" if upserted_count > 0 else "no"
        
        logger.info(f"  Decision: {decision} (confidence: {confidence}) - {reason}")
        return (decision, confidence, reason)
        
    except Exception as e:
        reason = f"Upsert failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)
