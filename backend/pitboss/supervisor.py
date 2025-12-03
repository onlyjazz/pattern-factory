"""
Pitboss Supervisor — Pattern Factory Edition
(Nov 2025 Message Protocol Version)

Responsibilities:
- Receive MessageEnvelope requests via WebSocket
- Route requests through WorkflowEngine decision trees
- Call stub agents and orchestrate decisions
- Send MessageEnvelope responses back to frontend
- Support HITL (human-in-the-loop) for "no" decisions
"""

import logging
from datetime import datetime
from typing import Optional
import uuid

from .config import get_config
from .context_builder import ContextBuilder
from .tools import ToolRegistry
from .envelope import (
    MessageEnvelope,
    MessageType,
    Verb,
    Decision,
    make_response,
    make_error,
    make_success,
)
from .workflow import WorkflowEngine
from .agents import call_agent

logger = logging.getLogger(__name__)


class PitbossSupervisor:
    """
    Orchestrates rule execution for Pattern Factory.
    """

    def __init__(self, db_connection, websocket=None):
        self.db = db_connection
        self.websocket = websocket
        self.config = get_config()

        # Components
        self.context_builder = ContextBuilder(db_connection)
        self.tool_registry = ToolRegistry(db_connection, self.config)
        self.workflow_engine = WorkflowEngine()

        logger.info("🧠 Pitboss Supervisor initialized")


    # ----------------------------------------------------------------------
    # Message Protocol Processing
    # ----------------------------------------------------------------------
    async def process_envelope(self, envelope_dict: dict):
        """
        Process a MessageEnvelope through the message protocol workflow.
        
        Entry point: validate envelope structure and verb before proceeding.
        """
        # Step 0: Validate envelope has required fields and valid verb
        session_id = envelope_dict.get("session_id", "")
        request_id = envelope_dict.get("request_id", "")
        verb_str = (envelope_dict.get("verb") or "").strip().upper()
        
        # Check for invalid verb
        if not verb_str:
            error_msg = "Missing or empty 'verb' field. Must be: RULE or CONTENT"
            logger.error(f"Invalid envelope: {error_msg}")
            if self.websocket:
                await self.websocket.send_json(make_error(
                    session_id=session_id,
                    request_id=request_id,
                    verb=Verb.GENERIC,
                    error_message=error_msg
                ).to_dict())
            return
        
        if verb_str not in [v.value for v in Verb]:
            error_msg = f"Invalid verb '{verb_str}'. Must be: RULE or CONTENT"
            logger.error(f"Invalid envelope: {error_msg}")
            if self.websocket:
                await self.websocket.send_json(make_error(
                    session_id=session_id,
                    request_id=request_id,
                    verb=Verb.GENERIC,
                    error_message=error_msg
                ).to_dict())
            return
        
        # Envelope is valid - proceed
        try:
            env = MessageEnvelope.from_dict(envelope_dict)
        except Exception as e:
            error_msg = f"Invalid envelope: {e}"
            logger.error(f"Envelope parsing failed: {error_msg}")
            if self.websocket:
                await self.websocket.send_json(make_error(
                    session_id=session_id,
                    request_id=request_id,
                    verb=Verb(verb_str),
                    error_message=error_msg
                ).to_dict())
            return

        # Check if this is a HITL return from human
        is_hitl_return = env.nextAgent and env.nextAgent not in ("model.LanguageCapo", "sendMessageToChat", None)
        
        if is_hitl_return:
            # HITL return: skip classification, go directly to nextAgent
            logger.info(f"📋 HITL return from human - routing to {env.nextAgent}")
            verb_str = env.verb.value if isinstance(env.verb, Verb) else str(env.verb)
            current_agent = env.nextAgent
        else:
            # New message: classify intent via LanguageCapo
            if env.verb.value == "GENERIC" or env.nextAgent == "model.LanguageCapo":
                logger.info(f"📋 Classifying user intent via LanguageCapo...")
                
                # Prepare body with raw text for language classification
                message_body_for_capo = env.messageBody.copy()
                if "rule_text" in message_body_for_capo and "raw_text" not in message_body_for_capo:
                    message_body_for_capo["raw_text"] = message_body_for_capo["rule_text"]
                
                # Call language capo (returns 4-tuple with verb)
                result = await call_agent("model.LanguageCapo", "GENERIC", message_body_for_capo)
                
                if len(result) == 4:
                    decision, confidence, reason, verb_determined = result
                else:
                    decision, confidence, reason = result
                    verb_determined = "RULE"
                
                logger.info(f"  Classification: {verb_determined} (confidence: {confidence:.2f})")
                
                # Validate verb from LanguageCapo
                verb_determined = (verb_determined or "").strip().upper()
                if verb_determined not in [v.value for v in Verb]:
                    error_msg = f"LanguageCapo returned invalid verb: {verb_determined}"
                    logger.error(error_msg)
                    if self.websocket:
                        await self.websocket.send_json(make_error(
                            session_id=env.session_id,
                            request_id=env.request_id,
                            verb=Verb.GENERIC,
                            error_message=error_msg
                        ).to_dict())
                    return
                
                verb_str = verb_determined
            else:
                verb_str = env.verb.value if isinstance(env.verb, Verb) else str(env.verb)

            # If user asked to run a rule code, populate message_body with rule metadata
            if verb_str == "RULE":
                rule_code = self._extract_rule_code_from_message(env.messageBody)
                if rule_code:
                    logger.info(f"📋 Detected explicit rule code: {rule_code}")
                    rule_entry = self._get_rule_from_yaml(rule_code)
                    if rule_entry:
                        logger.info(f"📋 Looked up rule from YAML: {rule_code}")
                        rule_name = rule_entry.get("name") or rule_code
                        rule_logic = rule_entry.get("logic") or ""
                        env.messageBody["rule_code"] = rule_code
                        env.messageBody["rule_name"] = rule_name
                        env.messageBody["rule_logic"] = rule_logic
                        env.messageBody["_tools"] = self.tool_registry
                        env.messageBody["_ctx"] = self.context_builder
            
            # Start workflow with Capo
            current_agent = "model.Capo"
        
        # Update env verb for consistency
        env.verb = Verb(verb_str)
        
        # Ensure context builder and tool registry are always available to agents
        # (unless explicitly added earlier for rule code lookups)
        if "_ctx" not in env.messageBody:
            env.messageBody["_ctx"] = self.context_builder
        if "_tools" not in env.messageBody:
            env.messageBody["_tools"] = self.tool_registry

        # Walk the decision tree until terminal or HITL (decision=no)
        while True:
            decision, confidence, reason = await call_agent(current_agent, verb_str, env.messageBody)
            # Normalize decision to enum
            dec_enum = Decision(decision) if isinstance(decision, str) else decision

            next_agent = self.workflow_engine.get_next_agent(verb_str, current_agent, dec_enum.value)

            # Strip internal dependencies before sending to frontend
            frontend_body = {k: v for k, v in env.messageBody.items() if not k.startswith("_")}
            
            # Send response (with appropriate return_code based on decision)
            return_code = -1 if dec_enum == Decision.NO else 0
            # For HITL (NO), recommend the agent to run after human approval
            hitl_next = self.workflow_engine.get_hitl_next_agent(verb_str, current_agent) if dec_enum == Decision.NO else next_agent
            step_resp = make_response(
                session_id=env.session_id,
                request_id=env.request_id,
                verb=env.verb,
                next_agent=hitl_next,
                decision=dec_enum,
                confidence=float(confidence),
                reason=str(reason),
                message_body=frontend_body,
                return_code=return_code,
            )
            await self._send_envelope(step_resp)

            # HITL on decision=no
            if dec_enum == Decision.NO:
                return

            # Terminal
            if next_agent is None or self.workflow_engine.is_terminal(next_agent):
                # Send views:refresh event if rule was executed (RULE verb)
                if env.verb == Verb.RULE and "table_name" in env.messageBody:
                    await self._send_event("views:refresh", {
                        "table_name": env.messageBody.get("table_name"),
                        "rule_code": env.messageBody.get("rule_code"),
                        "rule_name": env.messageBody.get("rule_name")
                    })
                
                success = make_success(
                    session_id=env.session_id,
                    request_id=env.request_id,
                    verb=env.verb,
                    message_body={"success": True}
                )
                await self._send_envelope(success)
                return

            # Continue to next agent
            current_agent = next_agent

    # Shared helper to look up rule in YAML
    def _extract_rule_code_from_message(self, message_body: dict) -> Optional[str]:
        """
        Extract rule code from message using agents' inline extraction logic.
        """
        from .agents import _extract_rule_code_inline
        raw_text = message_body.get("raw_text") or ""
        return _extract_rule_code_inline(raw_text)
    
    def _get_rule_from_yaml(self, rule_code: str):
        """
        Return the entire RULE entry dict for a given rule_code, or None.
        """
        if not rule_code:
            return None
        rules = self.context_builder.yaml_data.get("RULES", [])
        for rule in rules:
            if rule.get("rule_code") == rule_code:
                return rule
        return None

    def _list_rule_codes(self):
        rules = self.context_builder.yaml_data.get("RULES", [])
        return [r.get("rule_code") for r in rules if r.get("rule_code")]

    async def _send_to_frontend(self, message: str):
        if self.websocket:
            await self.websocket.send_json({
                "type": "rule_result",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })

    async def _send_event(self, event: str, payload: dict):
        if self.websocket:
            await self.websocket.send_json({
                "type": "event",
                "event": event,
                "payload": payload,
                "timestamp": datetime.now().isoformat()
            })

    async def _send_error(self, rule_name: str, msg: str):
        logger.error(f"[Supervisor] Error in {rule_name}: {msg}")
        if self.websocket:
            await self.websocket.send_json({
                "type": "error",
                "rule": rule_name,
                "message": msg,
                "timestamp": datetime.now().isoformat()
            })
        return {"status": "error", "rule": rule_name, "error": msg}

    async def _send_envelope(self, envelope: MessageEnvelope):
        if self.websocket:
            await self.websocket.send_json(envelope.to_dict())
