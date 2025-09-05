"""
Comprehensive tests for agent response models.

Tests all Pydantic models including validation, serialization, and integration.
"""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gemini_sre_agent.agents.agent_models import (
    ActionType,
    AnalysisFinding,
    AnalysisResult,
    BaseAgentResponse,
    CodeResponse,
    ComponentHealth,
    ConfidenceLevel,
    HealthCheckResponse,
    IssueCategory,
    RemediationPlan,
    RemediationStep,
    ResourceUtilization,
    RootCauseAnalysis,
    SeverityLevel,
    StatusCode,
    TextResponse,
    TriageResult,
)
from gemini_sre_agent.agents.agent_models import ValidationError as ModelValidationError
from gemini_sre_agent.agents.agent_models import (
    create_analysis_result,
    create_health_check_response,
    create_remediation_plan,
    create_triage_result,
)


class TestBaseAgentResponse:
    """Test the BaseAgentResponse model."""

    def test_valid_base_response(self):
        """Test creating a valid base response."""
        response = BaseAgentResponse(
            agent_id="test-agent-1",
            agent_type="test",
            status=StatusCode.SUCCESS,
            execution_time_ms=100.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.01,
        )

        assert response.agent_id == "test-agent-1"
        assert response.agent_type == "test"
        assert response.status == StatusCode.SUCCESS
        assert response.request_id is not None
        assert response.timestamp is not None
        assert response.validation_errors == []

    def test_base_response_with_optional_fields(self):
        """Test base response with optional fields."""
        response = BaseAgentResponse(
            agent_id="test-agent-1",
            agent_type="test",
            status=StatusCode.SUCCESS,
            execution_time_ms=150.5,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.05,
        )

        assert response.execution_time_ms == 150.5
        assert response.model_used == "gpt-4"
        assert response.provider_used == "openai"
        assert response.cost_usd == 0.05

    def test_base_response_serialization(self):
        """Test JSON serialization of base response."""
        response = BaseAgentResponse(
            agent_id="test-agent-1",
            agent_type="test",
            status=StatusCode.SUCCESS,
            execution_time_ms=100.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.01,
        )

        json_data = response.json()
        parsed_data = json.loads(json_data)

        assert parsed_data["agent_id"] == "test-agent-1"
        assert parsed_data["agent_type"] == "test"
        assert parsed_data["status"] == "success"
        assert "request_id" in parsed_data
        assert "timestamp" in parsed_data


