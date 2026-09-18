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
        # Check for YAML hot-reload before processing any request
        self.context_builder.reload_if_changed()
        
        # Step 0: Parse envelope
        session_id = envelope_dict.get("session_id", "")
        request_id = envelope_dict.get("request_id", "")
        
        try:
            env = MessageEnvelope.from_dict(envelope_dict)
        except Exception as e:
            error_msg = f"Invalid envelope structure: {e}"
            logger.error(f"Envelope parsing failed: {error_msg}")
            if self.websocket:
                await self.websocket.send_json(make_error(
                    session_id=session_id,
                    request_id=request_id,
                    verb=Verb.GENERIC,
                    error_message=error_msg
                ).to_dict())
            return
        
        verb_str = (env.verb.value if isinstance(env.verb, Verb) else str(env.verb)).strip().upper()

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
                
                # Call language capo (returns 4-tuple: decision, confidence, reason, verb)
                result = await call_agent("model.LanguageCapo", "GENERIC", message_body_for_capo)
                
                if len(result) == 4:
                    decision, confidence, reason, verb_determined = result
                else:
                    decision, confidence, reason = result
                    verb_determined = "RUN"
                
                logger.info(f"  Classification: {verb_determined} (decision: {decision}, confidence: {confidence:.2f})")
                
                # If LanguageCapo couldn't classify (decision=no), send HITL response and return
                if decision == "no":
                    logger.info(f"  LanguageCapo could not classify: {reason}")
                    step_resp = make_response(
                        session_id=env.session_id,
                        request_id=env.request_id,
                        verb=Verb.GENERIC,
                        next_agent=None,
                        decision=Decision.NO,
                        confidence=float(confidence),
                        reason=str(reason),
                        message_body=env.messageBody.copy(),
                        return_code=-1,
                    )
                    await self._send_envelope(step_resp)
                    return
                
                # Verb is determined - use it
                verb_determined = (verb_determined or "").strip().upper()
                verb_str = verb_determined
            else:
                verb_str = env.verb.value if isinstance(env.verb, Verb) else str(env.verb)
            
            # Start workflow with model.Capo
            current_agent = "model.Capo"
        
        # Update env verb for consistency
        env.verb = Verb(verb_str)
        
        # Ensure context builder and tool registry are always available to agents
        # (unless explicitly added earlier for rule code lookups)
        if "_ctx" not in env.messageBody:
            env.messageBody["_ctx"] = self.context_builder
        if "_tools" not in env.messageBody:
            env.messageBody["_tools"] = self.tool_registry
        if "_db" not in env.messageBody:
            env.messageBody["_db"] = self.db
        
        # Pass verb into message_body for agents to detect flow (RULE vs CONTENT)
        env.messageBody["_verb"] = verb_str

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
                # Send views:refresh event if rule was executed
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
