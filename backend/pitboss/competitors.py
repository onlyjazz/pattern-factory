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
    
    RESPONSIBILITY: Search Exa for top 3 competing products based on the
    product's device_description and intended_use. Extract competitor
    product names and company information from results.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchForCompetitors] Searching for competing products...")
    
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
        device_description = (product.get("device_description") or "").strip()
        panel = (product.get("panel") or "").strip()
        
        if not device:
            reason = f"Product missing device name"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)
        
        # Build simple search query focused on intended use
        # Search for competing devices with the same clinical purpose
        # Exclude the source company to avoid getting the source product itself in results
        if intended_use:
            search_query = f"competing medical devices {intended_use}"
        elif device:
            search_query = f"competing medical devices {device}"
        else:
            search_query = "competing medical devices"
        
        # Add company exclusion to filter out source company from Exa results
        if company:
            search_query += f" -{company}"
        
        logger.info(f"  Search query: {search_query}")
        
        # Use Exa to find competitors
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
            
            # Search using Exa Answer API for narrative extraction
            # Use type="auto" with num_results to get top results
            import asyncio
            
            def _search_exa():
                results = exa.search(
                    query=search_query,
                    num_results=10,
                    type="auto",
                    contents={"highlights": True}
                )
                return results
            
            results = await asyncio.to_thread(_search_exa)
            
            if not results or not results.results:
                reason = "No competitor products found in Exa results"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            # Extract competitor information from Exa results
            competitors_found = await _extract_competitor_products(
                results=results,
                product=product,
                message_body=message_body
            )
            
            if not competitors_found:
                reason = "Could not extract competitor product details from Exa results"
                logger.warning(f"  Decision: no (confidence: 0.65) - {reason}")
                return ("no", 0.65, reason)
            
            # Store results for next agent
            message_body["competitors_found"] = competitors_found
            
            reason = f"Found {len(competitors_found)} potential competitor products"
            logger.info(f"  Decision: yes (confidence: 0.88) - {reason}")
            return ("yes", 0.88, reason)
            
        except Exception as e:
            reason = f"Exa search failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Search failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


async def _extract_competitor_products(
    results: Any,
    product: Dict[str, Any],
    message_body: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Extract competitor product names and companies from Exa search results.
    Uses LLM to identify product/company pairs from search results.
    
    Returns: List of {company: str, device: str, description: str, rank: int}
    """
    logger.info("  Extracting competitor products from Exa results...")
    
    try:
        # Format Exa results for LLM extraction
        result_texts = []
        for i, result in enumerate(results.results[:10]):  # Top 10
            title = getattr(result, 'title', '')
            text = getattr(result, 'text', '')
            highlight = getattr(result, 'highlight', '')
            
            result_text = f"Result {i+1}: {title}\n"
            if highlight:
                result_text += f"Highlight: {highlight}\n"
            if text:
                result_text += f"Content: {text[:500]}\n"
            result_texts.append(result_text)
        
        combined_results = "\n---\n".join(result_texts)
        
        # Use LLM to extract competitor products
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("  OPENAI_API_KEY not set, falling back to heuristic extraction")
            return _extract_competitors_heuristic(combined_results)
        
        client = OpenAI(api_key=api_key)
        source_company = (product.get("company") or "").strip()
        source_device = (product.get("device") or "").strip()
        
        # Load system prompt from SEARCH.yaml
        system_prompt = (
            "You are a medical device competitive intelligence analyst. "
            "Extract the top 3 competing product companies and device names from the provided search results. "
            "IMPORTANT: Exclude any products from the same company as the source product. "
            "Return ONLY a JSON array with up to 3 objects from DIFFERENT companies: "
            '[{"company": "Company Name", "device": "Device Name", "description": "Brief description", "rank": 1}, ...]. '
            "If fewer than 3 competitors from different companies found, return only what you found. "
            "Ensure company names and device names are realistic FDA-cleared medical device names. "
            "Return ONLY valid JSON, no markdown, no extra text."
        )
        
        try:
            search_config = _load_search_config()
            system_prompt = (search_config.get("competitors_extraction_prompt") or system_prompt).strip()
            logger.info(f"  ✓ Loaded COMPETITORS extraction prompt from SEARCH.yaml")
        except Exception as e:
            logger.warning(f"  Could not load SEARCH.yaml prompt, using fallback: {e}")
        
        user_message = f"Search results:\n\n{combined_results}\n\nOriginal product: {product.get('device')} by {product.get('company')}"
        
        response = await _call_openai_async(
            client=client,
            system_prompt=system_prompt,
            user_message=user_message,
            model="gpt-4o-mini",
            temperature=0.1,
            timeout=30.0
        )
        
        competitors = json.loads(response)
        if not isinstance(competitors, list):
            competitors = [competitors]
        
        # Filter out source product and add rank to remaining
        competitors_ranked = []
        source_company_lower = source_company.lower()
        
        for comp in competitors:
            comp_company = (comp.get("company") or "").strip()
            
            # Skip if it's the same company as source
            if comp_company.lower() == source_company_lower:
                logger.info(f"  Skipping competitor from same company: {comp_company}")
                continue
            
            # Add rank and keep
            comp["rank"] = len(competitors_ranked) + 1
            competitors_ranked.append(comp)
            
            # Only keep top 3
            if len(competitors_ranked) >= 3:
                break
        
        logger.info(f"  Extracted {len(competitors_ranked)} competitors via LLM (filtered)")
        return competitors_ranked
        
    except json.JSONDecodeError as e:
        logger.warning(f"  LLM extraction failed: {e}, falling back to heuristic")
        return _extract_competitors_heuristic(combined_results)
    except Exception as e:
        logger.error(f"  Extraction failed: {e}", exc_info=True)
        return []


def _extract_competitors_heuristic(text: str) -> List[Dict[str, Any]]:
    """
    Fallback heuristic extraction of competitor products from text.
    Looks for company names and device names in search results.
    """
    # Simple heuristic: look for capitalized phrases that might be company/device names
    # This is a simplified approach; the LLM method is preferred
    logger.info("  Using heuristic competitor extraction (LLM unavailable)")
    
    # Extract potential company names (all caps or Title Case)
    company_pattern = r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:Inc|LLC|Corp|Ltd|Corporation|Company)"
    companies = re.findall(company_pattern, text)
    
    competitors = []
    for i, company in enumerate(companies[:3], 1):
        competitors.append({
            "company": company,
            "device": f"Medical Device {i}",  # Placeholder
            "description": "Competitor medical device (heuristic extraction)",
            "rank": i
        })
    
    return competitors


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
                        try:
                            logger.info(f"  Creating new product for competitor: {competitor_device}")
                            competitor_product_id = await db.fetchval(
                                """INSERT INTO public.products (device, company, org_id, status_id) 
                                   VALUES ($1, $2, $3, 1) 
                                   RETURNING id""",
                                competitor_device,
                                competitor_company,
                                competitor_org_id
                            )
                        except Exception as e:
                            logger.warning(f"  Could not create competitor product: {e}")
                
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
