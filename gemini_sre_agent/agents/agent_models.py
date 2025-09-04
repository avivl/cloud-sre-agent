"""
Comprehensive Pydantic response models for all agent types.

This module provides enhanced, structured response models for all agent types
including triage, analysis, remediation, and health check agents. These models
support validation, serialization, and integration with the multi-provider
LLM system.
"""

from datetime import datetime
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


class ValidationError(BaseModel):
    """Standardized error reporting for validation failures."""

    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")
    value: Optional[Any] = Field(None, description="Value that caused the error")
    code: Optional[str] = Field(
        None, description="Error code for programmatic handling"
    )


class BaseAgentResponse(BaseModel):
    """Base response model for all agents with common fields."""

    request_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique request identifier"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Response timestamp"
    )
    agent_id: str = Field(
        ..., description="Identifier of the agent that generated this response"
    )
    agent_type: str = Field(
        ..., description="Type of agent (triage, analysis, remediation, health_check)"
    )
    status: StatusCode = Field(..., description="Overall status of the response")
    execution_time_ms: Optional[float] = Field(
        None, description="Time taken to generate response in milliseconds"
    )
    model_used: Optional[str] = Field(
        None, description="LLM model used for this response"
    )
    provider_used: Optional[str] = Field(
        None, description="LLM provider used for this response"
    )
    cost_usd: Optional[float] = Field(None, description="Cost of this request in USD")
    validation_errors: List[ValidationError] = Field(
        default_factory=list, description="Any validation errors"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Triage Agent Models
# ============================================================================


class TriageResult(BaseAgentResponse):
    """Comprehensive triage result with detailed issue classification."""

    issue_type: str = Field(..., description="Type of issue detected")
    category: IssueCategory = Field(..., description="Category of the issue")
    severity: SeverityLevel = Field(..., description="Severity level of the issue")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score for the assessment"
    )
    confidence_level: ConfidenceLevel = Field(
        ..., description="Human-readable confidence level"
    )
    summary: str = Field(..., description="Brief summary of the issue")
    description: str = Field(..., description="Detailed description of the issue")
    urgency: str = Field(
        ..., description="Urgency level (immediate, high, medium, low)"
    )
    impact_assessment: str = Field(..., description="Assessment of potential impact")
    affected_components: List[str] = Field(
        default_factory=list, description="Components affected by the issue"
    )
    recommended_actions: List[str] = Field(
        ..., description="Recommended immediate actions"
    )
    escalation_required: bool = Field(
        False, description="Whether escalation is required"
    )
    estimated_resolution_time: Optional[str] = Field(
        None, description="Estimated time to resolve"
    )
    related_issues: List[str] = Field(
        default_factory=list, description="IDs of related issues"
    )
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorization and filtering"
    )

    @field_validator("confidence_level", mode="before")
    @classmethod
    def set_confidence_level(cls, v, info):
        """Set confidence level based on confidence score."""
        if hasattr(info, "data") and "confidence" in info.data:
            confidence = info.data["confidence"]
            if confidence >= 0.9:
                return ConfidenceLevel.VERY_HIGH
            elif confidence >= 0.7:
                return ConfidenceLevel.HIGH
            elif confidence >= 0.5:
                return ConfidenceLevel.MEDIUM
            elif confidence >= 0.3:
                return ConfidenceLevel.LOW
            else:
                return ConfidenceLevel.VERY_LOW
        return v

    @field_validator("confidence")
    @classmethod
    def check_confidence_threshold(cls, v):
        """Validate confidence score meets minimum threshold."""
        if v < 0.3:
            raise ValueError("Confidence score below acceptable threshold (0.3)")
        return v


# ============================================================================
# Analysis Agent Models
# ============================================================================


