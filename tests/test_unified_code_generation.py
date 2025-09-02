# tests/test_unified_code_generation.py

"""
Test the unified code generation system integration.

This test verifies that the enhanced analysis agent properly integrates
with specialized code generators to provide enhanced code generation.
"""

import pytest
from unittest.mock import patch
from gemini_sre_agent.ml.enhanced_analysis_agent import (
    EnhancedAnalysisAgent,
    EnhancedAnalysisConfig,
)
from gemini_sre_agent.ml.prompt_context_models import (
    IssueContext,
    IssueType,
)


class TestUnifiedCodeGeneration:
    """Test the unified code generation system."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return EnhancedAnalysisConfig(
            project_id="test-project",
            location="us-central1",
            main_model="gemini-1.5-pro-001",
            meta_model="gemini-1.5-flash-001",
            enable_specialized_generators=True,
            enable_validation=True,
        )

    @pytest.fixture
    def triage_packet(self):
        """Create a test triage packet."""
        return {
            "issue_id": "test-issue-123",
            "affected_files": ["src/api/endpoint.py"],
            "error_patterns": ["database connection failed", "timeout error"],
            "severity_level": 8,
            "impact_analysis": {"user_impact": "high", "business_impact": "critical"},
            "related_services": ["database-service", "api-gateway"],
            "temporal_context": {"first_occurrence": "2024-01-01T00:00:00Z"},
            "user_impact": "API endpoints are failing",
            "business_impact": "Customer requests are timing out",
        }

    @pytest.fixture
    def historical_logs(self):
        """Create test historical logs."""
        return [
            '{"timestamp": "2024-01-01T00:00:00Z", "severity": "ERROR", "message": "Database connection failed"}',
            '{"timestamp": "2024-01-01T00:01:00Z", "severity": "ERROR", "message": "Timeout error in API call"}',
        ]

    @pytest.fixture
    def configs(self):
        """Create test configuration data."""
        return {
            "architecture_type": "microservices",
            "technology_stack": {"database": "postgresql", "framework": "fastapi"},
            "coding_standards": {"style": "black", "linting": "flake8"},
            "error_handling_patterns": ["retry", "circuit_breaker"],
            "testing_patterns": ["pytest", "unittest"],
        }

    @pytest.mark.asyncio
    async def test_enhanced_analysis_agent_initialization(self, config):
        """Test that the enhanced analysis agent initializes correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        assert agent.config.enable_specialized_generators is True
        assert agent.config.enable_validation is True
        assert agent.code_generator_factory is not None
        assert agent.adaptive_strategy is not None
        assert agent.meta_prompt_generator is not None

    @pytest.mark.asyncio
    async def test_issue_classification(self, config):
        """Test that issue classification works correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        triage_packet = {
            "error_patterns": ["database connection failed"],
            "affected_files": ["src/database/connection.py"],
        }
        
        issue_context = agent._extract_issue_context(triage_packet)
        assert issue_context.issue_type == IssueType.DATABASE_ERROR
        assert issue_context.complexity_score > 1

    @pytest.mark.asyncio
    async def test_generator_type_determination(self, config):
        """Test that generator type is determined correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        issue_context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=["src/api/endpoint.py"],
            error_patterns=["rate limit exceeded"],
            severity_level=7,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="API rate limited",
            business_impact="Service degradation",
            complexity_score=6,
            context_richness=0.8,
        )
        
        generator_type = agent._determine_generator_type(issue_context)
        assert generator_type == "api_error"

    @pytest.mark.asyncio
    async def test_context_building(self, config):
        """Test that context is built correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        triage_packet = {
            "affected_files": ["src/api/endpoint.py"],
            "error_patterns": ["authentication failed"],
            "severity_level": 8,
            "impact_analysis": {"user_impact": "high"},
            "related_services": ["auth-service"],
            "temporal_context": {},
            "user_impact": "Authentication failing",
            "business_impact": "Users cannot access service",
        }
        
        historical_logs = ['{"message": "Auth error"}']
        configs = {"technology_stack": {"framework": "fastapi"}}
        
        context = await agent._build_analysis_context(
            triage_packet, historical_logs, configs, "test-flow"
        )
        
        assert context.issue_context.issue_type == IssueType.AUTHENTICATION_ERROR
        assert context.generator_type == "authentication_error"
        assert context.repository_context.technology_stack["framework"] == "fastapi"

    @pytest.mark.asyncio
    async def test_complexity_scoring(self, config):
        """Test that complexity scoring works correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        triage_packet = {
            "affected_files": ["file1.py", "file2.py", "file3.py"],
            "related_services": ["service1", "service2"],
            "severity_level": 9,
        }
        
        complexity_score = agent._calculate_complexity_score(triage_packet)
        assert complexity_score == 6  # 1 + 3 + 2

    @pytest.mark.asyncio
    async def test_context_richness_calculation(self, config):
        """Test that context richness is calculated correctly."""
        agent = EnhancedAnalysisAgent(config)
        
        triage_packet = {
            "affected_files": ["file1.py"],
            "error_patterns": ["error1"],
            "impact_analysis": {"impact": "high"},
            "related_services": ["service1"],
            "temporal_context": {"time": "now"},
        }
        
        richness = agent._calculate_context_richness(triage_packet)
        assert richness == 1.0  # All context elements present

    @pytest.mark.asyncio
    async def test_specialized_generators_disabled(self):
        """Test that specialized generators can be disabled."""
        config = EnhancedAnalysisConfig(
            project_id="test-project",
            location="us-central1",
            enable_specialized_generators=False,
        )
        
        agent = EnhancedAnalysisAgent(config)
        assert agent.code_generator_factory is None

    @pytest.mark.asyncio
    async def test_fallback_analysis(self, config):
        """Test that fallback analysis works when main analysis fails."""
        agent = EnhancedAnalysisAgent(config)
        
        # Mock the main model to fail
        with patch.object(agent.main_model, 'generate_content_async', side_effect=Exception("Model error")):
            result = await agent.analyze_issue(
                {"error_patterns": ["test error"]},
                ["test log"],
                {},
                "test-flow"
            )
            
            assert result.get("fallback") is True
            assert result.get("success") is True


if __name__ == "__main__":
    pytest.main([__file__])
