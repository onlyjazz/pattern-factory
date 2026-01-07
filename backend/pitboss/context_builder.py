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
        # Resolve relative to the backend directory to support different working directories
        if rules_yaml_path:
            self.rules_yaml_path = rules_yaml_path
        else:
            # Get the backend root directory (parent of pitboss/)
            backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Go up one more level to project root
            project_root = os.path.dirname(backend_root)
            self.rules_yaml_path = os.path.join(
                project_root, "prompts", "rules", "pattern-factory.yaml"
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
            # Verify file exists
            if not os.path.exists(self.rules_yaml_path):
                logger.error(f"DSL file not found: {self.rules_yaml_path}")
                logger.error(f"Current working directory: {os.getcwd()}")
                logger.error(f"Absolute path resolved to: {os.path.abspath(self.rules_yaml_path)}")
                raise FileNotFoundError(f"DSL file not found at {self.rules_yaml_path}")
            
            with open(self.rules_yaml_path, "r") as f:
                data = yaml.safe_load(f)
                logger.info(f"✅ Loaded Pattern Factory DSL: {self.rules_yaml_path}")
                
                # Log what was loaded
                system_keys = list(data.get("SYSTEM", {}).keys()) if data.get("SYSTEM") else []
                
                # Count tables from both flat and nested schema structures
                data_section = data.get("DATA", {})
                data_tables = len(data_section.get("tables", {}))  # Flat structure
                # Add tables from nested schemas
                schemas = data_section.get("schemas", {})
                if schemas:
                    for schema_data in schemas.values():
                        if isinstance(schema_data, dict):
                            data_tables += len(schema_data.get("tables", {}))
                
                rules_count = len(data.get("RULES", []))
                logger.info(f"   SYSTEM sections: {', '.join(system_keys)}")
                logger.info(f"   DATA tables: {data_tables}")
                logger.info(f"   Predefined RULES: {rules_count}")
                
                return data
        except Exception as e:
            logger.error(f"Failed to load YAML file {self.rules_yaml_path}: {e}")
            logger.error(f"Working directory: {os.getcwd()}")
            logger.error(f"Backend location: {os.path.dirname(os.path.dirname(os.path.abspath(__file__)))}")
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
        Supports both flat structure (DATA.tables) and nested schema structure (DATA.schemas.*.tables).
        """
        data_section = self.yaml_data.get("DATA", {})
        lines = ["Available Tables:"]
        
        # Try flat structure first
        tables = data_section.get("tables", {})
        if tables:
            for table_name, columns in tables.items():
                if isinstance(columns, list):
                    col_str = ", ".join(columns)
                else:
                    col_str = str(columns)
                lines.append(f"  {table_name}: {col_str}")
        
        # Then try nested schema structure (DATA.schemas.<schema_name>.tables)
        schemas = data_section.get("schemas", {})
        if schemas:
            for schema_name, schema_data in schemas.items():
                if isinstance(schema_data, dict):
                    schema_tables = schema_data.get("tables", {})
                    if schema_tables:
                        lines.append(f"  # Schema: {schema_name}")
                        for table_name, columns in schema_tables.items():
                            if isinstance(columns, list):
                                col_str = ", ".join(columns)
                            else:
                                col_str = str(columns)
                            lines.append(f"  {table_name}: {col_str}")
        
        if len(lines) == 1:  # Only header, no tables found
            return "(No DATA.tables or DATA.schemas found in YAML)"

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
