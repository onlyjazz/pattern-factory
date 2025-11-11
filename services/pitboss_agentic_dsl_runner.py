import yaml
import logging
import traceback
from typing import Any, Dict, List
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class LanguageAgent:
    def __init__(self, mock=False):
        self.mock = mock

    async def process_rule(self, messages: List[Dict[str, str]]) -> str:
        if self.mock:
            return "SELECT * FROM adlb_pds2019 WHERE LBTEST = 'Albumin' AND LBSTRESN > 100"
        import openai
        try:
            response = await asyncio.to_thread(
                openai.chat.completions.create,
                model="gpt-4o",
                messages=messages,
                temperature=0.2,
                max_tokens=200,
                top_p=0.1,
                frequency_penalty=0.5,
                presence_penalty=0.5
            )
            sql_query = response.choices[0].message.content.strip().strip("`")
            if sql_query.lower().startswith("sql"):
                sql_query = "\n".join(sql_query.split("\n")[1:])
            logger.info(f"Generated SQL: {sql_query}")
            return sql_query
        except Exception as e:
            logger.error(f"LanguageAgent error: {e}")
            raise

class ToolAgent:
    def __init__(self, db_connection, mock=False):
        self.db = db_connection
        self.mock = mock

    async def execute_rule(self, sql_query: str, rule_id: str, protocol_id: str) -> Dict[str, Any]:
        if self.mock:
            logger.info(f"[MOCK] Executing SQL query: {sql_query}")
            return {"type": "rule_result", "data": {"results": [{"SUBJID": "01", "LBSTRESN": 101}], "query": sql_query}}
        try:
            logger.info(f"Executing SQL query: {sql_query}")
            cursor = self.db.cursor()
            cursor.execute(sql_query)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            results = cursor.fetchall()
            formatted_results = []
            for row in results:
                row_dict = {}
                for i, value in enumerate(row):
                    row_dict[columns[i]] = value
                formatted_results.append(row_dict)
            for row_dict in formatted_results:
                subjid = row_dict.get("SUBJID") or row_dict.get("subjid")
                crf = row_dict.get("CRF") or row_dict.get("crf", "unknown")
                for k, v in row_dict.items():
                    if k.upper() not in {"SUBJID", "VISIT", "VISITDY", "CRF", "PROTOCOL_ID"}:
                        try:
                            numeric_val = float(v)
                            variable = k
                            value = numeric_val
                            break
                        except (ValueError, TypeError):
                            continue
                self.db.execute(
                    "\n"
                    "                    INSERT INTO alerts (\n"
                    "                        subjid, protocol_id, crf, variable, variable_value, rule_id, status, date_created\n"
                    "                    ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)\n"
                    "                    ",
                    (subjid, protocol_id, crf, variable, value, rule_id, datetime.now().isoformat())
                )
                logger.info(f"Alert inserted for {subjid}, {crf}, {variable}")
            return {"type": "rule_result", "data": {"results": formatted_results, "query": sql_query}}
        except Exception as e:
            logger.error(f"ToolAgent error: {e}")
            return {"type": "error", "data": {"error": str(e)}}

class CallbackAgent:
    def __init__(self, websocket):
        self.websocket = websocket

    async def send_results(self, results: str):
        try:
            await self.websocket.send_json({
                "type": "rule_result",
                "message": results,
                "timestamp": datetime.now().isoformat()
            })
            logger.info("Results sent back to frontend")
        except Exception as e:
            logger.error(f"CallbackAgent error: {e}")
            raise


def _format_rule_block(dsl: Dict[str, Any]) -> str:
    rules = dsl.get("RULES", {})
    if isinstance(rules, list):
        return "\n".join(rules)
    elif isinstance(rules, dict):
        return rules.get("logic", [])[0] or ""
    return ""


