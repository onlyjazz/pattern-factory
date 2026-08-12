"""
Profile Agent Flow for FDA Device Profiling

Extracts official device data from FDA Devices@FDA database:
- device_description: Official description from FDA clearance documents
- intended_use: The general function/purpose of the device as claimed by manufacturer
- indications_for_use: The specific medical conditions the device treats/diagnoses

Workflow:
1. model.validateProductId - Verify product exists
2. model.searchFDADatabase - Query FDA Devices@FDA for submission
3. model.extractDeviceProfile - Use LLM to parse clearance summary and extract profile data
4. tool.updateProductProfile - Update database with extracted data

Reference: https://www.fda.gov/cdrh/devicesatfda/
"""

import asyncio
import json
import logging
import os
import re
from typing import Tuple, Dict, Any, Optional
from datetime import datetime
from .logging_util import log_event

logger = logging.getLogger(__name__)

# Configure logger with timestamps
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Check if Exa is available for web search
try:
    from exa_py import Exa
    EXA_AVAILABLE = True
except ImportError:
    EXA_AVAILABLE = False
    logger.warning("Exa library not installed - web search will be unavailable")


# Note: agent_validate_product_id is shared with FEELGOOD workflow
# Both workflows validate products by ID, so we import it from feelgood module
# No duplicate code here - the agent works for both flows


# ============================================================================
# Model.searchFDADatabase - Query FDA Devices@FDA for submission
# ============================================================================

async def agent_search_fda_database(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchFDADatabase (PROFILE flow)
    
    RESPONSIBILITY: Search FDA Devices@FDA for clearance information using Exa.
    Uses strict domain filtering to retrieve official FDA clearance documents.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchFDADatabase] Searching FDA database via Exa for device profile...")
    
    try:
        product = message_body.get("product")
        if not product:
            reason = "Product data not available"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        submission_number = (product.get("submission_number") or "").strip()
        device = (product.get("device") or "").strip()
        company = (product.get("company") or "").strip()
        
        if not submission_number:
            reason = "No submission number available for FDA lookup"
            logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
            return ("no", 0.70, reason)
        
        # Identify submission type
        submission_type = "unknown"
        if submission_number.upper().startswith("K"):
            submission_type = "510k"
        elif submission_number.upper().startswith("P"):
            submission_type = "pma"
        elif submission_number.upper().startswith("DEN"):
            submission_type = "de-novo"
        
        logger.info(f"  Submission type: {submission_type.upper()}")
        logger.info(f"  Searching FDA for: {submission_number}")
        
        # Search FDA via Exa if available
        fda_clearance_text = None
        if EXA_AVAILABLE:
            try:
                exa_api_key = os.getenv("EXA_API_KEY")
                if exa_api_key:
                    fda_clearance_text = await _search_fda_with_exa(
                        submission_number=submission_number,
                        device=device,
                        api_key=exa_api_key
                    )
                    if fda_clearance_text:
                        logger.info(f"  ✓ Retrieved FDA clearance text ({len(fda_clearance_text)} chars)")
                    else:
                        logger.warning(f"  ⚠ No FDA text found for {submission_number}")
            except Exception as e:
                logger.warning(f"  ⚠ Exa search failed: {e}")
        else:
            logger.warning("  ⚠ Exa not available - will use basic information only")
        
        message_body["submission_number"] = submission_number
        message_body["submission_type"] = submission_type
        message_body["fda_clearance_text"] = fda_clearance_text
        message_body["fda_clearance_info"] = {
            "submission_number": submission_number,
            "submission_type": submission_type,
            "device": device,
            "company": company,
            "has_fda_text": bool(fda_clearance_text)
        }
        
        reason = f"FDA {submission_type.upper()} {submission_number} retrieved ({len(fda_clearance_text) if fda_clearance_text else 0} chars)"
        confidence = 0.95 if fda_clearance_text else 0.70
        logger.info(f"  Decision: yes (confidence: {confidence}) - {reason}")
        return ("yes", confidence, reason)
        
    except Exception as e:
        reason = f"FDA database search failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