class TestTriageResult:
    """Test the TriageResult model."""

    def test_valid_triage_result(self):
        """Test creating a valid triage result."""
        result = TriageResult(
            agent_id="triage-agent-1",
            agent_type="triage",
            status=StatusCode.SUCCESS,
            execution_time_ms=200.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.02,
            issue_type="memory_leak",
            category=IssueCategory.PERFORMANCE,
            severity=SeverityLevel.HIGH,
            confidence=0.85,
            confidence_level=ConfidenceLevel.HIGH,
            summary="Memory leak detected in application",
            description="Application memory usage is growing over time",
            urgency="high",
            impact_assessment="High impact on system performance",
            recommended_actions=[
                "Profile memory usage",
                "Check for unclosed resources",
            ],
            escalation_required=False,
            estimated_resolution_time="2-4 hours",
        )

        assert result.issue_type == "memory_leak"
        assert result.category == IssueCategory.PERFORMANCE
        assert result.severity == SeverityLevel.HIGH
        assert result.confidence == 0.85
        assert result.confidence_level == ConfidenceLevel.HIGH
        assert result.summary == "Memory leak detected in application"
        assert result.urgency == "high"

    def test_triage_result_confidence_validation(self):
        """Test confidence validation in triage result."""
        # Test valid confidence
        result = TriageResult(
            agent_id="triage-agent-1",
            agent_type="triage",
            status=StatusCode.SUCCESS,
            execution_time_ms=150.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.015,
            issue_type="test_issue",
            category=IssueCategory.PERFORMANCE,
            severity=SeverityLevel.MEDIUM,
            confidence=0.7,
            confidence_level=ConfidenceLevel.HIGH,
            summary="Test issue",
            description="Test description",
            urgency="medium",
            impact_assessment="Test impact",
            recommended_actions=["Test action"],
            escalation_required=False,
            estimated_resolution_time="1 hour",
        )
        assert result.confidence == 0.7

        # Test confidence below threshold
        with pytest.raises(ValidationError) as exc_info:
            TriageResult(
                agent_id="triage-agent-1",
                agent_type="triage",
                status=StatusCode.SUCCESS,
                execution_time_ms=150.0,
                model_used="gpt-4",
                provider_used="openai",
                cost_usd=0.015,
                issue_type="test_issue",
                category=IssueCategory.PERFORMANCE,
                severity=SeverityLevel.MEDIUM,
                confidence=0.2,  # Below threshold
                confidence_level=ConfidenceLevel.VERY_LOW,
                summary="Test issue",
                description="Test description",
                urgency="medium",
                impact_assessment="Test impact",
                recommended_actions=["Test action"],
                escalation_required=False,
                estimated_resolution_time="1 hour",
            )

        assert "Confidence score below acceptable threshold" in str(exc_info.value)

    def test_triage_result_confidence_level_mapping(self):
        """Test automatic confidence level mapping."""
        test_cases = [
            (0.95, ConfidenceLevel.VERY_HIGH),
            (0.8, ConfidenceLevel.HIGH),
            (0.6, ConfidenceLevel.MEDIUM),
            (0.4, ConfidenceLevel.LOW),
        ]

        for confidence, expected_level in test_cases:
            result = TriageResult(
                agent_id="triage-agent-1",
                agent_type="triage",
                status=StatusCode.SUCCESS,
                execution_time_ms=150.0,
                model_used="gpt-4",
                provider_used="openai",
                cost_usd=0.015,
                issue_type="test_issue",
                category=IssueCategory.PERFORMANCE,
                severity=SeverityLevel.MEDIUM,
                confidence=confidence,
                confidence_level=expected_level,
                summary="Test issue",
                description="Test description",
                urgency="medium",
                impact_assessment="Test impact",
                recommended_actions=["Test action"],
                escalation_required=False,
                estimated_resolution_time="1 hour",
            )
            assert result.confidence_level == expected_level

    def test_triage_result_factory(self):
        """Test the triage result factory function."""
        result = create_triage_result(
            issue_type="performance_issue",
            category=IssueCategory.PERFORMANCE,
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            summary="Performance issue detected",
            description="Detailed description",
            agent_id="triage-agent-1",
            execution_time_ms=200.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.02,
            confidence_level=ConfidenceLevel.HIGH,
            escalation_required=False,
            estimated_resolution_time="2 hours",
        )

        assert isinstance(result, TriageResult)
        assert result.issue_type == "performance_issue"
        assert result.category == IssueCategory.PERFORMANCE
        assert result.severity == SeverityLevel.HIGH
        assert result.confidence == 0.8
        assert result.agent_id == "triage-agent-1"


