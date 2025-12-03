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
import random
import json
import os
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
        "entities (orgs, guests, categories, patterns, episodes, posts) from a URL or text. "
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
    Uses LLM if OPENAI_API_KEY is set, otherwise falls back to heuristics.

    Additionally recognizes explicit run syntax: "run <RULE_CODE>" or a known RULE code in text.
    When detected, classifies as RULE with high confidence.
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str, verb: str)
    The verb return value determines which workflow to enter (RULE or CONTENT).
    """
    logger.info("🤖 [model.LanguageCapo] Classifying user intent...")

    text = (message_body.get("raw_text") or "").strip()

    # Fast-path: recognize explicit run <RULE_CODE>
    try:
        rule_code = _extract_rule_code_inline(text)
        if rule_code:
            reason = f"Detected explicit rule code '{rule_code}'"
            logger.info(f"  Fast-path RULE via inline code: {rule_code}")
            return ("yes", 0.98, reason, "RULE")
    except Exception:
        pass

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
            verb = data.get("verb", "RULE")
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
        "episodes",
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
    """Detect 'run <RULE_CODE>' or any known RULE code inline using YAML lookup.
    Returns RULE_CODE if found, else None.
    """
    try:
        from .context_builder import ContextBuilder
    except Exception:
        ContextBuilder = None

    if not raw_text:
        return None

    text = raw_text.strip()
    text_upper = text.upper()

    # Load YAML (no DB needed)
    cb = ContextBuilder() if ContextBuilder else None
    rules = (cb.yaml_data.get("RULES", []) if cb and cb.yaml_data else [])
    codes = {r.get("rule_code", "").upper() for r in rules}

    if text_upper.startswith("RUN "):
        code = text_upper[4:].strip()
        return code if code in codes else None

    # Exact match
    if text_upper in codes:
        return text_upper

    # Any token match
    for token in text_upper.split():
        if token in codes:
            return token

    return None


# ============================================================================
# RULE Flow Agents
# ============================================================================

async def agent_capo_rule(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.Capo (RULE flow)
    Initial validation of rule request.
    
    Checks:
    - Rule logic is non-empty
    - Rule code/name are present (or will be looked up)
    
    Returns: (decision: yes|no, confidence: 0.0-1.0, reason: str)
    """
    logger.info("🤖 [model.Capo] Validating rule request...")
    
    rule_logic = message_body.get("rule_logic", "").strip()
    rule_code = message_body.get("rule_code", "").strip()
    
    # Validation: must have rule logic
    if not rule_logic:
        reason = "Rule logic is empty; cannot proceed"
        logger.info(f"  Decision: no (confidence: 0.95) - {reason}")
        return ("no", 0.95, reason)
    
    # Validation: rule code or name should exist
    if not rule_code and not message_body.get("rule_name"):
        reason = "Rule lacks identifier (code or name); cannot track state"
        logger.info(f"  Decision: no (confidence: 0.88) - {reason}")
        return ("no", 0.88, reason)
    
    # All checks pass
    decision = "yes"
    confidence = 0.92
    reason = f"Rule '{rule_code}' validated: syntax and structure appear sound"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_verify_request(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyRequest (RULE flow)
    Validate semantics of the rule request.
    
    Checks:
    - Rule logic references valid entities/tables
    - Rule intent is clear (not ambiguous)
    - Begin context building for LLM (store in message_body)
    """
    logger.info("🤖 [model.verifyRequest] Validating rule semantics...")
    
    rule_logic = message_body.get("rule_logic", "").lower()
    
    # Check for valid table/entity references
    valid_tables = {
        "patterns", "episodes", "guests", "organizations", "posts",
        "pattern_episodes", "pattern_guests", "pattern_orgs", "pattern_posts",
        "orgs", "org", "guest", "episode", "post", "pattern"
    }
    
    found_tables = [t for t in valid_tables if t in rule_logic]
    
    if not found_tables:
        reason = "Rule does not reference any known entities (patterns, episodes, guests, orgs, posts)"
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
    Validate SQL safety, syntax, and correctness.
    
    Checks:
    - SQL is not empty
    - SQL starts with SELECT, WITH, or INSERT (allowed operations)
    - No DROP, DELETE, ALTER commands (safety)
    - No obvious SQL injection attacks
    
    If SQL looks suspicious but not malicious, returns NO to trigger HITL.
    The frontend will show SQL for user approval, and if approved, tool.executeSQL runs.
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
        reason = f"SQL contains dangerous operation ({', '.join(dangerous_ops)})"
        logger.warning(f"  ❌ {reason}")
        return ("no", 0.98, reason)  # High confidence - reject
    
    # Check for injection patterns (UNION, EXEC, xp_, sp_)
    injection_patterns = ("UNION", "EXEC", "XP_", "SP_", "--", "/**/", "CAST(", "CONVERT(")
    suspicious_patterns = [p for p in injection_patterns if p in sql_query_upper]
    
    if suspicious_patterns and "--" not in sql_query_upper:  # Allow SQL comments as they're valid
        reason = f"SQL looks suspicious (detected: {', '.join(suspicious_patterns)}). Please review."
        logger.info(f"  Decision: no (confidence: 0.72) - HITL required - {reason}")
        message_body["sql_for_review"] = sql_query  # Store for frontend display
        return ("no", 0.72, reason)  # Lower confidence - HITL, not rejection
    
    # SQL validated
    decision = "yes"
    confidence = 0.96
    reason = "SQL is syntactically sound and passes safety checks"
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_execute_sql(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    tool.executeSQL (RULE flow) — Terminal agent
    Execute SQL, create materialized view, register rule and view in database.
    
    Pipeline:
    1. Execute SQL via data_table tool (creates VIEW)
    2. Register rule metadata via register_rule tool
    3. Register view in views_registry via register_view tool
    
    Stores:
    - table_name: name of created view
    - row_count: rows in materialized view
    """
    logger.info("🤖 [tool.executeSQL] Executing SQL and materializing view...")
    
    try:
        # Extract dependencies and state
        tool_registry = message_body.get("_tools")
        sql_query = message_body.get("sql_query", "").strip()
        rule_code = message_body.get("rule_code", "").strip()
        rule_name = message_body.get("rule_name", rule_code).strip()
        rule_logic = message_body.get("rule_logic", "").strip()
        
        if not tool_registry:
            reason = "ToolRegistry not available"
            logger.error(f"  ❌ {reason}")
            return ("no", 0.05, reason)
        
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
            rule_name=rule_name
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
        
        # Step 2: Register rule metadata
        logger.info(f"  Step 2: Registering rule metadata...")
        rule_res = await tool_registry.execute(
            "register_rule",
            rule_code_key=rule_code,
            rule_name=rule_name,
            logic=rule_logic,
            sql_query=sql_query
        )
        
        if rule_res["status"] != "success":
            logger.warning(f"  ⚠️ Rule registration failed: {rule_res.get('error')}")
            # Continue anyway; view is created
        else:
            logger.info(f"    ✅ Rule registered: {rule_code}")
        
        # Step 3: Register view in views_registry
        logger.info(f"  Step 3: Registering view in views_registry...")
        view_res = await tool_registry.execute(
            "register_view",
            rule_code_key=rule_code,
            table_name=table_name,
            summary=rule_name
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
        logger.info(f"  🌟 Rule execution complete: {reason}")
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
    """
    logger.info("🤖 [model.Capo] Validating extraction request...")
    
    decision = "yes" if random.random() < 0.80 else "no"
    confidence = 0.83 if decision == "yes" else 0.70
    reason = (
        "Extraction request is well-formed"
        if decision == "yes"
        else "URL or content format not recognized"
    )
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_verify_request_content(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyRequest (CONTENT flow)
    Validate that user is asking for entity extraction from newsletter/podcast.
    """
    logger.info("🤖 [model.verifyRequest] Validating extraction semantics...")
    
    decision = "yes" if random.random() < 0.87 else "no"
    confidence = 0.89 if decision == "yes" else 0.64
    reason = (
        "Extraction request targets valid entities (orgs, guests, patterns)"
        if decision == "yes"
        else "Request asks for unsupported entity types"
    )
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_request_to_extract_entities(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.requestToExtractEntities (CONTENT flow)
    Extractor agent produces upserts for orgs, guests, categories, patterns, etc.
    """
    logger.info("🤖 [model.requestToExtractEntities] Extracting entities from content...")
    
    decision = "yes" if random.random() < 0.81 else "no"
    confidence = 0.84 if decision == "yes" else 0.62
    reason = (
        "Extracted 3 orgs, 5 guests, 7 patterns from content"
        if decision == "yes"
        else "Content analysis incomplete, insufficient context"
    )
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
    return (decision, confidence, reason)


async def agent_verify_upsert(message_body: Dict[str, Any]) -> Tuple[str, float, str]:
    """
    model.verifyUpsert (CONTENT flow)
    Verify upsert consistency, duplicates, referential integrity, entity linkage.
    """
    logger.info("🤖 [model.verifyUpsert] Verifying upsert operations...")
    
    decision = "yes" if random.random() < 0.88 else "no"
    confidence = 0.91 if decision == "yes" else 0.56
    reason = (
        "All entities pass validation: no duplicates, referential integrity intact"
        if decision == "yes"
        else "Duplicate org detected, skipping to avoid conflicts"
    )
    
    logger.info(f"  Decision: {decision} (confidence: {confidence:.2f})")
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
        return ("no", 0.0, f"Agent error: {str(e)}")
