"""
LLM-Supervised Pitboss using GPT-40-mini with Function Calling

This implementation uses the LLM itself as the supervisor, leveraging
function calling to orchestrate tool execution. The LLM decides which
tools to call and in what order, making the architecture more elegant
and flexible.
"""
import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import yaml

from openai import AsyncOpenAI
import openai
import markdown2
logger = logging.getLogger(__name__)
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    logger.warning("⚠️ OPENAI_API_KEY is missing or not loaded from environment!")
else:
    logger.info(f"🔑 OPENAI_API_KEY detected: {api_key[:50]}... (length={len(api_key)})")


class LLMSupervisedPitboss:
    """
    Pitboss that uses GPT-4o-mini as the supervisor via function calling.
    The LLM itself decides which tools to execute and in what order.
    """
    
    # Tool definitions for function calling
    TOOLS = [
        {
            "type": "function",
            "function": {
                "name": "sql_pitboss",
                "description": "Execute SQL for the current RULE - creates materialized table as protocol_id_rule_code and registers in results_registry.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "protocol_id": {"type": "string"},
                        "rule_code": {"type": "string"},
                        "sql": {"type": "string", "description": "SELECT statement to materialize"},
                        "message": {"type": "string", "description": "Alert message for the rule"}
                    },
                    "required": ["protocol_id", "rule_code", "sql"],
                    "additionalProperties": False
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "insert_alerts",
                "description": "Insert one audit row per rule run (logging).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "protocol_id": {"type": "string"},
                        "rule_code": {"type": "string"},
                        "status": {"type": "string", "enum": ["planned", "executed", "skipped", "error"]},
                        "note": {"type": "string"},
                        "record_count": {"type": "integer", "description": "Number of records flagged"}
                    },
                    "required": ["protocol_id", "rule_code", "status"],
                    "additionalProperties": False
                }
            }
        }
    ]
    
    SYSTEM_PROMPT = (
        "You are an AI agent in Pattern Factory. You are a clinical data review expert in SQL "
        "and in the protocol/database schema of the trial.\n"
        "Generate ONLY a SELECT SQL query for the given rule. No explanation, no markdown, just the SQL.\n"
        "The SQL should return the data specified in the rule's logic.\n"
        "RULES have highest precedence over PROTOCOL and DATA when conflicting."
    )
    
    INTENT_CLASSIFIER_PROMPT = (
        "You are an AI assistant that classifies user intent. Based on the user's message, determine what they want to do.\n"
        "Respond with a JSON object containing:\n"
        "- intent: one of 'execute_rule', 'execute_all_rules', 'ask_question', 'help'\n"
        "- rule_code: (if intent is 'execute_rule') the specific rule code mentioned\n"
        "- question: (if intent is 'ask_question') the user's question\n"
        "\n"
        "Examples:\n"
        "'run FULLY_ACTIVE' -> {\"intent\": \"execute_rule\", \"rule_code\": \"FULLY_ACTIVE\"}\n"
        "'execute all rules' -> {\"intent\": \"execute_all_rules\"}\n"
        "'what is the protocol about?' -> {\"intent\": \"ask_question\", \"question\": \"what is the protocol about?\"}\n"
        "'help' -> {\"intent\": \"help\"}\n"
        "\n"
        "Available rule codes in the DSL:\n"
    )
    
    QA_PROMPT = (
        "You are an AI assistant helping with clinical trial data review. "
        "Answer the user's question based on the provided context about the protocol, data, and rules. "
        "Be concise and helpful."
    )
    
    def __init__(self, db_connection, websocket=None, use_async=True):
        """
        Initialize the LLM-supervised Pitboss.
        
        Args:
            db_connection: Database connection
            websocket: Optional WebSocket for real-time communication
            use_async: Whether to use async OpenAI client
        """
        self.db = db_connection
        self.websocket = websocket
        
        # Initialize OpenAI client
        if use_async:
            self.client = AsyncOpenAI()
        else:
            self.client = openai.OpenAI()
        
        # Tool implementations
        self.tool_implementations = {
            "sql_pitboss": self._execute_sql_pitboss,
            "insert_alerts": self._execute_insert_alerts
        }
        
        # State tracking
        self.current_sql = None
        self.current_table_name = None
        self.execution_log = []
        self.sent_messages = set()  # Track sent messages to prevent duplicates
        
        logger.info("LLM-supervised Pitboss initialized with gpt-4o")
    
    async def generate_sql_for_rule(
        self,
        protocol_id: str,
        protocol_text: str,
        data_block: str,
        rule: Dict[str, Any],
        rules_context: Optional[str] = None
    ) -> str:
        """
        Generate SQL for a rule using the LLM without function calling.
        
        Args:
            protocol_id: Protocol identifier
            protocol_text: PROTOCOL section text
            data_block: DATA section with table schemas
            rule: Rule dictionary with rule_code, logic, message, etc.
            rules_context: Optional context of all rules for few-shot learning
            
        Returns:
            SQL query string
        """
        try:
            # Construct messages
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"# PROTOCOL\n{protocol_text}"},
                {"role": "user", "content": f"# DATA\n{data_block}"},
            ]
            
            # Include rules context if provided
            if rules_context:
                messages.append({"role": "user", "content": f"# EXAMPLE RULES (for context)\n{rules_context}"})
            
            # Add the specific rule
            rule_yaml = yaml.dump(rule)
            logger.info(f"[generate_sql_for_rule] Converting rule to SQL: {rule.get('rule_code', 'UNKNOWN')}")
            logger.debug(f"[generate_sql_for_rule] Rule YAML:\n{rule_yaml}")
            messages.append({"role": "user", "content": f"# RULE TO CONVERT TO SQL\n{rule_yaml}"})
            
            # Call GPT-4o for SQL generation (no function calling)
            if isinstance(self.client, AsyncOpenAI):
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.2,
                    messages=messages,
                    max_tokens=800  # SQL queries shouldn't be too long
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.2,
                    messages=messages,
                    max_tokens=800
                )
            
            # Extract SQL from response
            sql = response.choices[0].message.content.strip()
            
            # Clean up SQL (remove markdown if present)
            if sql.startswith("```sql"):
                sql = sql[6:]
            if sql.startswith("```"):
                sql = sql[3:]
            if sql.endswith("```"):
                sql = sql[:-3]
            sql = sql.strip()
            
            return sql
            
        except Exception as e:
            logger.error(f"Error generating SQL: {e}")
            raise
    
    async def run_rule_fastpath(
        self,
        protocol_id: str,
        protocol_text: str,
        data_block: str,
        dsl_rule_yaml: str,
        rules_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fast path for rule execution: generate SQL, then execute it programmatically.
        """
        try:
            # Parse the rule YAML back into a dict
            rule = yaml.safe_load(dsl_rule_yaml)
            rule_code = rule.get('rule_code', rule.get('alert_code', 'RULE'))
            message = rule.get('message')
            
            # Generate SQL using LLM (no function calling)
            sql = await self.generate_sql_for_rule(
                protocol_id=protocol_id,
                protocol_text=protocol_text,
                data_block=data_block,
                rule=rule,
                rules_context=rules_context
            )
            
            # Execute SQL programmatically
            result = await self._execute_sql_pitboss(
                protocol_id=protocol_id,
                rule_code=rule_code,
                sql=sql,
                message=message
            )
            
            # Optionally, we could insert alerts here programmatically
            # Skipping for now to keep flow simple and robust
            
            # Don't send summary here - let higher level functions handle it
            # to avoid duplicate messages
            
            return {
                "status": "success",
                "tool_calls": [{
                    "tool": "sql_pitboss",
                    "args": {"protocol_id": protocol_id, "rule_code": rule_code, "sql": sql},
                    "result": result
                }]
            }
            
        except Exception as e:
            logger.error(f"Error in run_rule_fastpath: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_single_rule(
        self,
        protocol_id: str,
        dsl_text: str,
        rule_code: str
    ) -> Dict[str, Any]:
        """
        Run a single rule from DSL file using the LLM supervisor.
        Provides full context (all PROTOCOL, DATA, and RULES sections) for few-shot learning.
        
        Args:
            protocol_id: Protocol identifier
            dsl_text: Complete DSL YAML content
            rule_code: The specific rule_code to execute
            
        Returns:
            Execution result for the rule
        """
        try:
            # Extract raw text sections from the DSL (same as run_all_rules)
            protocol_text = self._extract_section_text(dsl_text, 'PROTOCOL')
            data_block = self._extract_section_text(dsl_text, 'DATA')
            rules_text = self._extract_section_text(dsl_text, 'RULES')  # All rules for context
            
            if not rules_text:
                error_msg = "No RULES section found in DSL"
                logger.error(f"[run_single_rule] {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg
                }
            
            # Parse the DSL to find the specific rule
            dsl = yaml.safe_load(dsl_text)
            rules_section = dsl.get('RULES', [])
            
            # Find the specific rule to execute
            target_rule = None
            
            if isinstance(rules_section, list):
                # Multiple rules format
                for rule in rules_section:
                    if rule.get('rule_code') == rule_code or rule.get('alert_code') == rule_code:
                        target_rule = rule
                        break
            elif isinstance(rules_section, dict):
                # Single rule format
                if rules_section.get('rule_code') == rule_code or rules_section.get('alert_code') == rule_code:
                    target_rule = rules_section
            
            if not target_rule:
                error_msg = f"Rule '{rule_code}' not found in DSL"
                logger.error(f"[run_single_rule] {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg
                }
            
            # Ensure rule has rule_code
            if 'rule_code' not in target_rule and 'alert_code' in target_rule:
                target_rule['rule_code'] = target_rule['alert_code']
            elif 'rule_code' not in target_rule:
                target_rule['rule_code'] = rule_code
            
            # Convert rule to YAML format
            rule_yaml = yaml.dump(target_rule)
            
            # Run the rule through the fast path with full context
            result = await self.run_rule_fastpath(
                protocol_id=protocol_id,
                protocol_text=protocol_text,
                data_block=data_block,
                dsl_rule_yaml=rule_yaml,
                rules_context=rules_text  # Pass all rules for few-shot context
            )
            
            return {
                "status": "success",
                "rule_code": target_rule.get('rule_code', rule_code),
                "result": result
            }
            
        except Exception as e:
            error_msg = f"Error running single rule: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def run_all_rules(
        self,
        protocol_id: str,
        dsl_text: str
    ) -> Dict[str, Any]:
        """
        Run all rules in a DSL file using the LLM supervisor.
        
        Args:
            protocol_id: Protocol identifier
            dsl_text: Complete DSL YAML content
            
        Returns:
            Execution results for all rules
        """
        try:
            # Extract raw text sections from the DSL
            protocol_text = self._extract_section_text(dsl_text, 'PROTOCOL')
            data_block = self._extract_section_text(dsl_text, 'DATA')
            rules_text = self._extract_section_text(dsl_text, 'RULES')
            
            if not rules_text:
                return {
                    "status": "error",
                    "error": "No RULES section found in DSL"
                }
            
            # Parse just the RULES section to get individual rules
            dsl = yaml.safe_load(dsl_text)
            rules_section = dsl.get('RULES', [])
            
            if not rules_section:
                return {
                    "status": "error",
                    "error": "No rules found in DSL"
                }
            
            # Handle both single rule (dict) and multiple rules (list) formats
            rules = []
            if isinstance(rules_section, list):
                # Multiple rules format: RULES is a list
                rules = rules_section
            elif isinstance(rules_section, dict):
                # Single rule format: RULES is a dict with alert_code/rule_code
                # Convert single rule to list format
                if 'alert_code' in rules_section or 'rule_code' in rules_section:
                    # Use alert_code as rule_code if rule_code is not present
                    rule_code = rules_section.get('rule_code', rules_section.get('alert_code', 'UNKNOWN'))
                    rules_section['rule_code'] = rule_code
                    rules = [rules_section]
                else:
                    # Might be a dict of rules keyed by rule_code
                    for key, value in rules_section.items():
                        if isinstance(value, dict):
                            value['rule_code'] = key
                            rules.append(value)
            
            if not rules:
                return {
                    "status": "error",
                    "error": "No valid rules found in DSL"
                }
            
            results = []
            logger.info(f"[run_all_rules] Processing {len(rules)} rules")
            for i, rule in enumerate(rules, 1):
                rule_code = rule.get('rule_code', rule.get('alert_code', f'RULE_{i}'))
                logger.info(f"[run_all_rules] Processing rule {i}/{len(rules)}: {rule_code}")
                
                # Convert rule to YAML format
                rule_yaml = yaml.dump(rule)
                
                # Run the rule through the fast path
                # Pass the raw text sections for context
                result = await self.run_rule_fastpath(
                    protocol_id=protocol_id,
                    protocol_text=protocol_text,
                    data_block=data_block,
                    dsl_rule_yaml=rule_yaml,
                    rules_context=rules_text  # Pass all rules for few-shot context
                )
                
                results.append({
                    "rule_code": rule.get('rule_code', rule.get('alert_code', 'UNKNOWN')),
                    "result": result
                })
            
            return {
                "status": "success",
                "rules_executed": len(results),
                "results": results
            }
            
        except Exception as e:
            logger.error(f"Error running all rules: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    # Tool implementations
    async def _execute_sql_pitboss(
        self,
        protocol_id: str,
        rule_code: str,
        sql: str,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        sql_pitboss tool: Execute SQL and create materialized table.
        """
        logger.info(f"[sql_pitboss] Executing SQL for {rule_code}")
        logger.info(f"[sql_pitboss] SQL: {sql}")
        
        try:
            # Generate table name
            table_name = f"{protocol_id}_{rule_code}".lower().replace("-", "_")
            
            # Create materialized table with CREATE OR REPLACE
            create_sql = f"CREATE OR REPLACE TABLE {table_name} AS {sql}"
            logger.info(f"[sql_pitboss] Creating table: {table_name}")
            self.db.execute(create_sql)
            
            # Get row count
            count_result = self.db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()
            row_count = count_result[0] if count_result else 0
            
            # Register in results_registry
            self.db.execute(
                """
                CREATE TABLE IF NOT EXISTS results_registry (
                    protocol_id TEXT,
                    rule_id TEXT,
                    table_name TEXT,
                    sql_text TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                (protocol_id, rule_code, table_name, sql)
            )
            
            # Insert alert with the message
            if message:
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
                
                self.db.execute(
                    """
                    INSERT OR IGNORE INTO alerts (
                        subjid, protocol_id, crf, variable, 
                        variable_value, rule_id, status, date_created
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "SUMMARY",
                        protocol_id,
                        "RULE_EXECUTION",
                        message,
                        float(row_count),
                        rule_code,
                        1,
                        datetime.now().isoformat()
                    )
                )
            
            self.db.commit()
            
            logger.info(f"[sql_pitboss] Created {table_name} with {row_count} rows")
            
            # Log the execution
            self.execution_log.append({
                "tool": "sql_pitboss",
                "timestamp": datetime.now().isoformat(),
                "protocol_id": protocol_id,
                "rule_code": rule_code,
                "table_name": table_name,
                "row_count": row_count
            })
            
            return {
                "status": "success",
                "table_name": table_name,
                "row_count": row_count,
                "message": f"Created {table_name} with {row_count} records"
            }
            
        except Exception as e:
            logger.error(f"[sql_pitboss] Error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _execute_insert_alerts(
        self,
        protocol_id: str,
        rule_code: str,
        status: str = "executed",
        note: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        insert_alerts tool: Log rule execution status.
        """
        try:
            # Map status to integer
            status_map = {
                "planned": 0,
                "executed": 1,
                "skipped": 2,
                "error": -1
            }
            status_int = status_map.get(status, 1)
            
            logger.info(f"[insert_alerts] Logging {rule_code} as {status}")
            
            # Log the execution
            self.execution_log.append({
                "tool": "insert_alerts",
                "timestamp": datetime.now().isoformat(),
                "protocol_id": protocol_id,
                "rule_code": rule_code,
                "status": status,
                "note": note
            })
            
            return {
                "status": "success",
                "rule_code": rule_code,
                "alert_status": status
            }
            
        except Exception as e:
            logger.error(f"[insert_alerts] Error: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    # Helper methods
    def _extract_section_text(self, dsl_text: str, section_name: str) -> str:
        """
        Extract raw text of a specific section from the DSL.
        Returns everything from SECTION_NAME: until the next top-level section or end of file.
        """
        import re
        
        # Find the start of the section
        section_start = re.search(rf"^{section_name}:", dsl_text, re.MULTILINE)
        if not section_start:
            return ""
        
        # Find the next top-level section (if any)
        # Top-level sections are lines that start without spaces and end with ':'
        next_section = re.search(
            r"^(PROTOCOL|DATA|RULES|WORKFLOW):", 
            dsl_text[section_start.end():], 
            re.MULTILINE
        )
        
        if next_section:
            # Extract from section start to just before the next section
            end_pos = section_start.end() + next_section.start()
            return dsl_text[section_start.start():end_pos].rstrip()
        else:
            # Extract from section start to end of file
            return dsl_text[section_start.start():].rstrip()
    
    def _format_protocol_section(self, protocol: Dict[str, Any]) -> str:
        """Format PROTOCOL section for the LLM."""
        parts = []
        
        if 'id' in protocol:
            parts.append(f"Protocol ID: {protocol['id']}")
        if 'title' in protocol:
            parts.append(f"Title: {protocol['title']}")
        if 'description' in protocol:
            parts.append(f"Description: {protocol['description']}")
        
        if 'eligibility' in protocol:
            parts.append("\nEligibility:")
            eligibility = protocol['eligibility']
            if isinstance(eligibility, dict):
                if 'inclusion' in eligibility:
                    parts.append("Inclusion criteria:")
                    for criterion in eligibility.get('inclusion', []):
                        parts.append(f"  - {criterion}")
                if 'exclusion' in eligibility:
                    parts.append("Exclusion criteria:")
                    for criterion in eligibility.get('exclusion', []):
                        parts.append(f"  - {criterion}")
        
        return "\n".join(parts)
    
    def _format_data_section(self, data: Dict[str, Any]) -> str:
        """Format DATA section for the LLM."""
        parts = []
        
        sources = data.get('sources', [])
        requires = data.get('requires', {})
        
        parts.append("Available tables and columns:")
        for source in sources:
            if source in requires:
                columns = requires[source]
                parts.append(f"- {source}: {', '.join(columns)}")
            else:
                parts.append(f"- {source}")
        
        return "\n".join(parts)
    
    async def _send_summary(self, results: List[Dict], protocol_id: str):
        """Send execution summary to frontend."""
        if not self.websocket:
            return
        
        logger.info(f"[_send_summary] Called with {len(results)} results for protocol {protocol_id}")
        
        # Find the sql_pitboss result to get row count and table info
        row_count = 0
        table_name = ""
        alert_inserted = False
        for result in results:
            if result['tool'] == 'sql_pitboss' and result['result']['status'] == 'success':
                row_count = result['result'].get('row_count', 0)
                table_name = result['result'].get('table_name', '')
                alert_inserted = result['result'].get('alert_inserted', False)
                break
        
        # Check if execution was logged
        execution_logged = any(
            r['tool'] == 'insert_alerts' and r['result']['status'] == 'success' 
            for r in results
        )
        
        # Find rule_code
        rule_code = "UNKNOWN"
        for result in results:
            if 'args' in result and 'rule_code' in result['args']:
                rule_code = result['args']['rule_code']
                break
        
        # Create a unique message key to prevent duplicates
        # Use microsecond precision to avoid false positives
        message_key = f"{rule_code}_{row_count}_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # Check for recent duplicate (within last 2 seconds)
        current_time = datetime.now()
        for sent_key in list(self.sent_messages):
            parts = sent_key.rsplit('_', 1)
            if len(parts) == 2:
                key_prefix = parts[0]
                if key_prefix == f"{rule_code}_{row_count}":
                    try:
                        sent_time_str = parts[1]
                        sent_time = datetime.strptime(sent_time_str, '%Y%m%d%H%M%S%f')
                        if (current_time - sent_time).total_seconds() < 2:
                            logger.debug(f"[_send_summary] Skipping duplicate message for {rule_code} (sent {(current_time - sent_time).total_seconds():.2f}s ago)")
                            return
                    except:
                        pass
        
        self.sent_messages.add(message_key)
        
        # Clean up old message keys (keep only last 100)
        if len(self.sent_messages) > 100:
            self.sent_messages = set(list(self.sent_messages)[-100:])
        
        # Format message
        message_parts = [f"{rule_code} - {row_count} records flagged"]
        if alert_inserted:
            message_parts.append("alert logged")
        if execution_logged:
            message_parts.append("execution tracked")
        message_parts.append("(via pitboss_llm_supervisor)")
        message = " ".join(message_parts)
        
        logger.info(f"[_send_summary] Sending message: {message}")
        await self.websocket.send_json({
            "type": "rule_result",
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "supervisor": "gpt-4o",
            "table_name": table_name,
            "row_count": row_count,
            "alert_inserted": alert_inserted
        })
        logger.info(f"[_send_summary] Message sent successfully")
    
    def _markdown_to_html(self, text: str) -> str:
        """Convert markdown text to HTML.
        
        Args:
            text: Markdown formatted text
            
        Returns:
            str: HTML formatted text
        """
        try:
            # Use markdown2 with extras for better formatting
            html = markdown2.markdown(
                text,
                extras=[
                    "fenced-code-blocks",
                    "tables",
                    "break-on-newline",
                    "code-friendly"
                ]
            )
            return html
        except Exception as e:
            logger.warning(f"Failed to convert markdown to HTML: {e}")
            # Fallback: return the original text wrapped in pre tags
            return f"<pre>{text}</pre>"
    
    def get_execution_log(self) -> List[Dict]:
        """Get the execution log for debugging."""
        return self.execution_log
    
    async def classify_intent(self, user_message: str, dsl_text: str) -> Dict[str, Any]:
        """
        Classify user intent from natural language input.
        """
        try:
            # Extract available rule codes from DSL
            dsl = yaml.safe_load(dsl_text)
            rules_section = dsl.get('RULES', [])
            rule_codes = []
            
            if isinstance(rules_section, list):
                rule_codes = [r.get('rule_code', r.get('alert_code', '')) for r in rules_section if r.get('rule_code') or r.get('alert_code')]
            elif isinstance(rules_section, dict) and 'rule_code' in rules_section:
                rule_codes = [rules_section['rule_code']]
            
            # Build prompt with available rules
            classifier_prompt = self.INTENT_CLASSIFIER_PROMPT + ', '.join(rule_codes)
            
            messages = [
                {"role": "system", "content": classifier_prompt},
                {"role": "user", "content": user_message}
            ]
            
            if isinstance(self.client, AsyncOpenAI):
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.1,
                    messages=messages,
                    max_tokens=200
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.1,
                    messages=messages,
                    max_tokens=200
                )
            
            # Parse JSON response
            content = response.choices[0].message.content.strip()
            # Remove markdown code blocks if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            
            return json.loads(content.strip())
            
        except Exception as e:
            logger.error(f"Error classifying intent: {e}")
            # Default to treating as a question
            return {"intent": "ask_question", "question": user_message}
    
    async def answer_question(self, question: str, dsl_text: str) -> str:
        """
        Answer a question about the protocol, data, or rules.
        """
        try:
            # Extract context from DSL
            protocol_text = self._extract_section_text(dsl_text, 'PROTOCOL')
            data_block = self._extract_section_text(dsl_text, 'DATA')
            rules_text = self._extract_section_text(dsl_text, 'RULES')
            
            # Build context for Q&A
            context = f"""Protocol Information:
{protocol_text}

Data Schema:
{data_block}

Available Rules:
{rules_text}"""
            
            messages = [
                {"role": "system", "content": self.QA_PROMPT},
                {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
            ]
            
            if isinstance(self.client, AsyncOpenAI):
                response = await self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.3,
                    messages=messages,
                    max_tokens=500
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o",
                    temperature=0.3,
                    messages=messages,
                    max_tokens=500
                )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            return f"I encountered an error while trying to answer your question: {str(e)}"
    
    async def process_natural_language(self, user_message: str, protocol_id: str, dsl_text: str) -> Dict[str, Any]:
        """
        Process natural language input from the user.
        Routes to either rule execution or Q&A based on intent.
        """
        logger.info(f"Processing natural language: {user_message}")
        
        # Classify intent
        intent_result = await self.classify_intent(user_message, dsl_text)
        logger.info(f"Classified intent: {intent_result}")
        
        intent = intent_result.get('intent', 'ask_question')
        
        if intent == 'execute_rule':
            rule_code = intent_result.get('rule_code')
            if rule_code:
                # Execute specific rule
                result = await self.run_single_rule(protocol_id, dsl_text, rule_code)
                if result.get('status') == 'error':
                    # Send error message via websocket
                    if self.websocket:
                        await self.websocket.send_json({
                            "type": "rule_result",
                            "message": result.get('error', 'Unknown error'),
                            "timestamp": datetime.now().isoformat(),
                            "error": True
                        })
                else:
                    # Send success message for rule execution
                    if self.websocket and result.get('result', {}).get('tool_calls'):
                        await self._send_summary(result['result']['tool_calls'], protocol_id)
                return result
            else:
                error_msg = "I understood you want to run a rule, but I couldn't identify which one. Please specify the rule code."
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "assistant_message",
                        "message": error_msg,
                        "timestamp": datetime.now().isoformat()
                    })
                return {"status": "error", "error": error_msg}
        
        elif intent == 'execute_all_rules':
            # Execute all rules
            result = await self.run_all_rules(protocol_id, dsl_text)
            
            # Send summary message for all rules
            if result.get('status') == 'success':
                rules_count = result.get('rules_executed', 0)
                # Collect summary of all rule results
                total_records = 0
                successful_rules = 0
                
                for rule_result in result.get('results', []):
                    if rule_result['result'].get('status') == 'success':
                        successful_rules += 1
                        for tool_call in rule_result['result'].get('tool_calls', []):
                            if tool_call['tool'] == 'sql_pitboss' and tool_call['result']['status'] == 'success':
                                total_records += tool_call['result'].get('row_count', 0)
                
                summary_msg = f"Executed {successful_rules}/{rules_count} rules successfully. Total {total_records} records flagged across all rules."
                
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "rule_result",
                        "message": summary_msg,
                        "timestamp": datetime.now().isoformat(),
                        "supervisor": "gpt-4o",
                        "rules_executed": rules_count,
                        "total_records": total_records
                    })
            else:
                # Send error message
                if self.websocket:
                    await self.websocket.send_json({
                        "type": "rule_result",
                        "message": result.get('error', 'Failed to execute rules'),
                        "timestamp": datetime.now().isoformat(),
                        "error": True
                    })
            
            return result
        
        elif intent == 'help':
            # Provide help message
            help_msg = """I can help you with:
• Execute a specific rule: 'run RULE_NAME' or 'execute RULE_NAME'
• Execute all rules: 'run all' or 'execute all rules'
• Ask questions about the protocol, data, or rules
• View available rules and their descriptions

What would you like to do?"""
            # Convert markdown to HTML
            html_help = self._markdown_to_html(help_msg)
            if self.websocket:
                await self.websocket.send_json({
                    "type": "assistant_message",
                    "message": html_help,
                    "timestamp": datetime.now().isoformat()
                })
            return {"status": "success", "message": html_help}
        
        else:  # ask_question or default
            # Answer the question
            answer = await self.answer_question(user_message, dsl_text)
            # Convert markdown to HTML
            html_answer = self._markdown_to_html(answer)
            if self.websocket:
                await self.websocket.send_json({
                    "type": "assistant_message",
                    "message": html_answer,
                    "timestamp": datetime.now().isoformat()
                })
            return {"status": "success", "message": html_answer}


# Backwards compatibility wrapper
class Pitboss(LLMSupervisedPitboss):
    """
    Backwards compatibility wrapper that maps old interface to new LLM-supervised implementation.
    """
    
    async def process_rule_request(
        self,
        rule_code: str,
        system_prompt: Optional[str],
        protocol_id: Optional[str],
        rule_id: Optional[str],
        dsl_text: Optional[str] = None
    ):
        """Legacy method - convert to new interface."""
        
        # Check if this is natural language input
        if rule_code and rule_code.startswith('NATURAL_LANGUAGE:'):
            lines = rule_code.split('\n')
            user_message = lines[0].replace('NATURAL_LANGUAGE:', '').strip()
            
            # Extract DSL from the message
            if len(lines) > 1:
                dsl_start_idx = None
                for i, line in enumerate(lines[1:], 1):
                    if line.startswith('DSL:'):
                        dsl_start_idx = i
                        break
                
                if dsl_start_idx:
                    embedded_dsl = '\n'.join(lines[dsl_start_idx:])
                    embedded_dsl = embedded_dsl.replace('DSL:', '', 1).strip()
                    
                    # Process natural language input
                    return await self.process_natural_language(
                        user_message=user_message,
                        protocol_id=protocol_id or "unknown",
                        dsl_text=embedded_dsl
                    )
        
        # Check if this is a RUN_ALL_RULES command with embedded DSL
        elif rule_code and rule_code.startswith('RUN_ALL_RULES'):
            # Extract DSL from the message
            lines = rule_code.split('\n')
            if len(lines) > 1:
                # Find where DSL starts (after "DSL:" marker)
                dsl_start_idx = None
                for i, line in enumerate(lines[1:], 1):
                    if line.startswith('DSL:'):
                        dsl_start_idx = i
                        break
                
                if dsl_start_idx:
                    # Get everything after "DSL:"
                    embedded_dsl = '\n'.join(lines[dsl_start_idx:])
                    embedded_dsl = embedded_dsl.replace('DSL:', '', 1).strip()
                    
                    # Run ALL rules from the DSL
                    return await self.run_all_rules(
                        protocol_id=protocol_id or "unknown",
                        dsl_text=embedded_dsl
                    )
        
        # Check if this is a RUN_RULE command with embedded DSL
        if rule_code and rule_code.startswith('RUN_RULE:'):
            lines = rule_code.split('\n')
            command_line = lines[0]
            
            # Extract the rule to run from the command
            rule_to_run = command_line.replace('RUN_RULE:', '').strip()
            
            # Extract the DSL text from the rest of the message
            if len(lines) > 1:
                # Find where DSL starts (after "DSL:" marker)
                dsl_start_idx = None
                for i, line in enumerate(lines[1:], 1):
                    if line.startswith('DSL:'):
                        dsl_start_idx = i
                        break
                
                if dsl_start_idx:
                    # Get everything after "DSL:"
                    embedded_dsl = '\n'.join(lines[dsl_start_idx:])
                    embedded_dsl = embedded_dsl.replace('DSL:', '', 1).strip()
                    
                    # Use run_single_rule with the extracted DSL
                    result = await self.run_single_rule(
                        protocol_id=protocol_id or "unknown",
                        dsl_text=embedded_dsl,
                        rule_code=rule_to_run
                    )
                    
                    # Send error message if rule execution failed
                    if result.get('status') == 'error' and self.websocket:
                        await self.websocket.send_json({
                            "type": "rule_result",
                            "message": result.get('error', 'Unknown error'),
                            "timestamp": datetime.now().isoformat(),
                            "error": True
                        })
                    
                    return result
        
        # Check if DSL context is provided as a separate parameter
        if dsl_text:
            # If we have DSL, use run_single_rule for full context
            if rule_id:
                # We have a specific rule to run from the DSL
                return await self.run_single_rule(
                    protocol_id=protocol_id or "unknown",
                    dsl_text=dsl_text,
                    rule_code=rule_id
                )
            else:
                # Extract context from DSL but run the provided rule_code
                protocol_text = self._extract_section_text(dsl_text, 'PROTOCOL')
                data_block = self._extract_section_text(dsl_text, 'DATA')
                rules_text = self._extract_section_text(dsl_text, 'RULES')
                
                # Create rule YAML from the provided rule_code
                rule_yaml = yaml.dump({
                    "rule_code": rule_id or "RULE",
                    "logic": rule_code,
                    "severity": "major"
                })
                
                return await self.run_rule_fastpath(
                    protocol_id=protocol_id or "unknown",
                    protocol_text=protocol_text,
                    data_block=data_block,
                    dsl_rule_yaml=rule_yaml,
                    rules_context=rules_text  # Include all rules for context
                )
        else:
            # No DSL provided - use minimal context
            protocol_text = "Protocol context not provided"
            data_block = "Data schema not provided"
            
            # Create a simple rule YAML
            rule_yaml = yaml.dump({
                "rule_code": rule_id or "RULE",
                "logic": rule_code,
                "severity": "major"
            })
            
            return await self.run_rule_fastpath(
                protocol_id=protocol_id or "unknown",
                protocol_text=protocol_text,
                data_block=data_block,
                dsl_rule_yaml=rule_yaml
            )
    
    async def run_workflow(self, dsl_text: str):
        """Legacy method - run all rules in DSL."""
        # Extract protocol_id from DSL
        try:
            dsl = yaml.safe_load(dsl_text)
            protocol_id = dsl.get('PROTOCOL', {}).get('id', 'unknown')
        except:
            protocol_id = 'unknown'
        
        return await self.run_all_rules(protocol_id, dsl_text)