class TestAnalysisResult:
    """Test the AnalysisResult model."""

    def test_valid_analysis_result(self):
        """Test creating a valid analysis result."""
        finding = AnalysisFinding(
            title="Memory leak in service",
            description="Service is leaking memory over time",
            severity=SeverityLevel.HIGH,
            confidence=0.9,
            evidence=["Memory usage graph shows upward trend"],
            recommendations=["Implement proper resource cleanup"],
            category=IssueCategory.PERFORMANCE,
        )

        result = AnalysisResult(
            agent_id="analysis-agent-1",
            agent_type="analysis",
            status=StatusCode.SUCCESS,
            execution_time_ms=300.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.03,
            analysis_type="performance_analysis",
            summary="Performance analysis completed",
            key_findings=[finding],
            overall_severity=SeverityLevel.HIGH,
            overall_confidence=0.85,
            risk_assessment="High risk to system stability",
            business_impact="Potential service degradation",
            recommendations=["Implement fixes immediately"],
            next_steps=["Schedule maintenance window"],
            root_cause_analysis=None,
            technical_debt_score=7.5,
            requires_follow_up=True,
        )

        assert result.analysis_type == "performance_analysis"
        assert len(result.key_findings) == 1
        assert result.key_findings[0].title == "Memory leak in service"
        assert result.overall_severity == SeverityLevel.HIGH
        assert result.overall_confidence == 0.85

    def test_analysis_result_with_root_cause(self):
        """Test analysis result with root cause analysis."""
        root_cause = RootCauseAnalysis(
            primary_cause="Unclosed database connections",
            contributing_factors=["Missing connection pooling", "No timeout handling"],
            timeline=["Service started", "Connections accumulated", "Memory exhausted"],
            evidence=["Connection count logs", "Memory usage patterns"],
            confidence=0.9,
        )

        result = AnalysisResult(
            agent_id="analysis-agent-1",
            agent_type="analysis",
            status=StatusCode.SUCCESS,
            execution_time_ms=400.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.04,
            analysis_type="root_cause_analysis",
            summary="Root cause analysis completed",
            key_findings=[],
            root_cause_analysis=root_cause,
            overall_severity=SeverityLevel.HIGH,
            overall_confidence=0.9,
            risk_assessment="High risk",
            business_impact="Service degradation",
            recommendations=["Fix connection handling"],
            next_steps=["Implement connection pooling"],
            technical_debt_score=8.0,
            requires_follow_up=True,
        )

        assert result.root_cause_analysis is not None
        assert (
            result.root_cause_analysis.primary_cause == "Unclosed database connections"
        )
        assert result.root_cause_analysis.confidence == 0.9

    def test_analysis_result_confidence_validation(self):
        """Test confidence validation in analysis result."""
        with pytest.raises(ValidationError) as exc_info:
            AnalysisResult(
                agent_id="analysis-agent-1",
                agent_type="analysis",
                status=StatusCode.SUCCESS,
                execution_time_ms=300.0,
                model_used="gpt-4",
                provider_used="openai",
                cost_usd=0.03,
                analysis_type="test_analysis",
                summary="Test summary",
                key_findings=[],
                overall_severity=SeverityLevel.MEDIUM,
                overall_confidence=0.3,  # Below threshold
                risk_assessment="Test risk",
                business_impact="Test impact",
                recommendations=["Test recommendation"],
                next_steps=["Test step"],
                root_cause_analysis=None,
                technical_debt_score=5.0,
                requires_follow_up=False,
            )

        assert "Overall confidence below acceptable threshold" in str(exc_info.value)

    def test_analysis_result_factory(self):
        """Test the analysis result factory function."""
        finding = AnalysisFinding(
            title="Test finding",
            description="Test description",
            severity=SeverityLevel.MEDIUM,
            confidence=0.7,
            evidence=["Test evidence"],
            recommendations=["Test recommendation"],
            category=IssueCategory.PERFORMANCE,
        )

        result = create_analysis_result(
            analysis_type="performance_analysis",
            summary="Test analysis",
            key_findings=[finding],
            overall_severity=SeverityLevel.MEDIUM,
            overall_confidence=0.7,
            agent_id="analysis-agent-1",
            execution_time_ms=300.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.03,
            technical_debt_score=6.0,
            requires_follow_up=False,
        )

        assert isinstance(result, AnalysisResult)
        assert result.analysis_type == "performance_analysis"
        assert len(result.key_findings) == 1
        assert result.agent_id == "analysis-agent-1"


