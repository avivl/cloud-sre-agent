
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from gemini_sre_agent.llm.common.enums import ModelType


class CapabilityRequirements(BaseModel):
    """
    Defines the capabilities and criteria required for a specific task.
    """

    task_name: str = Field(..., description="Name of the task.")
    required_capabilities: List[str] = Field(
        default_factory=list, description="List of capability names required by the task."
    )
    preferred_model_type: Optional[ModelType] = Field(
        None, description="Preferred semantic model type for this task."
    )
    min_performance_score: float = Field(
        0.0, ge=0.0, le=1.0, description="Minimum acceptable performance score for required capabilities."
    )
    max_cost_per_1k_tokens: Optional[float] = Field(
        None, ge=0.0, description="Maximum acceptable cost per 1k tokens for the task."
    )
    latency_tolerance_ms: Optional[int] = Field(
        None, ge=0, description="Maximum acceptable latency in milliseconds."
    )
    # Add other criteria as needed, e.g., security, data privacy, specific provider features
    custom_criteria: Dict[str, Any] = Field(
        default_factory=dict, description="Custom criteria for advanced selection."
    )

    def validate_requirements(self) -> bool:
        """
        Validate that the requirements are logically consistent.
        
        Returns:
            True if requirements are valid, False otherwise.
        """
        if not self.required_capabilities:
            return True  # Empty requirements are valid
            
        # Check for duplicate capabilities
        if len(self.required_capabilities) != len(set(self.required_capabilities)):
            return False
            
        # Validate custom criteria if needed
        # Add more validation logic as requirements evolve
        
        return True
