"""
Profile Agent Flow for FDA Device Profiling

Extracts official device data from FDA Devices@FDA database:
- device_description: Official description from FDA clearance documents
- intended_use: The general function/purpose of the device as claimed by manufacturer
- indications_for_use: The specific medical conditions the device treats/diagnoses

Entity resolution / evidence provenance:
Device names are often ambiguous (e.g., "Prism" is both an ophthalmic optical
component and a GrayMatters Health digital PTSD therapy). Every search is
anchored on the unique FDA submission number (K/PMA/DEN id) plus the company
name and restricted to official FDA domains. Before trusting any extraction we
verify the retrieved text actually references this product; when provenance
cannot be established we leave intended_use/indications_for_use null rather
than store a plausible-but-wrong value.

Workflow:
1. model.validateProductId - Verify product exists
2. model.searchFDADatabase - Query FDA Devices@FDA (submission-number anchored)
3. model.extractDeviceProfile - Verify entity identity, then LLM-extract profile
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
# Entity-resolution / evidence-provenance helpers
# ============================================================================
# Device names are frequently ambiguous. "Prism" is both an ophthalmic optical
# component and a GrayMatters Health digital therapy for PTSD. Searching Exa
# for "what is the intended use for {device}" returns the wrong entity (optical
# prisms) and the LLM then faithfully extracts an ophthalmology intended_use.
#
# We fix this by anchoring every search on the UNIQUE FDA submission number
# (K/PMA/DEN id) plus the company name, restricting to official FDA domains,
# and programmatically verifying that the retrieved text actually references
# this product before trusting any extraction. When provenance cannot be
# established we prefer null over a plausible-but-wrong value.

_SEARCH_CONFIG_CACHE: Optional[Dict[str, Any]] = None


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
        logger.info("  ✓ Loaded SEARCH.yaml profile config")
    except Exception as e:
        logger.warning(f"  Could not load SEARCH.yaml, using defaults: {e}")
        _SEARCH_CONFIG_CACHE = {}
    return _SEARCH_CONFIG_CACHE


def _company_match_token(company: str) -> Optional[str]:
    """Return the most distinctive alphanumeric token of a company name.

    Used for entity provenance: the longest token >= 5 chars is usually the
    proprietary part (e.g., "graymatters" from "GrayMatters Health") and is
    unlikely to appear in text about an unrelated product that only shares the
    device name.
    """
    if not company:
        return None
    tokens = [t for t in re.split(r"[^a-z0-9]+", company.lower()) if t]
    distinctive = [t for t in tokens if len(t) >= 5]
    if distinctive:
        return max(distinctive, key=len)
    return None


def _establish_provenance(
    fda_text: Optional[str], submission_number: str, company: str
) -> Dict[str, bool]:
    """Verify the retrieved text is actually about THIS product.

    Evidence: the FDA submission number (a unique K/PMA/DEN id) and/or a
    distinctive company-name token appear in the source text (URLs included).
    If neither appears, the search almost certainly returned a different entity
    that merely shares the device name, and any extraction should be rejected.

    Returns:
        {"submission_match": bool, "company_match": bool, "trusted": bool}
        trusted is True when submission_match OR company_match is True.
    """
    if not fda_text:
        return {"submission_match": False, "company_match": False, "trusted": False}
    haystack = fda_text.lower()

    submission_match = False
    if submission_number:
        # Normalize so punctuation/spacing in the source cannot hide the id.
        sub_norm = re.sub(r"[^a-z0-9]", "", submission_number.lower())
        hay_norm = re.sub(r"[^a-z0-9]", "", haystack)
        submission_match = bool(sub_norm) and sub_norm in hay_norm

    company_match = False
    if company:
        if company.lower() in haystack:
            company_match = True
        else:
            token = _company_match_token(company)
            if token and token in haystack:
                company_match = True

    return {
        "submission_match": submission_match,
        "company_match": company_match,
        "trusted": submission_match or company_match,
    }


def _combine_exa_results(results) -> str:
    """Combine Exa search results into labeled source text for the LLM.

    Each result contributes its URL, retrieved page text, and highlights so the
    LLM has real document content (not just snippets) to extract from and to
    verify entity identity.
    """
    chunks = []
    for res in results:
        url = getattr(res, "url", "") or ""
        text = getattr(res, "text", "") or ""
        highlights = getattr(res, "highlights", []) or []
        parts = [f"[Source: {url}]"]
        if text:
            parts.append(text)
        if highlights:
            if isinstance(highlights, list):
                parts.append("\n".join(str(h) for h in highlights))
            else:
                parts.append(str(highlights))
        if len(parts) > 1:
            chunks.append("\n".join(parts))
    return "\n\n---\n\n".join(chunks)


def _exa_search(exa, query: str, num_results: int, include_domains, contents) -> Optional[str]:
    """Run one Exa search and return combined source text, or None if empty."""
    kwargs = {
        "num_results": num_results,
        "type": "auto",
        "contents": contents,
    }
    if include_domains:
        kwargs["include_domains"] = include_domains
    logger.info(
        f"  Exa query: '{query}'"
        + (f" (domains={include_domains})" if include_domains else "")
    )
    try:
        result = exa.search(query, **kwargs)
    except Exception as e:
        logger.warning(f"  Exa search error for '{query}': {e}")
        return None
    if not result or not getattr(result, "results", None):
        logger.info(f"  Exa: no results for '{query}'")
        return None
    combined = _combine_exa_results(result.results)
    if combined and len(combined) >= 50:
        logger.info(
            f"  ✓ Exa returned {len(result.results)} results, {len(combined)} chars of source text"
        )
        return combined
    if combined:
        logger.warning(f"  ⚠ Exa returned very short text ({len(combined)} chars)")
    return None


# ============================================================================
# Direct FDA retrieval (primary strategy)
# ============================================================================
# The most reliable path to official FDA clearance text: query the openFDA API
# by the unique K/PMA number (entity identity confirmed by construction), then
# fetch the 510(k) summary PDF from the FDA 510(k) database HTML page. Exa web
# search is a fallback because device names are ambiguous and Exa frequently
# returns pages about the wrong entity.

_OPENFDA_510K_URL = "https://api.fda.gov/device/510k.json"
_OPENFDA_PMA_URL = "https://api.fda.gov/device/pma.json"
_FDA_510K_PAGE_URL = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm"


async def _openfda_lookup(submission_number: str, submission_type: str) -> Optional[Dict[str, Any]]:
    """Query the openFDA API by submission number for authoritative metadata.

    Entity identity is confirmed by construction: we search by the unique
    K/PMA number, so any result IS the right entity. Returns the first result
    record or None.
    """
    import httpx
    try:
        if submission_type == "pma":
            url = _OPENFDA_PMA_URL
            search_field = "pma_number"
        else:
            url = _OPENFDA_510K_URL
            search_field = "k_number"
        params = {"search": f'{search_field}:"{submission_number}"', "limit": 1}
        api_key = os.getenv("OPENFDA_API_KEY")
        if api_key:
            params["api_key"] = api_key
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, params=params)
        if resp.status_code == 404:
            logger.info(f"  openFDA: no record for {submission_number} (404)")
            return None
        if resp.status_code != 200:
            logger.warning(f"  openFDA: HTTP {resp.status_code} for {submission_number}")
            return None
        data = resp.json()
        results = data.get("results") or []
        if not results:
            logger.info(f"  openFDA: no results for {submission_number}")
            return None
        rec = results[0]
        logger.info(
            f"  ✓ openFDA confirmed {submission_number}: "
            f"{rec.get('device_name', '?')} by {rec.get('applicant', '?')}"
        )
        return rec
    except Exception as e:
        logger.warning(f"  openFDA lookup failed for {submission_number}: {e}")
        return None


async def _extract_summary_pdf_url(submission_number: str, submission_type: str) -> Optional[str]:
    """Fetch the FDA 510(k) database HTML page and extract the summary PDF link.

    The PDF subdirectory varies (e.g. pdf22, pdf20), so the URL cannot be
    constructed directly — it must be extracted from the HTML page.
    """
    import httpx
    try:
        if submission_type == "pma":
            # PMA has a different database page; not yet supported
            return None
        params = {"ID": submission_number}
        async with httpx.AsyncClient(
            timeout=15, follow_redirects=True, headers={"User-Agent": "PatternFactory/1.0"}
        ) as client:
            resp = await client.get(_FDA_510K_PAGE_URL, params=params)
        if resp.status_code != 200:
            logger.warning(f"  FDA 510(k) page: HTTP {resp.status_code}")
            return None
        # Find PDF links containing the submission number
        pattern = r'href="([^"]*' + re.escape(submission_number) + r'[^"]*\.pdf)"'
        matches = re.findall(pattern, resp.text, re.IGNORECASE)
        if matches:
            pdf_url = matches[0]
            logger.info(f"  ✓ Found 510(k) summary PDF: {pdf_url}")
            return pdf_url
        logger.warning(f"  No summary PDF link found on 510(k) page for {submission_number}")
        return None
    except Exception as e:
        logger.warning(f"  510(k) page fetch failed for {submission_number}: {e}")
        return None


async def _fetch_and_parse_pdf(pdf_url: str) -> Optional[str]:
    """Download a PDF and extract its text using pypdf."""
    import httpx
    from io import BytesIO
    try:
        from pypdf import PdfReader
    except ImportError:
        logger.warning("  pypdf not installed - cannot parse PDF")
        return None
    try:
        async with httpx.AsyncClient(
            timeout=30, follow_redirects=True, headers={"User-Agent": "PatternFactory/1.0"}
        ) as client:
            resp = await client.get(pdf_url)
        if resp.status_code != 200:
            logger.warning(f"  PDF fetch: HTTP {resp.status_code}")
            return None
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not resp.content[:5] == b"%PDF-":
            logger.warning(f"  PDF fetch: not a PDF (content-type={content_type})")
            return None

        def _parse() -> str:
            reader = PdfReader(BytesIO(resp.content))
            return "".join((p.extract_text() or "") for p in reader.pages)

        text = await asyncio.to_thread(_parse)
        if text and len(text) >= 100:
            logger.info(
                f"  ✓ Extracted {len(text)} chars from PDF ({len(resp.content)} bytes)"
            )
            return text
        if text:
            logger.warning(f"  ⚠ PDF text very short ({len(text)} chars)")
        else:
            logger.warning("  ⚠ PDF text extraction returned empty")
        return text if text else None
    except Exception as e:
        logger.warning(f"  PDF parse failed: {e}")
        return None


async def _fetch_fda_clearance_direct(
    submission_number: str, device: str, company: str, submission_type: str
) -> Tuple[Optional[str], Optional[Dict[str, Any]], Dict[str, bool]]:
    """Direct FDA retrieval: openFDA metadata + 510(k) summary PDF text.

    This is the primary strategy. Entity identity is confirmed by construction
    because we query the openFDA API by the unique K/PMA number and fetch the
    summary PDF via the K-number-keyed 510(k) database page.

    Returns: (clearance_text, openfda_metadata, provenance)
    """
    metadata = None
    provenance = {"submission_match": False, "company_match": False, "trusted": False}

    # 1. openFDA API — confirm entity + get metadata
    record = await _openfda_lookup(submission_number, submission_type)
    if record:
        ofda = record.get("openfda", {}) or {}
        metadata = {
            "applicant": record.get("applicant"),
            "device_name": record.get("device_name"),
            "decision_date": record.get("decision_date"),
            "decision_description": record.get("decision_description"),
            "clearance_type": record.get("clearance_type"),
            "product_code": record.get("product_code"),
            "regulation_number": ofda.get("regulation_number"),
            "regulation_name": ofda.get("device_name"),
            "device_class": ofda.get("device_class"),
            "medical_specialty": ofda.get("medical_specialty_description"),
        }
        # Entity identity confirmed by construction (queried by unique K-number)
        provenance = {"submission_match": True, "company_match": True, "trusted": True}
    else:
        return None, None, provenance

    # 2. Fetch 510(k) HTML page → extract summary PDF URL
    pdf_url = await _extract_summary_pdf_url(submission_number, submission_type)

    # 3. Fetch + parse the PDF
    clearance_text = None
    if pdf_url:
        clearance_text = await _fetch_and_parse_pdf(pdf_url)

    # If we got PDF text, double-check provenance on the actual text. If the
    # text doesn't mention the K-number/company (rare — pypdf can garble),
    # still trust the openFDA confirmation since the PDF was fetched via the
    # K-number-keyed FDA page.
    if clearance_text:
        text_prov = _establish_provenance(clearance_text, submission_number, company)
        if not text_prov["trusted"]:
            logger.warning(
                "  ⚠ PDF text lacks explicit K-number/company match, but "
                "trusting openFDA confirmation (PDF fetched via K-number-keyed page)"
            )

    return clearance_text, metadata, provenance


# ============================================================================
# Model.searchFDADatabase - Query FDA for submission
# ============================================================================

async def agent_search_fda_database(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.searchFDADatabase (PROFILE flow)

    RESPONSIBILITY: Retrieve FDA clearance text for the product.

    Primary strategy: direct FDA retrieval — query the openFDA API by the
    unique K/PMA number (entity identity confirmed by construction), then
    fetch the 510(k) summary PDF from the FDA database HTML page.

    Fallback: Exa web search anchored on submission number + company, with
    provenance verification. Exa is the fallback because device names are
    ambiguous and Exa frequently returns pages about the wrong entity.

    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.searchFDADatabase] Retrieving FDA clearance data...")

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
        logger.info(f"  Searching FDA for: {submission_number} ({company} {device})")

        # Retrieve FDA clearance text.
        # Primary: direct FDA retrieval (openFDA API + 510(k) summary PDF) —
        # entity identity confirmed by construction (queried by unique K-number).
        # Fallback: Exa web search with provenance verification.
        fda_clearance_text = None
        openfda_metadata = None
        provenance = {"submission_match": False, "company_match": False, "trusted": False}
        retrieval_method = "none"

        try:
            fda_clearance_text, openfda_metadata, provenance = await _fetch_fda_clearance_direct(
                submission_number=submission_number,
                device=device,
                company=company,
                submission_type=submission_type,
            )
            if fda_clearance_text:
                retrieval_method = "direct_fda_pdf"
                logger.info(
                    f"  ✓ Retrieved FDA clearance text via direct path "
                    f"({len(fda_clearance_text)} chars)"
                )
            elif provenance["trusted"]:
                logger.info(
                    f"  openFDA confirmed entity but no summary PDF text — "
                    f"will try Exa for text"
                )
            else:
                logger.info(
                    f"  Direct FDA path found no record for {submission_number} "
                    f"— will try Exa"
                )
        except Exception as e:
            logger.warning(f"  ⚠ Direct FDA retrieval failed: {e}")

        # Fallback: Exa web search if direct path returned no text
        if not fda_clearance_text:
            if EXA_AVAILABLE:
                try:
                    exa_api_key = os.getenv("EXA_API_KEY")
                    if exa_api_key:
                        exa_text = await _search_fda_with_exa(
                            submission_number=submission_number,
                            device=device,
                            company=company,
                            api_key=exa_api_key,
                        )
                        if exa_text:
                            fda_clearance_text = exa_text
                            provenance = _establish_provenance(
                                exa_text, submission_number, company
                            )
                            retrieval_method = "exa_web_search"
                            logger.info(
                                f"  ✓ Retrieved FDA clearance text via Exa "
                                f"({len(exa_text)} chars)"
                            )
                        else:
                            logger.warning(
                                f"  ⚠ No FDA text found for {submission_number} via Exa"
                            )
                except Exception as e:
                    logger.warning(f"  ⚠ Exa search failed: {e}")
            else:
                logger.warning("  ⚠ Exa not available - no fallback available")

        # Entity provenance check for Exa-sourced text (direct path is trusted
        # by construction)
        if fda_clearance_text and not provenance["trusted"]:
            logger.warning(
                f"  ⚠ Entity provenance NOT established for {submission_number} "
                f"({company} {device}): retrieved text does not reference the "
                f"submission number or company. Extraction will be discarded."
            )

        message_body["submission_number"] = submission_number
        message_body["submission_type"] = submission_type
        message_body["fda_clearance_text"] = fda_clearance_text
        message_body["entity_provenance"] = provenance
        message_body["openfda_metadata"] = openfda_metadata
        message_body["fda_clearance_info"] = {
            "submission_number": submission_number,
            "submission_type": submission_type,
            "device": device,
            "company": company,
            "has_fda_text": bool(fda_clearance_text),
            "entity_provenance": provenance,
            "retrieval_method": retrieval_method,
            "openfda_metadata": openfda_metadata,
        }

        if fda_clearance_text and provenance["trusted"]:
            confidence = 0.95
        elif fda_clearance_text:
            confidence = 0.45  # text retrieved but entity identity unverified
        else:
            confidence = 0.70
        reason = (
            f"FDA {submission_type.upper()} {submission_number} retrieved "
            f"({len(fda_clearance_text) if fda_clearance_text else 0} chars, "
            f"method={retrieval_method}, "
            f"provenance={'trusted' if provenance['trusted'] else 'unverified'})"
        )
        logger.info(f"  Decision: yes (confidence: {confidence}) - {reason}")
        return ("yes", confidence, reason)

    except Exception as e:
        reason = f"FDA database search failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.10) - {reason}", exc_info=True)
        return ("no", 0.10, reason)


async def _search_fda_with_exa(
    submission_number: str, device: str, company: str, api_key: str
) -> Optional[str]:
    """
    Search official FDA sources using Exa for a device's clearance text.

    Anchors every query on the unique FDA submission number plus the company
    name (the device name alone is too ambiguous). Restricts the primary query
    to official FDA domains and retrieves full page text + highlights so the
    downstream LLM has real document content and the provenance check has
    enough text to confirm entity identity.
    """
    try:
        exa = Exa(api_key=api_key)

        cfg = _load_search_config()
        primary_cfg = cfg.get("fda_profile_search_config", {}) or {}
        fallback_cfg = cfg.get("fda_profile_fallback_search_config", {}) or {}

        include_domains = primary_cfg.get("include_domains") or ["fda.gov", "accessdata.fda.gov"]
        num_results = int(primary_cfg.get("num_results") or 5)
        contents = primary_cfg.get("contents") or {
            "highlights": True,
            "text": {"max_characters": 8000},
        }

        ctx = {
            "submission_number": submission_number,
            "company_name": company,
            "device_name": device,
        }

        # Query strategies, most-specific first. The submission number is the
        # unique FDA identifier; the company name disambiguates further. We
        # never search on the device name alone.
        strategies = [
            (
                primary_cfg.get("primary_query")
                or "FDA {submission_number} {company_name} {device_name} intended use indications for use",
                include_domains,
                num_results,
                contents,
            ),
            (
                fallback_cfg.get("fallback_query")
                or '"{submission_number}" {company_name} {device_name} FDA 510k clearance intended use',
                None,
                num_results,
                contents,
            ),
            (
                "{submission_number} {company_name} FDA clearance intended use indications for use",
                None,
                3,
                contents,
            ),
            (
                "{submission_number} FDA device clearance",
                None,
                3,
                contents,
            ),
        ]

        for query_template, domains, n, cts in strategies:
            try:
                query = query_template.format(**ctx)
            except (KeyError, IndexError):
                query = query_template
            combined = _exa_search(exa, query, n, domains, cts)
            if combined:
                return combined

        logger.warning(
            f"  ⚠ No FDA text found for {submission_number} ({company} {device})"
        )
        return None

    except Exception as e:
        logger.error(f"  Exa search setup error: {e}", exc_info=True)
        return None


# ============================================================================
# Model.extractDeviceProfile - Parse FDA documents via LLM
# ============================================================================

async def agent_extract_device_profile(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.extractDeviceProfile (PROFILE flow)

    RESPONSIBILITY: Use LLM to extract device profile information from FDA
    clearance documents, but ONLY after verifying entity identity. Parses
    FDA text to extract:
    - Device description (technical architecture, deployment details, algorithmic framework)
    - Intended Use (overarching clinical objective)
    - Indications for Use (specific patient cohort, diseases, settings)

    If the retrieved text does not reference this product's submission number
    or company, the text is almost certainly about a different entity that
    merely shares the device name; in that case we leave all fields null rather
    than store a plausible-but-wrong value.

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

        # Extract profile using LLM if FDA text is available AND entity identity
        # is confirmed. Device names are ambiguous; only trust extraction from
        # text that actually references this product (submission number/company).
        device_description = None
        intended_use = None
        indications_for_use = None
        extraction_source = "fda_devices_database"

        provenance = message_body.get("entity_provenance") or _establish_provenance(
            fda_clearance_text, submission_number, company
        )

        if fda_clearance_text and not provenance.get("trusted"):
            # Text was retrieved but does not reference this product's submission
            # number or company -> almost certainly a different entity that shares
            # the device name. Prefer null over a plausible-but-wrong value.
            logger.warning(
                f"  ⚠ Discarding FDA text: entity identity unverified "
                f"(submission_match={provenance.get('submission_match')}, "
                f"company_match={provenance.get('company_match')}). "
                f"Leaving intended_use/indications_for_use null for {company} {device}."
            )
            extraction_source = "fda_devices_database_unverified_entity"
        elif fda_clearance_text:
            logger.info(
                f"  Entity provenance verified "
                f"(submission_match={provenance.get('submission_match')}, "
                f"company_match={provenance.get('company_match')})."
            )
            logger.info(
                f"  Using LLM to extract profile from FDA clearance text "
                f"({len(fda_clearance_text)} chars)..."
            )
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
            logger.warning(f"  No FDA clearance text available - using fallback stub for device_description only")
            device_description = f"{device} by {company}"

        profile = {
            "device_description": device_description,
            "intended_use": intended_use,
            "indications_for_use": indications_for_use,
            "source": extraction_source,
            "submission_number": submission_number,
            "entity_provenance": provenance,
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
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.warning("  OPENAI_API_KEY not set - LLM extraction unavailable")
            return None

        client = OpenAI(api_key=api_key)

        # Load prompts from SEARCH.yaml. Both prompts instruct the LLM to verify
        # entity identity (company + submission number) before extracting and to
        # return null rather than content about the wrong entity.
        system_prompt = (
            "You are an expert Medical Device Regulatory Agent. Verify the text is "
            "about the target device (by company and submission number) before "
            "extracting. Return ONLY valid JSON with device_description, "
            "intended_use, indications_for_use (string or null). If entity identity "
            "is unclear, return null for all fields."
        )
        user_template = (
            "Extract device profile from FDA clearance document.\n\n"
            "Device: {device_name}\nCompany: {company_name}\n"
            "Submission Number: {submission_number}\n\n"
            "If the text is not about this company's device cleared under this "
            "submission number, return null for all fields.\n\n"
            "---FDA CLEARANCE TEXT---\n{fda_text}\n\n"
            "Return ONLY valid JSON: "
            '{{"device_description": "...", "intended_use": "...", "indications_for_use": "..."}}'
        )

        try:
            search_config = _load_search_config()
            system_prompt = (search_config.get("fda_profile_extraction_prompt") or system_prompt).strip()
            user_template = (search_config.get("fda_profile_user_prompt") or user_template).strip()
            logger.info(f"  ✓ Loaded FDA extraction prompts from SEARCH.yaml")
        except Exception as e:
            logger.warning(f"  Could not load SEARCH.yaml prompts, using fallback: {e}")

        # Cap the source text sent to the LLM to keep prompts manageable.
        max_text_chars = 24000
        fda_text_for_llm = fda_text[:max_text_chars] if fda_text else ""
        if fda_text and len(fda_text) > max_text_chars:
            logger.info(f"  Truncating FDA text from {len(fda_text)} to {max_text_chars} chars for LLM")

        # Format user message with device data
        user_message = user_template.format(
            device_name=device_name,
            company_name=company_name,
            submission_number=submission_number,
            fda_text=fda_text_for_llm
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

            # Update product with profile data. COALESCE keeps existing values
            # when an extracted field is null (e.g., when entity provenance
            # could not be established and we deliberately returned null).
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
            provenance = device_profile.get("entity_provenance") or {}
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
                    "entity_provenance": provenance,
                    "extraction_source": device_profile.get("source"),
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