class TestRemediationPlan:
    """Test the RemediationPlan model."""

    def test_valid_remediation_plan(self):
        """Test creating a valid remediation plan."""
        step1 = RemediationStep(
            order=1,
            title="Backup current system",
            description="Create backup before making changes",
            action_type=ActionType.IMMEDIATE,
            commands=["backup-system.sh"],
            estimated_duration="30 minutes",
            estimated_effort="low",
            risk_level=SeverityLevel.LOW,
            rollback_plan="Restore from backup if needed",
            requires_approval=False,
            automated=True,
        )

        step2 = RemediationStep(
            order=2,
            title="Apply fix",
            description="Apply the memory leak fix",
            action_type=ActionType.IMMEDIATE,
            commands=["apply-fix.sh"],
            estimated_duration="15 minutes",
            estimated_effort="medium",
            risk_level=SeverityLevel.MEDIUM,
            dependencies=[step1.step_id],
            rollback_plan="Revert to previous version",
            requires_approval=True,
            automated=False,
        )

        plan = RemediationPlan(
            agent_id="remediation-agent-1",
            agent_type="remediation",
            status=StatusCode.SUCCESS,
            execution_time_ms=500.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.05,
            plan_name="Memory leak fix",
            issue_description="Fix memory leak in service",
            priority=SeverityLevel.HIGH,
            estimated_total_duration="45 minutes",
            estimated_total_effort="medium",
            steps=[step1, step2],
            success_criteria=["Memory usage stable", "No errors in logs"],
            risk_assessment="Low risk with proper backup",
            rollback_strategy="Restore from backup",
            approval_required=False,
            automated_steps=1,
            manual_steps=1,
        )

        assert plan.plan_name == "Memory leak fix"
        assert len(plan.steps) == 2
        assert plan.steps[0].title == "Backup current system"
        assert plan.steps[1].title == "Apply fix"
        assert plan.automated_steps == 1
        assert plan.manual_steps == 1

    def test_remediation_plan_step_validation(self):
        """Test step validation in remediation plan."""
        # Test invalid step order
        with pytest.raises(ValidationError) as exc_info:
            step1 = RemediationStep(
                order=1,
                title="Step 1",
                description="First step",
                action_type=ActionType.IMMEDIATE,
                risk_level=SeverityLevel.LOW,
                estimated_duration="10 minutes",
                estimated_effort="low",
                rollback_plan="Rollback step 1",
                requires_approval=False,
                automated=True,
            )

            step2 = RemediationStep(
                order=3,  # Invalid: should be 2
                title="Step 2",
                description="Second step",
                action_type=ActionType.IMMEDIATE,
                risk_level=SeverityLevel.LOW,
                estimated_duration="15 minutes",
                estimated_effort="low",
                rollback_plan="Rollback step 2",
                requires_approval=False,
                automated=True,
            )

            RemediationPlan(
                agent_id="remediation-agent-1",
                agent_type="remediation",
                status=StatusCode.SUCCESS,
                execution_time_ms=400.0,
                model_used="gpt-4",
                provider_used="openai",
                cost_usd=0.04,
                plan_name="Test plan",
                issue_description="Test issue",
                priority=SeverityLevel.MEDIUM,
                estimated_total_duration="1 hour",
                estimated_total_effort="medium",
                steps=[step1, step2],
                success_criteria=["Test criteria"],
                risk_assessment="Test risk",
                rollback_strategy="Test rollback",
                approval_required=False,
                automated_steps=0,
                manual_steps=2,
            )

        assert "Steps must be numbered consecutively" in str(exc_info.value)

    def test_remediation_plan_factory(self):
        """Test the remediation plan factory function."""
        step = RemediationStep(
            order=1,
            title="Test step",
            description="Test description",
            action_type=ActionType.IMMEDIATE,
            risk_level=SeverityLevel.LOW,
            estimated_duration="5 minutes",
            estimated_effort="low",
            rollback_plan="Test rollback",
            requires_approval=False,
            automated=True,
        )

        plan = create_remediation_plan(
            plan_name="Test plan",
            issue_description="Test issue",
            priority=SeverityLevel.MEDIUM,
            steps=[step],
            agent_id="remediation-agent-1",
            execution_time_ms=300.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.03,
            estimated_total_duration="30 minutes",
            estimated_total_effort="low",
            rollback_strategy="Test rollback strategy",
            approval_required=False,
            automated_steps=0,
            manual_steps=1,
        )

        assert isinstance(plan, RemediationPlan)
        assert plan.plan_name == "Test plan"
        assert len(plan.steps) == 1
        assert plan.agent_id == "remediation-agent-1"