class AnalysisFinding(BaseModel):
    """Individual finding within an analysis result."""

    finding_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this finding",
    )
    title: str = Field(..., description="Title of the finding")
    description: str = Field(..., description="Detailed description of the finding")
    severity: SeverityLevel = Field(..., description="Severity of this finding")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in this finding"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Evidence supporting this finding"
    )
    recommendations: List[str] = Field(
        default_factory=list, description="Recommendations for this finding"
    )
    affected_files: List[str] = Field(
        default_factory=list, description="Files affected by this finding"
    )
    line_numbers: List[int] = Field(
        default_factory=list, description="Specific line numbers if applicable"
    )
    category: IssueCategory = Field(..., description="Category of this finding")


class RootCauseAnalysis(BaseModel):
    """Root cause analysis for an issue."""

    primary_cause: str = Field(..., description="Primary root cause identified")
    contributing_factors: List[str] = Field(
        default_factory=list, description="Contributing factors"
    )
    timeline: List[str] = Field(
        default_factory=list, description="Timeline of events leading to the issue"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Evidence supporting the root cause"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in the root cause analysis"
    )


class AnalysisResult(BaseAgentResponse):
    """Comprehensive analysis result with detailed findings and insights."""

    analysis_type: str = Field(..., description="Type of analysis performed")
    summary: str = Field(..., description="Executive summary of the analysis")
    key_findings: List[AnalysisFinding] = Field(
        ..., description="Key findings from the analysis"
    )
    root_cause_analysis: Optional[RootCauseAnalysis] = Field(
        None, description="Root cause analysis if applicable"
    )
    overall_severity: SeverityLevel = Field(
        ..., description="Overall severity of the analyzed issue"
    )
    overall_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence in the analysis"
    )
    risk_assessment: str = Field(..., description="Risk assessment of the findings")
    business_impact: str = Field(..., description="Assessment of business impact")
    technical_debt_score: Optional[float] = Field(
        None, ge=0.0, le=10.0, description="Technical debt score (0-10)"
    )
    recommendations: List[str] = Field(..., description="High-level recommendations")
    next_steps: List[str] = Field(..., description="Recommended next steps")
    requires_follow_up: bool = Field(
        False, description="Whether follow-up analysis is required"
    )
    analysis_scope: List[str] = Field(
        default_factory=list, description="Scope of the analysis"
    )
    excluded_areas: List[str] = Field(
        default_factory=list, description="Areas excluded from analysis"
    )

    @field_validator("overall_confidence")
    @classmethod
    def check_confidence_threshold(cls, v):
        """Validate overall confidence meets minimum threshold."""
        if v < 0.4:
            raise ValueError("Overall confidence below acceptable threshold (0.4)")
        return v


# ============================================================================
# Remediation Agent Models
# ============================================================================


class RemediationStep(BaseModel):
    """Individual step in a remediation plan."""

    step_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this step",
    )
    order: int = Field(..., ge=1, description="Execution order of this step")
    title: str = Field(..., description="Title of the remediation step")
    description: str = Field(..., description="Detailed description of the step")
    action_type: ActionType = Field(..., description="Type of action required")
    commands: List[str] = Field(
        default_factory=list, description="Commands or code to execute"
    )
    estimated_duration: Optional[str] = Field(
        None, description="Estimated time to complete this step"
    )
    estimated_effort: Optional[str] = Field(
        None, description="Estimated effort required (low, medium, high)"
    )
    risk_level: SeverityLevel = Field(..., description="Risk level of this step")
    prerequisites: List[str] = Field(
        default_factory=list, description="Prerequisites for this step"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Step IDs this step depends on"
    )
    rollback_plan: Optional[str] = Field(
        None, description="Plan for rolling back this step"
    )
    validation_criteria: List[str] = Field(
        default_factory=list, description="Criteria to validate success"
    )
    affected_systems: List[str] = Field(
        default_factory=list, description="Systems affected by this step"
    )
    requires_approval: bool = Field(
        False, description="Whether this step requires approval"
    )
    automated: bool = Field(False, description="Whether this step can be automated")


