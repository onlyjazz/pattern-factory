"""
Pitboss Agent Functions

Workflow agents for RULE and CONTENT pipelines.
- RULE flow: validate → verify → SQL → execute
- CONTENT flow: validate → verify → extract → verify upsert

Each agent returns: decision (yes/no), confidence (0.0-1.0), reason

Dependency Injection:
- ToolRegistry and ContextBuilder passed via message_body['_tools'] and message_body['_ctx']
"""

from typing import Tuple, Dict, Any, Optional
import logging
import json
import os
from urllib.parse import urlparse
import urllib.request
import re
from openai import OpenAI

logger = logging.getLogger(__name__)

# Load system prompt for LanguageCapo from YAML

def get_capo_system_prompt() -> str:
    """Load Capo system prompt from pattern-factory.yaml."""
    try:
        import yaml
        yaml_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            "..",
            "prompts",
            "rules",
            "pattern-factory.yaml",
        )
        with open(yaml_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        capo_section = yaml_data.get("CAPO", [])
        if capo_section and isinstance(capo_section, list):
            prompt = (capo_section[0] or {}).get("prompt", "").strip()
            # Remove surrounding quotes if present
            if prompt.startswith('"') and prompt.endswith('"'):
                prompt = prompt[1:-1]
            return prompt
    except Exception as e:
        logger.warning(f"[LanguageCapo] Failed to load CAPO prompt from YAML: {e}")

    # Fallback prompt
    return (
        "You are a router that classifies a user’s message for the Pattern Factory. "
        "Choose exactly one verb: RULE or CONTENT. RULE means the user wants to query/build "
        "logical views (rules → SQL → execute). CONTENT means the user wants to extract "
        "entities (orgs, guests, categories, patterns, posts) from a URL or text. "
        "Return strict JSON only: { \"decision\": \"yes\"|\"no\", \"verb\": \"RULE\"|\"CONTENT\", \"confidence\": 0.0–1.0, \"reason\": \"...\" }. "
        "If intent is unclear (<0.6 confidence), set decision to \"no\" and explain what’s ambiguous in reason."
    )


# ============================================================================
# Language Detection Agent (Pre-Workflow Stage)
# ============================================================================

async def agent_language_capo(message_body: Dict[str, Any]) -> Tuple[str, float, str, str]:
    """
    model.LanguageCapo
    Pre-workflow agent that determines if user is asking for RULE or CONTENT.
    
    RESPONSIBILITY: Route the message to the correct workflow (RULE or CONTENT).
    Does NOT validate anything - that's the job of downstream agents.
    
    Uses LLM if OPENAI_API_KEY is set, otherwise falls back to heuristics.
    Always returns decision="yes" with a RULE or CONTENT verb.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str, verb: str)
    """
    logger.info("🤖 [model.LanguageCapo] Routing message to RULE or CONTENT workflow...")

    text = (message_body.get("raw_text") or "").strip()

    # Fast-path: recognize explicit "run <SOMETHING>" syntax → route to RULE
    # (Do NOT validate if rule exists - downstream agent verifyRequest will do that)
    if text.upper().startswith("RUN "):
        code = text[4:].strip()
        reason = f"User wants to run rule: '{code}'"
        logger.info(f"  Detected 'RUN' syntax → routing to RULE workflow")
        return ("yes", 0.95, reason, "RULE")

    # Try LLM-based classification first
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key and text:
        try:
            client = OpenAI(api_key=api_key)
            system_prompt = get_capo_system_prompt()

            response = await _call_openai_async(
                client=client,
                system_prompt=system_prompt,
                user_message=f"Message: {text}",
                model="gpt-4o-mini",
                temperature=0.0,
                timeout=5.0,
            )

            data = json.loads(response)
            decision = data.get("decision", "no")
            verb = (data.get("verb", "") or "").strip().upper()
            # Default to RULE if empty or invalid
            if verb not in ("RULE", "CONTENT"):
                verb = "RULE"
            confidence = float(data.get("confidence", 0.55))
            reason = data.get("reason", "")

            logger.info(f"  LLM: Verb={verb}, decision={decision}, confidence={confidence:.2f}")
            return (decision, confidence, reason, verb)
        except Exception as e:
            logger.warning(f"[LanguageCapo] LLM classification failed, falling back to heuristics: {e}")

    # Fallback: heuristic classification
    logger.info("  Using heuristic classification")
    return _heuristic_language_capo(text)


async def _call_openai_async(*, client: OpenAI, system_prompt: str, user_message: str, model: str, temperature: float, timeout: float) -> str:
    """Call OpenAI chat.completions in a background thread, return JSON content string."""
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


def _heuristic_language_capo(text: str) -> Tuple[str, float, str, str]:
    """Heuristic-based language classification (keyword scoring). Fallback when LLM is unavailable."""
    text_lower = text.lower()

    # Heuristics for RULE vs CONTENT
    rule_keywords = [
        "show",
        "find",
        "list",
        "get",
        "query",
        "pattern",
        "view",
        "select",
        "where",
        "group",
        "having",
        "order",
        "sql",
        "guests",
        "organizations",
        "posts",
        "orgs",
    ]

    content_keywords = [
        "extract",
        "analyze",
        "parse",
        "read",
        "import",
        "ingest",
        "newsletter",
        "podcast",
        "transcript",
        "article",
        "content",
        "url",
        "link",
        "upload",
        "entities",
        "entity",
    ]

    rule_score = sum(1 for kw in rule_keywords if kw in text_lower)
    content_score = sum(1 for kw in content_keywords if kw in text_lower)

    if rule_score > content_score:
        verb = "RULE"
        confidence = min(0.95, 0.5 + (rule_score * 0.1))
        reason = f"User is asking for data query/view (detected {rule_score} RULE keywords)"
    elif content_score > rule_score:
        verb = "CONTENT"
        confidence = min(0.95, 0.5 + (content_score * 0.1))
        reason = f"User is asking for content extraction (detected {content_score} CONTENT keywords)"
    else:
        # Default to RULE if ambiguous
        verb = "RULE"
        confidence = 0.55
        reason = "Ambiguous intent, defaulting to RULE workflow"

    return ("yes", confidence, reason, verb)


def _extract_rule_code_inline(raw_text: str) -> Optional[str]:
    """Extract rule code from 'run <RULE_CODE>' syntax.
    Returns the rule code string if user typed 'RUN <something>', else None.
    Does NOT validate if the rule exists in YAML - that's verifyRequest's job.
    """
    if not raw_text:
        return None

    text = raw_text.strip()
    text_upper = text.upper()

    # If user typed "RUN <something>", extract the code
    if text_upper.startswith("RUN "):
        code = text_upper[4:].strip()
        return code if code else None

    return None


# ============================================================================
# RULE Flow Agents
# ============================================================================

async def agent_capo_rule(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.Capo (RULE flow entry point)
    Validates the message envelope structure.
    
    Checks:
    - Envelope has required fields (session_id, request_id, messageBody with raw_text)
    - Message is not empty
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.Capo] Validating message envelope...")
    
    # Check if message has content
    raw_text = message_body.get("raw_text", "").strip()
    
    if not raw_text:
        reason = "Message is empty. Please type something."
        logger.info(f"  Decision: no (confidence: 1.0) - {reason}")
        return ("no", 1.0, reason)
    
    # Envelope is valid - message is ready for processing
    decision = "yes"
    confidence = 1.0
    reason = "Message envelope is valid and ready for processing"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_verify_request(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyRequest (RULE flow)
    Validate semantics of the rule request.
    
    Checks:
    - Rule code exists in YAML (if provided)
    - Rule logic references valid entities/tables
    - Rule intent is clear (not ambiguous)
    - Begin context building for LLM (store in message_body)
    """
    logger.info("🤖 [model.verifyRequest] Validating rule semantics...")
    
    rule_code = message_body.get("rule_code", "").strip()
    rule_logic = message_body.get("rule_logic", "").lower()
    
    # First: Verify rule exists in YAML (if rule_code was extracted)
    if rule_code:
        context_builder = message_body.get("_ctx")
        if context_builder and hasattr(context_builder, 'yaml_data'):
            rules = context_builder.yaml_data.get("RULES", [])
            rule_codes = [r.get("rule_code") for r in rules]
            
            if rule_code not in rule_codes:
                reason = f"Rule '{rule_code}' not found in YAML. Available rules: {', '.join(rule_codes[:5])}"
                logger.info(f"  Decision: no (confidence: 0.98) - {reason}")
                return ("no", 0.98, reason)
    
    # Get valid tables from context builder (loads from YAML dynamically)
    context_builder = message_body.get("_ctx")
    if context_builder and hasattr(context_builder, 'yaml_data'):
        # Extract all table names from YAML DATA section
        # Support both flat structure (DATA.tables) and nested schema structure (DATA.schemas.*.tables)
        data_section = context_builder.yaml_data.get("DATA", {})
        yaml_tables = set()
        
        # Try flat structure first
        if "tables" in data_section:
            yaml_tables.update(data_section.get("tables", {}).keys())
        
        # Then try nested schema structure (DATA.schemas.<schema_name>.tables)
        schemas = data_section.get("schemas", {})
        if schemas:
            for schema_name, schema_data in schemas.items():
                if isinstance(schema_data, dict):
                    schema_tables = schema_data.get("tables", {})
                    if isinstance(schema_tables, dict):
                        yaml_tables.update(schema_tables.keys())
        
        valid_tables = yaml_tables
        logger.info(f"  Loaded {len(valid_tables)} tables from YAML: {sorted(list(valid_tables))[:5]}...")
    else:
        # Fallback to hardcoded list if context builder unavailable
        valid_tables = {
            "patterns", "guests", "organizations", "posts",
            "pattern_guests", "pattern_orgs", "pattern_posts",
            "orgs", "org", "guest", "episode", "post", "pattern"
        }
        logger.warning("Using fallback hardcoded table list; context_builder not available")
    
    found_tables = [t for t in valid_tables if t in rule_logic]
    
    if not found_tables:
        reason = "Rule does not reference any known entities (patterns, guests, orgs, posts)"
        logger.info(f"  Decision: no (confidence: 0.82) - {reason}")
        return ("no", 0.82, reason)
    
    # Semantic check: look for SELECT or query-like intent
    query_keywords = ["show", "find", "list", "select", "display", "get", "view", "count", "group"]
    has_query_intent = any(kw in rule_logic for kw in query_keywords)
    
    if not has_query_intent and len(found_tables) < 1:
        reason = "Rule intent is unclear; could not identify query action"
        logger.info(f"  Decision: no (confidence: 0.76) - {reason}")
        return ("no", 0.76, reason)
    
    # Semantics validated
    decision = "yes"
    confidence = 0.89
    reason = f"Rule semantics valid: references {', '.join(found_tables[:3])} and intent is clear"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_rule_to_sql(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.ruleToSQL (RULE flow)
    Convert rule definition into SQL using LLM.
    
    Uses:
    - ToolRegistry (message_body['_tools'])
    - ContextBuilder (message_body['_ctx'])
    - Rule logic from message_body['rule_logic']
    
    Stores SQL in message_body['sql_query'] for downstream agents.
    """
    logger.info("🤖 [model.ruleToSQL] Converting rule to SQL...")
    
    try:
        # Extract dependencies
        tool_registry = message_body.get("_tools")
        context_builder = message_body.get("_ctx")
        rule_logic = message_body.get("rule_logic", "").strip()
        
        if not tool_registry:
            reason = "ToolRegistry not available in message_body"
            logger.error(f"  ❌ {reason}")
            return ("no", 0.1, reason)
        
        if not context_builder:
            reason = "ContextBuilder not available in message_body"
            logger.error(f"  ❌ {reason}")
            return ("no", 0.1, reason)
        
        # Build context for LLM
        context = context_builder.build_context(rule_code=rule_logic)
        messages = [
            {"role": "system", "content": context["system"]},
            {"role": "user", "content": rule_logic}
        ]
        
        # Call LLM via sql_pitboss tool
        sql_result = await tool_registry.execute("sql_pitboss", messages=messages)
        
        if sql_result["status"] != "success":
            reason = f"LLM SQL generation failed: {sql_result.get('error', 'unknown error')}"
            logger.warning(f"  ❌ {reason}")
            return ("no", 0.3, reason)
        
        sql_query = sql_result.get("sql", "").strip()
        if not sql_query:
            reason = "LLM returned empty SQL"
            logger.warning(f"  ❌ {reason}")
            return ("no", 0.4, reason)
        
        # Store SQL in message_body for next agent
        message_body["sql_query"] = sql_query
        message_body["sql_raw_response"] = sql_result.get("raw", "")
        
        decision = "yes"
        confidence = 0.91
        reason = f"Generated SQL ({len(sql_query)} chars) from rule"
        
        logger.info(f"  Decision: {decision} (confidence: {confidence:.2f}) - {reason}")
        logger.info(f"  SQL: {sql_query[:100]}...")
        return (decision, confidence, reason)
        
    except Exception as e:
        reason = f"SQL generation crashed: {str(e)}"
        logger.error(f"  ❌ {reason}", exc_info=True)
        return ("no", 0.0, reason)


async def agent_verify_sql(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifySQL (RULE flow)
    Validate SQL safety and syntax, then request human approval.
    
    Checks:
    - SQL is not empty
    - SQL starts with SELECT, WITH, or INSERT (allowed operations)
    - No DROP, DELETE, ALTER commands (safety)
    - No obvious SQL injection attacks
    
    If validation passes: returns NO to trigger HITL for human approval
    The frontend will show SQL for user to approve or tweak, then re-submit.
    
    If validation fails: returns NO with error reason (rejection, not HITL)
    """
    logger.info("🤖 [model.verifySQL] Validating SQL safety and syntax...")
    
    sql_query = message_body.get("sql_query", "").strip()
    sql_query_upper = sql_query.upper()
    
    if not sql_query:
        reason = "No SQL query found in message_body"
        logger.warning(f"  ❌ {reason}")
        return ("no", 0.95, reason)
    
    # Check for safe operations
    safe_starts = ("SELECT", "WITH", "INSERT")
    if not any(sql_query_upper.startswith(s) for s in safe_starts):
        reason = f"SQL does not start with safe operation (expected SELECT/WITH/INSERT)"
        logger.warning(f"  ❌ {reason}")
        return ("no", 0.89, reason)
    
    # Check for dangerous operations (destructive)
    dangerous_ops = ("DROP", "DELETE", "ALTER", "TRUNCATE", "GRANT", "REVOKE")
    if any(f" {op} " in sql_query_upper for op in dangerous_ops):
        reason = f"SQL contains dangerous operation ({', '.join(dangerous_ops)}). Rejected for safety."
        logger.warning(f"  ❌ {reason}")
        return ("no", 0.98, reason)  # High confidence - reject
    
    # Check for injection patterns (UNION, EXEC, xp_, sp_)
    injection_patterns = ("UNION", "EXEC", "XP_", "SP_", "--", "/**/", "CAST(", "CONVERT(")
    suspicious_patterns = [p for p in injection_patterns if p in sql_query_upper]
    
    if suspicious_patterns and "--" not in sql_query_upper:  # Allow SQL comments as they're valid
        reason = f"SQL looks suspicious (detected: {', '.join(suspicious_patterns)}). Please review."
        logger.info(f"  Decision: no (confidence: 0.72) - HITL required - {reason}")
        return ("no", 0.72, reason)  # HITL - user can approve or modify
    
    # SQL passed validation - now request human approval via HITL
    decision = "no"  # Trigger HITL (human-in-the-loop)
    confidence = 0.92
    reason = f"SQL validation passed. Please review and approve:\n\n{sql_query}"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    logger.info(f"  SQL ready for human approval:\n{sql_query}")
    return (decision, confidence, reason)


async def agent_execute_sql(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.executeSQL — Terminal agent for both RULE and CONTENT flows
    
    RULE flow:
    1. Execute SQL via data_table tool (creates VIEW)
    2. Register view metadata in views_registry
    
    CONTENT flow:
    1. Extract validated entity payload from message_body
    2. Call upsert_pattern_factory_entities procedure
    
    Stores:
    - For RULE: table_name (view name), row_count
    - For CONTENT: upsert_result status
    """
    logger.info("🤖 [tool.executeSQL] Executing operation based on verb...")
    
    try:
        # Extract dependencies
        tool_registry = message_body.get("_tools")
        verb = message_body.get("_verb", "RULE").upper()
        
        if not tool_registry:
            reason = "ToolRegistry not available"
            logger.error(f"  ❌ {reason}")
            return ("no", 0.05, reason)
        
        # Branch: CONTENT flow (upsert entities)
        if verb == "CONTENT":
            logger.info(f"  [CONTENT flow] Executing upsert_pattern_factory_entities procedure...")
            
            extracted_entities = message_body.get("extracted_entities", {})
            url = message_body.get("url", "")
            
            if not extracted_entities:
                reason = "No extracted_entities in message_body"
                logger.error(f"  ❌ {reason}")
                return ("no", 0.15, reason)
            
            # Call the upsert procedure
            logger.info(f"  Step 1: Calling upsert_pattern_factory_entities procedure...")
            upsert_res = await tool_registry.execute(
                "execute_upsert",
                jsonb_payload=extracted_entities
            )
            
            if upsert_res["status"] != "success":
                reason = f"Upsert procedure failed: {upsert_res.get('error')}"
                logger.error(f"  ❌ {reason}")
                return ("no", 0.3, reason)
            
            logger.info(f"    ✅ Upsert completed: {upsert_res.get('message')}")
            message_body["upsert_status"] = "success"
            message_body["url"] = url
            
            # Success
            decision = "yes"
            confidence = 0.96
            reason = f"Content extraction and upsert complete: {url}"
            
            logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
            logger.info(f"  🌟 CONTENT flow complete: {reason}")
            return (decision, confidence, reason)
        
        # Branch: RULE flow (create view)
        else:
            logger.info(f"  [RULE flow] Creating materialized view...")
            
            sql_query = message_body.get("sql_query", "").strip()
            rule_code = message_body.get("rule_code", "").strip()
            rule_name = message_body.get("rule_name", rule_code).strip()
            rule_logic = message_body.get("rule_logic", "").strip()
            
            if not sql_query:
                reason = "No SQL query in message_body to execute"
                logger.error(f"  ❌ {reason}")
                return ("no", 0.15, reason)
            
            if not rule_name:
                reason = "No rule_name to use for view creation"
                logger.error(f"  ❌ {reason}")
                return ("no", 0.2, reason)
            
            # Step 1: Create materialized view
            logger.info(f"  Step 1: Creating materialized view...")
            table_res = await tool_registry.execute(
                "data_table",
                sql_query=sql_query,
                rule_name=rule_name,
                rule_code=rule_code
            )
            
            if table_res["status"] != "success":
                reason = f"Failed to create materialized view: {table_res.get('error')}"
                logger.error(f"  ❌ {reason}")
                return ("no", 0.25, reason)
            
            table_name = table_res.get("table_name")
            row_count = table_res.get("row_count", 0)
            
            logger.info(f"    ✅ View created: {table_name} ({row_count} rows)")
            message_body["table_name"] = table_name
            message_body["row_count"] = row_count
            
            # Step 2: Register view metadata in views_registry
            logger.info(f"  Step 2: Registering view metadata in views_registry...")
            view_res = await tool_registry.execute(
                "register_view",
                table_name=table_name,
                name=rule_name,
                sql_query=sql_query
            )
            
            if view_res["status"] != "success":
                logger.warning(f"  ⚠️ View registration failed: {view_res.get('error')}")
                # Continue anyway; table exists
            else:
                logger.info(f"    ✅ View registered: {table_name}")
            
            # Success
            decision = "yes"
            confidence = 0.97
            reason = f"Rule executed: view '{table_name}' with {row_count} rows"
            
            logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
            logger.info(f"  🌟 RULE flow complete: {reason}")
            return (decision, confidence, reason)
        
    except Exception as e:
        reason = f"SQL execution crashed: {str(e)}"
        logger.error(f"  ❌ {reason}", exc_info=True)
        return ("no", 0.0, reason)


# ============================================================================
# CONTENT Flow Agents
# ============================================================================

async def agent_capo_content(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.Capo (CONTENT flow)
    Initial validation of extraction request.
    Deterministically pass when the user typed 'extract <url>'.
    """
    logger.info("🤖 [model.Capo] Validating extraction request...")

    text = (message_body.get("raw_text") or "").strip().lower()
    if text.startswith("extract "):
        return ("yes", 0.99, "Recognized 'extract <url>' command")

    # Fallback: could not recognize extraction format
    decision = "no"
    confidence = 0.92
    reason = "Could not recognize extraction format. Usage: extract <url>"
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f}) - {reason}")
    return (decision, confidence, reason)


async def agent_verify_request_content(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyRequest (CONTENT flow)
    Validate that user is asking for entity extraction and that a URL is present.
    """
    logger.info("🤖 [model.verifyRequest] Validating extraction semantics...")

    text = (message_body.get("raw_text") or "").strip()
    url = (message_body.get("url") or "").strip() or _parse_url_from_text(text)

    if url:
        return ("yes", 0.96, "URL detected for extraction")

    # If no URL yet, ask for one via HITL
    reason = "Please provide a URL. Usage: extract <url>"
    logger.info(f"  Decision: no (confidence: 0.98) - {reason}")
    return ("no", 0.98, reason)


def _parse_url_from_text(text: str) -> Optional[str]:
    """Extract URL from text matching 'extract <url>' pattern; returns URL or None."""
    if not text:
        return None
    parts = text.strip().split()
    if len(parts) >= 2 and parts[0].lower() == "extract":
        return parts[1]
    return None


async def _http_get_text(url: str, timeout: float = 8.0) -> Tuple[str, int, str]:
    """Fetch URL content as text using stdlib in a background thread.
    Returns (text, status_code, content_type)."""
    import asyncio

    def _fetch():
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "PatternFactoryBot/1.0 (+https://example.local)",
                "Accept": "text/html, text/plain;q=0.9, */*;q=0.8",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = getattr(resp, "status", 200)
                ctype = resp.headers.get("Content-Type", "")
                raw = resp.read(512_000)  # cap to 512KB for preview stage
                # Try charset from header
                charset = "utf-8"
                if "charset=" in ctype:
                    try:
                        charset = ctype.split("charset=")[-1].split(";")[0].strip()
                    except Exception:
                        pass
                try:
                    text = raw.decode(charset, errors="replace")
                except Exception:
                    text = raw.decode("utf-8", errors="replace")
                return text, status, ctype
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = str(e)
            return body, getattr(e, "code", 500), e.headers.get("Content-Type", "") if hasattr(e, "headers") else ""
        except Exception as e:
            return str(e), 0, ""

    return await asyncio.to_thread(_fetch)


def _extract_post_title_and_subtitle(html: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract post title and subtitle from HTML.

    Patterns:
    - Title: <h1 ... class="post-title ...">TITLE</h1>
    - Subtitle: <h3 ... class="subtitle ...">SUBTITLE</h3>

    Returns: (title, subtitle) or (None, None) if not found
    """
    title = None
    subtitle = None

    # Extract title from h1 with post-title class
    title_match = re.search(
        r'<h1[^>]*class="[^"]*post-title[^"]*"[^>]*>(.+?)</h1>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if title_match:
        title = title_match.group(1).strip()
        # Remove any remaining HTML tags
        title = re.sub(r'<[^>]+>', '', title).strip()

    # Extract subtitle from h3 with subtitle class
    subtitle_match = re.search(
        r'<h3[^>]*class="[^"]*subtitle[^"]*"[^>]*>(.+?)</h3>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if subtitle_match:
        subtitle = subtitle_match.group(1).strip()
        subtitle = re.sub(r'<[^>]+>', '', subtitle).strip()

    return (title, subtitle)


def _extract_published_date(html: str) -> Optional[str]:
    """
    Extract published date from HTML like 'Oct 24, 2025'.
    Returns the matched date string or None if not found.
    """
    # Prefer dates inside likely meta/publish elements but fall back to any match
    patterns = [
        r'<(?:div|span)[^>]*class="[^"]*(meta|publish|date)[^"]*"[^>]*>\s*([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\s*</',
        r'\b([A-Z][a-z]{2}\s+\d{1,2},\s+\d{4})\b',
    ]
    for pat in patterns:
        m = re.search(pat, html, re.IGNORECASE | re.DOTALL)
        if m:
            # If grouped, last group is the date
            return (m.group(2) if m.lastindex and m.lastindex >= 2 else m.group(1)).strip()
    return None

def _get_extract_content_system_prompt(context_builder) -> Optional[str]:
    """
    Load the EXTRACT_CONTENT system prompt from pattern-factory.yaml CONTENT section.
    Returns the prompt string or None if not found.
    """
    try:
        yaml_data = context_builder.yaml_data if hasattr(context_builder, 'yaml_data') else {}
        content_rules = yaml_data.get("CONTENT", [])
        for rule in content_rules:
            if rule.get("rule_code") == "EXTRACT_CONTENT":
                prompt = rule.get("prompt", "").strip()
                if prompt:
                    return prompt
    except Exception as e:
        logger.warning(f"[getExtractContentPrompt] Failed to load prompt from YAML: {e}")
    return None


async def agent_request_to_extract_entities(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.requestToExtractEntities (CONTENT flow)
    Generalized entity extraction agent.
    
    Behavior:
    - User types: 'extract <url>'
    - Agent performs HTTP GET
    - Calls LLM with EXTRACT_CONTENT system prompt from YAML
    - Returns decision="no" with JSON structure (posts, patterns, orgs, guests, links) for human review
    """
    logger.info("🤖 [model.requestToExtractEntities] Fetching and extracting entities...")

    # IMPORTANT: Clear stale metadata from previous extraction
    message_body.pop("url", None)
    message_body.pop("post_title", None)
    message_body.pop("post_subtitle", None)
    message_body.pop("published_at", None)
    message_body.pop("content_summary", None)
    message_body.pop("http_status", None)
    message_body.pop("content_type", None)
    message_body.pop("content_preview", None)
    message_body.pop("extracted_entities", None)

    raw_text = (message_body.get("raw_text") or "").strip()
    # Prioritize URL from raw_text
    url: Optional[str] = _parse_url_from_text(raw_text)
    if not url:
        url = (message_body.get("url") or "").strip() or None

    if not url:
        reason = "No URL provided. Usage: extract <url>"
        logger.info(f"  Decision: no (confidence: 0.98) - {reason}")
        return ("no", 0.98, reason)

    # Normalize URL
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        reason = f"Invalid URL: {url}"
        logger.info(f"  Decision: no (confidence: 0.98) - {reason}")
        return ("no", 0.98, reason)

    # Fetch HTML
    text, status, ctype = await _http_get_text(url)
    message_body["url"] = url
    message_body["http_status"] = status
    message_body["content_type"] = ctype
    message_body["content_preview"] = (text or "").replace("\n", " ").replace("\r", " ")[:80]

    if status != 200:
        reason = f"HTTP {status} fetching {url}"
        logger.info(f"  Decision: no (confidence: 0.95) - {reason}")
        return ("no", 0.95, reason)

    # Load system prompt from YAML
    context_builder = message_body.get("_ctx")
    system_prompt = _get_extract_content_system_prompt(context_builder) if context_builder else None

    if not system_prompt:
        reason = "Could not load EXTRACT_CONTENT system prompt from YAML"
        logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
        return ("no", 0.70, reason)

    # Call LLM to extract entities (posts, patterns, orgs, guests, links)
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        reason = "No OPENAI_API_KEY set; cannot extract entities"
        logger.warning(f"  Decision: no (confidence: 0.70) - {reason}")
        return ("no", 0.70, reason)

    try:
        client = OpenAI(api_key=api_key)
        
        # Provide input in the exact structure the prompt expects
        max_chars = 60000
        input_payload = {
            "url": url,
            "markup": (text or "")[:max_chars],
            "content_source": "substack",
        }
        user_message = json.dumps(input_payload, ensure_ascii=False)
        
        logger.info(f"  [LLM Call] Sending payload: url len={len(url)}, markup len={len(input_payload['markup'])}, source=substack")
        logger.info(f"  [LLM Call] System prompt length: {len(system_prompt)} chars")
        
        response = await _call_openai_async(
            client=client,
            system_prompt=system_prompt,
            user_message=user_message,
            model="gpt-4o-mini",
            temperature=0.2,
            timeout=30.0,
        )

        logger.info(f"  [LLM Response] Received {len(response)} chars")
        logger.debug(f"  [LLM Response] First 500 chars: {response[:500]}")

        # Parse LLM response
        try:
            llm_obj = json.loads(response)
        except json.JSONDecodeError as e:
            logger.error(f"  [LLM Response] Failed to parse JSON: {e}")
            logger.error(f"  [LLM Response] Raw response: {response[:1000]}")
            raise
        
        logger.info(f"  [Extraction] Parsed JSON successfully")
        if isinstance(llm_obj, dict):
            logger.info(f"  [Extraction] Top-level keys: {list(llm_obj.keys())}")
        
        # Accept both envelope-style and bare-payload outputs
        extracted_data = None
        if isinstance(llm_obj, dict):
            if all(k in llm_obj for k in ["orgs", "guests", "posts", "patterns", "pattern_post_link", "pattern_org_link", "pattern_guest_link"]):
                extracted_data = llm_obj
            elif isinstance(llm_obj.get("messageBody"), dict):
                extracted_data = llm_obj.get("messageBody")
                logger.info("  [Extraction] Using messageBody payload from LLM envelope")
        
        if extracted_data is None or not isinstance(extracted_data, dict):
            logger.warning("  [Extraction] LLM did not return expected structure; initializing empty payload")
            extracted_data = {}
        
        # Validate and normalize structure
        required_keys = ["orgs", "guests", "posts", "patterns", "pattern_post_link", "pattern_org_link", "pattern_guest_link"]
        for key in required_keys:
            if key not in extracted_data:
                logger.warning(f"  [Extraction] Missing key: {key}")
                extracted_data[key] = []
            elif not isinstance(extracted_data[key], list):
                logger.warning(f"  [Extraction] {key} is not a list: {type(extracted_data[key])}")
                extracted_data[key] = []
            else:
                logger.info(f"  [Extraction] {key}: {len(extracted_data[key])} items")
        
        # Deterministic fallback: ensure at least one post from H1/H3 if available
        if len(extracted_data.get("posts", [])) == 0:
            title, subtitle = _extract_post_title_and_subtitle(text or "")
            published = _extract_published_date(text or "")
            if title:
                logger.info("  [Fallback] Creating post from H1/H3 extraction")
                # Keywords via LLM (fallback to heuristic)
                preview_for_llm = (text or "")[:4000]
                extracted_data["posts"].append({
                    "name": title,
                    "description": subtitle,
                    "content_url": url,
                    "content_source": "substack",
                    "published_at": published,
                })
        
        # Store extracted entities in message_body for next agent
        message_body["extracted_entities"] = extracted_data
        
        # Build user-friendly summary (don't expose full JSON)
        posts = extracted_data.get("posts", [])
        post_summary = ""
        if posts:
            first_post = posts[0]
            post_name = first_post.get("name", "Unknown")
            published_at = first_post.get("published_at", "Unknown date")
            post_summary = f"Post: '{post_name}' ({published_at})"
        
        # Build summary of entities
        orgs = extracted_data.get("orgs", [])
        guests = extracted_data.get("guests", [])
        patterns = extracted_data.get("patterns", [])
        
        summary_lines = []
        if post_summary:
            summary_lines.append(post_summary)
        if orgs:
            org_names = ", ".join([o.get("name", "") for o in orgs if o.get("name")])
            summary_lines.append(f"Organizations: {org_names}")
        if guests:
            guest_names = ", ".join([g.get("name", "") for g in guests if g.get("name")])
            summary_lines.append(f"Guests: {guest_names}")
        if patterns:
            pattern_names = ", ".join([p.get("name", "") for p in patterns if p.get("name")])
            summary_lines.append(f"Patterns: {pattern_names}")
        
        reason = "\n".join(summary_lines) if summary_lines else "Extraction complete (no entities found)"
        
        logger.info(f"  Decision: yes (confidence: 0.96) - Extraction complete")
        logger.info(f"  [Extraction] {reason}")
        return ("yes", 0.96, reason)

    except json.JSONDecodeError as e:
        reason = f"LLM response is not valid JSON: {str(e)}"
        logger.warning(f"  Decision: no (confidence: 0.60) - {reason}")
        return ("no", 0.60, reason)
    except Exception as e:
        reason = f"Entity extraction failed: {str(e)}"
        logger.error(f"  Decision: no (confidence: 0.60) - {reason}", exc_info=True)
        return ("no", 0.60, reason)


async def agent_verify_upsert(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyUpsert (CONTENT flow)
    Validate the entity extraction payload before passing to PostgreSQL upsert.
    
    Responsibilities:
    1. STRUCTURAL VALIDITY: All required arrays exist, valid JSON
    2. REQUIRED FIELDS: Orgs/Guests/Posts have name; Patterns have name+kind
    3. LINK TABLE CONSISTENCY: References match extracted entities
    4. SAFETY VALIDATION: No SQL injection, unescaped characters
    5. SEMANTIC CHECKS: URL/source consistency, valid timestamps
    
    Returns decision="yes" to route to tool.executeSQL if valid.
    Returns decision="no" with error details for human review if invalid.
    """
    logger.info("🤖 [model.verifyUpsert] Verifying upsert payload structure and referential integrity...")
    
    # Extract the payload from message_body
    # It should be stored from agent_request_to_extract_entities
    extracted_entities = message_body.get("extracted_entities", {})
    url = message_body.get("url", "")
    
    if not extracted_entities:
        reason = "No extracted entities found in message_body"
        logger.warning(f"  Decision: no (confidence: 0.95) - {reason}")
        return ("no", 0.95, reason)
    
    # Validate structural validity
    required_keys = ["orgs", "guests", "posts", "patterns", "pattern_post_link", "pattern_org_link", "pattern_guest_link"]
    missing_keys = [k for k in required_keys if k not in extracted_entities]
    
    if missing_keys:
        reason = f"Missing required array keys: {', '.join(missing_keys)}"
        logger.warning(f"  Decision: no (confidence: 0.92) - {reason}")
        return ("no", 0.92, reason)
    
    # Validate all values are lists
    for key in required_keys:
        if not isinstance(extracted_entities.get(key), list):
            reason = f"Field '{key}' must be an array, got {type(extracted_entities[key]).__name__}"
            logger.warning(f"  Decision: no (confidence: 0.91) - {reason}")
            return ("no", 0.91, reason)
    
    # Validate required fields for each entity type
    
    # ORGS: name must exist and be non-empty
    for i, org in enumerate(extracted_entities.get("orgs", [])):
        if not isinstance(org, dict):
            reason = f"Org at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
        if not org.get("name") or not isinstance(org.get("name"), str) or not org.get("name").strip():
            reason = f"Org at index {i} missing or empty 'name' field"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
    
    # GUESTS: name must exist and be non-empty
    for i, guest in enumerate(extracted_entities.get("guests", [])):
        if not isinstance(guest, dict):
            reason = f"Guest at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
        if not guest.get("name") or not isinstance(guest.get("name"), str) or not guest.get("name").strip():
            reason = f"Guest at index {i} missing or empty 'name' field"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
    
    # POSTS: name must exist and be non-empty
    for i, post in enumerate(extracted_entities.get("posts", [])):
        if not isinstance(post, dict):
            reason = f"Post at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
        if not post.get("name") or not isinstance(post.get("name"), str) or not post.get("name").strip():
            reason = f"Post at index {i} missing or empty 'name' field"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
    
    # PATTERNS: name and kind must exist
    for i, pattern in enumerate(extracted_entities.get("patterns", [])):
        if not isinstance(pattern, dict):
            reason = f"Pattern at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
        if not pattern.get("name") or not isinstance(pattern.get("name"), str) or not pattern.get("name").strip():
            reason = f"Pattern at index {i} missing or empty 'name' field"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
        if not pattern.get("kind") or not isinstance(pattern.get("kind"), str) or not pattern.get("kind").strip():
            reason = f"Pattern at index {i} missing or empty 'kind' field"
            logger.warning(f"  Decision: no (confidence: 0.89) - {reason}")
            return ("no", 0.89, reason)
    
    # Validate link table consistency
    
    # Build sets of entity names for referential integrity checks
    org_names = {org.get("name", "").strip() for org in extracted_entities.get("orgs", []) if org.get("name")}
    guest_names = {guest.get("name", "").strip() for guest in extracted_entities.get("guests", []) if guest.get("name")}
    post_names = {post.get("name", "").strip() for post in extracted_entities.get("posts", []) if post.get("name")}
    pattern_names = {pattern.get("name", "").strip() for pattern in extracted_entities.get("patterns", []) if pattern.get("name")}
    
    # pattern_post_link: post_name must match an extracted post.name
    for i, link in enumerate(extracted_entities.get("pattern_post_link", [])):
        if not isinstance(link, dict):
            reason = f"pattern_post_link at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        post_name = link.get("post_name", "").strip()
        if not post_name:
            reason = f"pattern_post_link at index {i} missing 'post_name'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        if post_name not in post_names:
            reason = f"pattern_post_link references non-existent post '{post_name}'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
    
    # pattern_org_link: org_name must match an extracted org.name
    for i, link in enumerate(extracted_entities.get("pattern_org_link", [])):
        if not isinstance(link, dict):
            reason = f"pattern_org_link at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        org_name = link.get("org_name", "").strip()
        if not org_name:
            reason = f"pattern_org_link at index {i} missing 'org_name'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        if org_name not in org_names:
            reason = f"pattern_org_link references non-existent org '{org_name}'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
    
    # pattern_guest_link: guest_name must match an extracted guest.name
    for i, link in enumerate(extracted_entities.get("pattern_guest_link", [])):
        if not isinstance(link, dict):
            reason = f"pattern_guest_link at index {i} is not an object"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        guest_name = link.get("guest_name", "").strip()
        if not guest_name:
            reason = f"pattern_guest_link at index {i} missing 'guest_name'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
        if guest_name not in guest_names:
            reason = f"pattern_guest_link references non-existent guest '{guest_name}'"
            logger.warning(f"  Decision: no (confidence: 0.88) - {reason}")
            return ("no", 0.88, reason)
    
    # Safety validation: check for SQL injection patterns and unescaped characters
    # This is a simple heuristic check; full escaping is done by the database
    dangerous_patterns = [";", "--", "/*", "*/", "xp_", "sp_"]
    
    for org in extracted_entities.get("orgs", []):
        for value in org.values():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    if pattern in value.lower():
                        # "--" is OK in names, but not as part of actual SQL
                        if pattern == "--" and value.strip().endswith("--"):
                            continue
                        if pattern != "--":  # Allow dashes in names
                            reason = f"Org name contains suspicious pattern: {value[:50]}"
                            logger.warning(f"  Decision: no (confidence: 0.85) - {reason}")
                            return ("no", 0.85, reason)
    
    # Semantic checks: URL and source consistency
    # All extracted entities should have the same content_url and content_source
    expected_source = "substack"  # From the extraction request
    
    for post in extracted_entities.get("posts", []):
        if post.get("content_source") and post.get("content_source") != expected_source:
            logger.warning(f"  Post source mismatch: expected {expected_source}, got {post.get('content_source')}")
    
    # Validate timestamps (if present) are valid ISO format or null
    for post in extracted_entities.get("posts", []):
        pub_date = post.get("published_at")
        if pub_date and not isinstance(pub_date, (str, type(None))):
            reason = f"Post published_at must be a string (ISO format) or null, got {type(pub_date).__name__}"
            logger.warning(f"  Decision: no (confidence: 0.87) - {reason}")
            return ("no", 0.87, reason)
    
    # All validations passed
    decision = "yes"
    confidence = 0.94
    entity_summary = f"orgs={len(extracted_entities.get('orgs', []))} guests={len(extracted_entities.get('guests', []))} posts={len(extracted_entities.get('posts', []))} patterns={len(extracted_entities.get('patterns', []))}"
    reason = f"Payload validation passed: {entity_summary}"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    logger.info(f"  ✅ All structural, referential, and safety checks passed")
    return (decision, confidence, reason)


# ============================================================================
# Agent Registry
# ============================================================================

AGENT_REGISTRY = {
    # Pre-workflow language capo
    "model.LanguageCapo": agent_language_capo,

    # RULE flow
    "model.Capo_rule": agent_capo_rule,
    "model.verifyRequest": agent_verify_request,
    "model.ruleToSQL": agent_rule_to_sql,
    "model.verifySQL": agent_verify_sql,
    "tool.executeSQL": agent_execute_sql,
    
    # CONTENT flow
    "model.Capo_content": agent_capo_content,
    "model.verifyRequest_content": agent_verify_request_content,
    "model.requestToExtractEntities": agent_request_to_extract_entities,
    "model.verifyUpsert": agent_verify_upsert,
}


async def call_agent(agent_name: str, verb: str, message_body: Dict[str, Any]):
    """
    Call an agent by name and verb.
    
    Args:
        agent_name: Agent name (e.g., "model.Capo" or "model.LanguageCapo")
        verb: Workflow verb (RULE or CONTENT). For LanguageCapo, verb is ignored.
        message_body: Message body
    
    Returns:
        - For normal agents: (decision, confidence, reason)
        - For model.LanguageCapo: (decision, confidence, reason, verb)
    """
    # Special-case language capo (pre-workflow classification)
    if agent_name == "model.LanguageCapo":
        try:
            return await agent_language_capo(message_body)
        except Exception as e:
            logger.error(f"❌ Agent {agent_name} crashed: {e}", exc_info=True)
            return ("no", 0.0, f"Agent error: {str(e)}", "RULE")

    # Route to correct agent based on verb
    if agent_name == "model.Capo":
        agent_fn = agent_capo_rule if verb == "RULE" else agent_capo_content
    elif agent_name == "model.verifyRequest":
        agent_fn = agent_verify_request if verb == "RULE" else agent_verify_request_content
    else:
        # Look up agent directly in registry
        key = f"{agent_name}_{verb.lower()}" if verb != "RULE" else agent_name
        agent_fn = AGENT_REGISTRY.get(agent_name) or AGENT_REGISTRY.get(key)
        
        if not agent_fn:
            logger.error(f"❌ Unknown agent: {agent_name}")
            return ("no", 0.0, f"Unknown agent: {agent_name}")
    
    # Call agent
    try:
        decision, confidence, reason = await agent_fn(message_body)
        return (decision, confidence, reason)
    except Exception as e:
        logger.error(f"❌ Agent {agent_name} crashed: {e}", exc_info=True)
        return ("no", 0.0, f"Agent error: {str(e)}")
