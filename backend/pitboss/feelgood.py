"""
Product Superiority Agent Flow (FEELGOOD Workflow)

FEELGOOD Workflow:
  model.Capo → model.validateProductId → model.searchForSuperiority
  → tool.updateProductSuperiority

Extracts competitive advantage claims for products using Exa's Answer API,
which returns a citation-backed narrative of how each device differentiates
from competing solutions.

Each agent returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
"""

import logging
import re
from typing import Tuple, Dict, Any, Optional
import json
from datetime import datetime
import os
from .logging_util import log_event

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
        product_device = message_body.get("product_device")  # Device name for lookup
        
        # Extract product ID or device name from raw_text if not already set
        # Formats: "feelgood 42", "competitors HeartLogic", etc
        if not product_id and not product_device and raw_text:
            # Try to extract number from text (product ID)
            import re
            matches = re.findall(r"\d+", raw_text)
            if matches:
                try:
                    product_id = int(matches[0])
                    message_body["product_id"] = product_id
                except (ValueError, IndexError):
                    pass
            else:
                # No number found; treat as device name
                # Extract everything after the workflow verb
                parts = raw_text.split(None, 1)
                if len(parts) > 1:
                    product_device = parts[1].strip()
                    message_body["product_device"] = product_device
        
        if not product_id and not product_device:
            reason = "No product ID or device name found in message"
            logger.warning(f"  Decision: no (confidence: 0.90) - {reason}")
            return ("no", 0.90, reason)
        
        # Validate product exists in database
        db = message_body.get("_db")
        if not db:
            reason = "Database connection not available"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}")
            return ("no", 0.10, reason)
        
        try:
            # Query: find product by ID or device name with required fields
            result = None
            if product_id:
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
            elif product_device:
                result = await db.fetchrow(
                    """
                    SELECT id, submission_number, device, company, intended_use, indications_for_use, device_description
                    FROM public.products
                    WHERE device = $1 AND deleted_at IS NULL
                    """,
                    product_device
                )
                if not result:
                    reason = f"Product '{product_device}' not found in database"
                    logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
                    return ("no", 0.85, reason)
                product_id = result['id']  # Store ID for future use
                message_body["product_id"] = product_id
            
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


# Cache for SEARCH.yaml config
_SEARCH_CONFIG_CACHE_FG: Optional[Dict[str, Any]] = None

def _load_search_config_feelgood() -> Dict[str, Any]:
    """Load and cache the SEARCH section from prompts/rules/SEARCH.yaml."""
    global _SEARCH_CONFIG_CACHE_FG
    if _SEARCH_CONFIG_CACHE_FG is not None:
        return _SEARCH_CONFIG_CACHE_FG
    try:
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "prompts", "rules", "SEARCH.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        _SEARCH_CONFIG_CACHE_FG = (yaml_data.get("SEARCH") or {}) if isinstance(yaml_data, dict) else {}
        logger.info("  ✓ Loaded SEARCH.yaml superiority extraction config")
    except Exception as e:
        logger.warning(f"  Could not load SEARCH.yaml, using defaults: {e}")
        _SEARCH_CONFIG_CACHE_FG = {}
    return _SEARCH_CONFIG_CACHE_FG

# Load prompts once at module load time
def _load_superiority_prompts():
    """Load system and user prompts for superiority extraction from SEARCH.yaml."""
    search_config = _load_search_config_feelgood()
    
    system_prompt = search_config.get(
        "superiority_extraction_system_prompt",
        "You are advising the CEO. Identify the single most important competitive superiority."
    )
    user_prompt_template = search_config.get(
        "superiority_extraction_user_prompt",
        "Given this product and its competitors, identify the key distinction.\n{exa_answer}"
    )
    
    return system_prompt, user_prompt_template

_SUPERIORITY_EXTRACTION_SYSTEM_PROMPT, _SUPERIORITY_EXTRACTION_USER_TEMPLATE = _load_superiority_prompts()


def _clean_superiority_text(text: str) -> str:
    """Normalize Exa Answer API output into clean single-paragraph prose.

    Strips inline citation markers (e.g. "[1][2]"), removes leading bullet /
    numbered-list markers on each line, flattens newlines into spaces, and
    collapses runs of whitespace. Keeps inline labels like "Predictive Lead
    Time:" intact since they carry useful structure once flattened.
    """
    if not text:
        return ""
    # Strip inline citation markers like [1], [2][3]
    text = re.sub(r"\s*\[\d+\]", "", text)
    # Strip leading bullet markers on each line (-, –, •, *)
    text = re.sub(r"(?m)^\s*[-–•*]\s+", "", text)
    # Strip leading numbered-list markers on each line (1. , 2. ) — only at
    # line starts so mid-sentence numbers like "48 minutes" are preserved
    text = re.sub(r"(?m)^\s*\d+\.\s+", "", text)
    # Flatten newlines (and surrounding whitespace) into single spaces
    text = re.sub(r"\s*\n\s*", " ", text)
    # Collapse any remaining runs of whitespace
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


