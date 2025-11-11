"""
Advanced Configuration for Choosing Pitboss Supervisor Strategy

This configuration allows switching between:
1. Traditional Python-supervised approach (GPT-4o for SQL only)
2. LLM-supervised approach (GPT-5-mini with function calling)
3. Hybrid approach (choose based on rule complexity)
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import os
import json
import logging

logger = logging.getLogger(__name__)


class SupervisorStrategy(Enum):
    """Available supervisor strategies."""
    TRADITIONAL = "traditional"  # Python orchestrates, GPT-4o for SQL
    LLM_SUPERVISED = "llm_supervised"  # GPT-5-mini orchestrates via function calling
    HYBRID = "hybrid"  # Choose based on context
    AUTO = "auto"  # Let system decide


@dataclass
class SupervisorConfig:
    """Configuration for supervisor selection and behavior."""
    
    # Strategy selection
    strategy: SupervisorStrategy = SupervisorStrategy.AUTO
    
    # Model configurations for each strategy
    traditional_model: str = "gpt-4o"
    llm_supervisor_model: str = "gpt-4o-mini"
    
    # Temperature settings
    traditional_temperature: float = 0.2  # Lower for deterministic SQL
    llm_supervisor_temperature: float = 0.25  # Slightly higher for orchestration
    
    # Complexity thresholds for hybrid mode
    simple_rule_max_tokens: int = 50  # Rules under this use traditional
    complex_rule_indicators: list = None  # Keywords that trigger LLM supervision
    
    # Performance settings
    prefer_speed: bool = False  # True = prefer traditional for speed
    prefer_flexibility: bool = False  # True = prefer LLM-supervised
    
    # Cost optimization
    max_tokens_per_request: int = 600
    enable_caching: bool = True
    
    def __post_init__(self):
        """Initialize default complex rule indicators."""
        if self.complex_rule_indicators is None:
            self.complex_rule_indicators = [
                "multiple",
                "complex",
                "join",
                "aggregate",
                "subquery",
                "case when",
                "union",
                "having"
            ]


@dataclass
class AdvancedModelConfig:
    """Extended model configuration with GPT-5-mini support."""
    
    # Model selection based on task
    sql_generation_model: str = "gpt-4o"  # For SQL generation only
    orchestration_model: str = "gpt-4o-mini"  # For orchestration
    question_answering_model: str = "gpt-4o"  # For Q&A
    
    # GPT-5-mini specific settings (if available in your account)
    gpt5_verbosity: str = "low"  # low, medium, high
    gpt5_reasoning_effort: str = "minimal"  # minimal, standard, thorough
    
    # Temperature by model and task
    temperatures: Dict[str, float] = None
    
    # Token limits by model
    token_limits: Dict[str, int] = None
    
    # Sampling parameters
    top_p: float = 0.1
    frequency_penalty: float = 0.5
    presence_penalty: float = 0.5
    
    def __post_init__(self):
        """Initialize default configurations."""
        if self.temperatures is None:
            self.temperatures = {
                "gpt-4o_sql": 0.2,
                "gpt-4o_qa": 0.4,
                "gpt-4o-mini_orchestration": 0.2,  # Updated to 0.2
                "gpt-4o-mini_sql": 0.2  # Updated to 0.2
            }
        
        if self.token_limits is None:
            self.token_limits = {
                "gpt-4o": 4000,
                "gpt-4o-mini": 600
            }


class AdvancedConfig:
    """
    Advanced configuration that supports both traditional and LLM-supervised approaches.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize advanced configuration."""
        
        # Supervisor strategy configuration
        self.supervisor = SupervisorConfig()
        
        # Model configurations
        self.models = AdvancedModelConfig()
        
        # Load from environment
        self._load_from_env()
        
        # Load from file if provided
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)
        
        # Determine actual strategy
        self.active_strategy = self._determine_strategy()
        
        logger.info(
            f"Advanced config initialized: "
            f"strategy={self.active_strategy}, "
            f"models={self._get_active_models()}"
        )
    
    def _load_from_env(self):
        """Load configuration from environment variables."""
        
        # Supervisor strategy
        if strategy := os.getenv("PITBOSS_STRATEGY"):
            try:
                self.supervisor.strategy = SupervisorStrategy(strategy.lower())
            except ValueError:
                logger.warning(f"Invalid strategy: {strategy}")
        
        # Check for gpt-4o-mini availability
        if os.getenv("GPT5_MINI_AVAILABLE") == "true":  # Keep env var name for compatibility
            self.models.orchestration_model = "gpt-4o-mini"
        
        # Performance preferences
        if os.getenv("PREFER_SPEED") == "true":
            self.supervisor.prefer_speed = True
        
        if os.getenv("PREFER_FLEXIBILITY") == "true":
            self.supervisor.prefer_flexibility = True
    
    def _load_from_file(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
            
            # Load supervisor config
            if 'supervisor' in data:
                for key, value in data['supervisor'].items():
                    if hasattr(self.supervisor, key):
                        if key == 'strategy':
                            self.supervisor.strategy = SupervisorStrategy(value)
                        else:
                            setattr(self.supervisor, key, value)
            
            # Load model config
            if 'models' in data:
                for key, value in data['models'].items():
                    if hasattr(self.models, key):
                        setattr(self.models, key, value)
            
            logger.info(f"Advanced configuration loaded from {config_path}")
            
        except Exception as e:
            logger.error(f"Error loading config from {config_path}: {e}")
    
    def _determine_strategy(self) -> SupervisorStrategy:
        """
        Determine which strategy to use based on configuration and availability.
        """
        strategy = self.supervisor.strategy
        
        if strategy == SupervisorStrategy.AUTO:
            # Auto-detect based on model availability and preferences
            if self._is_gpt5_mini_available():
                if self.supervisor.prefer_flexibility:
                    return SupervisorStrategy.LLM_SUPERVISED
                elif self.supervisor.prefer_speed:
                    return SupervisorStrategy.TRADITIONAL
                else:
                    return SupervisorStrategy.HYBRID
            else:
                return SupervisorStrategy.TRADITIONAL
        
        # Validate chosen strategy
        if strategy == SupervisorStrategy.LLM_SUPERVISED:
            if not self._is_gpt5_mini_available():
                logger.warning("GPT-5-mini not available, falling back to traditional")
                return SupervisorStrategy.TRADITIONAL
        
        return strategy
    
    def _is_gpt5_mini_available(self) -> bool:
        """Check if GPT-5-mini is available."""
        # Check environment variable or try a test call
        return os.getenv("GPT5_MINI_AVAILABLE") == "true"
    
    def _get_active_models(self) -> Dict[str, str]:
        """Get the models that will be used based on strategy."""
        if self.active_strategy == SupervisorStrategy.TRADITIONAL:
            return {
                "sql_generation": self.models.sql_generation_model,
                "orchestration": "Python"
            }
        elif self.active_strategy == SupervisorStrategy.LLM_SUPERVISED:
            return {
                "sql_generation": self.models.orchestration_model,
                "orchestration": self.models.orchestration_model
            }
        else:  # HYBRID
            return {
                "simple_rules": self.models.sql_generation_model,
                "complex_rules": self.models.orchestration_model
            }
    
    def should_use_llm_supervisor(self, rule_text: str) -> bool:
        """
        Determine if a specific rule should use LLM supervision.
        
        Args:
            rule_text: The rule logic text
            
        Returns:
            True if LLM supervisor should be used
        """
        if self.active_strategy == SupervisorStrategy.TRADITIONAL:
            return False
        elif self.active_strategy == SupervisorStrategy.LLM_SUPERVISED:
            return True
        elif self.active_strategy == SupervisorStrategy.HYBRID:
            # Check complexity indicators
            rule_lower = rule_text.lower()
            
            # Check token count
            if len(rule_text.split()) > self.supervisor.simple_rule_max_tokens:
                return True
            
            # Check for complex patterns
            for indicator in self.supervisor.complex_rule_indicators:
                if indicator in rule_lower:
                    return True
            
            return False
        
        return False
    
    def get_model_params(self, task: str = "sql_generation") -> Dict[str, Any]:
        """
        Get model parameters for a specific task.
        
        Args:
            task: The task type (sql_generation, orchestration, qa)
            
        Returns:
            Dictionary of model parameters
        """
        if self.active_strategy == SupervisorStrategy.LLM_SUPERVISED:
            model = self.models.orchestration_model
            temp_key = f"{model}_orchestration"
        else:
            if task == "sql_generation":
                model = self.models.sql_generation_model
                temp_key = f"{model}_sql"
            elif task == "qa":
                model = self.models.question_answering_model
                temp_key = f"{model}_qa"
            else:
                model = self.models.sql_generation_model
                temp_key = f"{model}_sql"
        
        params = {
            "model": model,
            "temperature": self.models.temperatures.get(temp_key, 0.2),  # Default to 0.2
            "max_tokens": self.models.token_limits.get(model, 600),  # gpt-4o-mini uses max_tokens
            "top_p": self.models.top_p,
            "frequency_penalty": self.models.frequency_penalty,
            "presence_penalty": self.models.presence_penalty
        }
        
        # Add GPT-5-mini specific parameters if applicable
        if model == "gpt-5-mini":
            params["verbosity"] = self.models.gpt5_verbosity
            params["reasoning"] = {"effort": self.models.gpt5_reasoning_effort}
        
        return params
    
    def create_pitboss(self, db_connection, websocket=None):
        """
        Factory method to create the appropriate Pitboss instance.
        
        Returns:
            Pitboss instance configured for the selected strategy
        """
        if self.active_strategy == SupervisorStrategy.LLM_SUPERVISED:
            from services.pitboss_llm_supervisor import Pitboss  # Using backwards-compatible class name
            logger.info("Creating LLM-supervised Pitboss with gpt-4o-mini")
            return Pitboss(db_connection, websocket)
        else:
            from services.pitboss_supervisor import Pitboss  # Using backwards-compatible class name
            logger.info("Creating traditional Pitboss with Python orchestration")
            return Pitboss(db_connection, websocket)
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "supervisor": {
                "strategy": self.supervisor.strategy.value,
                "traditional_model": self.supervisor.traditional_model,
                "llm_supervisor_model": self.supervisor.llm_supervisor_model,
                "prefer_speed": self.supervisor.prefer_speed,
                "prefer_flexibility": self.supervisor.prefer_flexibility
            },
            "models": {
                "sql_generation_model": self.models.sql_generation_model,
                "orchestration_model": self.models.orchestration_model,
                "temperatures": self.models.temperatures,
                "token_limits": self.models.token_limits
            },
            "active": {
                "strategy": self.active_strategy.value,
                "models": self._get_active_models()
            }
        }
    
    def save(self, config_path: str):
        """Save configuration to file."""
        try:
            with open(config_path, 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
            logger.info(f"Advanced configuration saved to {config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")


# Example configuration file
EXAMPLE_CONFIG = {
    "supervisor": {
        "strategy": "auto",
        "traditional_model": "gpt-4o",
        "llm_supervisor_model": "gpt-5-mini",
        "prefer_speed": False,
        "prefer_flexibility": True,
        "simple_rule_max_tokens": 50,
        "complex_rule_indicators": [
            "multiple", "complex", "join", "aggregate"
        ]
    },
    "models": {
        "sql_generation_model": "gpt-4o",
        "orchestration_model": "gpt-5-mini",
        "question_answering_model": "gpt-4o",
        "gpt5_verbosity": "low",
        "gpt5_reasoning_effort": "minimal",
        "temperatures": {
            "gpt-4o_sql": 0.2,
            "gpt-4o_qa": 0.4,
            "gpt-5-mini_orchestration": 0.25,
            "gpt-5-mini_sql": 0.3
        },
        "token_limits": {
            "gpt-4o": 4000,
            "gpt-5-mini": 600
        }
    }
}


if __name__ == "__main__":
    # Demo the advanced configuration
    print("Advanced Pitboss Configuration Demo")
    print("="*40)
    
    # Create config
    config = AdvancedConfig()
    
    # Show active strategy
    print(f"\nActive Strategy: {config.active_strategy.value}")
    print(f"Active Models: {config._get_active_models()}")
    
    # Test rule complexity detection
    simple_rule = "Flag subjects with ALT > 120"
    complex_rule = "Flag subjects with multiple lab abnormalities using aggregate functions"
    
    print(f"\nRule: '{simple_rule}'")
    print(f"Use LLM Supervisor: {config.should_use_llm_supervisor(simple_rule)}")
    
    print(f"\nRule: '{complex_rule}'")
    print(f"Use LLM Supervisor: {config.should_use_llm_supervisor(complex_rule)}")
    
    # Show model parameters
    print("\nModel Parameters for SQL Generation:")
    print(json.dumps(config.get_model_params("sql_generation"), indent=2))
    
    # Save example config
    print("\nSaving example configuration...")
    with open("pitboss_config_example.json", "w") as f:
        json.dump(EXAMPLE_CONFIG, f, indent=2)
    print("Saved to pitboss_config_example.json")