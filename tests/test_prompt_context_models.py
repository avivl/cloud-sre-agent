# tests/test_prompt_context_models.py

"""
Tests for prompt context models.

This module contains comprehensive tests for all context data models
used in the enhanced prompt generation system.
"""


from gemini_sre_agent.ml.prompt_context_models import (
    BusinessImpact,
    IssueContext,
    IssueType,
    MetaPromptContext,
    PromptContext,
    RepositoryContext,
    TaskComplexity,
    TaskContext,
    ValidationResult,
)


class TestIssueType:
    """Test IssueType enum."""

    def test_issue_type_values(self) -> None:
        """Test that issue type values are correct."""
        assert IssueType.DATABASE_ERROR.value == "database_error"
        assert IssueType.API_ERROR.value == "api_error"
        assert IssueType.SERVICE_ERROR.value == "service_error"
        assert IssueType.CONFIGURATION_ERROR.value == "configuration_error"
        assert IssueType.PERFORMANCE_ERROR.value == "performance_error"
        assert IssueType.SECURITY_ERROR.value == "security_error"
        assert IssueType.NETWORK_ERROR.value == "network_error"
        assert IssueType.AUTHENTICATION_ERROR.value == "authentication_error"
        assert IssueType.UNKNOWN.value == "unknown"

    def test_issue_type_enumeration(self) -> None:
        """Test that all issue types can be enumerated."""
        issue_types = list(IssueType)
        assert len(issue_types) == 9
        assert IssueType.DATABASE_ERROR in issue_types
        assert IssueType.UNKNOWN in issue_types


class TestTaskComplexity:
    """Test TaskComplexity enum."""

    def test_complexity_values(self) -> None:
        """Test that complexity values are correct."""
        assert TaskComplexity.LOW.value == 1
        assert TaskComplexity.MEDIUM.value == 2
        assert TaskComplexity.HIGH.value == 3
        assert TaskComplexity.CRITICAL.value == 4


class TestBusinessImpact:
    """Test BusinessImpact enum."""

    def test_impact_values(self) -> None:
        """Test that impact values are correct."""
        assert BusinessImpact.LOW.value == 1
        assert BusinessImpact.MEDIUM.value == 2
        assert BusinessImpact.HIGH.value == 3
        assert BusinessImpact.CRITICAL.value == 4


class TestRepositoryContext:
    """Test RepositoryContext dataclass."""

    def test_repository_context_creation(self) -> None:
        """Test creating a repository context."""
        context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"language": "python", "framework": "fastapi"},
            coding_standards={"linting": "pylint", "formatting": "black"},
            error_handling_patterns=["try_catch", "logging"],
            testing_patterns=["unit_tests", "integration_tests"],
            dependency_structure={"service_a": ["service_b", "service_c"]},
            recent_changes=[{"commit": "abc123", "message": "fix bug"}],
            historical_fixes=[{"issue": "timeout", "fix": "retry_logic"}],
            code_quality_metrics={"complexity": 5.2, "coverage": 0.85},
        )

        assert context.architecture_type == "microservices"
        assert context.technology_stack["language"] == "python"
        assert len(context.error_handling_patterns) == 2
        assert context.code_quality_metrics["coverage"] == 0.85

    def test_repository_context_to_dict(self) -> None:
        """Test converting repository context to dictionary."""
        context = RepositoryContext(
            architecture_type="monolith",
            technology_stack={"language": "java"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        context_dict = context.to_dict()
        assert isinstance(context_dict, dict)
        assert context_dict["architecture_type"] == "monolith"
        assert context_dict["technology_stack"]["language"] == "java"
        assert "coding_standards" in context_dict
        assert "error_handling_patterns" in context_dict


class TestIssueContext:
    """Test IssueContext dataclass."""

    def test_issue_context_creation(self) -> None:
        """Test creating an issue context."""
        context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=["db/connection.py", "models/user.py"],
            error_patterns=["connection_timeout", "deadlock"],
            severity_level=8,
            impact_analysis={"affected_users": 1000, "revenue_impact": "high"},
            related_services=["user_service", "auth_service"],
            temporal_context={"frequency": "high", "duration": "intermittent"},
            user_impact="Users cannot log in",
            business_impact="Revenue loss due to login failures",
            complexity_score=7,
            context_richness=0.8,
        )

        assert context.issue_type == IssueType.DATABASE_ERROR
        assert len(context.affected_files) == 2
        assert context.severity_level == 8
        assert context.complexity_score == 7
        assert context.context_richness == 0.8

    def test_issue_context_defaults(self) -> None:
        """Test issue context with default values."""
        context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="Minor impact",
            business_impact="Low impact",
        )

        assert context.complexity_score == 1  # Default value
        assert context.context_richness == 0.5  # Default value

    def test_issue_context_to_dict(self) -> None:
        """Test converting issue context to dictionary."""
        context = IssueContext(
            issue_type=IssueType.SECURITY_ERROR,
            affected_files=["auth.py"],
            error_patterns=["sql_injection"],
            severity_level=10,
            impact_analysis={"security_risk": "critical"},
            related_services=["auth_service"],
            temporal_context={"detected": "2024-01-01"},
            user_impact="Security vulnerability",
            business_impact="Critical security risk",
        )

        context_dict = context.to_dict()
        assert isinstance(context_dict, dict)
        assert context_dict["issue_type"] == "security_error"
        assert context_dict["severity_level"] == 10
        assert "affected_files" in context_dict
        assert "error_patterns" in context_dict


