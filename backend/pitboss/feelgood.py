"""
Product Superiority Agent Flow (FEELGOOD Workflow)

FEELGOOD Workflow:
  model.Capo → model.validateProductId → model.searchForSuperiority
  → model.extractSuperiorityClaim → tool.updateProductSuperiority

Extracts competitive advantage claims from web search results using Exa API
and LLM-based analysis of how products differentiate from competitors.

Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
"""

import logging
from typing import Tuple, Dict, Any, Optional
import json
from datetime import datetime
import os

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


# ============================================================================
# Model.validateProductId - Verify product exists in database
# ============================================================================

async def agent_validate_product_id(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.validateProductId (FEELGOOD flow)
    
    RESPONSIBILITY: Find product in database by ID.
    Extract product_id from message and verify it exists with required fields.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.validateProductId] Validating product ID in database...")
    
    try:
        raw_text = message_body.get("raw_text", "").strip()
        product_id = message_body.get("product_id")
        
        # Extract product ID from raw_text if not already set
        # Formats: "feelgood 42", "products 1-50", etc
        if not product_id and raw_text:
            # Try to extract number from text
            import re
            matches = re.findall(r"\d+", raw_text)
            if matches:
                try:
                    product_id = int(matches[0])
                    message_body["product_id"] = product_id
                except (ValueError, IndexError):
                    pass
        
        if not product_id:
            reason = "No product ID found in message"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        # Validate product exists in database
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        try:
            # Query: find product by ID with required fields
            result = await db.fetchrow(
                """
                SELECT id, submission_number, device, company, intended_use, indications_for_use, device_description
                FROM public.products
                WHERE id = $1 AND deleted_at IS NULL
                """,
                product_id
            )
            
            if not result:
                reason = f"Product ID {product_id} not found in database"
                logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
                return ("no", 0.85, reason)
            
            # Validate required fields for superiority search
            missing_fields = []
            if not result.get("company"):
                missing_fields.append("company")
            if not result.get("device"):
                missing_fields.append("device")
            
            if missing_fields:
                reason = f"Product {product_id} missing required fields: {', '.join(missing_fields)}"
                logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
                return ("no", 0.80, reason)
            
            # Store product data for next agent
            message_body["product_id"] = product_id
            message_body["product"] = dict(result)
            
            reason = f"Product {product_id} found: {result['device']} by {result['company']}"
            logger.info(f"  Decision: yes (confidence: 0.99) - {reason}")
            return ("yes", 0.99, reason)
            
        except Exception as e:
            reason = f"Database query failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Validation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# Model.searchForSuperiority - Search web for competitive advantages
# ============================================================================

async def agent_search_for_superiority(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchForSuperiority (FEELGOOD flow)
    
    RESPONSIBILITY: Search web for competitive advantage information using Exa API.
            Constructs query from product company, device name, and intended_use.
            Returns top search results for LLM analysis.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchForSuperiority] Searching web for superiority claims...")
    
    try:
        product = message_body.get("product")
        if not product:
            reason = "Product data not available"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        # Extract search parameters (handle None values gracefully)
        company = (product.get("company") or "").strip()
        device = (product.get("device") or "").strip()
        intended_use = (product.get("intended_use") or "").strip()
        indications_for_use = (product.get("indications_for_use") or "").strip()
        device_description = (product.get("device_description") or "").strip()
        
        # If intended_use is empty, construct it from FDA sources
        if not intended_use:
            # Every medical device has an intended use - if not in DB, construct from available info
            # Intended Use: The general function or purpose of the device as claimed by manufacturer
            # Pattern: medical devices are cleared for specific clinical applications
            # Examples: "Cardiac imaging", "Automated ECG analysis", "Breast lesion detection"
            # This is extracted from the FDA clearance summary
            submission_number = product.get("submission_number", "")
            if submission_number:
                # Construct a reasonable intended_use from device name and submission context
                # In a full implementation, this would query FDA Devices@FDA database
                # For now, we use device + company as context for web search
                intended_use = f"Clinical application for {device} by {company}"
            else:
                intended_use = f"Clinical application for {device}"
        
        # Build search query
        # Priority: device_description > indications_for_use > intended_use > device name
        search_context = device_description or indications_for_use or intended_use or device
        if not search_context:
            search_context = device
        
        # Build the search query
        query = f"how is the {search_context} from {company} superior to competing or existing solutions"
        
        logger.info(f"  Search query: {query}")
        
        # Check if Exa is available
        if not EXA_AVAILABLE:
            reason = "Exa search library not installed"
            logger.warning(f"  Decision: no (confidence: 0.50) - {reason}")
            return ("no", 0.50, reason)
        
        exa_api_key = os.getenv("EXA_API_KEY")
        if not exa_api_key:
            reason = "EXA_API_KEY environment variable not set"
            logger.warning(f"  Decision: no (confidence: 0.50) - {reason}")
            return ("no", 0.50, reason)
        
        try:
            # Search using Exa
            exa = Exa(api_key=exa_api_key)
            results = exa.search(
                query,
                num_results=5,
                type="neural",
                highlights=True
            )
            
            if not results or not results.results:
                reason = f"No search results found for: {query}"
                logger.warning(f"  Decision: no (confidence: 0.60) - {reason}")
                return ("no", 0.60, reason)
            
            # Extract highlights and URLs for LLM analysis
            search_results = []
            for result in results.results[:3]:  # Top 3 results
                search_results.append({
                    "url": result.url,
                    "title": result.title,
                    "snippet": result.text if hasattr(result, 'text') else "",
                    "highlights": result.highlights if hasattr(result, 'highlights') else []
                })
            
            message_body["search_query"] = query
            message_body["search_results"] = search_results
            
            reason = f"Found {len(search_results)} results for product superiority analysis"
            logger.info(f"  Decision: yes (confidence: 0.95) - {reason}")
            return ("yes", 0.95, reason)
            
        except Exception as e:
            reason = f"Exa search failed: {str(e)}"
            logger.warning(f"  Decision: no (confidence: 0.50) - {reason}", exc_info=True)
            return ("no", 0.50, reason)
        
    except Exception as e:
        reason = f"Search operation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# Model.extractSuperiorityClaim - Parse search results via LLM
