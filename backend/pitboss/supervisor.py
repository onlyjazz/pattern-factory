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

import asyncio
import logging
import re
import yaml
from datetime import datetime
from typing import Any, Dict, Optional

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
        system_prompt: Optional[str] = None,
        protocol_id: Optional[str] = None,   # unused but kept for compatibility
        rule_id: Optional[str] = None
    ):
        """
        Main entry point from WebSocket.
        For Pattern Factory, rule_code = natural-language logic.
        """
        logger.info(f"[Supervisor] Received rule request: {rule_code[:100]}")

        return await self._process_single_rule(
            rule_name=rule_id or self._auto_rule_name(rule_code),
            logic=rule_code
        )

    # ----------------------------------------------------------------------
    # Core Rule Pipeline
    # ----------------------------------------------------------------------
    async def _process_single_rule(self, rule_name: str, logic: str):
        """
        Pipeline for a single natural-language rule:

        1. Build system + user context
        2. Call LLM → SQL (sql_pitboss)
        3. Create materialized view (data_table)
        4. Register rule (register_rule)
        5. Register view (views_registry)
        """

        try:
            # 1. Build full context
            context = self.context_builder.build_context(
                rule_code=logic,
                include_examples=False,
                dsl=None
            )

            messages = [
                {"role": "system", "content": context["system"]},
                {"role": "user",   "content": logic}
            ]

            # 2. LLM → SQL
            sql_result = await self.tool_registry.execute("sql_pitboss", messages=messages)
            if sql_result["status"] != "success":
                return await self._send_error(rule_name, sql_result["error"])

            sql_query = sql_result["sql"]

            # 3. Create materialized view
            table_res = await self.tool_registry.execute(
                "data_table",
                sql_query=sql_query,
                rule_name=rule_name
            )
            if table_res["status"] != "success":
                return await self._send_error(rule_name, table_res["error"])

            table_name = table_res["table_name"]
            row_count = table_res["row_count"]

            # 4. Register rule
            rule_reg = await self.tool_registry.execute(
                "register_rule",
                rule_name=rule_name,
                logic=logic,
                sql_query=sql_query
            )

            # 5. Register view in views_registry
            await self.tool_registry.execute(
                "register_view",
                rule_name=rule_name,
                table_name=table_name,
                sql_query=sql_query,
                summary=row_count
            )

            # Push to frontend
            msg = f"Rule {rule_name} → {row_count} rows → {table_name}"
            await self._send_to_frontend(msg)

            return {
                "status": "success",
                "rule": rule_name,
                "table": table_name,
                "rows": row_count
            }

        except Exception as e:
            logger.error(f"[Supervisor] Crash in rule {rule_name}: {e}")
            return await self._send_error(rule_name, str(e))

    # ----------------------------------------------------------------------
    # Workflow (Phase 2)
    # ----------------------------------------------------------------------
    async def run_workflow(self, dsl_text: str):
        """
        Workflow execution via DSL.
        Phase 1: stub
        """
        try:
            dsl = yaml.safe_load(dsl_text)
            rules = dsl.get("RULES", [])

            results = []
            for r in rules:
                name = r.get("name") or self._auto_rule_name(r.get("logic", ""))
                logic = r.get("logic")
                result = await self._process_single_rule(name, logic)
                results.append(result)

            return {"status": "success", "results": results}

        except Exception as e:
            return await self._send_error("WORKFLOW", str(e))

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _auto_rule_name(self, text: str) -> str:
        """
        Generate a safe rule name from natural language.
        """
        base = text.lower().strip().replace(" ", "_")
        base = re.sub(r"[^a-z0-9_]", "", base)
        return base[:64] or "unnamed_rule"

    async def _send_to_frontend(self, message: str):
        if self.websocket:
            await self.websocket.send_json({
                "type": "rule_result",
                "message": message,
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


# ----------------------------------------------------------------------
# Backwards-compatible alias
# ----------------------------------------------------------------------
class Pitboss(PitbossSupervisor):
    pass
