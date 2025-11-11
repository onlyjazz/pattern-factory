"""
Context Builder for Clinical Trial Data Review
Assembles prompts with proper weighting: PROTOCOL → DATA → RULES
"""

import logging
from typing import Dict, Any, List, Optional
import yaml

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds context for LLM prompts following the priority ordering:
    1. PROTOCOL (lower weight) - Sets the scene
    2. DATA (medium weight) - Provides technical details
    3. RULES (highest weight) - Listed last for maximum influence
    
    The DSL acts as a fine-tuning prompt without actual fine-tuning.
    """
    
    def __init__(self, db_connection=None):
        self.db = db_connection
        self.max_context_tokens = 32000  # GPT-4 context window
        
    def build_context(
        self,
        dsl: Optional[Dict[str, Any]] = None,
        rule_code: Optional[str] = None,
        protocol_id: Optional[str] = None,
        include_examples: bool = True
    ) -> Dict[str, str]:
        """
        Build the complete context for the LLM.
        
        Returns:
            Dictionary with 'system' and 'user' prompts
        """
        context_parts = []
        
        # 1. Get base system prompt (constant)
        system_prompt = self._get_system_prompt(protocol_id)
        
        # 2. Add PROTOCOL context (lower weight - appears first)
        if dsl and 'PROTOCOL' in dsl:
            protocol_context = self._build_protocol_context(dsl['PROTOCOL'])
            if protocol_context:
                context_parts.append(("PROTOCOL", protocol_context))
        
        # 3. Add DATA context (medium weight)
        if dsl and 'DATA' in dsl:
            data_context = self._build_data_context(dsl['DATA'])
            if data_context:
                context_parts.append(("DATA", data_context))
        
        # 4. Add RULES context (highest weight - appears last)
        if dsl and 'RULES' in dsl:
            rules_context = self._build_rules_context(
                dsl['RULES'], 
                include_examples=include_examples
            )
            if rules_context:
                context_parts.append(("RULES", rules_context))
        
        # Assemble the complete context
        augmented_system_prompt = self._assemble_context(
            system_prompt, 
            context_parts
        )
        
        # Log token usage estimate
        self._log_token_usage(augmented_system_prompt, rule_code)
        
        return {
            "system": augmented_system_prompt,
            "user": rule_code or ""
        }
    
    def _get_system_prompt(self, protocol_id: str) -> str:
        """
        Fetch the constant system prompt from cards table.
        Falls back to default if not found.
        """
        default_prompt = (
            "You are an AI agent, a clinical data review expert in SQL and "
            "in the protocol and database schema of the trial. "
            "Output of a rule is valid SQL. No prose."
        )
        
        if not self.db or not protocol_id:
            return default_prompt
            
        try:
            result = self.db.execute(
                """
                SELECT prompt 
                FROM cards 
                WHERE protocol_id = ? AND agent = ? 
                ORDER BY date_amended DESC 
                LIMIT 1
                """,
                (protocol_id, "model_rule_agent")
            ).fetchone()
            
            if result:
                logger.info(f"Using custom system prompt for {protocol_id}")
                return result[0]
        except Exception as e:
            logger.warning(f"Could not fetch system prompt: {e}")
        
        return default_prompt
    
    def _build_protocol_context(self, protocol: Dict[str, Any]) -> str:
        """
        Build PROTOCOL context (appears first, lower weight).
        Includes title, description, eligibility criteria.
        """
        parts = ["# PROTOCOL Context (Study Information)"]
        
        if 'id' in protocol:
            parts.append(f"Protocol ID: {protocol['id']}")
        
        if 'title' in protocol:
            parts.append(f"Title: {protocol['title']}")
        
        if 'description' in protocol:
            parts.append(f"Description: {protocol['description']}")
        
        if 'eligibility' in protocol:
            parts.append("\nEligibility Criteria:")
            eligibility = protocol['eligibility']
            if isinstance(eligibility, dict):
                if 'inclusion' in eligibility:
                    parts.append("Inclusion:")
                    for criterion in eligibility['inclusion']:
                        parts.append(f"  - {criterion}")
                if 'exclusion' in eligibility:
                    parts.append("Exclusion:")
                    for criterion in eligibility['exclusion']:
                        parts.append(f"  - {criterion}")
            else:
                parts.append(str(eligibility))
        
        return "\n".join(parts)
    
    def _build_data_context(self, data: Dict[str, Any]) -> str:
        """
        Build DATA context (appears second, medium weight).
        Bridges to the tech stack of the database.
        """
        parts = ["# DATA Context (Available Tables and Fields)"]
        
        sources = data.get('sources', [])
        requires = data.get('requires', {})
        
        if sources:
            parts.append("\nAvailable data sources:")
            for source in sources:
                if source in requires:
                    columns = requires[source]
                    parts.append(f"  - {source}: {', '.join(columns)}")
                else:
                    parts.append(f"  - {source}")
        
        # Add any data dictionary information if available
        if 'dictionary' in data:
            parts.append("\nData Dictionary:")
            for key, value in data['dictionary'].items():
                parts.append(f"  {key}: {value}")
        
        return "\n".join(parts)
    
    def _build_rules_context(
        self, 
        rules: List[Dict[str, Any]], 
        include_examples: bool = True
    ) -> str:
        """
        Build RULES context (appears last, highest weight).
        This is where the magic happens - rules act as strong priors
        that guide probability distributions.
        """
        parts = ["# RULES Context (Data Review Rules)"]
        
        # Add example rules if requested (helps with few-shot learning)
        if include_examples:
            parts.append("\n## Example Rules:")
            parts.append("### Valid rule that generates valid SQL:")
            parts.append("Rule: Flag subjects with ALT > 3x ULN")
            parts.append("SQL: SELECT USUBJID, ALT, ALT/40 as TIMES_ULN FROM adlb_clovis WHERE ALT > 120")
            parts.append("\n### Invalid rule example:")
            parts.append("Rule: Check all the bad data")
            parts.append("ERROR: Too vague, needs specific criteria")
        
        # Add actual rules from DSL
        if rules:
            parts.append("\n## Active Rules for this Protocol:")
            for rule in rules[:5]:  # Limit to prevent context overflow
                rule_code = rule.get('rule_code', 'UNKNOWN')
                logic = rule.get('logic', rule.get('description', ''))
                severity = rule.get('severity', 'major')
                
                parts.append(f"\nRule {rule_code} (Severity: {severity}):")
                parts.append(f"Logic: {logic}")
                
                if 'message' in rule:
                    parts.append(f"Message: {rule['message']}")
                
                if 'crf' in rule:
                    parts.append(f"CRF: {rule['crf']}")
        
        return "\n".join(parts)
    
    def _assemble_context(
        self, 
        system_prompt: str, 
        context_parts: List[tuple]
    ) -> str:
        """
        Assemble the final context with proper ordering.
        Recent context has more influence on token prediction.
        """
        assembled = [system_prompt]
        
        # Add context parts in order of increasing importance
        for section_name, content in context_parts:
            assembled.append(f"\n\n{content}")
            logger.debug(f"Added {section_name} section to context")
        
        return "\n".join(assembled)
    
    def _log_token_usage(self, system_prompt: str, user_prompt: str):
        """
        Estimate and log token usage.
        Rough estimate: 1 token ≈ 4 characters
        """
        total_chars = len(system_prompt) + len(user_prompt or "")
        estimated_tokens = total_chars // 4
        
        logger.info(f"Context size: ~{estimated_tokens} tokens")
        
        if estimated_tokens > self.max_context_tokens:
            logger.warning(
                f"Context may exceed limit: {estimated_tokens} > {self.max_context_tokens}"
            )
    
    def build_workflow_context(
        self, 
        dsl_text: str,
        step: str
    ) -> Dict[str, str]:
        """
        Special context builder for workflow execution.
        """
        try:
            dsl = yaml.safe_load(dsl_text)
            
            # Add workflow-specific context
            workflow = dsl.get('WORKFLOW', {})
            
            base_context = self.build_context(
                dsl=dsl,
                include_examples=False  # No examples needed for workflow
            )
            
            # Augment with workflow step information
            workflow_prompt = f"\n\n# Current Workflow Step: {step}"
            if 'decision_tree' in workflow:
                workflow_prompt += "\nExecuting as part of automated workflow"
            
            base_context['system'] += workflow_prompt
            
            return base_context
            
        except Exception as e:
            logger.error(f"Error building workflow context: {e}")
            return {
                "system": self._get_system_prompt(None),
                "user": ""
            }