class TestHealthCheckResponse:
    """Test the HealthCheckResponse model."""

    def test_valid_health_check_response(self):
        """Test creating a valid health check response."""
        component1 = ComponentHealth(
            component_name="database",
            status=StatusCode.SUCCESS,
            last_check=datetime.now(timezone.utc),
            response_time_ms=50.0,
            error_message="",
            metrics={"connections": 10, "queries_per_second": 100},
        )

        component2 = ComponentHealth(
            component_name="api_server",
            status=StatusCode.SUCCESS,
            last_check=datetime.now(timezone.utc),
            response_time_ms=25.0,
            error_message="",
            metrics={"requests_per_second": 500, "error_rate": 0.01},
        )

        resource_util = ResourceUtilization(
            cpu_usage_percent=45.0,
            memory_usage_percent=60.0,
            disk_usage_percent=30.0,
            network_io_mbps=100.0,
            active_connections=150,
            queue_depth=5,
        )

        response = HealthCheckResponse(
            agent_id="health-agent-1",
            agent_type="health_check",
            status=StatusCode.SUCCESS,
            execution_time_ms=100.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.01,
            overall_status=StatusCode.SUCCESS,
            overall_severity=SeverityLevel.LOW,
            system_uptime="5 days",
            last_restart=datetime.now(timezone.utc),
            components=[component1, component2],
            resource_utilization=resource_util,
            critical_alerts=[],
            warnings=["High memory usage"],
            recommendations=["Monitor memory usage closely"],
            next_check_time=datetime.now(timezone.utc),
            health_score=100.0,
        )

        assert response.overall_status == StatusCode.SUCCESS
        assert len(response.components) == 2
        assert response.components[0].component_name == "database"
        assert response.resource_utilization is not None
        assert response.resource_utilization.cpu_usage_percent == 45.0
        assert response.health_score == 100.0  # Both components are healthy

    def test_health_check_response_auto_calculation(self):
        """Test automatic health score calculation."""
        healthy_component = ComponentHealth(
            component_name="healthy_service",
            status=StatusCode.SUCCESS,
            last_check=datetime.now(timezone.utc),
            response_time_ms=10.0,
            error_message="",
        )

        unhealthy_component = ComponentHealth(
            component_name="unhealthy_service",
            status=StatusCode.ERROR,
            last_check=datetime.now(timezone.utc),
            response_time_ms=None,
            error_message="Service unavailable",
        )

        response = HealthCheckResponse(
            agent_id="health-agent-1",
            agent_type="health_check",
            status=StatusCode.SUCCESS,
            execution_time_ms=150.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.015,
            overall_status=StatusCode.SUCCESS,
            overall_severity=SeverityLevel.MEDIUM,
            system_uptime="3 days",
            last_restart=datetime.now(timezone.utc),
            components=[healthy_component, unhealthy_component],
            resource_utilization=ResourceUtilization(
                cpu_usage_percent=50.0,
                memory_usage_percent=60.0,
                disk_usage_percent=40.0,
                network_io_mbps=100.0,
                active_connections=100,
                queue_depth=0,
            ),
            recommendations=["Fix unhealthy service"],
            next_check_time=datetime.now(timezone.utc),
            health_score=50.0,
        )

        # Should calculate 50% health score (1 healthy out of 2 components)
        assert response.health_score == 50.0

    def test_health_check_response_factory(self):
        """Test the health check response factory function."""
        component = ComponentHealth(
            component_name="test_component",
            status=StatusCode.SUCCESS,
            last_check=datetime.now(timezone.utc),
            response_time_ms=20.0,
            error_message="",
        )

        response = create_health_check_response(
            overall_status=StatusCode.SUCCESS,
            overall_severity=SeverityLevel.LOW,
            components=[component],
            agent_id="health-agent-1",
            execution_time_ms=100.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.01,
            system_uptime="1 day",
            last_restart=datetime.now(timezone.utc),
            resource_utilization=ResourceUtilization(
                cpu_usage_percent=30.0,
                memory_usage_percent=40.0,
                disk_usage_percent=20.0,
                network_io_mbps=50.0,
                active_connections=50,
                queue_depth=0,
            ),
            next_check_time=datetime.now(timezone.utc),
            health_score=100.0,
        )

        assert isinstance(response, HealthCheckResponse)
        assert response.overall_status == StatusCode.SUCCESS
        assert len(response.components) == 1
        assert response.agent_id == "health-agent-1"