class Pitboss:
    def __init__(self, db_connection, websocket, mock=False):
        self.db = db_connection
        self.websocket = websocket
        self.language_agent = LanguageAgent(mock=mock)
        self.tool_agent = ToolAgent(db_connection, mock=mock)
        self.callback_agent = CallbackAgent(websocket)

    def _get_card_context(self, agent_name: str) -> str:
        try:
            rows = self.db.execute("SELECT content FROM cards WHERE agent = ? ORDER BY updated_at DESC LIMIT 1", (agent_name,)).fetchall()
            return rows[0][0] if rows else ""
        except Exception as e:
            logger.warning(f"No card context found for {agent_name}: {e}")
            return ""

    async def run_workflow(self, dsl_text: str):
        try:
            dsl = yaml.safe_load(dsl_text)
            workflow = dsl.get("WORKFLOW", {})
            if not workflow:
                raise ValueError("Missing WORKFLOW section in DSL")

            entrypoint = workflow.get("entrypoint", "rule_evaluator")
            tree = workflow.get("decision_tree", {})

            logger.info(f"Starting workflow at entrypoint: {entrypoint}")
            await self._traverse_tree(tree, dsl)

            await self.websocket.send_json({
                "type": "done",
                "message": "/alerts",
                "timestamp": datetime.now().isoformat()
            })

        except Exception as e:
            error_msg = f"Workflow error: {str(e)}"
            logger.error(error_msg)
            logger.debug(traceback.format_exc())
            await self.websocket.send_json({
                "type": "error",
                "message": error_msg
            })

    async def _traverse_tree(self, node: Dict[str, Any], dsl: Dict[str, Any]):
        step = node.get("step")
        logger.info(f"Running step: {step}")

        match step:
            case "validate_schema":
                valid = self._validate_required_fields(dsl)
                logger.info(f"Schema validation: {'valid' if valid else 'invalid'}")
                next_node = node.get("if valid") if valid else node.get("else")

            case "expand_ruleset":
                next_node = node.get("then")

            case "translate_to_sql":
                rule_code = _format_rule_block(dsl)
                system_prompt = self._get_card_context("translate_to_sql") or "Translate DSL logic to SQL. Use correct table/column names."
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": rule_code}
                ]
                sql_query = await self.language_agent.process_rule(messages)
                self.db.execute("CREATE TEMP TABLE sql_result AS " + sql_query)
                self.sql_query = sql_query
                next_node = node.get("then")

            case "review_translation":
                prompt_context = self._get_card_context("review_translation")
                await self.websocket.send_json({
                    "type": "review",
                    "message": self.sql_query,
                    "prompt": prompt_context or "Approve this SQL translation? (yes/no)"
                })
                approval = await self.websocket.receive_text()
                next_node = node.get("if approved") if approval.strip().lower() == "yes" else node.get("else")

            case "execute_sql":
                await self.tool_agent.execute_rule(self.sql_query, rule_id="ALB_KIDNEY_RISK", protocol_id="20050203")
                next_node = node.get("then")

            case "insert_alerts":
                logger.info("Alerts inserted by tool agent during execution step.")
                next_node = node.get("then")

            case "manual_review":
                prompt_context = self._get_card_context("manual_review")
                await self.websocket.send_json({
                    "type": "manual_review",
                    "message": prompt_context or "Manual review required. Please provide input."
                })
                await self.websocket.receive_text()
                next_node = node.get("then")

            case "error_handler":
                await self.websocket.send_json({
                    "type": "error",
                    "message": "Schema validation failed. Please review DSL."
                })
                return

            case _:
                raise ValueError(f"Unknown step: {step}")

        if next_node:
            await self._traverse_tree(next_node, dsl)

    def _validate_required_fields(self, dsl: Dict[str, Any]) -> bool:
        try:
            sources = dsl["DATA"]["sources"]
            required = dsl["DATA"]["requires"]
            for source in sources:
                fields = required.get(source, [])
                if not fields:
                    logger.warning(f"No required fields listed for source {source}")
            return True
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
