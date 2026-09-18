"""
Pitboss Workflow Engine
Executes deterministic decision trees defined in YAML.

Decision tree structure:
- model.Capo (entry point)
  ├── No → sendMessageToChat
  └── Yes → model.verifyRequest
- model.verifyRequest
  ├── No → sendMessageToChat
  └── Yes → model.ruleToSQL
... and so on
"""

from dataclasses import dataclass
from typing import Dict, Optional, Callable, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class WorkflowNode:
    """A single node in the workflow decision tree."""
    agent_name: str  # e.g., "model.Capo"
    branch_yes: Optional[str] = None  # Next agent if decision == yes
    branch_no: Optional[str] = None   # Next agent if decision == no
    description: str = ""


class WorkflowEngine:
    """
    Executes Pattern Factory agents.
    
    Responsibilities:
    - start a RUN or CONTENT flow where agents determine nextAgent
    - Track current position in decision tree
    - Branch on agent decisions (yes/no)
    - Route to terminal nodes (sendMessageToChat, etc)
    - Provide HITL resume targets (which agent to call after human approval)
    """
    
    def __init__(self):
        """Initialize workflow engine."""
        self.workflows: Dict[str, Dict[str, WorkflowNode]] = {}
        self._load_workflows()
        logger.info("🔄 Workflow Engine initialized")
    
    def _load_workflows(self):
        """
        Load workflow definitions.
        Currently hardcoded; will be replaced with YAML loading.
        """
        # RULE Flow (RUN is API name, RULE is internal workflow key)
        self.workflows["RULE"] = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.verifyRequest",
                branch_no="sendMessageToChat",
                description="Initial validation of rule request"
            ),
            "model.verifyRequest": WorkflowNode(
                agent_name="model.verifyRequest",
                branch_yes="model.ruleToSQL",
                branch_no="sendMessageToChat",
                description="Validate semantics of rule request"
            ),
            "model.ruleToSQL": WorkflowNode(
                agent_name="model.ruleToSQL",
                branch_yes="model.verifySQL",
                branch_no="sendMessageToChat",
                description="Convert rule to SQL"
            ),
            "model.verifySQL": WorkflowNode(
                agent_name="model.verifySQL",
                branch_yes="tool.executeSQL",
                branch_no="sendMessageToChat",
                description="Validate SQL safety and correctness"
            ),
            "tool.executeSQL": WorkflowNode(
                agent_name="tool.executeSQL",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Execute the SQL"
            ),
        }
        
        # CONTENT Flow
        self.workflows["CONTENT"] = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.verifyRequest",
                branch_no="sendMessageToChat",
                description="Initial validation of extraction request"
            ),
            "model.verifyRequest": WorkflowNode(
                agent_name="model.verifyRequest",
                branch_yes="model.requestToExtractEntities",
                branch_no="sendMessageToChat",
                description="Validate extraction request semantics"
            ),
            "model.requestToExtractEntities": WorkflowNode(
                agent_name="model.requestToExtractEntities",
                branch_yes="model.verifyUpsert",
                branch_no="sendMessageToChat",
                description="Extract entities (orgs, guests, patterns, etc)"
            ),
            "model.verifyUpsert": WorkflowNode(
                agent_name="model.verifyUpsert",
                branch_yes="tool.executeSQL",
                branch_no="sendMessageToChat",
                description="Verify upsert consistency and referential integrity"
            ),
            "tool.executeSQL": WorkflowNode(
                agent_name="tool.executeSQL",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Execute the upsert"
            ),
        }
        
        # GENERATE Flow (Risk Model Extraction from Card Markdown)
        generate_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.verifyRequest",
                branch_no="sendMessageToChat",
                description="Initial validation of generate request"
            ),
            "model.verifyRequest": WorkflowNode(
                agent_name="model.verifyRequest",
                branch_yes="model.requestToExtractRiskModel",
                branch_no="sendMessageToChat",
                description="Validate generate request semantics"
            ),
            "model.requestToExtractRiskModel": WorkflowNode(
                agent_name="model.requestToExtractRiskModel",
                branch_yes="model.verifyUpsertRiskModel",
                branch_no="sendMessageToChat",
                description="Extract threats, vulnerabilities, countermeasures from card markdown"
            ),
            "model.verifyUpsertRiskModel": WorkflowNode(
                agent_name="model.verifyUpsertRiskModel",
                branch_yes="tool.executeSQL",
                branch_no="sendMessageToChat",
                description="Verify risk model payload consistency and safety"
            ),
            "tool.executeSQL": WorkflowNode(
                agent_name="tool.executeSQL",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Execute the upsert_risk_model procedure"
            ),
        }
        self.workflows["GENERATE"] = generate_workflow
        
        # ENRICH Flow (Organization data enrichment)
        enrich_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.validateOrgName",
                branch_no="sendMessageToChat",
                description="Initial validation of enrich request"
            ),
            "model.validateOrgName": WorkflowNode(
                agent_name="model.validateOrgName",
                branch_yes="model.searchForEnrichmentData",
                branch_no="sendMessageToChat",
                description="Validate org name in database"
            ),
            "model.searchForEnrichmentData": WorkflowNode(
                agent_name="model.searchForEnrichmentData",
                branch_yes="model.verifyExtractionResults",
                branch_no="sendMessageToChat",
                description="Search web for funding/revenue data"
            ),
            "model.verifyExtractionResults": WorkflowNode(
                agent_name="model.verifyExtractionResults",
                branch_yes="tool.enrichOrgDatabase",
                branch_no="sendMessageToChat",
                description="Verify extracted data with LLM (HITL: present for approval)"
            ),
            "tool.enrichOrgDatabase": WorkflowNode(
                agent_name="tool.enrichOrgDatabase",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Update organization record with approved data"
            ),
        }
        self.workflows["ENRICH"] = enrich_workflow
        
        # FEELGOOD Flow (Extract product superiority claims from web search)
        feelgood_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.validateProductId",
                branch_no="sendMessageToChat",
                description="Initial validation of feelgood request"
            ),
            "model.validateProductId": WorkflowNode(
                agent_name="model.validateProductId",
                branch_yes="model.searchForSuperiority",
                branch_no="sendMessageToChat",
                description="Validate product exists in database"
            ),
            "model.searchForSuperiority": WorkflowNode(
                agent_name="model.searchForSuperiority",
                branch_yes="model.extractSuperiorityClaim",
                branch_no="sendMessageToChat",
                description="Get superiority narrative via Exa Answer API"
            ),
            "model.extractSuperiorityClaim": WorkflowNode(
                agent_name="model.extractSuperiorityClaim",
                branch_yes="tool.updateProductSuperiority",
                branch_no="sendMessageToChat",
                description="Extract CEO-focused superiority claim from Exa results"
            ),
            "tool.updateProductSuperiority": WorkflowNode(
                agent_name="tool.updateProductSuperiority",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Update product record with superiority claim"
            ),
        }
        self.workflows["FEELGOOD"] = feelgood_workflow
        
        # PROFILE Flow (Extract device profile from FDA sources)
        # Note: Uses shared model.validateProductId agent with FEELGOOD
        profile_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.validateProductId",
                branch_no="sendMessageToChat",
                description="Initial validation of profile request"
            ),
            "model.validateProductId": WorkflowNode(
                agent_name="model.validateProductId",
                branch_yes="model.searchFDADatabase",
                branch_no="sendMessageToChat",
                description="Validate product exists in database (shared with FEELGOOD)"
            ),
            "model.searchFDADatabase": WorkflowNode(
                agent_name="model.searchFDADatabase",
                branch_yes="model.extractDeviceProfile",
                branch_no="sendMessageToChat",
                description="Search FDA Devices@FDA database for submission"
            ),
            "model.extractDeviceProfile": WorkflowNode(
                agent_name="model.extractDeviceProfile",
                branch_yes="tool.updateProductProfile",
                branch_no="sendMessageToChat",
                description="Extract device profile data from FDA clearance documents"
            ),
            "tool.updateProductProfile": WorkflowNode(
                agent_name="tool.updateProductProfile",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Update product record with device profile (description, intended_use, indications_for_use)"
            ),
        }
        self.workflows["PROFILE"] = profile_workflow
        
        # COMPETITORS Flow (Product competition intelligence)
        # Note: Uses shared model.validateProductId agent with FEELGOOD/PROFILE
        competitors_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.validateProductId",
                branch_no="sendMessageToChat",
                description="Initial validation of competitors request"
            ),
            "model.validateProductId": WorkflowNode(
                agent_name="model.validateProductId",
                branch_yes="model.searchForCompetitors",
                branch_no="sendMessageToChat",
                description="Validate product exists in database (shared with FEELGOOD/PROFILE)"
            ),
            "model.searchForCompetitors": WorkflowNode(
                agent_name="model.searchForCompetitors",
                branch_yes="tool.upsertCompetitors",
                branch_no="sendMessageToChat",
                description="Search Exa for top 3 competing products"
            ),
            "tool.upsertCompetitors": WorkflowNode(
                agent_name="tool.upsertCompetitors",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Upsert competitor relationships and missing org/product records"
            ),
        }
        self.workflows["COMPETITORS"] = competitors_workflow
        
        # PORTFOLIO Flow (FDA device portfolio discovery for organization)
        portfolio_workflow = {
            "model.Capo": WorkflowNode(
                agent_name="model.Capo",
                branch_yes="model.validateOrgName",
                branch_no="sendMessageToChat",
                description="Initial validation of portfolio request"
            ),
            "model.validateOrgName": WorkflowNode(
                agent_name="model.validateOrgName",
                branch_yes="agent_search_portfolio",
                branch_no="sendMessageToChat",
                description="Validate organization exists in database"
            ),
            "agent_search_portfolio": WorkflowNode(
                agent_name="agent_search_portfolio",
                branch_yes="agent_verify_portfolio_payload",
                branch_no="sendMessageToChat",
                description="Search Exa for FDA-cleared device portfolio"
            ),
            "agent_verify_portfolio_payload": WorkflowNode(
                agent_name="agent_verify_portfolio_payload",
                branch_yes="tool_upsert_portfolio",
                branch_no="sendMessageToChat",
                description="Verify portfolio payload structure and safety"
            ),
            "tool_upsert_portfolio": WorkflowNode(
                agent_name="tool_upsert_portfolio",
                branch_yes="sendMessageToChat",
                branch_no="sendMessageToChat",
                description="Upsert portfolio JSON to org record"
            ),
        }
        self.workflows["PORTFOLIO"] = portfolio_workflow
        
        logger.info(f"✅ Loaded {len(self.workflows)} workflows (RUN, CONTENT, GENERATE, ENRICH, FEELGOOD, PROFILE, COMPETITORS, PORTFOLIO)")
    
    def get_workflow(self, verb: str) -> Dict[str, WorkflowNode]:
        """Get workflow by verb (RUN, CONTENT, GENERATE, ENRICH, etc)."""
        if verb not in self.workflows:
            raise ValueError(f"Unknown workflow: {verb}")
        return self.workflows[verb]
    
    def get_node(self, verb: str, agent_name: str) -> Optional[WorkflowNode]:
        """Get a specific node in a workflow."""
        workflow = self.get_workflow(verb)
        return workflow.get(agent_name)
    
    def get_next_agent(self, verb: str, current_agent: str, decision: str) -> Optional[str]:
        """
        Get the next agent based on current agent and decision.
        
        Args:
            verb: RUN, CONTENT, GENERATE, ENRICH, etc.
            current_agent: Name of current agent
            decision: "yes" or "no"
        
        Returns:
            Name of next agent, or None if terminal
        """
        node = self.get_node(verb, current_agent)
        if not node:
            logger.warning(f"Unknown agent: {current_agent}")
            return None
        
        if decision == "yes":
            next_agent = node.branch_yes
        elif decision == "no":
            next_agent = node.branch_no
        else:
            logger.warning(f"Invalid decision: {decision}")
            return None
        
        logger.info(f"🔄 Workflow branching: {current_agent} ({decision}) → {next_agent}")
        return next_agent
    
    def is_terminal(self, agent_name: str) -> bool:
        """
        Check if an agent name is a terminal (sendMessageToChat, etc).
        Terminal agents don't have further workflow nodes.
        """
        return agent_name in [
            "sendMessageToChat",
            "sendHITL",
            "terminal",
            None,
        ]
    
    def get_hitl_next_agent(self, verb: str, current_agent: str) -> str:
        """
        After a NO decision (HITL), recommend which agent to call when the human replies.
        Defaults to sendMessageToChat unless explicitly mapped.
        """
        if verb == "RUN":
            if current_agent == "model.verifySQL":
                return "tool.executeSQL"
        elif verb == "GENERATE" or verb == "CARD":
            if current_agent == "model.verifyRequest":
                return "model.requestToExtractRiskModel"
            elif current_agent == "model.requestToExtractRiskModel":
                return "model.verifyUpsertRiskModel"
            elif current_agent == "model.verifyUpsertRiskModel":
                return "tool.executeSQL"
        # Default fallback
        return "sendMessageToChat"
