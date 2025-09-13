# gemini_sre_agent/agents/request_models.py

"""
Request models for agent operations.

This module provides comprehensive request models for all agent types
including triage, analysis, remediation, and health check agents. These models
support validation, serialization, and integration with the multi-provider
LLM system.
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Common Enums and Base Models
# ============================================================================


class StatusCode(str, Enum):
    """Standard status codes for agent responses."""

    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    PENDING = "pending"
    PARTIAL = "partial"


class SeverityLevel(str, Enum):
    """Severity levels for issues and alerts."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ConfidenceLevel(str, Enum):
    """Confidence levels for agent assessments."""

    VERY_HIGH = "very_high"  # 0.9-1.0
    HIGH = "high"  # 0.7-0.9
    MEDIUM = "medium"  # 0.5-0.7
    LOW = "low"  # 0.3-0.5
    VERY_LOW = "very_low"  # 0.0-0.3


class IssueCategory(str, Enum):
    """Categories for issues and problems."""

    INFRASTRUCTURE = "infrastructure"
    APPLICATION = "application"
    DATABASE = "database"
    NETWORK = "network"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AVAILABILITY = "availability"
    DATA = "data"
    INTEGRATION = "integration"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    """Types of actions that can be taken."""

    IMMEDIATE = "immediate"
    SCHEDULED = "scheduled"
    INVESTIGATION = "investigation"
    MONITORING = "monitoring"
    PREVENTION = "prevention"
    DOCUMENTATION = "documentation"


class ValidationError(BaseModel):
    """Validation error details."""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Validation error message")
    value: Any = Field(None, description="Value that failed validation")


class BaseAgentRequest(BaseModel):
    """Base request model for all agent operations."""

    request_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique request identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Request timestamp",
    )
    agent_type: str = Field(..., description="Type of agent handling the request")
    priority: SeverityLevel = Field(
        SeverityLevel.MEDIUM, description="Request priority level"
    )
    timeout_seconds: int | None = Field(
        None, description="Request timeout in seconds"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional request metadata"
    )

    class Config:
        """Pydantic configuration."""

        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class TriageRequest(BaseAgentRequest):
    """Request model for triage operations."""

    issue_description: str = Field(
        ..., description="Description of the issue to triage"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context information"
    )
    urgency_level: SeverityLevel = Field(
        SeverityLevel.MEDIUM, description="Urgency level of the issue"
    )
    affected_systems: list[str] = Field(
        default_factory=list, description="List of affected systems"
    )
    user_impact: str | None = Field(None, description="Description of user impact")
    business_impact: str | None = Field(
        None, description="Description of business impact"
    )
    historical_data: dict[str, Any] | None = Field(
        None, description="Historical data for context"
    )

    @field_validator("issue_description")
    @classmethod
    def validate_issue_description(cls, v: str) -> str:
        """Validate issue description is not empty."""
        if not v.strip():
            raise ValueError("Issue description cannot be empty")
        return v.strip()


class AnalysisRequest(BaseAgentRequest):
    """Request model for analysis operations."""

    content: str = Field(..., description="Content to analyze")
    criteria: list[str] = Field(..., description="Analysis criteria")
    analysis_type: str = Field("general", description="Type of analysis to perform")
    depth: str = Field("detailed", description="Analysis depth level")
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional analysis context"
    )
    historical_data: dict[str, Any] | None = Field(
        None, description="Historical data for comparison"
    )
    quality_threshold: float = Field(
        0.8, ge=0.0, le=1.0, description="Minimum quality threshold"
    )

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, v: list[str]) -> list[str]:
        """Validate criteria list is not empty."""
        if not v:
            raise ValueError("Analysis criteria cannot be empty")
        return v


class RemediationRequest(BaseAgentRequest):
    """Request model for remediation operations."""

    problem_description: str = Field(
        ..., description="Description of the problem to remediate"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Additional context information"
    )
    remediation_type: str = Field(
        "general", description="Type of remediation to perform"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Constraints to consider"
    )
    target_systems: list[str] = Field(
        default_factory=list, description="Target systems for remediation"
    )
    urgency: SeverityLevel = Field(
        SeverityLevel.MEDIUM, description="Urgency of the remediation"
    )
    expected_outcome: str | None = Field(
        None, description="Expected outcome of remediation"
    )

    @field_validator("problem_description")
    @classmethod
    def validate_problem_description(cls, v: str) -> str:
        """Validate problem description is not empty."""
        if not v.strip():
            raise ValueError("Problem description cannot be empty")
        return v.strip()