class RemediationPlan(BaseAgentResponse):
    """Comprehensive remediation plan with multiple steps."""

    plan_name: str = Field(..., description="Name of the remediation plan")
    issue_description: str = Field(
        ..., description="Description of the issue being remediated"
    )
    priority: SeverityLevel = Field(
        ..., description="Priority level of the remediation"
    )
    estimated_total_duration: Optional[str] = Field(
        None, description="Total estimated duration"
    )
    estimated_total_effort: Optional[str] = Field(
        None, description="Total estimated effort"
    )
    steps: List[RemediationStep] = Field(
        ..., description="Remediation steps in execution order"
    )
    success_criteria: List[str] = Field(
        ..., description="Criteria for successful remediation"
    )
    risk_assessment: str = Field(..., description="Assessment of risks involved")
    rollback_strategy: Optional[str] = Field(
        None, description="Overall rollback strategy"
    )
    testing_plan: List[str] = Field(
        default_factory=list, description="Testing plan for validation"
    )
    monitoring_plan: List[str] = Field(
        default_factory=list, description="Monitoring plan during execution"
    )
    approval_required: bool = Field(
        False, description="Whether the plan requires approval"
    )
    automated_steps: int = Field(0, description="Number of steps that can be automated")
    manual_steps: int = Field(
        0, description="Number of steps requiring manual intervention"
    )

    @field_validator("steps")
    @classmethod
    def validate_step_order(cls, v):
        """Validate that steps are in proper order and have unique IDs."""
        if not v:
            raise ValueError("Remediation plan must have at least one step")

        # Check for unique step IDs
        step_ids = [step.step_id for step in v]
        if len(step_ids) != len(set(step_ids)):
            raise ValueError("Step IDs must be unique")

        # Check for proper ordering
        orders = [step.order for step in v]
        if sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("Steps must be numbered consecutively starting from 1")

        return v

    @field_validator("automated_steps", "manual_steps", mode="before")
    @classmethod
    def calculate_step_counts(cls, v, info):
        """Calculate automated and manual step counts."""
        if hasattr(info, "data") and "steps" in info.data:
            steps = info.data["steps"]
            if not steps:
                return 0

            automated = sum(1 for step in steps if step.automated)
            manual = len(steps) - automated

            # Determine which field is being validated
            field_name = info.field_name
            if field_name == "automated_steps":
                return automated
            elif field_name == "manual_steps":
                return manual
        return v


# ============================================================================
# Health Check Agent Models
# ============================================================================


class ComponentHealth(BaseModel):
    """Health status of an individual component."""

    component_name: str = Field(..., description="Name of the component")
    status: StatusCode = Field(..., description="Health status of the component")
    last_check: datetime = Field(
        ..., description="Last time this component was checked"
    )
    response_time_ms: Optional[float] = Field(
        None, description="Response time in milliseconds"
    )
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")
    metrics: Dict[str, Any] = Field(
        default_factory=dict, description="Component-specific metrics"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Dependencies of this component"
    )


class ResourceUtilization(BaseModel):
    """Resource utilization metrics."""

    cpu_usage_percent: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="CPU usage percentage"
    )
    memory_usage_percent: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Memory usage percentage"
    )
    disk_usage_percent: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Disk usage percentage"
    )
    network_io_mbps: Optional[float] = Field(
        None, ge=0.0, description="Network I/O in Mbps"
    )
    active_connections: Optional[int] = Field(
        None, ge=0, description="Number of active connections"
    )
    queue_depth: Optional[int] = Field(
        None, ge=0, description="Queue depth if applicable"
    )


