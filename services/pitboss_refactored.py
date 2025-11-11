"""
Refactored Pitboss System for Clinical Trial Data Review

This is the new modular implementation that separates concerns:
- Context building (PROTOCOL + DATA + RULES ordering)
- Tool execution (sql_pitboss, data_table, insert_alerts, register_rule)
- Configuration management
- Supervisor orchestration

The original pitboss.py is preserved for reference.
"""

import logging
from typing import Optional

# Import new modular components
from services.config import get_config, Config
from services.context_builder import ContextBuilder
from services.tools import (
    ToolRegistry,
    SqlPitbossTool,
    DataTableTool,
    InsertAlertsTool,
    RegisterRuleTool
)
from services.pitboss_supervisor import PitbossSupervisor, Pitboss

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_pitboss(db_connection, websocket=None, config_path: Optional[str] = None):
    """
    Factory function to create a configured Pitboss instance.
    
    Args:
        db_connection: Database connection
        websocket: Optional WebSocket for real-time communication
        config_path: Optional path to configuration file
    
    Returns:
        Configured Pitboss instance
    """
    # Load or create configuration
    config = get_config(config_path)
    
    # Create the supervisor (using the backwards-compatible Pitboss class)
    pitboss = Pitboss(db_connection, websocket)
    
    logger.info(
        f"Pitboss created with configuration: "
        f"model={config.model.model_name}, "
        f"temperature={config.model.temperature}"
    )
    
    return pitboss


# Export main classes for external use
__all__ = [
    'PitbossSupervisor',
    'Pitboss',
    'ContextBuilder',
    'ToolRegistry',
    'Config',
    'create_pitboss',
    'get_config'
]


# Demonstration of the new architecture
def demonstrate_architecture():
    """
    Shows how the refactored system works with proper context injection.
    
    The key insight: DSL acts as a fine-tuning prompt without actual fine-tuning
    by leveraging token-level influence through careful prompt ordering.
    """
    
    example_flow = """
    USER INPUT → PITBOSS SUPERVISOR
                    ↓
            [Decides Action Type]
            - Run single rule?
            - Run all rules?
            - Answer question?
                    ↓
            [Builds Context]
            1. PROTOCOL (low weight) - Sets the scene
            2. DATA (medium weight) - Technical details  
            3. RULES (high weight) - Listed LAST for maximum influence
                    ↓
            [Executes Tools]
            - sql_pitboss: Generate SQL from rule
            - data_table: Create materialized table
            - insert_alerts: Record execution
            - register_rule: Track in registry
                    ↓
            [Returns Results]
            Format: RULE_ID message - X records flagged Severity: level
    """
    
    print(example_flow)
    
    # Show temperature adjustments for different tasks
    config = get_config()
    tasks = ['sql_generation', 'rule_translation', 'question_answering', 'workflow_decision']
    
    print("\nTemperature Settings by Task Type:")
    for task in tasks:
        temp = config.adjust_temperature_for_task(task)
        print(f"  {task}: {temp}")
    
    print("\nTool Registry:")
    print("  - sql_pitboss: Generates SQL from natural language")
    print("  - data_table: Creates materialized result tables")
    print("  - insert_alerts: Records rule executions")
    print("  - register_rule: Maintains rule registry")
    
    print("\nContext Priority (Recent = More Influence):")
    print("  1. PROTOCOL ← Lower weight (appears first)")
    print("  2. DATA ← Medium weight")
    print("  3. RULES ← HIGHEST weight (appears last)")
    print("\nThis ordering leverages LLM attention mechanisms")
    print("where recent tokens have more influence on generation.")


if __name__ == "__main__":
    # Run demonstration
    demonstrate_architecture()