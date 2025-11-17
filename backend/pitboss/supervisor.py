"""
Pitboss Supervisor - Main Orchestrator for Clinical Trial Data Review
Coordinates context building, LLM interactions, and tool execution.
"""

import asyncio
import logging
import re
import yaml
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import get_config
from .context_builder import ContextBuilder
from .tools import ToolRegistry

logger = logging.getLogger(__name__)


class PitbossSupervisor:
    """
    The brain that orchestrates the entire system.
    Decides what to do, constructs API calls, processes responses, executes tools.
    """
    
    def __init__(self, db_connection, websocket=None):
        """
        Initialize the supervisor with all its components.
        
        Args:
            db_connection: Database connection
            websocket: WebSocket for real-time communication
        """
        self.db = db_connection
        self.websocket = websocket
        
        # Initialize configuration
        self.config = get_config()
        
        # Initialize components
        self.context_builder = ContextBuilder(db_connection)
        self.tool_registry = ToolRegistry(db_connection, self.config)
        
        # Initialize memory tables
        self._init_memory_tables()
        
        # Workflow state
        self.protocol_id_from_dsl = None
        self.current_rule_id = None
        self.current_sql = None
        
        logger.info("PitbossSupervisor initialized")
    
    def _init_memory_tables(self):
        """Initialize memory tables for context persistence."""
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_memory (
                protocol_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        self.db.execute(
            """
            CREATE TABLE IF NOT EXISTS query_results (
                protocol_id TEXT,
                query TEXT,
                summary TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    
    async def process_request(
        self,
        rule_code: str,
        protocol_id: Optional[str] = None,
        rule_id: Optional[str] = None,
        dsl_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for processing requests.
        Decides action type and routes accordingly.
        
        Args:
            rule_code: The rule or command to process
            protocol_id: Protocol identifier
            rule_id: Rule identifier
            dsl_text: Optional DSL YAML content
            
        Returns:
            Processing result dictionary
        """
        logger.info(f"[Supervisor] Processing request: {rule_code[:100]}...")
        
        # Decide action type
        action = self._decide_action(rule_code)
        
        if action == "RUN_RULE":
            return await self._process_single_rule(
                rule_code, protocol_id, rule_id, dsl_text
            )
        elif action == "RUN_ALL_RULES":
            return await self._process_all_rules(dsl_text, protocol_id)
        elif action == "WORKFLOW":
            return await self._process_workflow(dsl_text)
        elif action == "QUESTION":
            return await self._process_question(rule_code, protocol_id)
        else:
            return await self._process_generic_rule(
                rule_code, protocol_id, rule_id, dsl_text
            )
    
    def _decide_action(self, rule_code: str) -> str:
        """
        Analyze the request to determine action type.
        
        Returns:
            Action type string
        """
        if rule_code.startswith("RUN_RULE:"):
            return "RUN_RULE"
        elif rule_code.startswith("RUN_ALL_RULES"):
            return "RUN_ALL_RULES"
        elif rule_code.startswith("WORKFLOW:"):
            return "WORKFLOW"
        elif "?" in rule_code or rule_code.lower().startswith(("how", "what", "why", "when")):
            return "QUESTION"
        else:
            return "GENERIC"
    
    async def _process_single_rule(
        self,
        rule_code: str,
        protocol_id: str,
        rule_id: str,
        dsl_text: Optional[str]
    ) -> Dict[str, Any]:
        """Process a single rule from DSL."""
        try:
            # Extract rule from DSL if provided
            if dsl_text and rule_code.startswith("RUN_RULE:"):
                rule_to_run = rule_code.replace("RUN_RULE:", "").strip()
                dsl = yaml.safe_load(dsl_text)
                
                # Find the specific rule in DSL
                rule = self._extract_rule_from_dsl(dsl, rule_to_run)
                if not rule:
                    return {
                        "status": "error",
                        "error": f"Rule {rule_to_run} not found in DSL"
                    }
                
                # Process the rule
                return await self._execute_rule(
                    rule=rule,
                    protocol_id=protocol_id,
                    dsl=dsl
                )
            else:
                # Process as generic rule
                return await self._process_generic_rule(
                    rule_code, protocol_id, rule_id, dsl_text
                )
                
        except Exception as e:
            logger.error(f"Error processing single rule: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _process_all_rules(
        self,
        dsl_text: str,
        protocol_id: str
    ) -> Dict[str, Any]:
        """Process all rules in DSL."""
        try:
            dsl = yaml.safe_load(dsl_text)
            rules = dsl.get('RULES', [])
            
            if not rules:
                return {
                    "status": "error",
                    "error": "No rules found in DSL"
                }
            
            results = []
            for rule in rules:
                result = await self._execute_rule(rule, protocol_id, dsl)
                results.append(result)
            
            return {
                "status": "success",
                "results": results,
                "total_rules": len(rules)
            }
            
        except Exception as e:
            logger.error(f"Error processing all rules: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _execute_rule(
        self,
        rule: Dict[str, Any],
        protocol_id: str,
        dsl: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a single rule through the complete pipeline.
        
        1. Build context (PROTOCOL + DATA + RULES)
        2. Generate SQL via sql_pitboss tool
        3. Create materialized table via data_table tool
        4. Insert alert via insert_alerts tool
        5. Register rule via register_rule tool
        """
        rule_id = rule.get('rule_code', 'UNKNOWN')
        logic = rule.get('logic', rule.get('description', ''))
        severity = rule.get('severity', 'major')
        message = rule.get('message', '')
        crf = rule.get('crf', None)
        
        logger.info(f"[Supervisor] Executing rule {rule_id}")
        
        try:
            # Step 1: Build context with proper ordering
            context = self.context_builder.build_context(
                dsl=dsl,
                rule_code=logic,
                protocol_id=protocol_id,
                include_examples=True
            )
            
            # Prepare messages for LLM
            messages = [
                {"role": "system", "content": context["system"]},
                {"role": "user", "content": context["user"]}
            ]
            
            # Step 2: Generate SQL using sql_pitboss tool
            sql_result = await self.tool_registry.execute(
                "sql_pitboss",
                messages=messages
            )
            
            if sql_result["status"] != "success":
                return sql_result
            
            sql_query = sql_result["sql"]
            
            # Step 3: Create materialized table
            table_result = await self.tool_registry.execute(
                "data_table",
                sql_query=sql_query,
                protocol_id=protocol_id,
                rule_id=rule_id
            )
            
            if table_result["status"] != "success":
                return table_result
            
            row_count = table_result["row_count"]
            
            # Step 4: Insert alert
            alert_result = await self.tool_registry.execute(
                "insert_alerts",
                protocol_id=protocol_id,
                rule_id=rule_id,
                record_count=row_count,
                severity=severity,
                message=message,
                crf=crf
            )
            
            # Step 5: Register rule
            register_result = await self.tool_registry.execute(
                "register_rule",
                rule_id=rule_id,
                protocol_id=protocol_id,
                rule_code=logic,
                sql_query=sql_query
            )
            
            # Format output message
            output_message = (
                f"{rule_id} {message} - {row_count} records flagged "
                f"Severity: {severity.title()}"
            )
            
            # Send to frontend if websocket available
            if self.websocket:
                await self._send_to_frontend(output_message)
            
            return {
                "status": "success",
                "rule_id": rule_id,
                "message": output_message,
                "row_count": row_count,
                "table_name": table_result.get("table_name")
            }
            
        except Exception as e:
            logger.error(f"Error executing rule {rule_id}: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _process_generic_rule(
        self,
        rule_code: str,
        protocol_id: str,
        rule_id: str,
        dsl_text: Optional[str]
    ) -> Dict[str, Any]:
        """Process a generic rule not from DSL."""
        try:
            # Parse DSL if provided
            dsl = yaml.safe_load(dsl_text) if dsl_text else None
            
            # Build context
            context = self.context_builder.build_context(
                dsl=dsl,
                rule_code=rule_code,
                protocol_id=protocol_id
            )
            
            # Generate SQL
            messages = [
                {"role": "system", "content": context["system"]},
                {"role": "user", "content": context["user"]}
            ]
            
            sql_result = await self.tool_registry.execute(
                "sql_pitboss",
                messages=messages
            )
            
            if sql_result["status"] != "success":
                return sql_result
            
            sql_query = sql_result["sql"]
            
            # Generate rule_id if not provided
            if not rule_id:
                rule_id = self._generate_rule_id(sql_query)
            
            # Execute through the pipeline
            return await self._execute_rule(
                rule={
                    "rule_code": rule_id,
                    "logic": rule_code,
                    "severity": "major",
                    "message": rule_code[:50]
                },
                protocol_id=protocol_id,
                dsl=dsl or {}
            )
            
        except Exception as e:
            logger.error(f"Error processing generic rule: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _process_question(
        self,
        question: str,
        protocol_id: str
    ) -> Dict[str, Any]:
        """Process a question (not a rule execution)."""
        try:
            # Adjust temperature for Q&A
            temp = self.config.adjust_temperature_for_task("question_answering")
            
            # Build context without examples
            context = self.context_builder.build_context(
                rule_code=question,
                protocol_id=protocol_id,
                include_examples=False
            )
            
            # This would normally call an LLM for Q&A
            # For now, return a placeholder
            response = f"To answer your question about '{question}', please refer to the documentation."
            
            if self.websocket:
                await self._send_to_frontend(response)
            
            return {
                "status": "success",
                "type": "question",
                "response": response
            }
            
        except Exception as e:
            logger.error(f"Error processing question: {e}")
            return {"status": "error", "error": str(e)}
    
    async def _process_workflow(self, dsl_text: str) -> Dict[str, Any]:
        """Process a workflow from DSL."""
        # Workflow processing would go here
        # This is a placeholder for the workflow executor
        return {
            "status": "info",
            "message": "Workflow processing not yet implemented in refactored version"
        }
    
    def _extract_rule_from_dsl(
        self,
        dsl: Dict[str, Any],
        rule_id: str
    ) -> Optional[Dict[str, Any]]:
        """Extract a specific rule from DSL by its rule_code."""
        rules = dsl.get('RULES', [])
        for rule in rules:
            if rule.get('rule_code') == rule_id:
                return rule
        return None
    
    def _generate_rule_id(self, sql: str) -> str:
        """Generate a rule ID from SQL query."""
        sql_l = sql.lower()
        
        # Extract main table
        tables = re.findall(r"\bfrom\s+(\w+)|\bjoin\s+(\w+)", sql_l)
        table_names = [t for pair in tables for t in pair if t]
        main_table = table_names[0] if table_names else "unknown"
        
        # Extract key conditions
        where_match = re.search(
            r"where\s+(.*?)(order by|group by|limit|$)",
            sql_l,
            re.DOTALL
        )
        where_clause = where_match.group(1) if where_match else ""
        
        # Find keywords
        tokens = re.findall(r"\b\w+\b", where_clause)
        stopwords = {
            "and", "or", "is", "null", "not", "in", "like",
            "between", "as", "on", "join", "from", "where"
        }
        keywords = [
            t for t in tokens
            if t not in stopwords and not t.isdigit() and len(t) > 2
        ]
        
        # Build rule ID
        base = main_table.replace("_clovis", "")
        parts = [base] + keywords[:2]
        rule_id = "_".join(parts).upper()
        rule_id = re.sub(r"[^A-Z0-9_]", "_", rule_id)
        
        return rule_id or "RULE_GENERIC"
    
    async def _send_to_frontend(self, message: str):
        """Send message to frontend via WebSocket."""
        if self.websocket:
            await self.websocket.send_json({
                "type": "rule_result",
                "message": message,
                "timestamp": datetime.now().isoformat()
            })
    
    def _save_to_memory(self, protocol_id: str, role: str, content: str):
        """Save interaction to chat memory."""
        self.db.execute(
            "INSERT INTO chat_memory (protocol_id, role, content) VALUES (?, ?, ?)",
            (protocol_id, role, content)
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get system metrics."""
        return {
            "tools": self.tool_registry.get_metrics(),
            "config": self.config.to_dict()
        }


# Backwards compatibility wrapper
class Pitboss(PitbossSupervisor):
    """
    Backwards compatibility wrapper for existing code.
    Maps old method names to new implementation.
    """
    
    async def process_rule_request(
        self,
        rule_code: str,
        system_prompt: Optional[str],
        protocol_id: Optional[str],
        rule_id: Optional[str]
    ):
        """Legacy method for processing rule requests."""
        return await self.process_request(
            rule_code=rule_code,
            protocol_id=protocol_id,
            rule_id=rule_id
        )
    
    async def run_workflow(self, dsl_text: str):
        """Legacy method for running workflows."""
        return await self._process_workflow(dsl_text)