class HealthCheckResponse(BaseAgentResponse):
    """Comprehensive health check response."""

    overall_status: StatusCode = Field(..., description="Overall system health status")
    overall_severity: SeverityLevel = Field(
        ..., description="Overall severity of health issues"
    )
    system_uptime: Optional[str] = Field(None, description="System uptime")
    last_restart: Optional[datetime] = Field(
        None, description="Last system restart time"
    )
    components: List[ComponentHealth] = Field(
        ..., description="Health status of individual components"
    )
    resource_utilization: Optional[ResourceUtilization] = Field(
        None, description="Resource utilization metrics"
    )
    critical_alerts: List[str] = Field(
        default_factory=list, description="Critical alerts requiring attention"
    )
    warnings: List[str] = Field(default_factory=list, description="Warning messages")
    recommendations: List[str] = Field(
        default_factory=list, description="Health improvement recommendations"
    )
    next_check_time: Optional[datetime] = Field(
        None, description="Scheduled time for next health check"
    )
    health_score: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="Overall health score (0-100)"
    )
    degraded_components: List[str] = Field(
        default_factory=list, description="Components in degraded state"
    )
    failed_components: List[str] = Field(
        default_factory=list, description="Components that have failed"
    )

    @field_validator("health_score", mode="before")
    @classmethod
    def calculate_health_score(cls, v, info):
        """Calculate health score based on component statuses."""
        if hasattr(info, "data") and "components" in info.data:
            components = info.data["components"]
            if not components:
                return None

            healthy_count = sum(
                1 for comp in components if comp.status == StatusCode.SUCCESS
            )
            total_count = len(components)

            if total_count == 0:
                return 0.0

            return round((healthy_count / total_count) * 100, 1)
        return v


# ============================================================================
# Enhanced Text Agent Models
# ============================================================================


class TextResponse(BaseAgentResponse):
    """Enhanced text response with additional metadata."""

    text: str = Field(..., description="The generated text")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    word_count: int = Field(
        ..., ge=0, description="Number of words in the generated text"
    )
    character_count: int = Field(
        ..., ge=0, description="Number of characters in the generated text"
    )
    language: Optional[str] = Field(None, description="Detected or specified language")
    sentiment: Optional[str] = Field(None, description="Sentiment analysis result")
    topics: List[str] = Field(
        default_factory=list, description="Detected topics or themes"
    )
    quality_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Quality score of the generated text"
    )

    @field_validator("word_count", "character_count", mode="before")
    @classmethod
    def calculate_counts(cls, v, info):
        """Calculate word and character counts from text."""
        if hasattr(info, "data") and "text" in info.data:
            text = info.data["text"]
            field_name = info.field_name
            if field_name == "word_count":
                return len(text.split())
            elif field_name == "character_count":
                return len(text)
        return v


# ============================================================================
# Enhanced Code Agent Models
# ============================================================================


class CodeResponse(BaseAgentResponse):
    """Enhanced code response with comprehensive metadata."""

    code: str = Field(..., description="The generated code")
    language: str = Field(..., description="Programming language")
    explanation: str = Field(..., description="Explanation of the code")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    dependencies: List[str] = Field(
        default_factory=list, description="Required dependencies"
    )
    imports: List[str] = Field(default_factory=list, description="Required imports")
    functions: List[str] = Field(
        default_factory=list, description="Functions defined in the code"
    )
    classes: List[str] = Field(
        default_factory=list, description="Classes defined in the code"
    )
    complexity_score: Optional[float] = Field(
        None, ge=0.0, le=10.0, description="Code complexity score"
    )
    test_coverage: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Estimated test coverage"
    )
    security_issues: List[str] = Field(
        default_factory=list, description="Potential security issues"
    )
    performance_notes: List[str] = Field(
        default_factory=list, description="Performance considerations"
    )
    best_practices: List[str] = Field(
        default_factory=list, description="Best practices applied"
    )
    line_count: int = Field(
        ..., ge=0, description="Number of lines in the generated code"
    )

    @field_validator("line_count", mode="before")
    @classmethod
    def calculate_line_count(cls, v, info):
        """Calculate line count from code."""
        if hasattr(info, "data") and "code" in info.data:
            code = info.data["code"]
            return len(code.splitlines())
        return v


# ============================================================================
# Factory Functions and Utilities
# ============================================================================