class CodeGenerationRequest(BaseAgentRequest):
    """Request model for code generation operations."""

    description: str = Field(..., description="Description of code to generate")
    language: str = Field(..., description="Programming language")
    framework: str | None = Field(None, description="Framework to use")
    style_guide: str | None = Field(None, description="Coding style guide to follow")
    requirements: list[str] = Field(
        default_factory=list, description="Functional requirements"
    )
    constraints: list[str] = Field(
        default_factory=list, description="Technical constraints"
    )
    quality_level: str = Field("high", description="Code quality level required")

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        """Validate programming language is supported."""
        supported_languages = [
            "python",
            "javascript",
            "typescript",
            "java",
            "go",
            "rust",
            "c++",
            "c#",
            "php",
            "ruby",
            "swift",
            "kotlin",
        ]
        if v.lower() not in supported_languages:
            raise ValueError(f"Unsupported programming language: {v}")
        return v.lower()


class TextGenerationRequest(BaseAgentRequest):
    """Request model for text generation operations."""

    prompt: str = Field(..., description="Text generation prompt")
    context: dict[str, Any] | None = Field(
        None, description="Additional context for generation"
    )
    max_length: int = Field(
        2000, ge=1, le=10000, description="Maximum length of generated text"
    )
    temperature: float = Field(
        0.7, ge=0.0, le=2.0, description="Generation temperature"
    )
    creativity_level: str = Field(
        "balanced", description="Creativity level for generation"
    )
    style: str | None = Field(None, description="Writing style to follow")
    audience: str | None = Field(None, description="Target audience")

    @field_validator("prompt")
    @classmethod
    def validate_prompt(cls, v: str) -> str:
        """Validate prompt is not empty."""
        if not v.strip():
            raise ValueError("Prompt cannot be empty")
        return v.strip()


class HealthCheckRequest(BaseAgentRequest):
    """Request model for health check operations."""

    component_name: str | None = Field(
        None, description="Specific component to check"
    )
    check_type: str = Field(
        "comprehensive", description="Type of health check to perform"
    )
    include_metrics: bool = Field(True, description="Include performance metrics")
    include_dependencies: bool = Field(True, description="Include dependency health")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Health check timeout")

    @field_validator("check_type")
    @classmethod
    def validate_check_type(cls, v: str) -> str:
        """Validate check type is supported."""
        supported_types = ["quick", "comprehensive", "diagnostic", "performance"]
        if v not in supported_types:
            raise ValueError(f"Unsupported check type: {v}")
        return v


class BatchRequest(BaseAgentRequest):
    """Request model for batch operations."""

    requests: list[BaseAgentRequest] = Field(
        ..., description="List of requests to process"
    )
    max_concurrent: int = Field(
        5, ge=1, le=20, description="Maximum concurrent requests"
    )
    fail_fast: bool = Field(False, description="Stop on first failure")
    retry_failed: bool = Field(True, description="Retry failed requests")

    @field_validator("requests")
    @classmethod
    def validate_requests(cls, v: list[BaseAgentRequest]) -> list[BaseAgentRequest]:
        """Validate requests list is not empty."""
        if not v:
            raise ValueError("Requests list cannot be empty")
        return v


class ValidationRequest(BaseAgentRequest):
    """Request model for validation operations."""

    content: str = Field(..., description="Content to validate")
    validation_type: str = Field(..., description="Type of validation to perform")
    rules: list[str] = Field(
        default_factory=list, description="Validation rules to apply"
    )
    context: dict[str, Any] = Field(
        default_factory=dict, description="Validation context"
    )
    strict_mode: bool = Field(False, description="Enable strict validation mode")

    @field_validator("validation_type")
    @classmethod
    def validate_validation_type(cls, v: str) -> str:
        """Validate validation type is supported."""
        supported_types = [
            "syntax",
            "semantic",
            "style",
            "security",
            "performance",
            "compliance",
        ]
        if v not in supported_types:
            raise ValueError(f"Unsupported validation type: {v}")
        return v
