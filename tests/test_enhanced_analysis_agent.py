# tests/test_enhanced_analysis_agent.py

"""
Tests for enhanced analysis agent.

This module contains comprehensive tests for the enhanced analysis agent
that integrates dynamic prompt generation with the existing analysis system.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.ml.enhanced_analysis_agent import (
    EnhancedAnalysisAgent,
    EnhancedAnalysisConfig,
)
from gemini_sre_agent.ml.prompt_context_models import IssueType


class TestEnhancedAnalysisConfig:
    """Test EnhancedAnalysisConfig dataclass."""

    def test_config_creation(self) -> None:
        """Test creating an enhanced analysis config."""
        config = EnhancedAnalysisConfig(
            project_id="test-project", location="us-central1"
        )

        assert config.project_id == "test-project"
        assert config.location == "us-central1"
        assert config.main_model == "gemini-1.5-pro-001"
        assert config.meta_model == "gemini-1.5-flash-001"
        assert config.enable_meta_prompt is True
        assert config.enable_validation is True
        assert config.max_retries == 3
        assert config.timeout_seconds == 30

    def test_config_custom_values(self) -> None:
        """Test config with custom values."""
        config = EnhancedAnalysisConfig(
            project_id="custom-project",
            location="us-east1",
            main_model="gemini-1.5-flash-001",
            meta_model="gemini-1.5-pro-001",
            enable_meta_prompt=False,
            enable_validation=False,
            max_retries=5,
            timeout_seconds=60,
        )

        assert config.project_id == "custom-project"
        assert config.location == "us-east1"
        assert config.main_model == "gemini-1.5-flash-001"
        assert config.meta_model == "gemini-1.5-pro-001"
        assert config.enable_meta_prompt is False
        assert config.enable_validation is False
        assert config.max_retries == 5
        assert config.timeout_seconds == 60


class TestEnhancedAnalysisAgent:
    """Test EnhancedAnalysisAgent class."""

    @pytest.fixture
    def config(self) -> None:
        """Create test configuration."""
        return EnhancedAnalysisConfig(project_id="test-project", location="us-central1")

    @pytest.fixture
    def agent(self, config: str) -> None:
        """Create test agent with mocked dependencies."""
        with patch("gemini_sre_agent.ml.enhanced_analysis_agent.GenerativeModel"):
            with patch(
                "gemini_sre_agent.ml.enhanced_analysis_agent.AdaptivePromptStrategy"
            ):
                with patch(
                    "gemini_sre_agent.ml.enhanced_analysis_agent.MetaPromptGenerator"
                ):
                    return EnhancedAnalysisAgent(config)

    def test_agent_initialization(self, config: str) -> None:
        """Test agent initialization."""
        with patch("gemini_sre_agent.ml.enhanced_analysis_agent.GenerativeModel"):
            with patch(
                "gemini_sre_agent.ml.enhanced_analysis_agent.AdaptivePromptStrategy"
            ):
                with patch(
                    "gemini_sre_agent.ml.enhanced_analysis_agent.MetaPromptGenerator"
                ):
                    agent = EnhancedAnalysisAgent(config)

                    assert agent.config == config
                    assert agent.main_model is not None
                    assert agent.meta_model is not None
                    assert agent.adaptive_strategy is not None
                    assert agent.meta_prompt_generator is not None

    def test_classify_issue_type_database(self, agent: str) -> None:
        """Test issue type classification for database errors."""
        triage_packet = {
            "error_patterns": ["database connection timeout", "sql error"],
            "affected_files": ["db.py"],
        }

        issue_type = agent._classify_issue_type(triage_packet)
        assert issue_type == IssueType.DATABASE_ERROR

    def test_classify_issue_type_api(self, agent: str) -> None:
        """Test issue type classification for API errors."""
        triage_packet = {
            "error_patterns": ["api timeout", "http 500"],
            "affected_files": ["api.py"],
        }

        issue_type = agent._classify_issue_type(triage_packet)
        assert issue_type == IssueType.API_ERROR

    def test_classify_issue_type_security(self, agent: str) -> None:
        """Test issue type classification for security errors."""
        triage_packet = {
            "error_patterns": ["security vulnerability", "authentication failed"],
            "affected_files": ["auth.py"],
        }

        issue_type = agent._classify_issue_type(triage_packet)
        assert issue_type == IssueType.SECURITY_ERROR

    def test_classify_issue_type_unknown(self, agent: str) -> None:
        """Test issue type classification for unknown errors."""
        triage_packet = {
            "error_patterns": ["unknown error"],
            "affected_files": ["unknown.py"],
        }

        issue_type = agent._classify_issue_type(triage_packet)
        assert issue_type == IssueType.UNKNOWN

    def test_determine_generator_type(self, agent: str) -> None:
        """Test generator type determination."""
        from gemini_sre_agent.ml.prompt_context_models import IssueContext

        # Test database error
        issue_context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        generator_type = agent._determine_generator_type(issue_context)
        assert generator_type == "database_error"

        # Test API error
        issue_context.issue_type = IssueType.API_ERROR
        generator_type = agent._determine_generator_type(issue_context)
        assert generator_type == "api_error"

        # Test security error
        issue_context.issue_type = IssueType.SECURITY_ERROR
        generator_type = agent._determine_generator_type(issue_context)
        assert generator_type == "security_error"

    def test_calculate_complexity_score(self, agent: str) -> None:
        """Test complexity score calculation."""
        # Simple case
        triage_packet = {
            "affected_files": ["file1.py"],
            "related_services": ["service1"],
            "severity_level": 5,
        }

        score = agent._calculate_complexity_score(triage_packet)
        assert score == 3  # 1 base + 1 file + 1 service

        # Complex case
        triage_packet = {
            "affected_files": ["file1.py", "file2.py", "file3.py"],
            "related_services": ["service1", "service2"],
            "severity_level": 9,
        }

        score = agent._calculate_complexity_score(triage_packet)
        assert score == 8  # 1 base + 3 files + 2 services + 2 high severity

        # Capped case
        triage_packet = {
            "affected_files": ["file1.py"] * 10,
            "related_services": ["service1"] * 10,
            "severity_level": 10,
        }

        score = agent._calculate_complexity_score(triage_packet)
        assert score == 10  # Capped at 10

    def test_calculate_context_richness(self, agent: str) -> None:
        """Test context richness calculation."""
        # Empty case
        triage_packet = {}
        richness = agent._calculate_context_richness(triage_packet)
        assert richness == 0.0

        # Full case
        triage_packet = {
            "affected_files": ["file1.py"],
            "error_patterns": ["error1"],
            "impact_analysis": {"users": 1000},
            "related_services": ["service1"],
            "temporal_context": {"frequency": "high"},
        }

        richness = agent._calculate_context_richness(triage_packet)
        assert richness == 1.0  # All elements present

        # Partial case
        triage_packet = {"affected_files": ["file1.py"], "error_patterns": ["error1"]}

        richness = agent._calculate_context_richness(triage_packet)
        assert richness == 0.4  # 2 out of 5 elements

    def test_extract_issue_context(self, agent: str) -> None:
        """Test issue context extraction."""
        triage_packet = {
            "affected_files": ["db.py", "models.py"],
            "error_patterns": ["connection timeout", "deadlock"],
            "severity_level": 8,
            "impact_analysis": {"affected_users": 1000},
            "related_services": ["user_service", "auth_service"],
            "temporal_context": {"frequency": "high"},
            "user_impact": "Users cannot log in",
            "business_impact": "Revenue loss",
        }

        issue_context = agent._extract_issue_context(triage_packet)

        assert issue_context.affected_files == ["db.py", "models.py"]
        assert issue_context.error_patterns == ["connection timeout", "deadlock"]
        assert issue_context.severity_level == 8
        assert issue_context.impact_analysis["affected_users"] == 1000
        assert issue_context.related_services == ["user_service", "auth_service"]
        assert issue_context.temporal_context["frequency"] == "high"
        assert issue_context.user_impact == "Users cannot log in"
        assert issue_context.business_impact == "Revenue loss"
        assert issue_context.complexity_score > 1
        assert issue_context.context_richness > 0.0

    def test_extract_repository_context(self, agent: str) -> None:
        """Test repository context extraction."""
        configs = {
            "architecture_type": "microservices",
            "technology_stack": {"language": "python", "framework": "fastapi"},
            "coding_standards": {"linting": "pylint"},
            "error_handling_patterns": ["try_catch", "logging"],
            "testing_patterns": ["unit_tests", "integration_tests"],
            "dependency_structure": {"service_a": ["service_b"]},
            "recent_changes": [{"commit": "abc123"}],
            "historical_fixes": [{"issue": "timeout"}],
            "code_quality_metrics": {"complexity": 5.0},
        }

        repo_context = agent._extract_repository_context(configs)

        assert repo_context.architecture_type == "microservices"
        assert repo_context.technology_stack["language"] == "python"
        assert repo_context.coding_standards["linting"] == "pylint"
        assert "try_catch" in repo_context.error_handling_patterns
        assert "unit_tests" in repo_context.testing_patterns
        assert repo_context.dependency_structure["service_a"] == ["service_b"]
        assert len(repo_context.recent_changes) == 1
        assert len(repo_context.historical_fixes) == 1
        assert repo_context.code_quality_metrics["complexity"] == 5.0

    @pytest.mark.asyncio
    async def test_analyze_issue_success(self, agent):
        """Test successful issue analysis."""
        # Mock dependencies
        agent._build_analysis_context = AsyncMock(return_value=Mock())
        agent._generate_optimized_prompt = AsyncMock(return_value="test prompt")
        agent._execute_analysis = AsyncMock(
            return_value={
                "success": True,
                "analysis": {
                    "root_cause_analysis": "Test analysis",
                    "proposed_fix": "Test fix",
                    "code_patch": "Test code",
                },
            }
        )
        agent._validate_and_refine = AsyncMock(
            return_value={
                "success": True,
                "analysis": {
                    "root_cause_analysis": "Test analysis",
                    "proposed_fix": "Test fix",
                    "code_patch": "Test code",
                },
            }
        )

        triage_packet = {"error_patterns": ["test error"]}
        historical_logs = ["log1", "log2"]
        configs = {"test": "config"}
        flow_id = "test_flow_123"

        result = await agent.analyze_issue(
            triage_packet, historical_logs, configs, flow_id
        )

        assert result["success"] is True
        assert "analysis" in result
        assert result["analysis"]["root_cause_analysis"] == "Test analysis"
        assert result["analysis"]["proposed_fix"] == "Test fix"
        assert result["analysis"]["code_patch"] == "Test code"

    @pytest.mark.asyncio
    async def test_analyze_issue_failure(self, agent):
        """Test issue analysis failure with fallback."""
        # Mock dependencies to fail
        agent._build_analysis_context = AsyncMock(side_effect=Exception("Test error"))
        agent._fallback_analysis = AsyncMock(
            return_value={
                "success": True,
                "analysis": {
                    "root_cause_analysis": "Fallback analysis",
                    "proposed_fix": "Fallback fix",
                    "code_patch": "Fallback code",
                },
                "fallback": True,
            }
        )

        triage_packet = {"error_patterns": ["test error"]}
        historical_logs = ["log1", "log2"]
        configs = {"test": "config"}
        flow_id = "test_flow_123"

        result = await agent.analyze_issue(
            triage_packet, historical_logs, configs, flow_id
        )

        assert result["success"] is True
        assert result["fallback"] is True
        assert "analysis" in result

    @pytest.mark.asyncio
    async def test_validate_and_refine_success(self, agent):
        """Test successful validation and refinement."""
        analysis_result = {
            "success": True,
            "analysis": {
                "root_cause_analysis": "Test analysis",
                "proposed_fix": "Test fix",
                "code_patch": "Test code",
            },
        }

        context = Mock()

        result = await agent._validate_and_refine(analysis_result, context)

        assert result["success"] is True
        assert result["analysis"]["root_cause_analysis"] == "Test analysis"
        assert result["analysis"]["proposed_fix"] == "Test fix"
        assert result["analysis"]["code_patch"] == "Test code"

    @pytest.mark.asyncio
    async def test_validate_and_refine_missing_analysis(self, agent):
        """Test validation failure due to missing analysis."""
        analysis_result = {
            "success": True,
            "analysis": {
                "proposed_fix": "Test fix",
                "code_patch": "Test code",
                # Missing root_cause_analysis
            },
        }

        context = Mock()

        result = await agent._validate_and_refine(analysis_result, context)

        assert result["success"] is False
        assert "Missing root cause analysis" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_and_refine_missing_fix(self, agent):
        """Test validation failure due to missing fix."""
        analysis_result = {
            "success": True,
            "analysis": {
                "root_cause_analysis": "Test analysis",
                "code_patch": "Test code",
                # Missing proposed_fix
            },
        }

        context = Mock()

        result = await agent._validate_and_refine(analysis_result, context)

        assert result["success"] is False
        assert "Missing proposed fix" in result["error"]

    @pytest.mark.asyncio
    async def test_validate_and_refine_missing_code_patch(self, agent):
        """Test validation failure due to missing code patch."""
        analysis_result = {
            "success": True,
            "analysis": {
                "root_cause_analysis": "Test analysis",
                "proposed_fix": "Test fix",
                # Missing code_patch
            },
        }

        context = Mock()

        result = await agent._validate_and_refine(analysis_result, context)

        assert result["success"] is False
        assert "Missing code patch" in result["error"]

    @pytest.mark.asyncio
    async def test_fallback_analysis_success(self, agent):
        """Test successful fallback analysis."""
        # Mock the model response
        mock_response = Mock()
        mock_response.text = json.dumps(
            {
                "root_cause_analysis": "Fallback analysis",
                "proposed_fix": "Fallback fix",
                "code_patch": "Fallback code",
            }
        )

        agent.main_model.generate_content_async = AsyncMock(return_value=mock_response)

        triage_packet = {"error_patterns": ["test error"]}
        historical_logs = ["log1", "log2"]
        configs = {"test": "config"}

        result = await agent._fallback_analysis(triage_packet, historical_logs, configs)

        assert result["success"] is True
        assert result["fallback"] is True
        assert result["analysis"]["root_cause_analysis"] == "Fallback analysis"
        assert result["analysis"]["proposed_fix"] == "Fallback fix"
        assert result["analysis"]["code_patch"] == "Fallback code"

    @pytest.mark.asyncio
    async def test_fallback_analysis_failure(self, agent):
        """Test fallback analysis failure."""
        # Mock the model to raise an exception
        agent.main_model.generate_content_async = AsyncMock(
            side_effect=Exception("Model error")
        )

        triage_packet = {"error_patterns": ["test error"]}
        historical_logs = ["log1", "log2"]
        configs = {"test": "config"}

        result = await agent._fallback_analysis(triage_packet, historical_logs, configs)

        assert result["success"] is False
        assert result["fallback"] is True
        assert "Model error" in result["error"]
