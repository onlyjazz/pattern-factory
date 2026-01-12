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
import time

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
        
        # Initialize mtime tracking AFTER loading (so we capture the current mtime)
        try:
            self._last_yaml_mtime = os.path.getmtime(self.rules_yaml_path) if os.path.exists(self.rules_yaml_path) else None
            msg = f"[ContextBuilder] Initial YAML mtime cached: {self._last_yaml_mtime}"
            logger.info(msg)
            print(msg)  # Also print to ensure visibility
        except Exception as e:
            msg = f"[ContextBuilder] Failed to cache initial YAML mtime: {e}"
            logger.warning(msg)
            print(msg)
            self._last_yaml_mtime = None

    # ---------------------------------------------------------------------
    # YAML Loader with Hot-Reload
    # ---------------------------------------------------------------------
    def reload_if_changed(self) -> bool:
        """Check if YAML file has been modified and reload if needed.
        Returns True if reloaded, False otherwise.
        """
        try:
            if not os.path.exists(self.rules_yaml_path):
                logger.warning(f"[ContextBuilder] YAML file does not exist: {self.rules_yaml_path}")
                return False
            
            current_mtime = os.path.getmtime(self.rules_yaml_path)
            logger.debug(f"[ContextBuilder] Checking YAML mtime: current={current_mtime}, last={self._last_yaml_mtime}")
            
            # Check if file was modified
            if current_mtime != self._last_yaml_mtime:
                msg = f"\n{'='*80}\n🔄 HOT-RELOAD: YAML file modified\n   File: {self.rules_yaml_path}\n   Old mtime: {self._last_yaml_mtime}\n   New mtime: {current_mtime}\n   Reloading rules...\n"
                logger.warning(msg)
                print(msg)
                self.yaml_data = self._load_yaml()
                self._last_yaml_mtime = current_mtime
                success_msg = f"✅ YAML reloaded successfully\n{'='*80}\n"
                logger.warning(success_msg)
                print(success_msg)
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Error checking YAML modification: {e}")
            return False
    
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
        
        # DEBUG: Log assembly steps
        logger.info(f"\n[ContextBuilder._assemble_system_block]")
        logger.info(f"  System prompt: {len(system)} chars")
        logger.info(f"  Data section: {len(data_section)} chars")
        print(f"\n[ContextBuilder._assemble_system_block]")
        print(f"  System prompt: {len(system)} chars")
        print(f"  Data section: {len(data_section)} chars")
        print(f"  Data section preview:\n{data_section[:300]}...")

        result = f"{system}\n\n# DATA\n{data_section}"
        logger.info(f"  Final assembled prompt: {len(result)} chars")
        print(f"  Final assembled prompt: {len(result)} chars")
        return result

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
        logger.info(f"\n[_format_data_section] DATA section exists: {bool(data_section)}")
        print(f"\n[_format_data_section] DATA section exists: {bool(data_section)}")
        print(f"  DATA keys: {list(data_section.keys())}")
        
        lines = ["Available Tables:"]
        
        # Try flat structure first
        tables = data_section.get("tables", {})
        logger.info(f"  Flat tables: {len(tables)} found")
        print(f"  Flat tables: {len(tables)} found")
        if tables:
            for table_name, columns in tables.items():
                if isinstance(columns, list):
                    col_str = ", ".join(columns)
                else:
                    col_str = str(columns)
                lines.append(f"  public.{table_name}: {col_str}")
        
        # Then try nested schema structure (DATA.schemas.<schema_name>.tables)
        schemas = data_section.get("schemas", {})
        logger.info(f"  Nested schemas: {len(schemas)} found")
        print(f"  Nested schemas: {len(schemas)} found")
        print(f"    Schema names: {list(schemas.keys())}")
        if schemas:
            for schema_name, schema_data in schemas.items():
                if isinstance(schema_data, dict):
                    schema_tables = schema_data.get("tables", {})
                    logger.info(f"    Schema '{schema_name}': {len(schema_tables)} tables")
                    print(f"    Schema '{schema_name}': {len(schema_tables)} tables")
                    if schema_tables:
                        lines.append(f"")
                        lines.append(f"  # Schema '{schema_name}': All tables below must be referenced as {schema_name}.<table_name>")
                        for table_name, columns in schema_tables.items():
                            if isinstance(columns, list):
                                col_str = ", ".join(columns)
                            else:
                                col_str = str(columns)
                            lines.append(f"  {schema_name}.{table_name}: {col_str}")
        
        result = "\n".join(lines)
        logger.info(f"  Final data section: {len(result)} chars, {len(lines)} lines")
        print(f"  Final data section: {len(result)} chars, {len(lines)} lines")
        
        if len(lines) == 1:  # Only header, no tables found
            logger.warning("  NO TABLES FOUND IN DATA SECTION!")
            print("  NO TABLES FOUND IN DATA SECTION!")
            return "(No DATA.tables or DATA.schemas found in YAML)"

        return result

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
