"""
Main coordination module for agent models.

This module serves as the main coordination point for all agent-related models,
importing and re-exporting models from specialized modules while maintaining
backward compatibility. It provides a clean, organized interface to all agent
models including request models, response models, state models, and validation utilities.

The module is organized as follows:
- Common enums and base models are defined here
- Specialized models are imported from dedicated modules
- All exports are maintained for backward compatibility
- Module-level utilities and factory functions are provided
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
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
    """Categories for different types of issues."""

    PERFORMANCE = "performance"
    SECURITY = "security"
    RELIABILITY = "reliability"
    USABILITY = "usability"
    COMPATIBILITY = "compatibility"
    DATA_QUALITY = "data_quality"
    INFRASTRUCTURE = "infrastructure"
    CODE_QUALITY = "code_quality"
    DEPLOYMENT = "deployment"
    MONITORING = "monitoring"


class ActionType(str, Enum):
    """Types of actions that can be recommended."""

    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    INVESTIGATION = "investigation"
    MONITORING = "monitoring"


# ============================================================================
# Import Specialized Models
# ============================================================================

# Import from request_models (when created)
# from .request_models import *

# Import from response_models
from .response_models import (
    # Base models
    BaseAgentResponse,
    ValidationError,
    
    # Response models
    TriageResult,
    AnalysisResult,
    RemediationPlan,
    HealthCheckResponse,
    TextResponse,
    CodeResponse,
    
    # Supporting models
    AnalysisFinding,
    RootCauseAnalysis,
    RemediationStep,
    ComponentHealth,
    ResourceUtilization,
    
    # Factory functions
    create_triage_result,
    create_analysis_result,
    create_remediation_plan,
    create_health_check_response,
    
    # Registry and utilities
    AGENT_RESPONSE_MODELS,
    get_response_model,
    validate_response_model,
)

# Import from state_models
from .state_models import (
    # State enums
    AgentState,
    WorkflowState,
    StateTransition as StateTransitionEnum,
    
    # State models
    StateSnapshot,
    StateTransition,
    AgentExecutionContext,
    AgentExecutionMetrics,
    AgentExecutionState,
    WorkflowStep,
    WorkflowContext,
    ConversationHistory,
    PersistentAgentData,
    
    # State utilities
    StateManager,
)

# Import from validation_models
from .validation_models import (
    # Validation error models
    ValidationWarning,
    ValidationResult,
    ValidationSeverity,
    
    # Validation schemas
    MetricValidationSchema,
    LogValidationSchema,
    CodeAnalysisValidationSchema,
    
    # Validation utilities
    ValidationUtils,
    ValidationRegistry,
    
    # Custom validators
    validate_confidence_score,
    validate_confidence_threshold,
    validate_severity_level,
    validate_positive_number,
    validate_non_empty_string,
    validate_uuid_format,
    validate_timestamp,
    validate_enum_value,
    
    # Validation decorators
    validate_with_schema,
    validate_confidence,
    validate_severity,
)


# ============================================================================
# Module-level Utilities
# ============================================================================


def get_all_response_models() -> Dict[str, type]:
    """Get all available response models."""
    return AGENT_RESPONSE_MODELS.copy()


def get_all_state_models() -> Dict[str, type]:
    """Get all available state models."""
    return {
        "AgentExecutionState": AgentExecutionState,
        "WorkflowContext": WorkflowContext,
        "ConversationHistory": ConversationHistory,
        "PersistentAgentData": PersistentAgentData,
    }


def get_all_validation_models() -> Dict[str, type]:
    """Get all available validation models."""
    return {
        "ValidationError": ValidationError,
        "ValidationWarning": ValidationWarning,
        "ValidationResult": ValidationResult,
        "MetricValidationSchema": MetricValidationSchema,
        "LogValidationSchema": LogValidationSchema,
        "CodeAnalysisValidationSchema": CodeAnalysisValidationSchema,
    }


def create_agent_response(
    agent_type: str,
    agent_id: str,
    status: StatusCode = StatusCode.SUCCESS,
    **kwargs
) -> BaseAgentResponse:
    """Create an agent response using the appropriate model."""
    model_class = get_response_model(agent_type)
    return model_class(
        agent_type=agent_type,
        agent_id=agent_id,
        status=status,
        **kwargs
    )


def validate_agent_data(data: Dict[str, Any], data_type: str = "agent_response") -> ValidationResult:
    """Validate agent data using the appropriate validator."""
    if data_type == "agent_response":
        return ValidationUtils.validate_agent_response_data(data)
    elif data_type == "workflow":
        return ValidationUtils.validate_workflow_data(data)
    else:
        raise ValueError(f"Unknown data type: {data_type}")


# ============================================================================
# Module Exports
# ============================================================================

__all__ = [
    # Common enums
    "StatusCode",
    "SeverityLevel", 
    "ConfidenceLevel",
    "IssueCategory",
    "ActionType",
    
    # Base models
    "BaseAgentResponse",
    "ValidationError",
    
    # Response models
    "TriageResult",
    "AnalysisResult", 
    "RemediationPlan",
    "HealthCheckResponse",
    "TextResponse",
    "CodeResponse",
    
    # Supporting response models
    "AnalysisFinding",
    "RootCauseAnalysis",
    "RemediationStep",
    "ComponentHealth",
    "ResourceUtilization",
    
    # State models
    "AgentState",
    "WorkflowState",
    "StateTransitionEnum",
    "StateSnapshot",
    "StateTransition",
    "AgentExecutionContext",
    "AgentExecutionMetrics", 
    "AgentExecutionState",
    "WorkflowStep",
    "WorkflowContext",
    "ConversationHistory",
    "PersistentAgentData",
    
    # Validation models
    "ValidationWarning",
    "ValidationResult",
    "ValidationSeverity",
    "MetricValidationSchema",
    "LogValidationSchema",
    "CodeAnalysisValidationSchema",
    
    # Factory functions
    "create_triage_result",
    "create_analysis_result",
    "create_remediation_plan",
    "create_health_check_response",
    "create_agent_response",
    
    # Registry and utilities
    "AGENT_RESPONSE_MODELS",
    "get_response_model",
    "validate_response_model",
    "get_all_response_models",
    "get_all_state_models", 
    "get_all_validation_models",
    "validate_agent_data",
    
    # State utilities
    "StateManager",
    
    # Validation utilities
    "ValidationUtils",
    "ValidationRegistry",
    "validate_confidence_score",
    "validate_confidence_threshold",
    "validate_severity_level",
    "validate_positive_number",
    "validate_non_empty_string",
    "validate_uuid_format",
    "validate_timestamp",
    "validate_enum_value",
    "validate_with_schema",
    "validate_confidence",
    "validate_severity",
]


# All old model definitions have been moved to specialized modules
# This file now serves as a coordination module that imports and re-exports
# all models while maintaining backward compatibility
