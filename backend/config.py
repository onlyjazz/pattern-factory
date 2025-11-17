"""
Configuration Management for Clinical Trial Data Review System
Handles model settings, temperature, and other runtime parameters.
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any
import os
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for LLM model settings."""
    
    # Model selection
    model_name: str = "gpt-4o"  # Using gpt-4o as specified
    
    # Temperature settings (lower = more deterministic)
    temperature: float = 0.2  # 0.2-0.3 for SQL generation (deterministic)
    
    # Token limits
    max_tokens: int = 400  # Maximum tokens in response
    context_window: int = 32000  # GPT-4 context window
    
    # Sampling parameters
    top_p: float = 0.1  # Nucleus sampling (lower = more focused)
    frequency_penalty: float = 0.5  # Reduce repetition
    presence_penalty: float = 0.5  # Encourage new topics
    
    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for OpenAI API calls."""
        return {
            "model": self.model_name,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty
        }


@dataclass
class WorkflowConfig:
    """Configuration for workflow execution."""
    
    max_feedback_loops: int = 3  # Maximum iterations for user feedback
    auto_approve_threshold: float = 0.95  # Confidence threshold for auto-approval
    enable_human_review: bool = True  # Whether to ask for human review
    parallel_execution: bool = False  # Whether to run rules in parallel
    

@dataclass
class DatabaseConfig:
    """Configuration for database operations."""
    
    connection_timeout: int = 30
    query_timeout: int = 300  # 5 minutes for complex queries
    enable_materialized_views: bool = True
    cleanup_old_results: bool = False
    results_retention_days: int = 30


@dataclass
class ToolConfig:
    """Configuration for tool execution."""
    
    # Tool-specific settings
    sql_pitboss_enabled: bool = True
    data_table_enabled: bool = True
    insert_alerts_enabled: bool = True
    register_rule_enabled: bool = True
    
    # Execution settings
    enable_logging: bool = True
    enable_metrics: bool = True
    dry_run_mode: bool = False  # For testing without DB changes


class Config:
    """
    Main configuration class that aggregates all settings.
    Follows the pattern: Constants + Variables
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration from file or defaults.
        
        Args:
            config_path: Path to JSON configuration file
        """
        # Initialize with defaults
        self.model = ModelConfig()
        self.workflow = WorkflowConfig()
        self.database = DatabaseConfig()
        self.tools = ToolConfig()
        
        # Load from environment variables
        self._load_from_env()
        
        # Load from config file if provided
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)
        
        # Log configuration
        logger.info(f"Configuration loaded: model={self.model.model_name}, "
                   f"temperature={self.model.temperature}")
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        
        # Model settings
        if model_name := os.getenv("MODEL_NAME"):
            self.model.model_name = model_name
        
        if temp := os.getenv("MODEL_TEMPERATURE"):
            try:
                self.model.temperature = float(temp)
            except ValueError:
                logger.warning(f"Invalid temperature value: {temp}")
        
        # Workflow settings
        if max_loops := os.getenv("MAX_FEEDBACK_LOOPS"):
            try:
                self.workflow.max_feedback_loops = int(max_loops)
            except ValueError:
                logger.warning(f"Invalid max_feedback_loops: {max_loops}")
        
        # Database settings
        if timeout := os.getenv("QUERY_TIMEOUT"):
            try:
                self.database.query_timeout = int(timeout)
            except ValueError:
                logger.warning(f"Invalid query_timeout: {timeout}")
    
    def _load_from_file(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            # Update model config
            if 'model' in data:
                for key, value in data['model'].items():
                    if hasattr(self.model, key):
                        setattr(self.model, key, value)
            
            # Update workflow config
            if 'workflow' in data:
                for key, value in data['workflow'].items():
                    if hasattr(self.workflow, key):
                        setattr(self.workflow, key, value)
            
            # Update database config
            if 'database' in data:
                for key, value in data['database'].items():
                    if hasattr(self.database, key):
                        setattr(self.database, key, value)
            
            # Update tools config
            if 'tools' in data:
                for key, value in data['tools'].items():
                    if hasattr(self.tools, key):
                        setattr(self.tools, key, value)
            
            logger.info(f"Configuration loaded from {config_path}")
            
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
    
    def get_model_params(self, override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get model parameters for API calls.
        
        Args:
            override: Optional parameter overrides
        
        Returns:
            Dictionary of model parameters
        """
        params = self.model.to_dict()
        
        if override:
            params.update(override)
        
        return params
    
    def adjust_temperature_for_task(self, task_type: str) -> float:
        """
        Adjust temperature based on task type.
        
        Args:
            task_type: Type of task (e.g., 'sql_generation', 'question_answering')
        
        Returns:
            Adjusted temperature value
        """
        temperatures = {
            'sql_generation': 0.2,  # Very deterministic for SQL
            'rule_translation': 0.25,  # Slightly more flexible for rules
            'question_answering': 0.4,  # More creative for Q&A
            'workflow_decision': 0.1,  # Very deterministic for workflow
        }
        
        return temperatures.get(task_type, self.model.temperature)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export entire configuration as dictionary."""
        return {
            'model': {
                'model_name': self.model.model_name,
                'temperature': self.model.temperature,
                'max_tokens': self.model.max_tokens,
                'context_window': self.model.context_window,
                'top_p': self.model.top_p,
                'frequency_penalty': self.model.frequency_penalty,
                'presence_penalty': self.model.presence_penalty,
            },
            'workflow': {
                'max_feedback_loops': self.workflow.max_feedback_loops,
                'auto_approve_threshold': self.workflow.auto_approve_threshold,
                'enable_human_review': self.workflow.enable_human_review,
                'parallel_execution': self.workflow.parallel_execution,
            },
            'database': {
                'connection_timeout': self.database.connection_timeout,
                'query_timeout': self.database.query_timeout,
                'enable_materialized_views': self.database.enable_materialized_views,
                'cleanup_old_results': self.database.cleanup_old_results,
                'results_retention_days': self.database.results_retention_days,
            },
            'tools': {
                'sql_pitboss_enabled': self.tools.sql_pitboss_enabled,
                'data_table_enabled': self.tools.data_table_enabled,
                'insert_alerts_enabled': self.tools.insert_alerts_enabled,
                'register_rule_enabled': self.tools.register_rule_enabled,
                'enable_logging': self.tools.enable_logging,
                'enable_metrics': self.tools.enable_metrics,
                'dry_run_mode': self.tools.dry_run_mode,
            }
        }
    
    def save(self, config_path: str):
        """Save current configuration to file."""
        try:
            with open(config_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving config to {config_path}: {e}")


# Global config instance
_config = None


def get_config(config_path: Optional[str] = None) -> Config:
    """
    Get or create global configuration instance.
    
    Args:
        config_path: Optional path to configuration file
    
    Returns:
        Config instance
    """
    global _config
    
    if _config is None:
        _config = Config(config_path)
    
    return _config


def reset_config():
    """Reset global configuration (mainly for testing)."""
    global _config
    _config = None