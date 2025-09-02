# gemini_sre_agent/ml/enhanced_code_generation_config.py

"""
Configuration for the enhanced code generation agent.

This module defines the configuration class that controls the behavior
of the enhanced code generation agent, including model selection,
quality thresholds, and learning settings.
"""


class EnhancedCodeGenerationConfig:
    """Configuration for the enhanced code generation agent"""
    
    def __init__(
        self,
        project_id: str,
        location: str,
        main_model: str,
        meta_model: str = "gemini-1.5-flash-001",
        max_iterations: int = 3,
        quality_threshold: float = 8.0,
        enable_learning: bool = True,
        human_review_threshold: float = 7.0
    ):
        """
        Initialize the configuration.
        
        Args:
            project_id: Google Cloud project ID
            location: Google Cloud location/region
            main_model: Primary model for code generation
            meta_model: Model for meta-prompt generation
            max_iterations: Maximum iterations for code refinement
            quality_threshold: Minimum quality score threshold
            enable_learning: Whether to enable learning from results
            human_review_threshold: Quality score below which human review is required
        """
        self.project_id = project_id
        self.location = location
        self.main_model = main_model
        self.meta_model = meta_model
        self.max_iterations = max_iterations
        self.quality_threshold = quality_threshold
        self.enable_learning = enable_learning
        self.human_review_threshold = human_review_threshold
    
    def to_dict(self) -> dict:
        """Convert configuration to dictionary."""
        return {
            "project_id": self.project_id,
            "location": self.location,
            "main_model": self.main_model,
            "meta_model": self.meta_model,
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "enable_learning": self.enable_learning,
            "human_review_threshold": self.human_review_threshold
        }
    
    @classmethod
    def from_dict(cls, config_dict: dict) -> "EnhancedCodeGenerationConfig":
        """Create configuration from dictionary."""
        return cls(**config_dict)
    
    def validate(self) -> bool:
        """Validate configuration values."""
        if not self.project_id:
            return False
        if not self.location:
            return False
        if not self.main_model:
            return False
        if self.max_iterations < 1:
            return False
        if not (0.0 <= self.quality_threshold <= 10.0):
            return False
        if not (0.0 <= self.human_review_threshold <= 10.0):
            return False
        return True
