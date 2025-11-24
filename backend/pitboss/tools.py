"""
Pattern Factory Tool Registry (async Postgres version)
(Nov 2025 — clean rewrite)

Tools:
- sql_pitboss:   LLM → SQL
- data_table:    SQL → CREATE TABLE AS SELECT
- register_rule: Insert/update rule metadata
- register_view: Insert view entry in views_registry
"""

import asyncio
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------------
# Base Tool
# -------------------------------------------------------------------------
class Tool:
    def __init__(self, name: str, db_pool=None):
        self.name = name
        self.db_pool = db_pool      # asyncpg pool
        self.metrics = {
            "executions": 0,
            "successes": 0,
            "failures": 0,
            "total_time": 0,
        }

    async def execute(self, **kwargs) -> Dict[str, Any]:
        raise NotImplementedError

    def log_execution(self, success: bool, duration: float):
        self.metrics["executions"] += 1
        if success:
            self.metrics["successes"] += 1
        else:
            self.metrics["failures"] += 1
        self.metrics["total_time"] += duration


# -------------------------------------------------------------------------
# SQL Pitboss Tool — LLM → SQL
# -------------------------------------------------------------------------
class SqlPitbossTool(Tool):
    """
    Calls OpenAI to convert natural-language logic → SQL.
    """

    def __init__(self, db_pool, config):
        super().__init__("sql_pitboss", db_pool)
        self.config = config
        self.client = OpenAI()

    async def execute(self, messages: List[Dict[str, str]], **kwargs):
        start = datetime.now()
        try:
            params = self.config.get_model_params()

            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                messages=messages,
                **params
            )

            content = response.choices[0].message.content.strip()
            sql = self._extract_sql(content)

            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)

            return {
                "status": "success",
                "sql": sql,
                "raw": content,
                "duration": duration,
            }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[SqlPitbossTool] Error: {e}")

            return {"status": "error", "error": str(e), "duration": duration}

    def _extract_sql(self, content: str) -> str:
        """Extract SQL from code block or inline."""
        block = re.search(r"```(?:sql)?\s*([^`]+)```", content, re.I | re.S)
        if block:
            return block.group(1).strip()

        inline = re.search(r"\b(SELECT|INSERT|UPDATE|DELETE|WITH)\b.*", content, re.I | re.S)
        if inline:
            return inline.group(0).strip()

        return content.strip()


# -------------------------------------------------------------------------
# Data Table Tool — Create physical table from SELECT
# -------------------------------------------------------------------------
class DataTableTool(Tool):
    """
    Convert SQL → logical view (CREATE OR REPLACE VIEW)
    and return the row count.
    """

    async def execute(self, sql_query: str, rule_name: str, **kwargs):
        start = datetime.now()
        try:
            view_name = self._safe_table_name(rule_name)
            select_sql = self._strip_to_select(sql_query)

            async with self.db_pool.acquire() as conn:
                # Drop view if exists, then create or replace
                await conn.execute(f"DROP VIEW IF EXISTS {view_name}")
                await conn.execute(f"CREATE VIEW {view_name} AS {select_sql}")

                row = await conn.fetchrow(f"SELECT COUNT(*) AS c FROM {view_name}")
                row_count = row["c"] if row else 0

            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)

            return {
                "status": "success",
                "table_name": view_name,
                "row_count": row_count,
                "duration": duration,
            }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[DataTableTool] Error: {e}")

            return {"status": "error", "error": str(e), "duration": duration}

    def _safe_table_name(self, rule_name: str) -> str:
        name = rule_name.lower().strip()
        name = re.sub(r"[^a-z0-9_]", "_", name)
        if re.match(r"^\d", name):
            name = "v_" + name
        return name

    def _strip_to_select(self, sql: str) -> str:
        cleaned = sql.strip().strip("`").strip()
        return cleaned


# -------------------------------------------------------------------------
# Register Rule Tool — write to rules table
# -------------------------------------------------------------------------
class RegisterRuleTool(Tool):
    """
    Insert or update a rule in the `rules` table:
    id (serial), name, description, rule_code, sql, created_at, updated_at
    """

    async def execute(self, rule_name: str, logic: str, sql_query: str, **kwargs):
        start = datetime.now()
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO rules (name, description, rule_code, sql)
                    VALUES ($1, $2, $3, $4)
                    ON CONFLICT (name)
                    DO UPDATE SET
                        description = EXCLUDED.description,
                        rule_code   = EXCLUDED.rule_code,
                        sql         = EXCLUDED.sql
                """, rule_name, logic, logic, sql_query)

            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)

            return {"status": "success", "rule": rule_name, "duration": duration}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[RegisterRuleTool] Error: {e}")

            return {"status": "error", "error": str(e), "duration": duration}


# -------------------------------------------------------------------------
# Register View Tool — record in views_registry
# -------------------------------------------------------------------------
class RegisterViewTool(Tool):
    """
    Register materialized view info into views_registry:
    id, rule_id, table_name, summary, created_at, updated_at
    """

    async def execute(self, rule_name: str, table_name: str, sql_query: str, summary: int, **kwargs):
        start = datetime.now()
        try:
            async with self.db_pool.acquire() as conn:

                row = await conn.fetchrow(
                    "SELECT id FROM rules WHERE name=$1 LIMIT 1", rule_name
                )
                rule_id = row["id"] if row else None

                await conn.execute("""
                    INSERT INTO views_registry (rule_id, table_name, summary)
                    VALUES ($1, $2, $3)
                """, rule_id, table_name, summary)

            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)

            return {"status": "success", "view": table_name, "duration": duration}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[RegisterViewTool] Error: {e}")

            return {"status": "error", "error": str(e), "duration": duration}


# -------------------------------------------------------------------------
# Tool Registry
# -------------------------------------------------------------------------
class ToolRegistry:
    def __init__(self, db_pool, config):
        self.db_pool = db_pool
        self.config = config
        self.tools = {}

        self._register_default_tools()

    def _register_default_tools(self):
        self.register(SqlPitbossTool(self.db_pool, self.config))
        self.register(DataTableTool(self.db_pool))
        self.register(RegisterRuleTool(self.db_pool))
        self.register(RegisterViewTool(self.db_pool))

    def register(self, tool: Tool):
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")

    def get(self, name: str) -> Optional[Tool]:
        return self.tools.get(name)

    async def execute(self, tool_name: str, **kwargs):
        tool = self.get(tool_name)
        if not tool:
            return {"status": "error", "error": f"Tool '{tool_name}' not found"}

        return await tool.execute(**kwargs)

    def get_metrics(self) -> Dict[str, Any]:
        return {name: t.metrics for name, t in self.tools.items()}