class TestTextResponse:
    """Test the TextResponse model."""

    def test_valid_text_response(self):
        """Test creating a valid text response."""
        response = TextResponse(
            agent_id="text-agent-1",
            agent_type="text",
            status=StatusCode.SUCCESS,
            execution_time_ms=200.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.02,
            text="This is a test response with multiple words.",
            confidence=0.9,
            word_count=8,
            character_count=45,
            language="en",
            sentiment="positive",
            topics=["testing", "validation"],
            quality_score=0.85,
        )

        assert response.text == "This is a test response with multiple words."
        assert response.confidence == 0.9
        assert response.word_count == 8  # Auto-calculated
        assert response.character_count == 44  # Auto-calculated
        assert response.language == "en"
        assert response.sentiment == "positive"
        assert "testing" in response.topics

    def test_text_response_auto_calculation(self):
        """Test automatic word and character count calculation."""
        response = TextResponse(
            agent_id="text-agent-1",
            agent_type="text",
            status=StatusCode.SUCCESS,
            execution_time_ms=150.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.015,
            text="Hello world!",
            confidence=0.8,
            word_count=2,
            character_count=12,
            language="en",
            sentiment="neutral",
            quality_score=0.8,
        )

        assert response.word_count == 2
        assert response.character_count == 12


class TestCodeResponse:
    """Test the CodeResponse model."""

    def test_valid_code_response(self):
        """Test creating a valid code response."""
        code = """def hello_world():
    print("Hello, World!")
    return "success"

if __name__ == "__main__":
    hello_world()"""

        response = CodeResponse(
            agent_id="code-agent-1",
            agent_type="code",
            status=StatusCode.SUCCESS,
            execution_time_ms=300.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.03,
            code=code,
            language="python",
            explanation="A simple hello world function",
            confidence=0.95,
            dependencies=["python3"],
            imports=["sys"],
            functions=["hello_world"],
            classes=[],
            complexity_score=2.0,
            test_coverage=0.8,
            line_count=6,
            security_issues=[],
            performance_notes=["Efficient implementation"],
            best_practices=["Follows PEP 8"],
        )

        assert response.code == code
        assert response.language == "python"
        assert response.line_count == 6  # Auto-calculated
        assert response.confidence == 0.95
        assert "hello_world" in response.functions
        assert response.complexity_score == 2.0

    def test_code_response_auto_calculation(self):
        """Test automatic line count calculation."""
        code = "line1\nline2\nline3"

        response = CodeResponse(
            agent_id="code-agent-1",
            agent_type="code",
            status=StatusCode.SUCCESS,
            execution_time_ms=200.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.02,
            code=code,
            language="python",
            explanation="Test code",
            confidence=0.8,
            dependencies=[],
            imports=[],
            functions=[],
            classes=[],
            complexity_score=1.0,
            test_coverage=0.5,
            line_count=3,
            security_issues=[],
            performance_notes=[],
            best_practices=[],
        )

        assert response.line_count == 3


class TestModelRegistry:
    """Test the model registry and utility functions."""

    def test_get_response_model(self):
        """Test getting response models by agent type."""
        from gemini_sre_agent.agents.agent_models import get_response_model

        assert get_response_model("triage") == TriageResult
        assert get_response_model("analysis") == AnalysisResult
        assert get_response_model("remediation") == RemediationPlan
        assert get_response_model("health_check") == HealthCheckResponse
        assert get_response_model("text") == TextResponse
        assert get_response_model("code") == CodeResponse

    def test_get_response_model_invalid(self):
        """Test getting response model for invalid agent type."""
        from gemini_sre_agent.agents.agent_models import get_response_model

        with pytest.raises(ValueError) as exc_info:
            get_response_model("invalid_type")

        assert "Unknown agent type" in str(exc_info.value)

    def test_validate_response_model(self):
        """Test validating response model from raw data."""
        from gemini_sre_agent.agents.agent_models import validate_response_model

        raw_data = {
            "agent_id": "test-agent-1",
            "agent_type": "triage",
            "status": "success",
            "issue_type": "test_issue",
            "category": "performance",
            "severity": "high",
            "confidence": 0.8,
            "confidence_level": "high",
            "summary": "Test summary",
            "description": "Test description",
            "urgency": "high",
            "impact_assessment": "Test impact",
            "recommended_actions": ["Test action"],
            "escalation_required": False,
            "estimated_resolution_time": "1 hour",
        }

        result = validate_response_model(raw_data, "triage")
        assert isinstance(result, TriageResult)
        assert result.issue_type == "test_issue"
        assert result.severity == SeverityLevel.HIGH