# ============================================================================
# Model.searchForSuperiority - Search web for competitive advantages
# ============================================================================

async def agent_search_for_superiority(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchForSuperiority (FEELGOOD flow)
    
    RESPONSIBILITY: Use Exa's Answer API to produce a superiority narrative
            for the product. Constructs a query from product company and device
            name, calls exa.answer(model="exa"), and stores the returned answer
            directly as message_body["superiority_claim"] — no separate LLM
            extraction step is needed.
    
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
        
        # Build simple, effective search query
        # Keep it short and direct for better search results
        query = f"How is {device} from {company} better than other solutions in the market?"
        
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
            # Use Exa's Answer API to find superior features and advantages
            # Then use LLM to extract a crisp, CEO-focused one-sentence claim (≤35 words)
            exa = Exa(api_key=exa_api_key)
            answer_response = exa.answer(query, model="exa")

            superiority_answer = ""
            if answer_response and hasattr(answer_response, "answer"):
                superiority_answer = (answer_response.answer or "").strip()

            if not superiority_answer or len(superiority_answer) < 20:
                reason = f"Exa Answer API returned no substantial answer for: {query}"
                logger.warning(f"  Decision: no (confidence: 0.60) - {reason}")
                return ("no", 0.60, reason)

            # Store Exa's answer for LLM extraction
            message_body["search_query"] = query
            message_body["search_results"] = [{
                "url": "exa-answer",
                "title": "Exa Answer API",
                "snippet": superiority_answer,
            }]
            message_body["exa_answer"] = superiority_answer
            
            # Now route to LLM extraction which will refine into CEO-focused claim
            reason = f"Exa found competitive advantage info ({len(superiority_answer)} chars)"
            logger.info(f"  Decision: yes (confidence: 0.88) - {reason}")
            return ("yes", 0.88, reason)

        except Exception as e:
            reason = f"Exa Answer API call failed: {str(e)}"
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
    
    RESPONSIBILITY: Extract a crisp CEO-focused superiority claim from Exa results.
    Produces a single sentence (max 35 words) identifying one key commercial advantage.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.extractSuperiorityClaim] Extracting CEO-focused superiority claim...")
    
    try:
        product = message_body.get("product")
        exa_answer = message_body.get("exa_answer", "")
        
        if not exa_answer:
            reason = "No Exa answer available for extraction"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        if not product:
            reason = "Product data not available"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        # Prepare context for LLM
        company = product.get("company", "")
        device = product.get("device", "")
        intended_use = product.get("intended_use", "")
        competitors_str = product.get("competitors", "")  # Comma-separated list from DB
        
        # Build user prompt from template
        user_prompt = _SUPERIORITY_EXTRACTION_USER_TEMPLATE.format(
            device=device,
            company=company,
            intended_use=intended_use,
            competitors=competitors_str if competitors_str else "(Not yet specified)",
            exa_answer=exa_answer
        )
        
        try:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                reason = "OPENAI_API_KEY not set"
                logger.warning(f"  Decision: no (confidence: 0.60) - {reason}")
                return ("no", 0.60, reason)
            
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {
                        "role": "system",
                        "content": _SUPERIORITY_EXTRACTION_SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": user_prompt
                    }
                ]
            )
            
            superiority_claim = response.choices[0].message.content.strip()
            
            if not superiority_claim:
                reason = "LLM extraction produced no text"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            # Enforce 35-word limit
            word_count = len(superiority_claim.split())
            if word_count > 35:
                logger.warning(f"  Superiority claim exceeded 35 words ({word_count}), truncating...")
                words = superiority_claim.split()
                superiority_claim = " ".join(words[:35])
                # Ensure it ends with a period if not already
                if not superiority_claim.endswith("."):
                    superiority_claim += "."
            
            message_body["superiority_claim"] = superiority_claim
            message_body["extraction_confidence"] = 0.88
            
            reason = f"Extracted CEO-focused claim ({word_count} words): {superiority_claim[:60]}..."
            logger.info(f"  Decision: yes (confidence: 0.88) - {reason}")
            return ("yes", 0.88, reason)
            
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
            
            # Log the operation using shared logging utility
            await log_event(
                db,
                "FEELGOOD_COMPLETE",
                {
                    "product_id": product_id,
                    "superiority_claim": superiority_claim[:200] + ("..." if len(superiority_claim) > 200 else ""),
                    "claim_length": len(superiority_claim),
                    "extraction_source": message_body.get("extraction_source", "llm_extraction"),
                    "timestamp": datetime.utcnow().isoformat()
                }
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
