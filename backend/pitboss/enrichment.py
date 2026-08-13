"""
Organization Data Enrichment Agents

ENRICH Workflow:
  model.validateOrgName → model.searchForEnrichmentData → model.verifyExtractionResults → tool.enrichOrgDatabase
  
Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
"""

import logging
from typing import Tuple, Dict, Any, Optional, List
import re
import httpx
import json
import html
from difflib import SequenceMatcher
from openai import OpenAI
from urllib.parse import quote
import os
import asyncio
import yaml
from pathlib import Path
from datetime import datetime
from .logging_util import log_event

try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# Load prompts from YAML configuration files
# ============================================================================

def load_search_prompts() -> Dict[str, str]:
    """
    Load extraction prompts from prompts/rules/SEARCH.yaml.
    Resolves path relative to the backend directory.
    """
    try:
        # Find the backend directory and locate SEARCH.yaml
        backend_dir = Path(__file__).parent.parent  # backend/
        search_yaml_path = backend_dir / "../prompts/rules/SEARCH.yaml"
        search_yaml_path = search_yaml_path.resolve()
        
        if not search_yaml_path.exists():
            logger.warning(f"SEARCH.yaml not found at {search_yaml_path}, using fallback prompts")
            return {"extraction_prompt": None}
        
        with open(search_yaml_path, "r") as f:
            config = yaml.safe_load(f)
        
        if not config or "SEARCH" not in config:
            logger.warning(f"SEARCH section not found in {search_yaml_path}, using fallback prompts")
            return {"extraction_prompt": None}
        
        search_config = config["SEARCH"]
        extraction_prompt = search_config.get("extraction_prompt")
        
        if not extraction_prompt:
            logger.warning("extraction_prompt not found in SEARCH.yaml")
            return {"extraction_prompt": None}
        
        logger.info(f"Loaded SEARCH prompts from {search_yaml_path}")
        return {"extraction_prompt": extraction_prompt}
        
    except Exception as e:
        logger.error(f"Failed to load SEARCH.yaml: {str(e)}", exc_info=True)
        return {"extraction_prompt": None}


# Cache loaded prompts
_SEARCH_PROMPTS = load_search_prompts()


# ============================================================================
# Model.validateOrgName - Lookup organization in database
# ============================================================================

async def agent_validate_org_name(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.validateOrgName (ENRICH flow)
    
    RESPONSIBILITY: Find organization in database by fuzzy matching against raw_text.
    Extract org name from message like "enrich 3D Systems Inc" and look it up.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.validateOrgName] Validating org name in database...")
    
    try:
        raw_text = message_body.get("raw_text", "").strip()
        
        # Extract org name from "enrich <ORG_NAME>" or similar patterns
        if not raw_text:
            reason = "Empty message - cannot extract org name"
            logger.warning(f"  Decision: no (confidence: 0.95) - {reason}")
            return ("no", 0.95, reason)
        
        # Strip "enrich " prefix if present
        org_name = raw_text
        if org_name.lower().startswith("enrich "):
            org_name = org_name[7:].strip()
        
        # Remove trailing "with funding" or "with revenue" etc
        for suffix in [" with funding", " with revenue", " with sales"]:
            if org_name.lower().endswith(suffix):
                org_name = org_name[:-len(suffix)].strip()
        
        if not org_name or len(org_name) < 2:
            reason = f"Invalid org name extracted: '{org_name}'"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        # Query database for matching organizations
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        # Query: find orgs with similar names (case-insensitive)
        # Use PostgreSQL similarity or simple ILIKE
        try:
            # Try exact match first
            result = await db.fetchrow(
                "SELECT id, name FROM public.orgs WHERE LOWER(name) = LOWER($1) LIMIT 1",
                org_name
            )
            
            if result:
                message_body["org_id"] = result["id"]
                message_body["org_name"] = result["name"]
                message_body["org_match_confidence"] = 1.0
                
                reason = f"Exact match found: '{result['name']}' (id={result['id']})"
                logger.info(f"  Decision: yes (confidence: 0.99) - {reason}")
                return ("yes", 0.99, reason)
            
            # Try fuzzy match - get top 10 candidates
            candidates = await db.fetch(
                "SELECT id, name FROM public.orgs WHERE name ILIKE $1 LIMIT 10",
                f"%{org_name}%"
            )
            
            if candidates:
                # Find best fuzzy match using SequenceMatcher
                best_match = None
                best_ratio = 0.0
                
                for candidate in candidates:
                    ratio = SequenceMatcher(None, org_name.lower(), candidate["name"].lower()).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = candidate
                
                # Threshold: 0.8 confidence
                if best_ratio >= 0.80:
                    message_body["org_id"] = best_match["id"]
                    message_body["org_name"] = best_match["name"]
                    message_body["org_match_confidence"] = best_ratio
                    
                    reason = f"Fuzzy match (confidence {best_ratio:.2f}): '{org_name}' → '{best_match['name']}' (id={best_match['id']})"
                    logger.info(f"  Decision: yes (confidence: {best_ratio:.2f}) - {reason}")
                    return ("yes", best_ratio, reason)
                else:
                    reason = f"Fuzzy matches found but confidence too low (best: {best_ratio:.2f})"
                    logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
                    return ("no", 0.80, reason)
            
            # No matches found
            reason = f"Organization '{org_name}' not found in database"
            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
            return ("no", 0.85, reason)
            
        except Exception as e:
            reason = f"Database query failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Validation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# Model.searchForEnrichmentData - Search web for funding/revenue data
