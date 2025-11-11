"""
Tool Registry System for Clinical Trial Data Review
Manages specialized tools: sql_pitboss, data_table, insert_alerts, register_rule
"""

import asyncio
import logging
import re
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional
import openai

logger = logging.getLogger(__name__)


class Tool(ABC):
    """Base class for all tools."""
    
    def __init__(self, name: str, db_connection=None):
        self.name = name
        self.db = db_connection
        self.metrics = {
            'executions': 0,
            'successes': 0,
            'failures': 0,
            'total_time': 0
        }
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """Execute the tool's main functionality."""
        pass
    
    def validate_inputs(self, **kwargs) -> bool:
        """Validate tool inputs before execution."""
        return True
    
    def log_execution(self, success: bool, duration: float):
        """Log metrics for this execution."""
        self.metrics['executions'] += 1
        if success:
            self.metrics['successes'] += 1
        else:
            self.metrics['failures'] += 1
        self.metrics['total_time'] += duration


class SqlPitbossTool(Tool):
    """
    SQL Pitboss Tool - Generates SQL from natural language rules.
    This is the Language Agent that converts rules to SQL.
    """
    
    def __init__(self, db_connection=None, config=None):
        super().__init__("sql_pitboss", db_connection)
        self.config = config
    
    async def execute(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Generate SQL from rule description using LLM.
        
        Args:
            messages: List of message dictionaries for the LLM
            
        Returns:
            Dictionary with SQL query and metadata
        """
        start_time = datetime.now()
        
        try:
            logger.info("[SqlPitboss] Starting SQL generation...")
            
            # Get model parameters from config if available
            model_params = self.config.get_model_params() if self.config else {
                "model": "gpt-4o-mini",
                "temperature": 0.2,
                "max_tokens": 400,  # gpt-4o-mini uses max_tokens
                "top_p": 0.1,
                "frequency_penalty": 0.5,
                "presence_penalty": 0.5
            }
            
            # Call OpenAI API
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                messages=messages,
                **model_params
            )
            
            content = response.choices[0].message.content.strip()
            sql_query = self._extract_sql(content)
            
            logger.info(f"[SqlPitboss] Generated SQL: {sql_query[:100]}...")
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(True, duration)
            
            return {
                "status": "success",
                "sql": sql_query,
                "raw_response": content,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"[SqlPitboss] Error: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(False, duration)
            
            return {
                "status": "error",
                "error": str(e),
                "duration": duration
            }
    
    def _extract_sql(self, content: str) -> str:
        """Extract SQL from LLM response."""
        # Look for SQL in code blocks
        sql_block_match = re.search(
            r'```(?:sql)?\s*\n?([^`]+)```', 
            content, 
            re.IGNORECASE | re.DOTALL
        )
        if sql_block_match:
            return sql_block_match.group(1).strip()
        
        # Look for SELECT/INSERT/UPDATE/DELETE/CREATE statements
        sql_match = re.search(
            r'((?:SELECT|INSERT|UPDATE|DELETE|CREATE|WITH)\b[^;]*(?:;|$))',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if sql_match:
            return sql_match.group(1).strip()
        
        # If content starts with SQL keywords, return it
        if re.match(r'^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|WITH)\b', content, re.IGNORECASE):
            return content.strip()
        
        # Last resort: return the original content
        return content.strip()


class DataTableTool(Tool):
    """
    Data Table Tool - Creates materialized tables for results.
    Manages the creation and registration of result tables.
    """
    
    def __init__(self, db_connection):
        super().__init__("data_table", db_connection)
    
    async def execute(
        self, 
        sql_query: str, 
        protocol_id: str, 
        rule_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a materialized table from SQL query.
        
        Args:
            sql_query: The SQL SELECT statement
            protocol_id: Protocol identifier
            rule_id: Rule identifier
            
        Returns:
            Dictionary with table creation status
        """
        start_time = datetime.now()
        
        try:
            # Generate table name
            table_name = self._make_table_name(protocol_id, rule_id)
            
            # Strip SQL to just SELECT statement if needed
            select_sql = self._strip_to_select(sql_query)
            
            # Create materialized table
            create_sql = f"CREATE OR REPLACE TABLE {table_name} AS {select_sql}"
            logger.info(f"[DataTable] Creating table: {table_name}")
            
            self.db.execute(create_sql)
            
            # Register in results_registry
            self._register_table(protocol_id, rule_id, table_name, sql_query)
            
            # Get row count
            count_result = self.db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(True, duration)
            
            logger.info(f"[DataTable] Created {table_name} with {row_count} rows")
            
            return {
                "status": "success",
                "table_name": table_name,
                "row_count": row_count,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"[DataTable] Error creating table: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(False, duration)
            
            return {
                "status": "error",
                "error": str(e),
                "duration": duration
            }
    
    def _make_table_name(self, protocol_id: str, rule_id: str) -> str:
        """Generate a valid table name."""
        proto = (protocol_id or "unknown").lower()
        rid = (rule_id or "rule").lower()
        name = f"res_{proto}_{rid}"
        name = re.sub(r'[^a-z0-9_]+', '_', name)
        if re.match(r'^\d', name):
            name = f"t_{name}"
        return name
    
    def _strip_to_select(self, sql: str) -> str:
        """Extract SELECT statement from SQL."""
        s = sql.strip()
        # Remove code fences
        s = re.sub(r'^```(?:sql)?\s*', '', s, flags=re.IGNORECASE)
        s = re.sub(r'\s*```$', '', s)
        s = s.strip().rstrip(';').strip()
        
        # If it's CREATE ... AS SELECT, extract the SELECT
        m = re.search(r'\bas\b\s*(select.*)$', s, flags=re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip().rstrip(';')
        
        return s
    
    def _register_table(self, protocol_id: str, rule_id: str, table_name: str, sql_text: str):
        """Register the table in results_registry."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS results_registry (
                protocol_id TEXT,
                rule_id     TEXT,
                table_name  TEXT,
                sql_text    TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (protocol_id, rule_id)
            )
            """
        )
        
        self.db.execute(
            """
            INSERT OR REPLACE INTO results_registry 
            (protocol_id, rule_id, table_name, sql_text)
            VALUES (?, ?, ?, ?)
            """,
            (protocol_id, rule_id, table_name, sql_text)
        )


class InsertAlertsTool(Tool):
    """
    Insert Alerts Tool - Records rule execution in alerts table.
    Creates summary records for each rule execution.
    """
    
    def __init__(self, db_connection):
        super().__init__("insert_alerts", db_connection)
    
    async def execute(
        self,
        protocol_id: str,
        rule_id: str,
        record_count: int,
        severity: str = "major",
        message: str = "",
        crf: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Insert a summary alert for rule execution.
        
        Args:
            protocol_id: Protocol identifier
            rule_id: Rule identifier
            record_count: Number of records flagged
            severity: Rule severity level
            message: Alert message
            crf: CRF form name if applicable
            
        Returns:
            Dictionary with insertion status
        """
        start_time = datetime.now()
        
        try:
            # Ensure alerts table exists
            self._ensure_alerts_table()
            
            # Insert summary alert
            self.db.execute(
                """
                INSERT OR IGNORE INTO alerts (
                    subjid, protocol_id, crf, variable, 
                    variable_value, rule_id, status, date_created
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "SUMMARY",  # Special subjid for summary records
                    protocol_id,
                    crf or "RULE_EXECUTION",
                    message or f"Number of records flagged",
                    float(record_count),
                    rule_id,
                    1,  # Active status
                    datetime.now().isoformat()
                )
            )
            
            self.db.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(True, duration)
            
            logger.info(f"[InsertAlerts] Alert created for {rule_id}: {record_count} records")
            
            return {
                "status": "success",
                "rule_id": rule_id,
                "record_count": record_count,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"[InsertAlerts] Error: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(False, duration)
            
            return {
                "status": "error",
                "error": str(e),
                "duration": duration
            }
    
    def _ensure_alerts_table(self):
        """Ensure the alerts table exists."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                subjid TEXT,
                protocol_id TEXT,
                crf TEXT,
                variable TEXT,
                variable_value FLOAT,
                rule_id TEXT,
                status INTEGER,
                date_created TIMESTAMP,
                UNIQUE(subjid, rule_id, protocol_id, variable, variable_value, date_created)
            )
            """
        )


class RegisterRuleTool(Tool):
    """
    Register Rule Tool - Manages rule registry.
    Tracks all executed rules and their SQL.
    """
    
    def __init__(self, db_connection):
        super().__init__("register_rule", db_connection)
    
    async def execute(
        self,
        rule_id: str,
        protocol_id: str,
        rule_code: str,
        sql_query: str,
        sponsor: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Register a rule execution in the rules table.
        
        Args:
            rule_id: Rule identifier
            protocol_id: Protocol identifier
            rule_code: Original rule logic
            sql_query: Generated SQL query
            sponsor: Study sponsor name
            
        Returns:
            Dictionary with registration status
        """
        start_time = datetime.now()
        
        try:
            # Get sponsor if not provided
            if not sponsor:
                sponsor = self._get_sponsor(protocol_id)
            
            # Ensure rules table exists
            self._ensure_rules_table()
            
            # Insert or update rule record
            now = datetime.now().isoformat()
            self.db.execute(
                """
                INSERT INTO rules 
                (rule_id, protocol_id, sponsor, rule_code, date_created, date_amended)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    rule_code = excluded.rule_code,
                    date_amended = excluded.date_amended
                """,
                (
                    rule_id,
                    protocol_id,
                    sponsor,
                    f"Logic: {rule_code}\n\nGenerated SQL:\n{sql_query}",
                    now,
                    now
                )
            )
            
            self.db.commit()
            
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(True, duration)
            
            logger.info(f"[RegisterRule] Registered {rule_id} for {protocol_id}")
            
            return {
                "status": "success",
                "rule_id": rule_id,
                "duration": duration
            }
            
        except Exception as e:
            logger.error(f"[RegisterRule] Error: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self.log_execution(False, duration)
            
            return {
                "status": "error",
                "error": str(e),
                "duration": duration
            }
    
    def _get_sponsor(self, protocol_id: str) -> str:
        """Get sponsor from protocols table."""
        try:
            result = self.db.execute(
                "SELECT sponsor FROM protocols WHERE protocol_id = ? LIMIT 1",
                (protocol_id,)
            ).fetchone()
            return result[0] if result else "Unknown"
        except:
            return "Unknown"
    
    def _ensure_rules_table(self):
        """Ensure the rules table exists."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS rules (
                rule_id TEXT PRIMARY KEY,
                protocol_id TEXT,
                sponsor TEXT,
                rule_code TEXT,
                date_created TIMESTAMP,
                date_amended TIMESTAMP
            )
            """
        )


class ToolRegistry:
    """
    Central registry for all tools.
    Manages tool lifecycle and execution.
    """
    
    def __init__(self, db_connection=None, config=None):
        self.db = db_connection
        self.config = config
        self.tools = {}
        
        # Register default tools
        self._register_default_tools()
    
    def _register_default_tools(self):
        """Register the standard set of tools."""
        if self.config and self.config.tools.sql_pitboss_enabled:
            self.register(SqlPitbossTool(self.db, self.config))
        
        if self.config and self.config.tools.data_table_enabled:
            self.register(DataTableTool(self.db))
        
        if self.config and self.config.tools.insert_alerts_enabled:
            self.register(InsertAlertsTool(self.db))
        
        if self.config and self.config.tools.register_rule_enabled:
            self.register(RegisterRuleTool(self.db))
    
    def register(self, tool: Tool):
        """Register a new tool."""
        self.tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name}")
    
    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self.tools.get(name)
    
    async def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name."""
        tool = self.get(tool_name)
        
        if not tool:
            return {
                "status": "error",
                "error": f"Tool '{tool_name}' not found"
            }
        
        if not tool.validate_inputs(**kwargs):
            return {
                "status": "error",
                "error": f"Invalid inputs for tool '{tool_name}'"
            }
        
        return await tool.execute(**kwargs)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get metrics for all tools."""
        metrics = {}
        for name, tool in self.tools.items():
            metrics[name] = tool.metrics
        return metrics