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
    Executes YAML-based decision trees for Pattern Factory agents.
    
    Responsibilities:
    - Load workflow definitions from YAML
    - Track current position in decision tree
    - Branch on agent decisions (yes/no)
    - Route to terminal nodes (sendMessageToChat, etc)
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
        # RULE Flow
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
        
        logger.info(f"✅ Loaded {len(self.workflows)} workflows (RULE, CONTENT)")
    
    def get_workflow(self, verb: str) -> Dict[str, WorkflowNode]:
        """Get workflow by verb (RULE or CONTENT)."""
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
            verb: RULE or CONTENT
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
