"""
Data schemas for Gemini AI pattern detection with structured output support.

This module provides Pydantic models for structured responses from Gemini API,
enabling precise JSON schema generation and validation.
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PromptType(str, Enum):
    """Types of prompts supported by the engine."""

    CLASSIFICATION = "classification"
    CONFIDENCE = "confidence"


class PatternType(str, Enum):
    """Incident pattern types for classification."""

    CASCADING_FAILURE = "cascading_failure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    DEPLOYMENT_ISSUE = "deployment_issue"
    DEPENDENCY_FAILURE = "dependency_failure"
    CONFIGURATION_ERROR = "configuration_error"
    PERFORMANCE_DEGRADATION = "performance_degradation"
    DATA_CORRUPTION = "data_corruption"
    SECURITY_INCIDENT = "security_incident"
    NETWORK_PARTITION = "network_partition"
    HARDWARE_FAILURE = "hardware_failure"


class ConfidenceLevel(str, Enum):
    """Confidence levels for pattern classification."""

    VERY_HIGH = "very_high"  # 90-100%
    HIGH = "high"  # 70-90%
    MEDIUM = "medium"  # 50-70%
    LOW = "low"  # 30-50%
    VERY_LOW = "very_low"  # 0-30%


class SeverityLevel(str, Enum):
    """Incident severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class Evidence(BaseModel):
    """Evidence supporting pattern classification."""

    type: str = Field(description="Type of evidence")
    description: str = Field(description="Detailed description of the evidence")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence in this evidence (0.0-1.0)"
    )
    weight: float = Field(ge=0.0, le=1.0, description="Weight of this evidence (0.0-1.0)")
    source: str = Field(description="Source of evidence (logs, metrics, etc.)")


class RootCause(BaseModel):
    """Root cause analysis result."""

    primary_cause: str = Field(description="Primary root cause identified")
    contributing_factors: List[str] = Field(
        default_factory=list, description="Contributing factors to the incident"
    )
    affected_components: List[str] = Field(
        default_factory=list, description="System components affected"
    )
    blast_radius: str = Field(description="Estimated blast radius description")


class Recommendation(BaseModel):
    """Actionable recommendation."""

    action: str = Field(description="Recommended action to take")
    priority: str = Field(description="Priority level (immediate, high, medium, low)")
    rationale: str = Field(description="Reasoning behind the recommendation")
    estimated_effort: str = Field(description="Estimated effort to implement")


class PatternClassificationResponse(BaseModel):
    """Structured response for pattern classification with Gemini schema support."""

    pattern_type: PatternType = Field(description="Classified incident pattern type")
    confidence: float = Field(
        ge=0.0, le=1.0, description="Overall confidence in classification (0.0-1.0)"
    )
    severity: SeverityLevel = Field(description="Estimated incident severity")
    evidence: List[Evidence] = Field(
        description="Evidence supporting the classification", min_length=1
    )
    root_cause: RootCause = Field(description="Root cause analysis")
    recommendations: List[Recommendation] = Field(
        description="Actionable recommendations", min_length=1
    )
    reasoning: str = Field(description="Detailed reasoning for the classification")
    similar_incidents: List[str] = Field(
        default_factory=list, description="References to similar historical incidents"
    )
    time_to_resolution: Optional[str] = Field(
        default=None, description="Estimated time to resolution"
    )

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Get JSON schema for Gemini structured output."""
        return cls.model_json_schema()


class ConfidenceFactors(BaseModel):
    """Factors affecting confidence assessment."""

    data_completeness: float = Field(
        ge=0.0, le=1.0, description="Completeness of available data"
    )
    pattern_clarity: float = Field(
        ge=0.0, le=1.0, description="Clarity of observed patterns"
    )
    evidence_consistency: float = Field(
        ge=0.0, le=1.0, description="Consistency across evidence sources"
    )
    historical_precedent: float = Field(
        ge=0.0, le=1.0, description="Similarity to known incidents"
    )
    expert_validation: float = Field(
        ge=0.0, le=1.0, description="Level of expert validation available"
    )


class ConfidenceAssessmentResponse(BaseModel):
    """Structured response for confidence assessment with Gemini schema support."""

    overall_confidence: ConfidenceLevel = Field(description="Overall confidence level")
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Numerical confidence score (0.0-1.0)"
    )
    confidence_factors: ConfidenceFactors = Field(
        description="Breakdown of factors affecting confidence"
    )
    reliability_indicators: List[str] = Field(
        description="Indicators supporting reliability of classification"
    )
    uncertainty_sources: List[str] = Field(
        description="Sources of uncertainty in the assessment"
    )
    data_quality_assessment: str = Field(description="Assessment of input data quality")
    recommendation: str = Field(
        description="Recommendation on whether to trust this classification"
    )

    @classmethod
    def get_json_schema(cls) -> Dict[str, Any]:
        """Get JSON schema for Gemini structured output."""
        return cls.model_json_schema()


# Legacy models for backward compatibility
class PatternClassificationResult(BaseModel):
    """Legacy structured output for pattern classification."""

    pattern_type: str
    confidence_score: float
    reasoning: str
    key_indicators: List[str]
    recommended_actions: List[str]
    severity_level: str  # LOW, MEDIUM, HIGH, CRITICAL


class ConfidenceAssessmentResult(BaseModel):
    """Legacy structured output for confidence assessment."""

    overall_confidence: float
    confidence_level: str  # VERY_LOW, LOW, MEDIUM, HIGH, VERY_HIGH
    contributing_factors: Dict[str, float]
    key_evidence: List[str]
    uncertainty_sources: List[str]


class CodeAnalysisResult(BaseModel):
    """Structured output for code analysis findings."""

    has_relevant_changes: bool
    recent_commits: List[str]
    affected_files: List[str]
    complexity_issues: List[str]
    static_analysis_findings: List[str]
    dependency_vulnerabilities: List[str]
    change_risk_assessment: str  # LOW, MEDIUM, HIGH


@dataclass
class PatternContext:
    """Context information for pattern detection."""

    primary_service: Optional[str] = None
    affected_services: Optional[List[str]] = None
    time_window_start: Optional[datetime] = None
    time_window_end: Optional[datetime] = None
    error_patterns: Optional[Dict[str, Any]] = None
    timing_analysis: Optional[Dict[str, Any]] = None
    service_topology: Optional[Dict[str, Any]] = None
    code_changes_context: Optional[str] = None
    static_analysis_findings: Optional[Dict[str, Any]] = None
    code_quality_metrics: Optional[Dict[str, float]] = None
    dependency_vulnerabilities: Optional[List[str]] = None
    error_related_files: Optional[List[str]] = None
    recent_commits: Optional[List[str]] = None


@dataclass
class PromptTemplate:
    """Template for prompt generation."""

    prompt_type: PromptType
    system_prompt: str
    user_prompt_template: str
    expected_schema: Dict[str, Any]
    version: str = "1.0"
    created_at: datetime = datetime.now()
