"""
Pitboss Supervisor — Pattern Factory Edition
(Nov 2025 Clean Version)

Responsibilities:
- Build LLM context (SYSTEM + DATA + RULE LOGIC)
- Generate SQL via sql_pitboss tool
- Create a materialized view via data_table tool
- Register the rule + link to views_registry
- Push results over WebSocket
"""

import logging
from datetime import datetime
from typing import Optional

from .config import get_config
from .context_builder import ContextBuilder
from .tools import ToolRegistry

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

        logger.info("🧠 Pitboss Supervisor initialized")

    # ----------------------------------------------------------------------
    # Incoming WebSocket Request Dispatcher
    # ----------------------------------------------------------------------
    async def process_rule_request(
        self,
        rule_code: str,
        rule_id: Optional[str] = None
    ):
        """
        Main entry point from WebSocket.
        rule_code: Natural-language rule logic from user OR rule code when using the chat shortcut
        rule_id: Stable identifier from YAML (e.g., LIST_ORGS) – if missing, we treat rule_code as the id
        """
        # Normalize: prefer explicit rule_id, else use rule_code as the identifier
        rule_identifier = rule_id or rule_code
        logger.info(f"[Supervisor] Processing rule: {rule_identifier}")

        # Resolve the YAML rule entry by code (so we get a stable name + logic)
        rule_entry = self._get_rule_from_yaml(rule_identifier)
        if not rule_entry:
            # Deterministic error when the rule code is unknown
            available = ", ".join(self._list_rule_codes()) or "(no rules found)"
            msg = f"Rule '{rule_identifier}' not found in DSL. Try one of: {available}."
            return await self._send_error(rule_identifier, msg)

        # Use the DSL-provided name and logic
        rule_name = rule_entry.get("name") or rule_identifier
        logic = rule_entry.get("logic") or ""

        return await self._process_single_rule(
            rule_code_key=rule_identifier,
            rule_name=rule_name,
            logic=logic
        )

    # ----------------------------------------------------------------------
    # Core Rule Pipeline
    # ----------------------------------------------------------------------
    async def _process_single_rule(self, rule_code_key: str, rule_name: str, logic: str):
        """
        Pipeline for a single natural-language rule:

        1. Build system + user context
        2. Call LLM → SQL (sql_pitboss)
        3. Create materialized view (data_table)
        4. Register rule (register_rule)  - UPSERT on rule_code_key
        5. Register view (views_registry)
        
        rule_code_key: Stable identifier from YAML (e.g., PATTERN_IN_EPISODE)
        rule_name: Display name from YAML (e.g., "Patterns in Episodes")
        logic: Natural language rule description
        """
        
        # Use rule_name from YAML
        display_name = rule_name or rule_code_key

        try:
            # 1. Build full context
            context = self.context_builder.build_context(rule_code=logic)

            messages = [
                {"role": "system", "content": context["system"]},
                {"role": "user",   "content": logic}
            ]

            # 2. LLM → SQL
            sql_result = await self.tool_registry.execute("sql_pitboss", messages=messages)
            if sql_result["status"] != "success":
                return await self._send_error(display_name, sql_result["error"])

            sql_query = sql_result["sql"]

            # 3. Create materialized view
            table_res = await self.tool_registry.execute(
                "data_table",
                sql_query=sql_query,
                rule_name=display_name
            )
            if table_res["status"] != "success":
                return await self._send_error(display_name, table_res["error"])

            table_name = table_res["table_name"]
            row_count = table_res["row_count"]

            # 4. Register rule - use rule_code_key for UPSERT
            rule_res = await self.tool_registry.execute(
                "register_rule",
                rule_code_key=rule_code_key,
                rule_name=display_name,
                logic=logic,
                sql_query=sql_query
            )
            if rule_res["status"] != "success":
                logger.error(f"[Supervisor] Failed to register rule: {rule_res.get('error')}")
                return await self._send_error(display_name, f"Failed to register rule: {rule_res.get('error')}")

            # 5. Register view in views_registry
            view_res = await self.tool_registry.execute(
                "register_view",
                rule_code_key=rule_code_key,
                table_name=table_name,
                summary=display_name
            )
            if view_res["status"] != "success":
                logger.error(f"[Supervisor] Failed to register view: {view_res.get('error')}")
                return await self._send_error(display_name, f"Failed to register view: {view_res.get('error')}")

            # Push to frontend with better formatting
            msg = f"Rule {display_name} ({rule_code_key}) created/replaced a view which returns {row_count} rows."
            await self._send_to_frontend(msg)
            # Also notify frontend sidebars to refresh
            await self._send_event("views:refresh", {"table": table_name, "rule": display_name})

            return {
                "status": "success",
                "rule": display_name,
                "table": table_name,
                "rows": row_count
            }

        except Exception as e:
            logger.error(f"[Supervisor] Crash in rule {display_name}: {e}", exc_info=True)
            return await self._send_error(display_name, str(e))

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
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