async def _search_fda_with_exa(submission_number: str, device: str, api_key: str) -> Optional[str]:
    """
    Search FDA Devices@FDA using Exa with highlights to get FDA document snippets.
    Returns cleaned highlights as combined text.
    """
    try:
        exa = Exa(api_key=api_key)
        
        # Simple, direct query: "what is the intended use for <device_name>"
        primary_query = f"what is the intended use for {device}"
        logger.info(f"  Exa query: '{primary_query}'")
        
        # Call Exa search exactly as documented in the working example
        result = exa.search(
            primary_query,
            num_results=10,
            type="auto",
            contents={"highlights": True}
        )
        
        if not result or not hasattr(result, 'results') or not result.results:
            logger.warning(f"  Exa: No results for query '{primary_query}'")
            
            # Fallback: Search with submission number
            logger.info(f"  Attempting fallback search on FDA AI devices table...")
            fallback_query = f"FDA {submission_number}"
            
            fallback_result = exa.search(
                fallback_query,
                num_results=5,
                type="auto",
                contents={"highlights": True}
            )
            
            if fallback_result and hasattr(fallback_result, 'results') and fallback_result.results:
                logger.info(f"  ✓ Fallback search found results")
                # Use highlights from fallback results
                for res in fallback_result.results:
                    if hasattr(res, 'highlights') and res.highlights:
                        if isinstance(res.highlights, list):
                            return "\n\n".join(res.highlights)
                        else:
                            return str(res.highlights)
            
            return None
        
        # Combine highlights from all results
        fda_text_chunks = []
        for res in result.results:
            # Get highlights (snippet of matching FDA document text)
            if hasattr(res, 'highlights') and res.highlights:
                if isinstance(res.highlights, list):
                    fda_text_chunks.extend(res.highlights)
                else:
                    fda_text_chunks.append(str(res.highlights))
                logger.info(f"    Result URL: {getattr(res, 'url', 'N/A')}")
        
        combined_text = "\n\n".join(fda_text_chunks)
        logger.info(f"  Exa: Retrieved {len(result.results)} results, {len(fda_text_chunks)} highlight chunks, total {len(combined_text)} chars")
        
        if combined_text:
            if len(combined_text) < 50:
                logger.warning(f"  ⚠ Exa returned very short highlights")
            else:
                logger.info(f"  ✓ Exa returned substantial FDA content ({len(combined_text)} chars)")
        
        return combined_text if combined_text else None
        
    except Exception as e:
        logger.error(f"  Exa search error: {e}", exc_info=True)
        return None


# ============================================================================
# Model.extractDeviceProfile - Parse FDA documents via LLM
# ============================================================================

async def agent_extract_device_profile(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.extractDeviceProfile (PROFILE flow)
    
    RESPONSIBILITY: Use LLM to extract device profile information from FDA clearance documents.
    Parses cleaned FDA text to extract:
    - Device description (technical architecture, deployment details, algorithmic framework)
    - Intended Use (overarching clinical objective)
    - Indications for Use (specific patient cohort, diseases, settings)
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.extractDeviceProfile] Extracting device profile from FDA sources...")
    
    try:
        product = message_body.get("product")
        submission_number = message_body.get("submission_number")
        fda_clearance_text = message_body.get("fda_clearance_text")
        
        if not product or not submission_number:
            reason = "Missing product or submission data"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        device = product.get("device", "")
        company = product.get("company", "")
        
        logger.info(f"  Device: {device}")
        logger.info(f"  Company: {company}")
        logger.info(f"  Submission: {submission_number}")
        
        # Extract profile using LLM if FDA text is available
        device_description = None
        intended_use = None
        indications_for_use = None
        extraction_source = "fda_devices_database"
        
        if fda_clearance_text:
            logger.info(f"  Using LLM to extract profile from FDA clearance text ({len(fda_clearance_text)} chars)...")
            extracted = await _extract_profile_with_llm(
                fda_text=fda_clearance_text,
                device_name=device,
                company_name=company,
                submission_number=submission_number
            )
            if extracted:
                device_description = extracted.get("device_description")
                intended_use = extracted.get("intended_use")
                indications_for_use = extracted.get("indications_for_use")
                logger.info(f"  ✓ LLM extraction complete")
                if device_description:
                    logger.info(f"    - device_description: {len(device_description)} chars")
                if intended_use:
                    logger.info(f"    - intended_use: {len(intended_use)} chars")
                if indications_for_use:
                    logger.info(f"    - indications_for_use: {len(indications_for_use)} chars")
        else:
            logger.warning(f"  No FDA clearance text available - using fallback")
            device_description = f"{device} by {company}"
        
        profile = {
            "device_description": device_description,
            "intended_use": intended_use,
            "indications_for_use": indications_for_use,
            "source": extraction_source,
            "submission_number": submission_number,
            "extracted_at": datetime.utcnow().isoformat()
        }
        
        message_body["device_profile"] = profile
        
        # Calculate confidence based on what was extracted
        fields_extracted = sum([
            bool(device_description),
            bool(intended_use),
            bool(indications_for_use)
        ])
        confidence = 0.99 if fields_extracted == 3 else (0.85 if fields_extracted >= 1 else 0.70)
        
        reason = f"Device profile extracted ({fields_extracted}/3 fields): {device} ({submission_number})"
        logger.info(f"  Decision: yes (confidence: {confidence}) - {reason}")
        return ("yes", confidence, reason)
        
    except Exception as e:
        reason = f"Profile extraction failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