class TestTaskContext:
    """Test TaskContext dataclass."""

    def test_task_context_creation(self) -> None:
        """Test creating a task context."""
        context = TaskContext(
            task_type="code_generation",
            complexity_score=8,
            context_variability=0.7,
            business_impact=9,
            accuracy_requirement=0.95,
            latency_requirement=2000,
            context_richness=0.8,
            frequency="low",
            cost_sensitivity=0.3,
        )

        assert context.task_type == "code_generation"
        assert context.complexity_score == 8
        assert context.context_variability == 0.7
        assert context.business_impact == 9
        assert context.accuracy_requirement == 0.95
        assert context.latency_requirement == 2000
        assert context.context_richness == 0.8
        assert context.frequency == "low"
        assert context.cost_sensitivity == 0.3

    def test_task_context_to_dict(self) -> None:
        """Test converting task context to dictionary."""
        context = TaskContext(
            task_type="log_analysis",
            complexity_score=3,
            context_variability=0.2,
            business_impact=5,
            accuracy_requirement=0.8,
            latency_requirement=500,
            context_richness=0.4,
            frequency="high",
            cost_sensitivity=0.8,
        )

        context_dict = context.to_dict()
        assert isinstance(context_dict, dict)
        assert context_dict["task_type"] == "log_analysis"
        assert context_dict["complexity_score"] == 3
        assert context_dict["frequency"] == "high"


class TestPromptContext:
    """Test PromptContext dataclass."""

    def test_prompt_context_creation(self) -> None:
        """Test creating a prompt context."""
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"language": "python"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="Test impact",
            business_impact="Test business impact",
        )

        context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="database_error",
            validation_feedback={"syntax_issues": "none"},
            iteration_count=1,
        )

        assert context.issue_context.issue_type == IssueType.DATABASE_ERROR
        assert context.repository_context.architecture_type == "microservices"
        assert context.generator_type == "database_error"
        assert context.validation_feedback["syntax_issues"] == "none"
        assert context.iteration_count == 1

    def test_prompt_context_defaults(self) -> None:
        """Test prompt context with default values."""
        repo_context = RepositoryContext(
            architecture_type="monolith",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="Test",
            business_impact="Test",
        )

        context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="api_error",
        )

        assert context.validation_feedback is None
        assert context.iteration_count == 0

    def test_prompt_context_to_dict(self) -> None:
        """Test converting prompt context to dictionary."""
        repo_context = RepositoryContext(
            architecture_type="serverless",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.SERVICE_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="Test",
            business_impact="Test",
        )

        context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="service_error",
        )

        context_dict = context.to_dict()
        assert isinstance(context_dict, dict)
        assert context_dict["generator_type"] == "service_error"
        assert "issue_context" in context_dict
        assert "repository_context" in context_dict


class TestMetaPromptContext:
    """Test MetaPromptContext dataclass."""

    def test_meta_prompt_context_creation(self) -> None:
        """Test creating a meta-prompt context."""
        context = MetaPromptContext(
            issue_context={"type": "database_error", "severity": 8},
            repository_context={"architecture": "microservices"},
            triage_packet={"service": "user_service"},
            historical_logs=["error log 1", "error log 2"],
            configs={"timeout": "30s"},
            flow_id="test_flow_123",
            previous_attempts=[{"attempt": 1, "result": "failed"}],
            validation_feedback={"syntax": "good"},
        )

        assert context.issue_context["type"] == "database_error"
        assert context.repository_context["architecture"] == "microservices"
        assert len(context.historical_logs) == 2
        assert context.flow_id == "test_flow_123"
        assert context.previous_attempts is not None
        assert len(context.previous_attempts) == 1
        assert context.validation_feedback is not None
        assert context.validation_feedback["syntax"] == "good"

    def test_meta_prompt_context_defaults(self) -> None:
        """Test meta-prompt context with default values."""
        context = MetaPromptContext(
            issue_context={},
            repository_context={},
            triage_packet={},
            historical_logs=[],
            configs={},
            flow_id="test_flow_456",
        )

        assert context.previous_attempts is None
        assert context.validation_feedback is None

    def test_meta_prompt_context_to_dict(self) -> None:
        """Test converting meta-prompt context to dictionary."""
        context = MetaPromptContext(
            issue_context={"type": "api_error"},
            repository_context={"framework": "fastapi"},
            triage_packet={"endpoint": "/users"},
            historical_logs=["log1"],
            configs={"rate_limit": "100/min"},
            flow_id="test_flow_789",
        )

        context_dict = context.to_dict()
        assert isinstance(context_dict, dict)
        assert context_dict["flow_id"] == "test_flow_789"
        assert "issue_context" in context_dict
        assert "repository_context" in context_dict


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_validation_result_creation(self) -> None:
        """Test creating a validation result."""
        result = ValidationResult(
            success=True, issues=[], suggestions=["Good prompt"], confidence_score=0.95
        )

        assert result.success is True
        assert len(result.issues) == 0
        assert len(result.suggestions) == 1
        assert result.confidence_score == 0.95

    def test_validation_result_defaults(self) -> None:
        """Test validation result with default values."""
        result = ValidationResult(
            success=False, issues=["Missing context"], suggestions=[]
        )

        assert result.success is False
        assert len(result.issues) == 1
        assert len(result.suggestions) == 0
        assert result.confidence_score == 0.0  # Default value

    def test_validation_result_to_dict(self) -> None:
        """Test converting validation result to dictionary."""
        result = ValidationResult(
            success=True,
            issues=[],
            suggestions=["Well structured"],
            confidence_score=0.9,
        )

        result_dict = result.to_dict()
        assert isinstance(result_dict, dict)
        assert result_dict["success"] is True
        assert result_dict["confidence_score"] == 0.9
        assert "issues" in result_dict
        assert "suggestions" in result_dict