# ============================================================================

async def _exa_search(
    client: Any,
    query: str,
    num_results: int = 10,
    max_chars: int = 1500,
) -> List[Dict[str, Any]]:
    """
    Run a single Exa search and return normalized result dicts.

    Each dict has: query, snippet, source, url. Search errors are logged and
    an empty list is returned so one failing query never aborts the whole
    enrichment search.
    """
    logger.info(f"  Searching Exa: {query}")
    results: List[Dict[str, Any]] = []
    try:
        response = await asyncio.to_thread(
            client.search,
            query,
            num_results=num_results,
            type="auto",
            contents={
                "highlights": True,
                "text": True,
            },
        )
    except Exception as e:
        logger.error(f"  Exa search error for '{query}': {str(e)}", exc_info=True)
        return results

    if response and hasattr(response, "results") and response.results:
        for result in response.results[:3]:  # top 3 per query
            snippet = ""
            # Prefer full text, fallback to highlights, then summary
            if hasattr(result, "text") and result.text:
                snippet = result.text[:max_chars]
            elif hasattr(result, "highlights") and result.highlights:
                snippet = " ".join(result.highlights)
            elif hasattr(result, "summary"):
                snippet = result.summary[:500]

            if snippet.strip():
                results.append({
                    "query": query,
                    "snippet": snippet.strip(),
                    "source": "exa",
                    "url": getattr(result, "url", ""),
                })
    else:
        logger.warning(f"  No Exa search results found for '{query}'")

    return results


async def agent_search_for_enrichment_data(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchForEnrichmentData (ENRICH flow)
    
    RESPONSIBILITY: Search the web for funding/revenue data using DuckDuckGo.
    For now, return mock data to allow flow testing. Production: integrate SerpAPI or similar.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchForEnrichmentData] Searching for enrichment data...")
    
    try:
        org_id = message_body.get("org_id")
        org_name = message_body.get("org_name", "").strip()
        
        if not org_id or not org_name:
            reason = "Organization ID or name missing from context"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        # Search the web using Exa API. Two passes are merged into one pool of
        # snippets so the LLM sees pages covering every target field:
        #   Pass 1 (financials): funding/revenue reliably rank on Crunchbase /
        #     PitchBook / press releases; HQ and founded often ride along on
        #     funding announcements.
        #   Pass 2 (company profile): employees/headcount live on LinkedIn /
        #     ZoomInfo / "About" pages that do not rank for financial language,
        #     so a dedicated profile query is needed to surface them.
        all_results: List[Dict[str, Any]] = []
        exa_api_key = os.getenv("EXA_API_KEY")

        if not exa_api_key:
            reason = "EXA_API_KEY not configured"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)

        if not EXA_AVAILABLE:
            reason = "exa_py package not installed"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)

        try:
            client = Exa(api_key=exa_api_key)

            # Pass 1: financial data (funding + revenue, often HQ/founded too)
            all_results.extend(
                await _exa_search(
                    client,
                    f"{org_name} total funding raised annual revenue financial",
                )
            )

            # Pass 2: company profile (employees / headcount)
            all_results.extend(
                await _exa_search(
                    client,
                    f'"{org_name}" employees headcount team size company size',
                )
            )

            logger.info(f"  Found {len(all_results)} search results across both passes")
        except Exception as e:
            logger.error(f"  Exa search error: {str(e)}", exc_info=True)
        
        # Store search results in message body
        message_body["search_results"] = all_results
        message_body["search_result_count"] = len(all_results)
        
        # Proceed even if no results (LLM will note no data)
        reason = f"Found {len(all_results)} search results for '{org_name}'"
        logger.info(f"  Decision: yes (confidence: 0.90) - {reason}")
        return ("yes", 0.90, reason)
        
    except Exception as e:
        reason = f"Search failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.50) - {reason}", exc_info=True)
        return ("no", 0.50, reason)