def create_triage_result(
    issue_type: str,
    category: IssueCategory,
    severity: SeverityLevel,
    confidence: float,
    summary: str,
    description: str,
    agent_id: str,
    **kwargs,
) -> TriageResult:
    """Factory function to create a TriageResult with common defaults."""
    # Determine confidence level based on confidence score
    if confidence >= 0.9:
        confidence_level = ConfidenceLevel.VERY_HIGH
    elif confidence >= 0.7:
        confidence_level = ConfidenceLevel.HIGH
    elif confidence >= 0.5:
        confidence_level = ConfidenceLevel.MEDIUM
    elif confidence >= 0.3:
        confidence_level = ConfidenceLevel.LOW
    else:
        confidence_level = ConfidenceLevel.VERY_LOW

    # Remove confidence_level from kwargs if present to avoid duplicate
    kwargs.pop("confidence_level", None)

    return TriageResult(
        agent_type="triage",
        status=StatusCode.SUCCESS,
        issue_type=issue_type,
        category=category,
        severity=severity,
        confidence=confidence,
        confidence_level=confidence_level,
        summary=summary,
        description=description,
        urgency="medium",
        impact_assessment="Impact assessment pending",
        recommended_actions=["Investigate further", "Monitor closely"],
        agent_id=agent_id,
        **kwargs,
    )


def create_analysis_result(
    analysis_type: str,
    summary: str,
    key_findings: List[AnalysisFinding],
    overall_severity: SeverityLevel,
    overall_confidence: float,
    agent_id: str,
    **kwargs,
) -> AnalysisResult:
    """Factory function to create an AnalysisResult with common defaults."""
    return AnalysisResult(
        agent_type="analysis",
        status=StatusCode.SUCCESS,
        analysis_type=analysis_type,
        summary=summary,
        key_findings=key_findings,
        overall_severity=overall_severity,
        overall_confidence=overall_confidence,
        risk_assessment="Risk assessment pending",
        business_impact="Business impact assessment pending",
        recommendations=["Review findings", "Plan remediation"],
        next_steps=["Schedule follow-up", "Implement recommendations"],
        agent_id=agent_id,
        **kwargs,
    )


def create_remediation_plan(
    plan_name: str,
    issue_description: str,
    priority: SeverityLevel,
    steps: List[RemediationStep],
    agent_id: str,
    **kwargs,
) -> RemediationPlan:
    """Factory function to create a RemediationPlan with common defaults."""
    return RemediationPlan(
        agent_type="remediation",
        status=StatusCode.SUCCESS,
        plan_name=plan_name,
        issue_description=issue_description,
        priority=priority,
        steps=steps,
        success_criteria=["Issue resolved", "System stable"],
        risk_assessment="Risk assessment pending",
        agent_id=agent_id,
        **kwargs,
    )


def create_health_check_response(
    overall_status: StatusCode,
    overall_severity: SeverityLevel,
    components: List[ComponentHealth],
    agent_id: str,
    **kwargs,
) -> HealthCheckResponse:
    """Factory function to create a HealthCheckResponse with common defaults."""
    return HealthCheckResponse(
        agent_type="health_check",
        status=StatusCode.SUCCESS,
        overall_status=overall_status,
        overall_severity=overall_severity,
        components=components,
        recommendations=["Monitor system health", "Address any warnings"],
        agent_id=agent_id,
        **kwargs,
    )


# ============================================================================
# Response Model Registry
# ============================================================================

AGENT_RESPONSE_MODELS = {
    "triage": TriageResult,
    "analysis": AnalysisResult,
    "remediation": RemediationPlan,
    "health_check": HealthCheckResponse,
    "text": TextResponse,
    "code": CodeResponse,
}


def get_response_model(agent_type: str) -> type[BaseAgentResponse]:
    """Get the appropriate response model for an agent type."""
    if agent_type not in AGENT_RESPONSE_MODELS:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return AGENT_RESPONSE_MODELS[agent_type]


def validate_response_model(response_data: dict, agent_type: str) -> BaseAgentResponse:
    """Validate and create a response model from raw data."""
    model_class = get_response_model(agent_type)
    return model_class(**response_data)
