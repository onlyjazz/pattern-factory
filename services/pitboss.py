import asyncio
import yaml
import logging
import traceback
from typing import Any, Dict, List, Optional
from datetime import datetime
import re
from tabulate import tabulate

# -----------------------------
# Three–agent Pitboss (workflow-ready)
# -----------------------------
logger = logging.getLogger(__name__)

# =============== Language Agent ===============
class LanguageAgent:
    def __init__(self):
        pass

    async def process_rule(self, messages: List[Dict[str, str]]) -> str:
        import openai
        print("\n[LanguageAgent] Starting process_rule...")
        print(f"[LanguageAgent] Messages: {messages}")
        try:
            print("[LanguageAgent] Calling OpenAI API...")
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4o",
                messages=messages,
                temperature=0.2,
                max_tokens=400,
                top_p=0.1,
                frequency_penalty=0.5,
                presence_penalty=0.5,
            )
            content = response.choices[0].message.content.strip()
            print(f"[LanguageAgent] Raw GPT response: {content[:200]}...")  # Log first 200 chars
            logger.info(f"Raw GPT response: {content[:200]}...")  # Log first 200 chars
            
            # Extract SQL from the response
            sql_query = self.extract_sql_from_response(content)
            print(f"[LanguageAgent] Extracted SQL: {sql_query}")
            logger.info(f"Extracted SQL: {sql_query}")
            return sql_query
        except Exception as e:
            print(f"[LanguageAgent] ERROR: {e}")
            logger.error(f"LanguageAgent error: {e}")
            raise
    
    def extract_sql_from_response(self, content: str) -> str:
        """Extract SQL from GPT response that might include explanatory text."""
        # First try to find SQL in code blocks
        import re
        
        # Look for ```sql blocks
        sql_block_match = re.search(r'```(?:sql)?\s*\n?([^`]+)```', content, re.IGNORECASE | re.DOTALL)
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
        
        # If the content starts with SQL keywords, take everything
        if re.match(r'^\s*(?:SELECT|INSERT|UPDATE|DELETE|CREATE|WITH)\b', content, re.IGNORECASE):
            # Remove any trailing explanation after the SQL
            lines = content.split('\n')
            sql_lines = []
            for line in lines:
                # Stop if we hit explanatory text
                if line.strip() and not re.match(r'^\s*(?:--|/\*|\w+\s*[:=]|FROM|WHERE|JOIN|GROUP|ORDER|HAVING|UNION|AND|OR|ON|AS|IN|BETWEEN|LIKE|IS|NULL|NOT)', line, re.IGNORECASE):
                    if sql_lines:  # We already have SQL, stop here
                        break
                sql_lines.append(line)
            return '\n'.join(sql_lines).strip()
        
        # Last resort: if nothing else worked, return the original content
        # but strip common prefixes
        content = re.sub(r'^(To\s+.*?:|Here\'s|The SQL.*?:)\s*', '', content, flags=re.IGNORECASE)
        return content.strip()

