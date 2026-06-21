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
    Builds LLM-ready context by loading split component YAML files:

    SYSTEM.yaml:   System instruction block
    DATA.yaml:     Database table and column definitions
    RULES.yaml:    Predefined rule definitions
    CAPO.yaml:     Capo router and human-in-the-loop prompts
    CONTENT.yaml:  Entity extraction and risk model prompts

    Each file is loaded independently with its own mtime tracking for hot-reload.
    """

    # Component files (relative to prompts/rules/)
    COMPONENT_FILES = [
        "SYSTEM.yaml",
        "DATA.yaml",
        "RULES.yaml",
        "CAPO.yaml",
        "CONTENT.yaml"
    ]

    def __init__(self, db_connection=None, rules_yaml_path: str = None):
        self.db = db_connection

        # Allow override but default to prompts/rules/ directory
        # Resolve relative to the backend directory to support different working directories
        if rules_yaml_path:
            # Support legacy single-file path (will be ignored, we load from directory)
            self.rules_dir = os.path.dirname(rules_yaml_path)
        else:
            # Get the backend root directory (parent of pitboss/)
            backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            # Go up one more level to project root
            project_root = os.path.dirname(backend_root)
            self.rules_dir = os.path.join(project_root, "prompts", "rules")

        # Build full paths to component files
        self.component_paths = {
            name: os.path.join(self.rules_dir, name)
            for name in self.COMPONENT_FILES
        }

        self.max_context_tokens = 32000

        # Load on init
        self.yaml_data = self._load_yaml()
        
        # Initialize mtime tracking AFTER loading (so we capture the current mtimes)
        self._last_mtimes = {}
        try:
            for name, path in self.component_paths.items():
                if os.path.exists(path):
                    self._last_mtimes[name] = os.path.getmtime(path)
                    msg = f"[ContextBuilder] Cached initial mtime for {name}: {self._last_mtimes[name]}"
                    logger.info(msg)
                    print(msg)
                else:
                    self._last_mtimes[name] = None
                    msg = f"[ContextBuilder] Component file not found: {path}"
                    logger.warning(msg)
                    print(msg)
        except Exception as e:
            msg = f"[ContextBuilder] Failed to cache initial component mtimes: {e}"
            logger.warning(msg)
            print(msg)
            self._last_mtimes = {name: None for name in self.COMPONENT_FILES}

    # ---------------------------------------------------------------------
    # YAML Loader with Multi-File Hot-Reload
    # ---------------------------------------------------------------------
    def reload_if_changed(self) -> bool:
        """Check if any component YAML file has been modified and reload if needed.
        Returns True if reloaded, False otherwise.
        """
        try:
            changed_files = []
            for name, path in self.component_paths.items():
                if not os.path.exists(path):
                    continue
                current_mtime = os.path.getmtime(path)
                if current_mtime != self._last_mtimes.get(name):
                    changed_files.append(f"{name} (old={self._last_mtimes.get(name)}, new={current_mtime})")
            
            if changed_files:
                msg = f"\n{'='*80}\n🔄 HOT-RELOAD: Component file(s) modified\n   Files: {', '.join(changed_files)}\n   Reloading rules...\n"
                logger.warning(msg)
                print(msg)
                self.yaml_data = self._load_yaml()
                
                # Update all mtimes
                for name, path in self.component_paths.items():
                    if os.path.exists(path):
                        self._last_mtimes[name] = os.path.getmtime(path)
                
                success_msg = f"✅ Component files reloaded successfully\n{'='*80}\n"
                logger.warning(success_msg)
                print(success_msg)
                return True
            
            return False
        except Exception as e:
            logger.warning(f"Error checking component file modifications: {e}")
            return False
    
    def _load_yaml(self) -> Dict[str, Any]:
        """Load component YAML files and merge them into a single dict.
        
        Loads SYSTEM.yaml, DATA.yaml, RULES.yaml, CAPO.yaml, CONTENT.yaml
        and merges them into a single in-memory dict with keys:
        SYSTEM, DATA, RULES, CAPO, CONTENT.
        """
        result = {}
        try:
            for component_name in self.COMPONENT_FILES:
                component_path = self.component_paths[component_name]
                
                if not os.path.exists(component_path):
                    logger.warning(f"Component file not found: {component_path}")
                    continue
                
                with open(component_path, "r") as f:
                    data = yaml.safe_load(f)
                    if data:
                        # Each file has a root key matching its name (SYSTEM, DATA, RULES, CAPO, CONTENT)
                        # Extract that key and merge into result
                        root_key = component_name.replace(".yaml", "").upper()
                        if root_key in data:
                            result[root_key] = data[root_key]
                            logger.debug(f"Loaded {component_name}: root key '{root_key}' found")
                        else:
                            logger.warning(f"No root key '{root_key}' found in {component_name}")
            
            logger.info(f"✅ Loaded Pattern Factory DSL from {len([p for p in self.component_paths.values() if os.path.exists(p)])} component files")
            
            # Log what was loaded
            if "SYSTEM" in result:
                logger.info(f"   ✓ SYSTEM prompt loaded")
            if "DATA" in result:
                data_section = result.get("DATA", {})
                schemas = data_section.get("schemas", {})
                data_tables = sum(len(s.get("tables", {})) for s in schemas.values() if isinstance(s, dict))
                logger.info(f"   ✓ DATA schema loaded ({data_tables} tables)")
            if "RULES" in result:
                rules_count = len(result.get("RULES", []))
                logger.info(f"   ✓ RULES loaded ({rules_count} rules)")
            if "CAPO" in result:
                capo_count = len(result.get("CAPO", []))
                logger.info(f"   ✓ CAPO loaded ({capo_count} prompts)")
            if "CONTENT" in result:
                content_count = len(result.get("CONTENT", []))
                logger.info(f"   ✓ CONTENT loaded ({content_count} prompts)")
            
            return result
        except Exception as e:
            logger.error(f"Failed to load component YAML files: {e}")
            logger.error(f"Working directory: {os.getcwd()}")
            logger.error(f"Rules directory: {self.rules_dir}")
            logger.error(f"Component paths: {list(self.component_paths.values())}")
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
