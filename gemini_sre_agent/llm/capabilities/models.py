from typing import Any, Dict, List

from pydantic import BaseModel, Field


class ModelCapability(BaseModel):
    """Describes a specific capability of an LLM model."""

    name: str = Field(
        ...,
        description="Name of the capability (e.g., 'text_generation', 'code_generation').",
    )
    description: str = Field(..., description="A brief description of the capability.")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Parameters supported by this capability."
    )
    performance_score: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Score indicating model's performance for this capability (0-1).",
    )
    cost_efficiency: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Score indicating model's cost efficiency for this capability (0-1).",
    )


class ModelCapabilities(BaseModel):
    """A collection of capabilities for a specific model."""

    model_id: str = Field(..., description="Unique identifier for the model.")
    capabilities: List[ModelCapability] = Field(
        default_factory=list, description="List of capabilities supported by the model."
    )