class TestSerialization:
    """Test serialization and deserialization of models."""

    def test_triage_result_serialization(self):
        """Test JSON serialization of TriageResult."""
        result = create_triage_result(
            issue_type="test_issue",
            category=IssueCategory.PERFORMANCE,
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            summary="Test summary",
            description="Test description",
            agent_id="triage-agent-1",
        )

        # Test JSON serialization
        json_data = result.json()
        parsed_data = json.loads(json_data)

        assert parsed_data["issue_type"] == "test_issue"
        assert parsed_data["category"] == "performance"
        assert parsed_data["severity"] == "high"
        assert parsed_data["confidence"] == 0.8

        # Test deserialization
        reconstructed = TriageResult(**parsed_data)
        assert reconstructed.issue_type == result.issue_type
        assert reconstructed.category == result.category
        assert reconstructed.severity == result.severity

    def test_analysis_result_serialization(self):
        """Test JSON serialization of AnalysisResult."""
        finding = AnalysisFinding(
            title="Test finding",
            description="Test description",
            severity=SeverityLevel.MEDIUM,
            confidence=0.7,
            evidence=["Test evidence"],
            recommendations=["Test recommendation"],
            category=IssueCategory.PERFORMANCE,
        )

        result = create_analysis_result(
            analysis_type="test_analysis",
            summary="Test summary",
            key_findings=[finding],
            overall_severity=SeverityLevel.MEDIUM,
            overall_confidence=0.7,
            agent_id="analysis-agent-1",
        )

        # Test JSON serialization
        json_data = result.json()
        parsed_data = json.loads(json_data)

        assert parsed_data["analysis_type"] == "test_analysis"
        assert len(parsed_data["key_findings"]) == 1
        assert parsed_data["key_findings"][0]["title"] == "Test finding"

        # Test deserialization
        reconstructed = AnalysisResult(**parsed_data)
        assert reconstructed.analysis_type == result.analysis_type
        assert len(reconstructed.key_findings) == 1
        assert reconstructed.key_findings[0].title == "Test finding"


class TestValidationErrors:
    """Test validation error handling."""

    def test_validation_error_model(self):
        """Test ValidationError model."""
        error = ModelValidationError(
            field="confidence",
            message="Value must be between 0.0 and 1.0",
            value=1.5,
            code="VALUE_ERROR",
        )

        assert error.field == "confidence"
        assert error.message == "Value must be between 0.0 and 1.0"
        assert error.value == 1.5
        assert error.code == "VALUE_ERROR"

    def test_validation_errors_in_response(self):
        """Test validation errors in agent response."""
        validation_error = ModelValidationError(
            field="confidence",
            message="Invalid confidence value",
            value=1.5,
            code="VALUE_ERROR",
        )

        response = BaseAgentResponse(
            agent_id="test-agent-1",
            agent_type="test",
            status=StatusCode.ERROR,
            execution_time_ms=100.0,
            model_used="gpt-4",
            provider_used="openai",
            cost_usd=0.01,
            validation_errors=[validation_error],
        )

        assert len(response.validation_errors) == 1
        assert response.validation_errors[0].field == "confidence"
        assert response.validation_errors[0].message == "Invalid confidence value"


if __name__ == "__main__":
    pytest.main([__file__])
