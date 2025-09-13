# gemini_sre_agent/ml/prompt_context_models.py

"""
Context data models for enhanced prompt generation system.

This module defines the data structures used for context-aware prompt generation,
including issue context, repository context, and task context models.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class IssueType(Enum):
    """Enumeration of different issue types for specialized prompt generation."""

    DATABASE_ERROR = "database_error"
    API_ERROR = "api_error"
    SERVICE_ERROR = "service_error"
    CONFIGURATION_ERROR = "configuration_error"
    PERFORMANCE_ERROR = "performance_error"
    SECURITY_ERROR = "security_error"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    UNKNOWN = "unknown"


class TaskComplexity(Enum):
    """Enumeration of task complexity levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class BusinessImpact(Enum):
    """Enumeration of business impact levels."""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class RepositoryContext:
    """Comprehensive repository context for prompt generation."""

    architecture_type: str  # microservices, monolith, serverless
    technology_stack: dict[str, str]  # {"language": "python", "framework": "fastapi"}
    coding_standards: dict[str, Any]  # linting rules, style guides
    error_handling_patterns: list[str]  # common error handling approaches
    testing_patterns: list[str]  # testing conventions
    dependency_structure: dict[str, list[str]]  # service dependencies
    recent_changes: list[dict[str, Any]]  # recent commits and changes
    historical_fixes: list[dict[str, Any]]  # similar past fixes
    code_quality_metrics: dict[str, float]  # complexity, coverage, etc.

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "architecture_type": self.architecture_type,
            "technology_stack": self.technology_stack,
            "coding_standards": self.coding_standards,
            "error_handling_patterns": self.error_handling_patterns,
            "testing_patterns": self.testing_patterns,
            "dependency_structure": self.dependency_structure,
            "recent_changes": self.recent_changes,
            "historical_fixes": self.historical_fixes,
            "code_quality_metrics": self.code_quality_metrics,
        }


@dataclass
class IssueContext:
    """Detailed context for specific issues."""

    issue_type: IssueType
    affected_files: list[str]
    error_patterns: list[str]
    severity_level: int
    impact_analysis: dict[str, Any]
    related_services: list[str]
    temporal_context: dict[str, Any]
    user_impact: str
    business_impact: str
    complexity_score: int = 1
    context_richness: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issue_type": self.issue_type.value,
            "affected_files": self.affected_files,
            "error_patterns": self.error_patterns,
            "severity_level": self.severity_level,
            "impact_analysis": self.impact_analysis,
            "related_services": self.related_services,
            "temporal_context": self.temporal_context,
            "user_impact": self.user_impact,
            "business_impact": self.business_impact,
            "complexity_score": self.complexity_score,
            "context_richness": self.context_richness,
        }


@dataclass
class TaskContext:
    """Context for determining prompt generation strategy."""

    task_type: str
    complexity_score: int  # 1-10
    context_variability: float  # 0-1
    business_impact: int  # 1-10
    accuracy_requirement: float  # 0-1
    latency_requirement: int  # ms
    context_richness: float  # 0-1
    frequency: str  # "low", "medium", "high"
    cost_sensitivity: float  # 0-1

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "task_type": self.task_type,
            "complexity_score": self.complexity_score,
            "context_variability": self.context_variability,
            "business_impact": self.business_impact,
            "accuracy_requirement": self.accuracy_requirement,
            "latency_requirement": self.latency_requirement,
            "context_richness": self.context_richness,
            "frequency": self.frequency,
            "cost_sensitivity": self.cost_sensitivity,
        }


@dataclass
class PromptContext:
    """Complete context for prompt generation."""

    issue_context: IssueContext
    repository_context: RepositoryContext
    generator_type: str
    validation_feedback: dict[str, Any] | None = None
    iteration_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issue_context": self.issue_context.to_dict(),
            "repository_context": self.repository_context.to_dict(),
            "generator_type": self.generator_type,
            "validation_feedback": self.validation_feedback,
            "iteration_count": self.iteration_count,
        }


@dataclass
class MetaPromptContext:
    """Context for meta-prompt generation."""

    issue_context: dict[str, Any]
    repository_context: dict[str, Any]
    triage_packet: dict[str, Any]
    historical_logs: list[str]
    configs: dict[str, str]
    flow_id: str
    previous_attempts: list[dict[str, Any]] | None = None
    validation_feedback: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issue_context": self.issue_context,
            "repository_context": self.repository_context,
            "triage_packet": self.triage_packet,
            "historical_logs": self.historical_logs,
            "configs": self.configs,
            "flow_id": self.flow_id,
            "previous_attempts": self.previous_attempts,
            "validation_feedback": self.validation_feedback,
        }


@dataclass
class ValidationResult:
    """Result of prompt validation."""

    success: bool
    issues: list[str]
    suggestions: list[str]
    confidence_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "success": self.success,
            "issues": self.issues,
            "suggestions": self.suggestions,
            "confidence_score": self.confidence_score,
        }