# =============== Tool Agent ===============
class ToolAgent:
    def __init__(self, db_connection):
        self.db = db_connection

    def extract_crf_from_sql(self, sql: str) -> str:
        """Derive CRF from first table in FROM/JOIN (e.g., adlb_clovis -> adlb)."""
        match = re.search(r"\bFROM\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        if not match:
            match = re.search(r"\bJOIN\s+([a-zA-Z0-9_]+)", sql, re.IGNORECASE)
        if match:
            table = match.group(1)
            return table.split('_')[0]
        return "unspecified"

    async def execute_rule(self, sql_query: str, rule_id: str, protocol_id: Optional[str]) -> Dict[str, Any]:
        print(f"\n[ToolAgent] Starting execute_rule...")
        print(f"[ToolAgent] SQL: {sql_query}")
        print(f"[ToolAgent] Rule ID: {rule_id}")
        print(f"[ToolAgent] Protocol ID: {protocol_id}")
        try:
            logger.info(f"Executing SQL query: {sql_query}")
            print("[ToolAgent] Executing SQL...")
            cursor = self.db.cursor()
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            print(f"[ToolAgent] Query returned {len(rows)} rows")

            formatted: List[Dict[str, Any]] = []
            for row in rows:
                formatted.append({columns[i]: row[i] for i in range(len(row))})

            # Note: Individual row alerts are now optional - we're using materialized tables instead
            # Commenting out individual alerts since we're using materialized tables
            print(f"[ToolAgent] Skipping individual row alerts (using materialized table instead)")
            
            print(f"[ToolAgent] Returning {len(formatted)} formatted results")
            return {"type": "rule_result", "data": {"results": formatted, "query": sql_query}}
        except Exception as e:
            print(f"[ToolAgent] ERROR: {e}")
            logger.error(f"ToolAgent error: {e}")
            return {"type": "error", "data": {"error": str(e)}}

# =============== Output / Callback Agent ===============
class CallbackAgent:
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_results(self, results: str):
        await self.websocket.send_json(
            {"type": "rule_result", "message": results, "timestamp": datetime.now().isoformat()}
        )
        logger.info("Results sent back to frontend")

# =============== Helpers ===============
def summarize_sql_to_rule_id(sql: str) -> str:
    """Short, descriptive rule_id from SQL: <TABLE>_<KEYWORD>_<KEYWORD>."""
    sql_l = sql.lower()
    tables = re.findall(r"\bfrom\s+(\w+)|\bjoin\s+(\w+)", sql_l)
    table_names = [t for pair in tables for t in pair if t]
    main_table = table_names[0] if table_names else "unknown"

    where_match = re.search(r"where\s+(.*?)(order by|group by|limit|$)", sql_l, re.DOTALL)
    where_clause = where_match.group(1) if where_match else ""
    tokens = re.findall(r"\b\w+\b", where_clause)
    stopwords = {
        "and","or","is","null","not","in","like","between","as","on","join","from","where","select","case","when","then","else","end"
    }
    keywords = [t for t in tokens if t not in stopwords and not t.isdigit() and len(t) > 2]

    base = main_table.replace("_clovis", "")
    parts = [base] + keywords[:2]
    rule_id = "_".join(parts).upper()
    rule_id = re.sub(r"[^A-Z0-9_]", "_", rule_id)
    return rule_id or "RULE_GENERIC"

def _make_results_table_name(self, protocol_id: str, rule_id: str) -> str:
    """
    Make a DuckDB-safe table name like: res_<protocol>_<rule_id> (lowercased, only [a-z0-9_]).
    """
    proto = (protocol_id or "unknown").lower()
    rid   = (rule_id or "rule").lower()
    name  = f"res_{proto}_{rid}"
    name  = re.sub(r'[^a-z0-9_]+', '_', name)
    if re.match(r'^\d', name):
        name = f"t_{name}"
    return name

def _strip_to_select(self, sql: str) -> str:
    """
    Remove code fences and trailing ';'. If SQL is 'CREATE TABLE ... AS SELECT ...',
    extract and return the 'SELECT ...'.
    """
    s = sql.strip()
    # strip code fences
    s = re.sub(r'^```(?:sql)?\s*', '', s, flags=re.IGNORECASE)
    s = re.sub(r'\s*```$', '', s)
    # drop leading line 'sql'
    lines = s.splitlines()
    if lines and lines[0].strip().lower() == "sql":
        s = "\n".join(lines[1:])
    s = s.strip().rstrip(';').strip()

    # If it's CREATE ... AS SELECT ...
    m = re.search(r'\bas\b\s*(select.*)$', s, flags=re.IGNORECASE | re.DOTALL)
    if m:
        return m.group(1).strip().rstrip(';')

    return s


# =============== Pitboss (Supervisor) ===============
class Pitboss:
    def __init__(self, db_connection, websocket):
        self.db = db_connection
        self.websocket = websocket
        self.language_agent = LanguageAgent()
        self.tool_agent = ToolAgent(db_connection)
        self.callback_agent = CallbackAgent(websocket)
        self.max_feedback_loops = 3
        self._init_memory_tables()

    # ---- memory tables ----
    def _init_memory_tables(self):
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

    def _save_message(self, protocol_id: str, role: str, content: str):
        self.db.execute(
            "INSERT INTO chat_memory (protocol_id, role, content) VALUES (?, ?, ?)",
            (protocol_id, role, content),
        )

    def _save_result(self, protocol_id: str, query: str, summary: str):
        self.db.execute(
            "INSERT INTO query_results (protocol_id, query, summary) VALUES (?, ?, ?)",
            (protocol_id, query, summary),
        )

    def _get_recent_results(self, protocol_id: str, limit: int = 4):
        rows = self.db.execute(
            "SELECT query FROM query_results WHERE protocol_id = ? ORDER BY timestamp DESC LIMIT ?",
            (protocol_id, limit),
        ).fetchall()
        return [{"query": r[0]} for r in reversed(rows)]
    
    def _ensure_results_registry(self):
        """Ensure results_registry table exists for tracking materialized tables."""
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

    def extract_rule_from_dsl(self, dsl_text: str, rule_id: str) -> Optional[Dict[str, Any]]:
        """Extract a specific rule from DSL by its rule_code using proper YAML parsing."""
        try:
            dsl = yaml.safe_load(dsl_text)
            rules = dsl.get('RULES', [])
            for rule in rules:
                if rule.get('rule_code') == rule_id:
                    return rule
        except Exception as e:
            logger.warning(f"Could not parse DSL or find rule {rule_id}: {e}")
        return None
    
    def _build_data_sources_addendum(self, data_section: Dict[str, Any]) -> str:
        """Build an addendum to append to the system prompt with available data sources."""
        sources = data_section.get('sources', [])
        requires = data_section.get('requires', {})
        
        addendum = "In general your data dictionary will include these tables:\n"
        addendum += "sources:\n"
        
        for source in sources:
            addendum += f"    - {source}"
            if source in requires:
                columns = requires[source]
                addendum += f" (columns: {', '.join(columns)})"
            addendum += "\n"
        
        return addendum
    
    async def run_all_rules(self, dsl_text: str, protocol_id: Optional[str]):
        """Execute all rules found in the DSL."""
        try:
            dsl = yaml.safe_load(dsl_text)
            rules = dsl.get('RULES', [])
            
            if not rules:
                await self.websocket.send_json({
                    "type": "error",
                    "message": "No rules found in DSL"
                })
                return
            
            results_summary = []
            
            for rule in rules:
                rule_id = rule.get('rule_code', 'UNKNOWN')
                logic = rule.get('logic', rule.get('description', ''))
                severity = rule.get('severity', 'major')
                message = rule.get('message', '')
                crf = rule.get('crf', None)  # Extract CRF if provided
                
                print(f"\n[Pitboss] Processing rule {rule_id}")
                
                # Process each rule with DSL context for dynamic prompt
                await self.process_single_rule(
                    rule_code=logic,
                    rule_id=rule_id,
                    protocol_id=protocol_id,
                    severity=severity,
                    message=message,
                    crf=crf,  # Pass CRF to process_single_rule
                    dsl_context=dsl  # Pass the full DSL context
                )
            
            print(f"[Pitboss] Completed processing {len(rules)} rules")
            
        except Exception as e:
            logger.error(f"Error running all rules: {e}")
            await self.websocket.send_json({
                "type": "error",
                "message": f"Error running all rules: {str(e)}"
            })
    
    async def process_single_rule(self, rule_code: str, rule_id: str, protocol_id: Optional[str], 
                                  severity: str = 'major', message: str = '', crf: str = None, dsl_context: Optional[Dict] = None):
        """Process a single rule and send formatted result."""
        proto = protocol_id or "unknown"
        
        # Get base system prompt
        system_prompt = "You are an expert SQL translator. Always output only valid SQL."
        try:
            result = self.db.execute(
                "SELECT prompt FROM cards WHERE protocol_id = ? AND agent = ? ORDER BY date_amended DESC LIMIT 1",
                (proto, "model_rule_agent")
            ).fetchone()
            if result:
                system_prompt = result[0]
        except:
            pass
        
        # Append available data sources if DSL context is provided
        if dsl_context and 'DATA' in dsl_context:
            data_sources_addendum = self._build_data_sources_addendum(dsl_context['DATA'])
            system_prompt = system_prompt + "\n\n" + data_sources_addendum
        
        # Generate SQL
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": rule_code},
        ]
        
        sql_query = await self.language_agent.process_rule(messages)
        
        # Create a materialized results table
        table_name = f"{proto}_{rule_id}".replace("-", "_").lower()
        create_sql = f"CREATE OR REPLACE TABLE {table_name} AS {sql_query}"
        print(f"[process_single_rule] Creating materialized table: {table_name}")
        try:
            self.db.execute(create_sql)
            print(f"[process_single_rule] ✓ Successfully created table: {table_name}")
            
            # Register in results_registry
            self._ensure_results_registry()
            self.db.execute(
                """
                INSERT OR REPLACE INTO results_registry (protocol_id, rule_id, table_name, sql_text)
                VALUES (?, ?, ?, ?)
                """,
                (proto, rule_id, table_name, sql_query)
            )
            print(f"[process_single_rule] ✓ Registered table in results_registry")
        except Exception as e:
            print(f"[process_single_rule] ✗ ERROR creating table {table_name}: {e}")
        
        # Execute SQL
        results = await self.tool_agent.execute_rule(sql_query, rule_id, proto)
        
        if results.get("type") == "error":
            error_msg = f"{rule_id} - Error executing rule"
            await self.callback_agent.send_results(error_msg)
            return
        
        rows = results["data"]["results"]
        
        # Insert summary alert for number of records flagged
        print(f"[process_single_rule] Inserting summary alert for {len(rows)} records flagged...")
        try:
            # Ensure alerts table exists
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
            
            # Insert summary alert
            self.db.execute(
                """
                INSERT OR IGNORE INTO alerts (
                    subjid, protocol_id, crf, variable, variable_value, rule_id, status, date_created
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "SUMMARY",  # Special subjid for summary records
                    proto,
                    crf or "RULE_EXECUTION",  # Use rule's CRF if provided, otherwise default
                    message or "Number of records flagged",  # Use rule's message if provided
                    float(len(rows)),
                    rule_id,
                    1,
                    datetime.now().isoformat(),
                ),
            )
            print(f"[process_single_rule] ✓ Summary alert inserted for rule {rule_id}")
            # Commit the transaction to ensure the alert is saved
            self.db.commit()
            print(f"[process_single_rule] ✓ Alert committed to database")
        except Exception as e:
            import traceback
            print(f"[process_single_rule] Warning: Could not insert summary alert: {e}")
            print(f"[process_single_rule] Full traceback:\n{traceback.format_exc()}")
        
        # Format output according to spec: RULE_ID message - X records flagged Severity: severity
        output_message = f"{rule_id} {message} - {len(rows)} records flagged Severity: {severity.title()}"
        
        # Send result
        await self.callback_agent.send_results(output_message)

    # ---- single-shot pipeline ----
    async def process_rule_request(
        self,
        rule_code: str,
        system_prompt: Optional[str],
        protocol_id: Optional[str],
        rule_id: Optional[str],
    ):
        print("\n" + "="*60)
        print("[Pitboss] STARTING PROCESS_RULE_REQUEST")
        print(f"[Pitboss] Rule code: {rule_code[:100]}...")
        print(f"[Pitboss] System prompt from frontend: {system_prompt[:100] if system_prompt else 'None'}")
        print(f"[Pitboss] Protocol ID: {protocol_id}")
        print(f"[Pitboss] Rule ID: {rule_id}")
        print("="*60)
        
        proto = protocol_id or "unknown"
        
        # Check if this is a RUN_RULE or RUN_ALL_RULES command
        if rule_code and (rule_code.startswith('RUN_RULE:') or rule_code.startswith('RUN_ALL_RULES')):
            # Extract DSL from the message
            lines = rule_code.split('\n')
            command_line = lines[0]
            dsl_text = '\n'.join(lines[1:]).replace('DSL:', '').strip() if len(lines) > 1 else ''
            
            if command_line.startswith('RUN_RULE:'):
                # Execute specific rule
                rule_to_run = command_line.replace('RUN_RULE:', '').strip()
                print(f"[Pitboss] Executing specific rule: {rule_to_run}")
                
                if dsl_text:
                    dsl = yaml.safe_load(dsl_text)  # Parse the full DSL
                    rule = self.extract_rule_from_dsl(dsl_text, rule_to_run)
                    if rule:
                        # Execute the rule immediately with extracted metadata and DSL context
                        await self.process_single_rule(
                            rule_code=rule.get('logic', rule.get('description', '')),
                            rule_id=rule.get('rule_code', rule_to_run),
                            protocol_id=protocol_id,
                            severity=rule.get('severity', 'major'),
                            message=rule.get('message', ''),
                            crf=rule.get('crf', None),  # Extract and pass CRF if provided
                            dsl_context=dsl  # Pass the full DSL context
                        )
                        return
                    else:
                        print(f"[Pitboss] Rule {rule_to_run} not found in DSL")
                        await self.websocket.send_json({
                            "type": "error",
                            "message": f"Rule {rule_to_run} not found in DSL"
                        })
                        return
                else:
                    # No DSL provided, execute as plain rule
                    print(f"[Pitboss] No DSL provided for rule lookup")
                    await self.process_single_rule(
                        rule_code=f"Execute rule {rule_to_run}",
                        rule_id=rule_to_run,
                        protocol_id=protocol_id,
                        severity='major',
                        message='',
                        crf=None  # No CRF when DSL not provided
                    )
                    return
            
            elif command_line.startswith('RUN_ALL_RULES'):
                # Execute all rules in DSL
                print(f"[Pitboss] Executing all rules from DSL")
                
                if dsl_text:
                    await self.run_all_rules(dsl_text, protocol_id)
                    return
                else:
                    await self.websocket.send_json({
                        "type": "error",
                        "message": "No DSL provided for RUN_ALL_RULES"
                    })
                    return
        
        # For non-command rules, continue with regular processing
        
        # Fetch system prompt from cards table for model_rule_agent
        print(f"[Pitboss] Fetching system prompt from cards table for protocol_id={proto}...")
        try:
            result = self.db.execute(
                "SELECT prompt FROM cards WHERE protocol_id = ? AND agent = ? ORDER BY date_amended DESC LIMIT 1",
                (proto, "model_rule_agent")
            ).fetchone()
            
            if result:
                system_prompt = result[0]
                print(f"[Pitboss] Found system prompt from cards table (length: {len(system_prompt)} chars)")
                print(f"[Pitboss] First 200 chars: {system_prompt[:200]}...")
            else:
                print(f"[Pitboss] No card found for protocol_id={proto}, agent=model_rule_agent")
                # Fallback if no card found
                system_prompt = system_prompt or "You are an expert SQL translator. Always output only valid SQL."
        except Exception as e:
            print(f"[Pitboss] Error fetching from cards table: {e}")
            system_prompt = system_prompt or "You are an expert SQL translator. Always output only valid SQL."
        
        print(f"[Pitboss] Final system prompt (first 200 chars): {system_prompt[:200]}...")
        print(f"[Pitboss] Saving message to chat_memory...")
        self._save_message(proto, "user", rule_code)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": rule_code},
        ]
        recent = self._get_recent_results(proto)
        if recent:
            prior = "\n".join([f"Query: {r['query']}" for r in recent])
            messages.append({"role": "system", "content": f"Prior results (context only):\n{prior}"})

        print("[Pitboss] Calling Language Agent...")
        sql_query = await self.language_agent.process_rule(messages)
        print(f"[Pitboss] SQL from Language Agent: {sql_query}")
        
        rule_id = rule_id or summarize_sql_to_rule_id(sql_query)
        print(f"[Pitboss] Final rule_id: {rule_id}")
        logger.info(f"Generated rule_id: {rule_id}")

        # Create a materialized results table
        table_name = f"{proto}_{rule_id}".replace("-", "_")
        create_sql = f"CREATE OR REPLACE TABLE {table_name} AS {sql_query}"
        print(f"[Pitboss] Attempting to create table: {table_name}")
        print(f"[Pitboss] Create SQL: {create_sql}")
        try:
            self.db.execute(create_sql)
            print(f"[Pitboss] ✓ Successfully created table: {table_name}")
            logger.info(f"Created results table: {table_name}")
        except Exception as e:
            print(f"[Pitboss] ✗ ERROR creating table {table_name}: {e}")
            logger.error(f"Error creating table {table_name}: {e}")

        # Execute and collect results
        print("[Pitboss] Calling Tool Agent to execute rule...")
        results = await self.tool_agent.execute_rule(sql_query, rule_id, proto)
        print(f"[Pitboss] Tool Agent returned: {results.get('type')}")
        if results.get("type") == "error":
            print(f"[Pitboss] Error from Tool Agent, sending to frontend: {results}")
            await self.websocket.send_json(results)
            return

        rows = results["data"]["results"]
        print(f"[Pitboss] Processing {len(rows)} rows for output...")
        print(f"[Pitboss] DEBUG: rows type = {type(rows)}, len = {len(rows)}")
        print(f"[Pitboss] DEBUG: proto = {proto}, rule_id = {rule_id}")
        
        # 1. Insert summary alert for number of records flagged
        print(f"[Pitboss] Inserting summary alert for {len(rows)} records flagged...")
        try:
            # Ensure alerts table exists
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
            
            # Insert summary alert
            self.db.execute(
                """
                INSERT OR IGNORE INTO alerts (
                    subjid, protocol_id, crf, variable, variable_value, rule_id, status, date_created
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "SUMMARY",  # Special subjid for summary records
                    proto,
                    "RULE_EXECUTION",  # Special CRF for rule summaries
                    "Number of records flagged",
                    float(len(rows)),
                    rule_id,
                    1,
                    datetime.now().isoformat(),
                ),
            )
            print(f"[Pitboss] ✓ Summary alert inserted for rule {rule_id}")
            # Commit the transaction to ensure the alert is saved
            self.db.commit()
            print(f"[Pitboss] ✓ Alert committed to database")
        except Exception as e:
            import traceback
            print(f"[Pitboss] Warning: Could not insert summary alert: {e}")
            print(f"[Pitboss] Full traceback:\n{traceback.format_exc()}")
        
        # 2. Register rule execution in rules table
        print(f"[Pitboss] Registering rule execution in rules table...")
        try:
            # Get sponsor from protocols table or cards table
            sponsor_result = self.db.execute(
                "SELECT sponsor FROM protocols WHERE protocol_id = ? LIMIT 1",
                (proto,)
            ).fetchone()
            sponsor = sponsor_result[0] if sponsor_result else "Unknown"
            
            # Ensure rules table exists
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
            
            # Insert or update rule record with the logic/SQL that was executed
            now = datetime.now().isoformat()
            self.db.execute(
                """
                INSERT INTO rules (rule_id, protocol_id, sponsor, rule_code, date_created, date_amended)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(rule_id) DO UPDATE SET
                    rule_code = excluded.rule_code,
                    date_amended = excluded.date_amended
                """,
                (
                    rule_id,
                    proto,
                    sponsor,
                    f"Logic: {rule_code}\n\nGenerated SQL:\n{sql_query}",  # Store both logic and SQL
                    now,
                    now,
                ),
            )
            print(f"[Pitboss] ✓ Rule {rule_id} registered in rules table")
        except Exception as e:
            print(f"[Pitboss] Warning: Could not register rule: {e}")
        # Generate summary message in the specified format
        # Extract message and severity - these could be extracted from DSL in the future
        # For now, use the rule_code as a simple description
        if rule_id and rule_id.startswith(('ECOG', 'ALT', 'AST', 'BILI')):
            # Known rule types - use simplified message
            message = rule_id.replace('_', ' ').title()
            severity = "Major"  # Could be extracted from DSL
        else:
            # Generic rule
            message = rule_code[:50] if len(rule_code) > 50 else rule_code
            severity = "Major"
        
        # Create summary message in the format: RULE_ID <message> - X records flagged Severity: <severity>
        summary_message = f"{rule_id} {message} - {len(rows)} records flagged Severity: {severity}"
        
        # Send just the summary message for clean output
        full_output = summary_message

        print("[Pitboss] Saving to chat memory and query results...")
        self._save_message(proto, "assistant", full_output)
        self._save_result(proto, sql_query, f"{len(rows)} rows returned")
        
        print("[Pitboss] Sending results to frontend via Callback Agent...")
        await self.callback_agent.send_results(full_output)
        print("[Pitboss] ✓ PROCESS_RULE_REQUEST COMPLETE")
        print("="*60)

    # ---- workflow runtime ----
    async def run_workflow(self, dsl_text: str):
        try:
            dsl = yaml.safe_load(dsl_text)
            workflow = dsl.get("WORKFLOW", {})
            if not workflow:
                raise ValueError("Missing WORKFLOW section in DSL")

            self.protocol_id_from_dsl = (
                (dsl.get("PROTOCOL") or {}).get("id")
            )
            tree = workflow.get("decision_tree", {})
            logger.info("Starting workflow traversal")
            await self._traverse_tree(tree, dsl, loops=0)

            await self.websocket.send_json(
                {"type": "done", "message": "/alerts", "timestamp": datetime.now().isoformat()}
            )
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            await self.websocket.send_json({"type": "error", "message": str(e)})

    async def _traverse_tree(self, node: Dict[str, Any], dsl: Dict[str, Any], loops: int):
        step = node.get("step")
        logger.info(f"Workflow step: {step}")
        next_node = None

        match step:
            case "model_abnormal_labs":
                valid = self._validate_required_fields(dsl)
                next_node = node.get("if valid") if valid else node.get("else")

            case "sql_pitboss_agent":
                rule_code = self._format_rule_block(dsl)
                messages = [
                    {"role": "system", "content": self._get_card_prompt("sql_pitboss_agent") or "Translate DSL logic to valid DuckDB SQL."},
                    {"role": "user", "content": rule_code},
                ]
                # 1) LLM → SQL
                self.sql_query = await self.language_agent.process_rule(messages)
                self.rule_id   = summarize_sql_to_rule_id(self.sql_query)

                # 2) Materialize results table
                proto_id = self.protocol_id_from_dsl or "unknown"
                self.results_table_name = self._make_results_table_name(proto_id, self.rule_id)
                select_sql = self._strip_to_select(self.sql_query)

                # Prefer idempotent replace so latest run is visible to UI
                if re.match(r'^\s*select\b', select_sql, flags=re.IGNORECASE):
                    self.db.execute(f"CREATE OR REPLACE TABLE {self.results_table_name} AS {select_sql}")
                else:
                    # Fallback: if LLM returned something non-SELECT, just execute it
                    self.db.execute(self.sql_query)

                # 3) Register for UI
                self._ensure_results_registry()
                self.db.execute(
                    """
                    INSERT OR REPLACE INTO results_registry (protocol_id, rule_id, table_name, sql_text)
                    VALUES (?, ?, ?, ?)
                    """,
                    (proto_id, self.rule_id, self.results_table_name, self.sql_query),
                )

                await self.websocket.send_json({
                    "type": "info",
                    "message": f"Results table created: {self.results_table_name}"
                })
                next_node = node.get("then")

            case "ai_chat":
                # Ask for approval / feedback
                await self.websocket.send_json(
                    {"type": "review", "message": self.sql_query, "prompt": "Approve this SQL? Reply 'yes' or provide feedback."}
                )
                reply = (await self.websocket.receive_text()).strip()
                if reply.lower().startswith("yes"):
                    next_node = node.get("if approved")
                else:
                    # Re-run translation with feedback (loop up to max_feedback_loops)
                    if loops >= self.max_feedback_loops:
                        await self.websocket.send_json({"type": "info", "message": "Max feedback loops reached; continuing."})
                        next_node = node.get("if approved")
                    else:
                        messages = [
                            {"role": "system", "content": self._get_card_prompt("sql_pitboss_agent") or "Translate DSL logic to valid DuckDB SQL."},
                            {"role": "user", "content": self._format_rule_block(dsl)},
                            {"role": "user", "content": f"Incorporate this feedback: {reply}"},
                        ]
                        self.sql_query = await self.language_agent.process_rule(messages)
                        self.rule_id = summarize_sql_to_rule_id(self.sql_query)
                        # Loop back to the same step
                        await self._traverse_tree({"step": "ai_chat", "if approved": node.get("if approved"), "else": node.get("else")}, dsl, loops + 1)
                        return

            case "render_alerts_table":
                # Placeholder: UI rendering is handled by frontend after /get_alerts fetch
                next_node = node.get("then")

            case "insert_alerts":
                # Execute the rule and get results
                results = await self.tool_agent.execute_rule(self.sql_query, self.rule_id, self.protocol_id_from_dsl)
                
                # Insert summary alert for the rule execution
                if results.get("type") == "rule_result":
                    rows = results["data"]["results"]
                    proto = self.protocol_id_from_dsl or "unknown"
                    
                    print(f"[Workflow] Inserting summary alert for {len(rows)} records flagged...")
                    try:
                        # Ensure alerts table exists
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
                        
                        # Insert summary alert
                        self.db.execute(
                            """
                            INSERT OR IGNORE INTO alerts (
                                subjid, protocol_id, crf, variable, variable_value, rule_id, status, date_created
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "SUMMARY",  # Special subjid for summary records
                                proto,
                                "RULE_EXECUTION",  # Special CRF for rule summaries
                                "Number of records flagged",
                                float(len(rows)),
                                self.rule_id,
                                1,
                                datetime.now().isoformat(),
                            ),
                        )
                        print(f"[Workflow] ✓ Summary alert inserted for rule {self.rule_id}")
                        logger.info(f"Summary alert inserted for rule {self.rule_id}: {len(rows)} records flagged")
                        # Commit the transaction to ensure the alert is saved
                        self.db.commit()
                        print(f"[Workflow] ✓ Alert committed to database")
                    except Exception as e:
                        print(f"[Workflow] Warning: Could not insert summary alert: {e}")
                        logger.warning(f"Failed to insert summary alert: {e}")
                
                next_node = node.get("then")

            case "validate_schema":
                valid = self._validate_required_fields(dsl)
                next_node = node.get("if valid") if valid else node.get("else")

            case "translate_to_sql":
                # Generic translate step (alt path)
                rule_code = self._format_rule_block(dsl)
                messages = [
                    {"role": "system", "content": self._get_card_prompt("translate_to_sql") or "Translate DSL logic to SQL. Use correct table/column names."},
                    {"role": "user", "content": rule_code},
                ]
                self.sql_query = await self.language_agent.process_rule(messages)
                next_node = node.get("then")

            case "review_translation":
                await self.websocket.send_json(
                    {"type": "review", "message": self.sql_query, "prompt": "Approve this SQL translation? (yes/no)"}
                )
                approval = (await self.websocket.receive_text()).strip().lower()
                next_node = node.get("if approved") if approval == "yes" else node.get("else")

            case "execute_sql":
                # Execute the rule and get results
                results = await self.tool_agent.execute_rule(self.sql_query, self.rule_id or "WF_RULE", self.protocol_id_from_dsl)
                
                # Insert summary alert for the rule execution
                if results.get("type") == "rule_result":
                    rows = results["data"]["results"]
                    proto = self.protocol_id_from_dsl or "unknown"
                    
                    print(f"[Workflow-execute_sql] Inserting summary alert for {len(rows)} records flagged...")
                    try:
                        # Ensure alerts table exists
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
                        
                        # Insert summary alert
                        self.db.execute(
                            """
                            INSERT OR IGNORE INTO alerts (
                                subjid, protocol_id, crf, variable, variable_value, rule_id, status, date_created
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                "SUMMARY",  # Special subjid for summary records
                                proto,
                                "RULE_EXECUTION",  # Special CRF for rule summaries
                                "Number of records flagged",
                                float(len(rows)),
                                self.rule_id or "WF_RULE",
                                1,
                                datetime.now().isoformat(),
                            ),
                        )
                        print(f"[Workflow-execute_sql] ✓ Summary alert inserted for rule {self.rule_id or 'WF_RULE'}")
                        logger.info(f"Summary alert inserted for rule {self.rule_id or 'WF_RULE'}: {len(rows)} records flagged")
                        # Commit the transaction to ensure the alert is saved
                        self.db.commit()
                        print(f"[Workflow-execute_sql] ✓ Alert committed to database")
                    except Exception as e:
                        print(f"[Workflow-execute_sql] Warning: Could not insert summary alert: {e}")
                        logger.warning(f"Failed to insert summary alert: {e}")
                
                next_node = node.get("then")

            case "error_handler":
                await self.websocket.send_json({"type": "error", "message": "Schema validation failed."})
                return

            case _:
                logger.warning(f"Unknown step: {step}")

        if next_node:
            await self._traverse_tree(next_node, dsl, loops)

    # ---- utilities ----
    def _validate_required_fields(self, dsl: Dict[str, Any]) -> bool:
        try:
            sources = (dsl.get("DATA") or {}).get("sources", [])
            required = (dsl.get("DATA") or {}).get("requires", {})
            for source in sources:
                fields = required.get(source, [])
                if not isinstance(fields, list):
                    logger.warning(f"Malformed requires for {source}")
            return True
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False

    def _format_rule_block(self, dsl: Dict[str, Any]) -> str:
        rules = dsl.get("RULES", {})
        if isinstance(rules, list):
            return "\n".join(rules)
        if isinstance(rules, dict):
            # Prefer description + logic block to give the LLM more context
            desc = rules.get("description", "")
            logic = rules.get("logic", "")
            if isinstance(logic, list):
                logic = "\n".join(logic)
            return f"{desc}\n\nLogic:\n{logic}".strip()
        return ""

    def _get_card_prompt(self, agent_name: str) -> Optional[str]:
        """Fetch latest prompt for an agent from `cards` (optional)."""
        try:
            row = self.db.execute(
                "SELECT prompt FROM cards WHERE agent = ? ORDER BY date_amended DESC LIMIT 1",
                (agent_name,),
            ).fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.warning(f"No card prompt for {agent_name}: {e}")
            return None