# ============================================================================

async def agent_extract_superiority_claim(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.extractSuperiorityClaim (FEELGOOD flow)
    
    RESPONSIBILITY: Use LLM to extract competitive advantage claims from search results.
    Analyzes top 3 search results and produces structured superiority narrative.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.extractSuperiorityClaim] Extracting superiority claims from search results...")
    
    try:
        product = message_body.get("product")
        search_results = message_body.get("search_results", [])
        
        if not search_results:
            reason = "No search results available for analysis"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        if not product:
            reason = "Product data not available"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        # Prepare context for LLM
        company = product.get("company", "")
        device = product.get("device", "")
        indicated_use = product.get("indicated_use", "")
        
        # Build search results text for LLM
        search_text = "\n\n".join([
            f"Result {i+1}: {r['title']}\nURL: {r['url']}\nSnippet: {r['snippet']}"
            for i, r in enumerate(search_results)
        ])
        
        # Construct prompt for LLM
        prompt = f"""Analyze the following search results about how the '{device}' from '{company}' 
is superior to competing solutions. Extract a concise summary (2-3 sentences) of the key 
competitive advantages. Focus on technical superiority, clinical benefits, or market differentiation.

Product: {device}
Company: {company}
Indicated Use: {indicated_use}

Search Results:
{search_text}

Provide a concise superiority claim (2-3 sentences) that highlights how this product differentiates from competitors."""
        
        try:
            client = OpenAI()
            response = client.messages.create(
                model="gpt-4o",
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            superiority_claim = response.content[0].text.strip()
            
            if not superiority_claim or len(superiority_claim) < 20:
                reason = "LLM extraction produced insufficient text"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            message_body["superiority_claim"] = superiority_claim
            message_body["extraction_confidence"] = 0.85
            
            reason = f"Extracted superiority claim ({len(superiority_claim)} chars)"
            logger.info(f"  Decision: yes (confidence: 0.85) - {reason}")
            return ("yes", 0.85, reason)
            
        except Exception as e:
            reason = f"LLM extraction failed: {str(e)}"
            logger.warning(f"  Decision: no (confidence: 0.40) - {reason}", exc_info=True)
            return ("no", 0.40, reason)
        
    except Exception as e:
        reason = f"Extraction operation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


# ============================================================================
# Tool.updateProductSuperiority - Write result to database
# ============================================================================

async def tool_update_product_superiority(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.updateProductSuperiority (FEELGOOD flow)
    
    RESPONSIBILITY: Update products table with extracted superiority claim.
    Writes superiority_claim to products.superiority column.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [tool.updateProductSuperiority] Updating product record...")
    
    try:
        product_id = message_body.get("product_id")
        superiority_claim = message_body.get("superiority_claim")
        
        if not product_id or not superiority_claim:
            reason = "Missing product_id or superiority_claim"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        try:
            # Update product with superiority claim
            await db.execute(
                """
                UPDATE public.products
                SET superiority = $1, updated_at = NOW()
                WHERE id = $2
                """,
                superiority_claim,
                product_id
            )
            
            # Log the operation
            await db.execute(
                """
                INSERT INTO public.system_log (event_type, entity_table, entity_id, details)
                VALUES ($1, $2, $3, $4)
                """,
                "FEELGOOD_COMPLETE",
                "products",
                product_id,
                json.dumps({
                    "superiority_claim": superiority_claim[:200] + ("..." if len(superiority_claim) > 200 else ""),
                    "claim_length": len(superiority_claim),
                    "timestamp": datetime.utcnow().isoformat()
                })
            )
            
            reason = f"Product {product_id} superiority claim updated ({len(superiority_claim)} chars)"
            logger.info(f"  Decision: yes (confidence: 0.99) - {reason}")
            return ("yes", 0.99, reason)
            
        except Exception as e:
            reason = f"Database update failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Update operation failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)
