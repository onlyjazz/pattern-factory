"""
Context Builder — Pattern Factory Edition (Clean Version, Nov 2025)

This builder loads:
- SYSTEM prompt from pattern-factory.yaml
- DATA (table+columns) from pattern-factory.yaml
- No PROTOCOL, no clinical content

Produces:
{
   "system": "...",
   "user":   "<logic from rule>"
}
"""

import logging
from typing import Dict, Any, Optional
import yaml
import os

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds LLM-ready context:

    SYSTEM: fixed instruction block from pattern-factory.yaml
    DATA:   list of tables + columns (schema)
    USER:   the natural-language rule logic

    No protocol, no clinical tables, no eligibility, no CRFs.
    """

    def __init__(self, db_connection=None, rules_yaml_path: str = None):
        self.db = db_connection

        # Allow override but default to prompts/rules/pattern-factory.yaml
        self.rules_yaml_path = rules_yaml_path or os.path.join(
            "prompts", "rules", "pattern-factory.yaml"
        )

        self.max_context_tokens = 32000

        # Load on init
        self.yaml_data = self._load_yaml()

    # ---------------------------------------------------------------------
    # YAML Loader
    # ---------------------------------------------------------------------
    def _load_yaml(self) -> Dict[str, Any]:
        """Load pattern-factory.yaml file."""
        try:
            with open(self.rules_yaml_path, "r") as f:
                data = yaml.safe_load(f)
                logger.info(f"Loaded Pattern Factory YAML: {self.rules_yaml_path}")
                return data
        except Exception as e:
            logger.error(f"Failed to load YAML file {self.rules_yaml_path}: {e}")
            return {"SYSTEM": {}, "DATA": {}}

    # ---------------------------------------------------------------------
    # Main Entry
    # ---------------------------------------------------------------------
    def build_context(
        self,
        dsl: Optional[Dict[str, Any]] = None,    # unused in Phase 1
        rule_code: Optional[str] = None,
        include_examples: bool = False           # could support future few-shot
    ) -> Dict[str, str]:
        """
        Build SYSTEM + USER:

        SYSTEM = static system prompt + data tables
        USER   = rule logic
        """
        system_prompt = self._assemble_system_block()
        user_prompt = rule_code or ""

        # Token size logging
        self._log_token_usage(system_prompt, user_prompt)

        return {
            "system": system_prompt,
            "user": user_prompt
        }

    # ---------------------------------------------------------------------
    # SYSTEM BLOCK
    # ---------------------------------------------------------------------
    def _assemble_system_block(self) -> str:
        """
        Build the system prompt:

        SYSTEM.prompt (your long system message)
        +
        DATA tables and columns
        """
        system = self._extract_system_prompt()
        data_section = self._format_data_section()

        return f"{system}\n\n# DATA\n{data_section}"

    def _extract_system_prompt(self) -> str:
        """Return SYSTEM.prompt from YAML, or fallback."""
        sys = self.yaml_data.get("SYSTEM", {})
        prompt = sys.get("prompt", "").strip()

        if not prompt:
            logger.warning("SYSTEM.prompt missing from YAML, using fallback")
            prompt = (
                "You are the model_rule_agent.\n"
                "Generate correct ANSI SQL for the given rule.\n"
                "No explanations. Output ONLY SQL."
            )

        return prompt

    # ---------------------------------------------------------------------
    # DATA BLOCK
    # ---------------------------------------------------------------------
    def _format_data_section(self) -> str:
        """
        Format DATA section (tables + columns) into readable text.
        """
        data_list = self.yaml_data.get("DATA", [])
        if not data_list:
            return "(No DATA section found in YAML)"

        lines = ["Available Tables:"]
        for entry in data_list:
            # entries look like: `- table_name (col1, col2, ...)`
            lines.append(f"  - {entry}")

        return "\n".join(lines)

    # ---------------------------------------------------------------------
    # Token logging
    # ---------------------------------------------------------------------
    def _log_token_usage(self, system_prompt: str, user_prompt: str):
        total_chars = len(system_prompt) + len(user_prompt)
        est_tokens = total_chars // 4

        logger.info(f"Context ~{est_tokens} tokens")

        if est_tokens > self.max_context_tokens:
            logger.warning(
                f"Context may exceed limit: {est_tokens} > {self.max_context_tokens}"
            )

    # ---------------------------------------------------------------------
    # Workflow stub (Phase 2)
    # ---------------------------------------------------------------------
    def build_workflow_context(self, dsl_text: str, step: str) -> Dict[str, str]:
        """
        For Phase 2 automation; currently minimal stub.
        """
        try:
            dsl = yaml.safe_load(dsl_text)
        except:
            dsl = {}

        base = self.build_context(rule_code="")
        base["system"] += f"\n\n# Workflow Step\nCurrent step: {step}"

        return base