async def _extract_profile_with_llm(fda_text: str, device_name: str, company_name: str, submission_number: str) -> Optional[Dict[str, Optional[str]]]:
    """
    Use OpenAI LLM to extract device profile from FDA clearance text.
    Uses prompts from SEARCH.yaml (fda_profile_extraction_prompt and fda_profile_user_prompt).
    
    Returns dict with keys: device_description, intended_use, indications_for_use (all Optional[str])
    """
    try:
        import asyncio
        from openai import OpenAI
        import yaml
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("  OPENAI_API_KEY not set - LLM extraction unavailable")
            return None
        
        client = OpenAI(api_key=api_key)
        
        # Load prompts from SEARCH.yaml
        system_prompt = "You are an expert Medical Device Regulatory Agent."  # Fallback
        user_template = "Extract device profile from FDA clearance document"  # Fallback
        
        try:
            yaml_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "prompts",
                "rules",
                "SEARCH.yaml",
            )
            with open(yaml_path, "r", encoding="utf-8") as f:
                yaml_data = yaml.safe_load(f)
            search_config = yaml_data.get("SEARCH", {})
            system_prompt = (search_config.get("fda_profile_extraction_prompt") or system_prompt).strip()
            user_template = (search_config.get("fda_profile_user_prompt") or user_template).strip()
            logger.info(f"  ✓ Loaded FDA extraction prompts from SEARCH.yaml")
        except Exception as e:
            logger.warning(f"  Could not load SEARCH.yaml prompts, using fallback: {e}")
        
        # Format user message with device data
        user_message = user_template.format(
            device_name=device_name,
            company_name=company_name,
            submission_number=submission_number,
            fda_text=fda_text
        )
        
        def _call_openai() -> str:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={"type": "json_object"},
                timeout=30.0
            )
            return response.choices[0].message.content
        
        # Run LLM call in background thread to avoid blocking
        response_json = await asyncio.to_thread(_call_openai)
        
        logger.info(f"  LLM raw response: {response_json}")
        
        try:
            extracted = json.loads(response_json)
        except json.JSONDecodeError as e:
            logger.error(f"  Failed to parse LLM response as JSON: {e}")
            logger.error(f"  Response was: {response_json}")
            return None
        
        # Validate response structure
        result = {
            "device_description": extracted.get("device_description"),
            "intended_use": extracted.get("intended_use"),
            "indications_for_use": extracted.get("indications_for_use")
        }
        
        logger.info(f"  Extracted fields:")
        for key, value in result.items():
            if value:
                if isinstance(value, str):
                    logger.info(f"    {key}: {value[:80]}..." if len(value) > 80 else f"    {key}: {value}")
                else:
                    logger.info(f"    {key}: {value} (type: {type(value).__name__})")
            else:
                logger.info(f"    {key}: None")
        
        return result
        
    except Exception as e:
        logger.warning(f"  LLM extraction failed: {e}")
        return None


# ============================================================================
# Tool.updateProductProfile - Update database with profile data
# ============================================================================

async def tool_update_product_profile(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.updateProductProfile (PROFILE flow)
    
    RESPONSIBILITY: Update product database with extracted profile information.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [tool.updateProductProfile] Updating product profile in database...")
    
    try:
        product_id = message_body.get("product_id")
        device_profile = message_body.get("device_profile")
        db = message_body.get("_db")
        
        if not product_id or not device_profile or not db:
            reason = "Missing product ID, profile data, or database connection"
            logger.warning(f"  Decision: no (confidence: 0.80) - {reason}")
            return ("no", 0.80, reason)
        
        try:
            # Log what we're about to update
            logger.info(f"  Database update values:")
            logger.info(f"    product_id: {product_id}")
            logger.info(f"    device_description: {device_profile.get('device_description')[:50] if device_profile.get('device_description') else None}...")
            logger.info(f"    intended_use: {device_profile.get('intended_use')[:50] if device_profile.get('intended_use') else None}...")
            logger.info(f"    indications_for_use: {device_profile.get('indications_for_use')[:50] if device_profile.get('indications_for_use') else None}...")
            
            # Update product with profile data
            result = await db.execute(
                """
                UPDATE public.products
                SET 
                    device_description = COALESCE($1, device_description),
                    intended_use = COALESCE($2, intended_use),
                    indications_for_use = COALESCE($3, indications_for_use),
                    updated_at = NOW()
                WHERE id = $4 AND deleted_at IS NULL
                """,
                device_profile.get("device_description"),
                device_profile.get("intended_use"),
                device_profile.get("indications_for_use"),
                product_id
            )
            
            logger.info(f"  Database update result: {result}")
            
            if result == "UPDATE 0":
                reason = f"Product {product_id} not found or already deleted"
                logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
                return ("no", 0.70, reason)
            
            # Log the update using shared logging utility
            fields_extracted = sum([bool(device_profile.get(f)) for f in ["device_description", "intended_use", "indications_for_use"]])
            await log_event(
                db,
                "PROFILE_COMPLETE",
                {
                    "product_id": product_id,
                    "submission_number": device_profile.get("submission_number"),
                    "fields_extracted": fields_extracted,
                    "has_device_description": bool(device_profile.get("device_description")),
                    "has_intended_use": bool(device_profile.get("intended_use")),
                    "has_indications_for_use": bool(device_profile.get("indications_for_use")),
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            
            logger.info(f"✓ Updated product {product_id} with profile data")
            
            reason = f"Product {product_id} profile updated successfully"
            logger.info(f"  Decision: yes (confidence: 0.99) - {reason}")
            return ("yes", 0.99, reason)
            
        except Exception as e:
            reason = f"Database update failed: {str(e)}"
            logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
            return ("no", 0.10, reason)
        
    except Exception as e:
        reason = f"Profile update failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)