# ============================================================================
# Model.verifyExtractionResults - Parse search results with LLM
# ============================================================================

async def agent_verify_extraction_results(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyExtractionResults (ENRICH flow)
    
    RESPONSIBILITY: Use GPT-4o-mini to parse search results and extract:
    - Currency amounts ($100M, $1.2B, etc)
    - Dates (Series A 2022, founded 2019)
    - Data quality and recency
    - Calculate confidence score
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.verifyExtractionResults] Verifying extraction results with LLM...")
    
    try:
        org_name = message_body.get("org_name", "").strip()
        search_results = message_body.get("search_results", [])
        
        if not search_results:
            reason = "No search results to extract from"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        # Prepare snippets for LLM
        snippets_text = "\n\n".join([
            f"[{r.get('query')}]: {r.get('snippet', '')}"
            for r in search_results
        ])
        
        # Use LLM to extract structured data
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            reason = "OpenAI API key not configured - cannot parse search results"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)
        
        try:
            client = OpenAI(api_key=api_key)
            
            # Load extraction prompt from SEARCH.yaml
            extraction_prompt_template = _SEARCH_PROMPTS.get("extraction_prompt")
            if not extraction_prompt_template:
                reason = "Extraction prompt template not loaded from SEARCH.yaml"
                logger.error(f"  Decision: no (confidence: 0.50) - {reason}")
                return ("no", 0.50, reason)
            
            # Format prompt with dynamic values
            prompt = extraction_prompt_template.format(
                org_name=org_name,
                snippets_text=snippets_text
            )
            
            response = await asyncio.to_thread(
                lambda: client.chat.completions.create(
                    model="gpt-4o-mini",
                    temperature=0.0,
                    messages=[
                        {"role": "system", "content": "You are a financial data extraction expert. Return valid JSON only."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    timeout=10.0,
                )
            )
            
            extracted_data = json.loads(response.choices[0].message.content)
            confidence = float(extracted_data.get("confidence", 0.5))
            
            # Log extracted data for debugging
            logger.info(f"  Extracted data keys: {list(extracted_data.keys())}")
            logger.info(f"  Description: {extracted_data.get('description')}")
            logger.info(f"  Headquarters: {extracted_data.get('headquarters')}")
            logger.info(f"  Employees: {extracted_data.get('employees')}")
            logger.info(f"  Date Founded: {extracted_data.get('date_founded')}")
            
            # Store extracted data in message body
            message_body["extracted_data"] = extracted_data
            message_body["extraction_confidence"] = confidence
            
            # Only approve if confidence > 0.7
            if confidence >= 0.70:
                annual_revenue = extracted_data.get('annual_revenue') or 0
                total_funding = extracted_data.get('total_funding_raised') or 0
                
                # Format revenue/funding for logging
                revenue_str = f"${annual_revenue:,}" if annual_revenue else "$0"
                funding_str = f"${total_funding:,}" if total_funding else "$0"
                
                reason = f"Extraction successful: revenue={revenue_str}, total_funding={funding_str}, confidence={confidence:.2f}"
                logger.info(f"  Decision: yes (confidence: {confidence:.2f}) - {reason}")
                return ("yes", confidence, reason)
            else:
                reason = f"Extraction confidence too low: {confidence:.2f} (need >= 0.70)"
                logger.warning(f"  Decision: no (confidence: {confidence:.2f}) - {reason}")
                return ("no", confidence, reason)
            
        except json.JSONDecodeError as e:
            reason = f"LLM response is not valid JSON: {str(e)}"
            logger.warning(f"  Decision: no (confidence: 0.60) - {reason}")
            return ("no", 0.60, reason)
        
    except Exception as e:
        reason = f"Extraction failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.50) - {reason}", exc_info=True)
        return ("no", 0.50, reason)


# ============================================================================
# Tool.enrichOrgDatabase - Update organization with extracted data
# ============================================================================

async def agent_enrich_org_database(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.enrichOrgDatabase (ENRICH flow, after HITL approval)
    
    RESPONSIBILITY: Update orgs table with extracted data after user approval.
    - Update estimated_annual_sales
    - Update updated_at timestamp
    - Log enrichment event
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [tool.enrichOrgDatabase] Updating organization record...")
    
    try:
        org_id = message_body.get("org_id")
        org_name = message_body.get("org_name", "").strip()
        extracted_data = message_body.get("extracted_data", {})
        raw_text = message_body.get("raw_text", "").strip()  # User approval comment
        
        if not org_id:
            reason = "Organization ID missing"
            logger.error(f"  Decision: no (confidence: 0.95) - {reason}")
            return ("no", 0.95, reason)
        
        if not extracted_data:
            reason = "No extracted data to write"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        try:
            # Pass None through when extraction yields nothing so the UPDATE
            # below preserves the existing value (preserve-if-null, same pattern
            # used for the text/date fields). Coercing null to 0 here would
            # clobber a previously stored funding/sales figure on every re-run.
            annual_revenue = extracted_data.get("annual_revenue")
            total_funding = extracted_data.get("total_funding_raised")
            description = extracted_data.get("description")
            headquarters = extracted_data.get("headquarters")
            employees = extracted_data.get("employees")
            if employees is not None:
                employees = int(employees)
            date_founded = extracted_data.get("date_founded")  # ISO 8601 string or YYYY
            
            # Convert date_founded string to datetime object if provided
            date_founded_ts = None
            if date_founded:
                try:
                    # Handle both YYYY-MM-DD and YYYY formats
                    if len(str(date_founded)) == 4:  # Just year
                        date_founded_ts = datetime.strptime(f"{date_founded}-01-01", "%Y-%m-%d")
                    else:
                        # Try to parse ISO format (YYYY-MM-DD or other formats)
                        date_founded_ts = datetime.fromisoformat(str(date_founded))
                except Exception as e:
                    logger.warning(f"  Could not parse date_founded '{date_founded}': {str(e)}")
            
            # Update orgs table with enriched data. Every field uses the
            # preserve-if-null pattern: a null extraction keeps the existing
            # column value, so re-running enrichment (e.g. to fill employees)
            # never clobbers a previously stored funding/sales figure. funding
            # and estimated_annual_sales are NUMERIC; employees is INTEGER.
            update_query = """
                UPDATE public.orgs 
                SET estimated_annual_sales = CASE WHEN $1::NUMERIC IS NOT NULL THEN $1::NUMERIC ELSE estimated_annual_sales END,
                    funding = CASE WHEN $2::NUMERIC IS NOT NULL THEN $2::NUMERIC ELSE funding END,
                    description = CASE WHEN $3::TEXT IS NOT NULL THEN $3::TEXT ELSE description END,
                    headquarters = CASE WHEN $4::TEXT IS NOT NULL THEN $4::TEXT ELSE headquarters END,
                    employees = CASE WHEN $5::INTEGER IS NOT NULL THEN $5::INTEGER ELSE employees END,
                    date_founded = CASE WHEN $6::TIMESTAMP IS NOT NULL THEN $6::TIMESTAMP ELSE date_founded END,
                    updated_at = now()
                WHERE id = $7
                RETURNING id, name, estimated_annual_sales, funding, description, headquarters, employees, date_founded
            """
            
            result = await db.fetchrow(update_query, annual_revenue, total_funding, description, headquarters, employees, date_founded_ts, org_id)
            
            if result:
                # Log enrichment using shared logging utility
                await log_event(
                    db,
                    "ENRICH_COMPLETE",
                    {
                        "org_id": org_id,
                        "org_name": result['name'],
                        "estimated_annual_sales": annual_revenue,
                        "total_funding": total_funding,
                        "fields_updated": sum([(annual_revenue or 0) > 0, (total_funding or 0) > 0, description is not None, headquarters is not None, employees is not None, date_founded_ts is not None]),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                )
                
                # Report the actual merged DB state (preserved + new), not the
                # possibly-None extracted values, so the log reflects what was
                # really stored.
                rev_now = result['estimated_annual_sales']
                fund_now = result['funding']
                rev_str = f"${rev_now:,.0f}" if rev_now else "$0"
                fund_str = f"${fund_now:,.0f}" if fund_now else "$0"
                reason = f"✅ Updated {result['name']}: estimated_annual_sales={rev_str}, total_funding={fund_str}"
                logger.info(f"  Decision: yes (confidence: 0.98) - {reason}")
                return ("yes", 0.98, reason)
            else:
                reason = f"Organization record not found or update failed (id={org_id})"
                logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
                return ("no", 0.85, reason)
                
        except Exception as e:
            reason = f"Database update failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Enrichment failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)
