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

    def __init__(self, db_pool):
        super().__init__("data_table", db_pool)

    async def execute(self, sql_query: str, rule_name: str, rule_code: str = None, **kwargs):
        start = datetime.now()
        try:
            # Use rule_code directly if provided (preserves case)
            # Otherwise derive from rule_name
            if rule_code:
                view_name = rule_code
            else:
                view_name = self._safe_table_name(rule_name)
            select_sql = self._strip_to_select(sql_query)

            async with self.db_pool.acquire() as conn:
                # Drop view if exists, then create or replace
                # Quote view name to preserve case sensitivity
                await conn.execute(f'DROP VIEW IF EXISTS "{view_name}" CASCADE')
                await conn.execute(f'CREATE VIEW "{view_name}" AS {select_sql}')

                row = await conn.fetchrow(f'SELECT COUNT(*) AS c FROM "{view_name}"')
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
# Register View Tool — upsert complete view metadata in views_registry
# -------------------------------------------------------------------------
class RegisterViewTool(Tool):
    """
    Register or update materialized view in views_registry.
    
    The views_registry table now contains all metadata:
    - id: serial primary key
    - name: human-readable name from YAML rule
    - table_name: YAML rule_code (stable identifier, unique constraint)
    - sql: generated SQL for the view
    - created_at, updated_at: timestamps
    
    Uses UPSERT on table_name to ensure idempotency:
    - If table_name already exists, updates name, sql, and updated_at
    - Otherwise, inserts a new entry
    """

    def __init__(self, db_pool):
        super().__init__("register_view", db_pool)

    async def execute(self, table_name: str, name: str, sql_query: str, **kwargs):
        start = datetime.now()
        try:
            async with self.db_pool.acquire() as conn:
                # UPSERT on table_name (stable identifier from YAML rule_code)
                # If table_name already exists, update name, sql, and updated_at
                # This ensures re-running the same rule updates the existing view entry
                await conn.execute("""
                    INSERT INTO views_registry (name, table_name, sql)
                    VALUES ($1, $2, $3)
                    ON CONFLICT (table_name) DO UPDATE SET
                        name        = EXCLUDED.name,
                        sql         = EXCLUDED.sql,
                        updated_at  = CURRENT_TIMESTAMP
                """, name, table_name, sql_query)

            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)

            return {"status": "success", "view": table_name, "duration": duration}

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[RegisterViewTool] Error: {e}")

            return {"status": "error", "error": str(e), "duration": duration}


# -------------------------------------------------------------------------
# Execute Upsert Tool — Call upsert_pattern_factory_entities procedure
# -------------------------------------------------------------------------
class ExecuteUpsertTool(Tool):
    """
    Execute the PostgreSQL upsert procedure for entity extraction.
    
    Calls: CALL upsert_pattern_factory_entities(%s::jsonb, NULL::jsonb)
    Where %s is the validated JSON payload from verifyUpsert.
    """

    def __init__(self, db_pool):
        super().__init__("execute_upsert", db_pool)

    async def execute(self, jsonb_payload: Dict[str, Any], **kwargs):
        start = datetime.now()
        try:
            import json as json_module
            
            # Convert payload to JSON string for parameterized query
            payload_json = json_module.dumps(jsonb_payload)
            
            async with self.db_pool.acquire() as conn:
                # Execute the upsert procedure
                # The procedure signature expects:
                #   IN p_entities jsonb,
                #   IN p_results jsonb
                # We pass the extracted entities and NULL for results (output-only)
                result = await conn.fetchrow(
                    "CALL upsert_pattern_factory_entities($1::jsonb, NULL::jsonb)",
                    payload_json
                )
                
                row_count = 0
                if result:
                    # Procedure may return row counts or status
                    row_count = result.get(0) if isinstance(result, tuple) else 0
            
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(True, duration)
            
            return {
                "status": "success",
                "row_count": row_count,
                "duration": duration,
                "message": "Entities upserted successfully"
            }

        except Exception as e:
            duration = (datetime.now() - start).total_seconds()
            self.log_execution(False, duration)
            logger.error(f"[ExecuteUpsertTool] Error: {e}")
            
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
        self.register(RegisterViewTool(self.db_pool))
        self.register(ExecuteUpsertTool(self.db_pool))

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
