"""
Comprehensive tests for the enhanced multi-provider LLM system.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any

from gemini_sre_agent.agents.enhanced_triage_agent import EnhancedTriageAgent
from gemini_sre_agent.agents.enhanced_analysis_agent import EnhancedAnalysisAgent
from gemini_sre_agent.agents.enhanced_remediation_agent import EnhancedRemediationAgent
from gemini_sre_agent.agents.legacy_adapter import (
    LegacyTriageAgentAdapter,
    LegacyAnalysisAgentAdapter,
    LegacyRemediationAgentAdapter,
)
from gemini_sre_agent.llm.config import LLMConfig, ProviderConfig
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal


@pytest.fixture
def mock_llm_config():
    """Create a mock LLM configuration for testing."""
    return LLMConfig(
        providers={
            "test_provider": ProviderConfig(
                provider_type="test",
                base_url="http://localhost:8000",
                models=["test-model-1", "test-model-2"],
                default_model="test-model-1",
            )
        }
    )


@pytest.fixture
def sample_logs():
    """Sample log entries for testing."""
    return [
        "2024-01-15 10:30:15 ERROR [ServiceA] Database connection failed: timeout after 30s",
        "2024-01-15 10:30:16 WARN [ServiceA] Retrying database connection...",
        "2024-01-15 10:30:17 ERROR [ServiceA] Database connection failed again: timeout after 30s",
        "2024-01-15 10:30:18 CRITICAL [ServiceA] Service unavailable - database unreachable",
    ]


class TestEnhancedTriageAgent:
    """Test the enhanced triage agent."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_llm_config):
        """Test agent initialization."""
        agent = EnhancedTriageAgent(
            llm_config=mock_llm_config,
            primary_model="test-model-1",
            fallback_model="test-model-2",
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        assert agent.llm_config == mock_llm_config
        assert agent.optimization_goal == OptimizationGoal.QUALITY

    @pytest.mark.asyncio
    async def test_analyze_logs(self, mock_llm_config, sample_logs):
        """Test log analysis functionality."""
        agent = EnhancedTriageAgent(llm_config=mock_llm_config)
        
        # Mock the process_request method
        with patch.object(agent, 'process_request') as mock_process:
            mock_response = Mock()
            mock_response.severity = "high"
            mock_response.category = "database"
            mock_response.description = "Database connection issues"
            mock_response.suggested_actions = ["Check database connectivity"]
            mock_process.return_value = mock_response
            
            result = await agent.analyze_logs(sample_logs, "test_flow_1")
            
            assert result.severity == "high"
            assert result.category == "database"
            assert "Database connection issues" in result.description
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_legacy_compatibility(self, mock_llm_config, sample_logs):
        """Test legacy compatibility method."""
        agent = EnhancedTriageAgent(llm_config=mock_llm_config)
        
        with patch.object(agent, 'analyze_logs') as mock_analyze:
            mock_response = Mock()
            mock_response.severity = "high"
            mock_response.description = "Test issue"
            mock_analyze.return_value = mock_response
            
            result = await agent.analyze_logs_legacy(sample_logs, "test_flow_1")
            
            assert isinstance(result, dict)
            assert "issue_id" in result
            assert "detected_pattern" in result
            assert result["preliminary_severity_score"] == 8  # high severity


class TestEnhancedAnalysisAgent:
    """Test the enhanced analysis agent."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_llm_config):
        """Test agent initialization."""
        agent = EnhancedAnalysisAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.COST_EFFECTIVE,
            max_cost=0.01,
        )
        
        assert agent.llm_config == mock_llm_config
        assert agent.optimization_goal == OptimizationGoal.COST_EFFECTIVE

    @pytest.mark.asyncio
    async def test_analyze_issue(self, mock_llm_config, sample_logs):
        """Test issue analysis functionality."""
        agent = EnhancedAnalysisAgent(llm_config=mock_llm_config)
        
        triage_packet = {
            "issue_id": "test_issue_1",
            "severity": "high",
            "description": "Database connection failed",
        }
        
        with patch.object(agent, 'process_request') as mock_process:
            mock_response = Mock()
            mock_response.root_cause_analysis = "Database server is down"
            mock_response.proposed_fix = "Restart database service"
            mock_response.priority = "high"
            mock_process.return_value = mock_response
            
            result = await agent.analyze_issue(triage_packet, sample_logs, {}, "test_flow_1")
            
            assert result.root_cause_analysis == "Database server is down"
            assert result.proposed_fix == "Restart database service"
            assert result.priority == "high"


class TestEnhancedRemediationAgent:
    """Test the enhanced remediation agent."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_llm_config):
        """Test agent initialization."""
        agent = EnhancedRemediationAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.HYBRID,
        )
        
        assert agent.llm_config == mock_llm_config
        assert agent.optimization_goal == OptimizationGoal.HYBRID

    @pytest.mark.asyncio
    async def test_create_remediation_plan(self, mock_llm_config):
        """Test remediation plan creation."""
        agent = EnhancedRemediationAgent(llm_config=mock_llm_config)
        
        with patch.object(agent, 'process_request') as mock_process:
            mock_response = Mock()
            mock_response.code_patch = "# Fix database connection\\ndb.reconnect()"
            mock_response.proposed_fix = "Add database reconnection logic"
            mock_response.priority = "medium"
            mock_response.estimated_effort = "2 hours"
            mock_process.return_value = mock_response
            
            result = await agent.create_remediation_plan(
                issue_description="Database connection failed",
                error_context="Connection timeout",
                target_file="app.py",
                analysis_summary="Database server unreachable",
                key_points=["Add retry logic"],
            )
            
            assert "db.reconnect()" in result.code_patch
            assert result.priority == "medium"
            assert result.estimated_effort == "2 hours"


class TestLegacyAdapters:
    """Test legacy adapter functionality."""

    def test_triage_adapter_initialization(self, mock_llm_config):
        """Test triage adapter initialization."""
        adapter = LegacyTriageAgentAdapter(
            project_id="test-project",
            location="us-central1",
            triage_model="test-model",
            llm_config=mock_llm_config,
        )
        
        assert adapter.project_id == "test-project"
        assert adapter.location == "us-central1"
        assert adapter.triage_model == "test-model"
        assert adapter.use_enhanced is True

    def test_analysis_adapter_initialization(self, mock_llm_config):
        """Test analysis adapter initialization."""
        adapter = LegacyAnalysisAgentAdapter(
            project_id="test-project",
            location="us-central1",
            analysis_model="test-model",
            llm_config=mock_llm_config,
        )
        
        assert adapter.project_id == "test-project"
        assert adapter.use_enhanced is True

    def test_remediation_adapter_initialization(self, mock_llm_config):
        """Test remediation adapter initialization."""
        adapter = LegacyRemediationAgentAdapter(
            github_token="test-token",
            repo_name="test/repo",
            llm_config=mock_llm_config,
        )
        
        assert adapter.github_token == "test-token"
        assert adapter.repo_name == "test/repo"
        assert adapter.use_enhanced is True

    @pytest.mark.asyncio
    async def test_legacy_adapter_fallback(self):
        """Test legacy adapter fallback when no LLM config provided."""
        adapter = LegacyTriageAgentAdapter(
            project_id="test-project",
            location="us-central1",
            triage_model="test-model",
            llm_config=None,  # No enhanced config
        )
        
        assert adapter.use_enhanced is False
        assert adapter.enhanced_agent is None


class TestIntegration:
    """Integration tests for the complete system."""

    @pytest.mark.asyncio
    async def test_end_to_end_pipeline(self, mock_llm_config, sample_logs):
        """Test complete end-to-end processing pipeline."""
        # Create agents
        triage_agent = EnhancedTriageAgent(llm_config=mock_llm_config)
        analysis_agent = EnhancedAnalysisAgent(llm_config=mock_llm_config)
        remediation_agent = EnhancedRemediationAgent(llm_config=mock_llm_config)
        
        # Mock responses
        with patch.object(triage_agent, 'process_request') as mock_triage, \
             patch.object(analysis_agent, 'process_request') as mock_analysis, \
             patch.object(remediation_agent, 'process_request') as mock_remediation:
            
            # Setup mock responses
            mock_triage_response = Mock()
            mock_triage_response.severity = "high"
            mock_triage_response.category = "database"
            mock_triage_response.description = "Database connection failed"
            mock_triage.return_value = mock_triage_response
            
            mock_analysis_response = Mock()
            mock_analysis_response.root_cause_analysis = "Database server down"
            mock_analysis_response.proposed_fix = "Restart database"
            mock_analysis_response.priority = "high"
            mock_analysis.return_value = mock_analysis_response
            
            mock_remediation_response = Mock()
            mock_remediation_response.code_patch = "# Database fix"
            mock_remediation_response.proposed_fix = "Add retry logic"
            mock_remediation_response.priority = "medium"
            mock_remediation.return_value = mock_remediation_response
            
            # Execute pipeline
            flow_id = "integration_test_1"
            
            # Step 1: Triage
            triage_result = await triage_agent.analyze_logs(sample_logs, flow_id)
            assert triage_result.severity == "high"
            
            # Step 2: Analysis
            triage_data = {
                "issue_id": "test_issue",
                "severity": triage_result.severity,
                "description": triage_result.description,
            }
            analysis_result = await analysis_agent.analyze_issue(
                triage_data, sample_logs, {}, flow_id
            )
            assert analysis_result.priority == "high"
            
            # Step 3: Remediation
            remediation_result = await remediation_agent.create_remediation_plan(
                issue_description=triage_result.description,
                error_context="Test context",
                target_file="app.py",
                analysis_summary=analysis_result.root_cause_analysis,
                key_points=[analysis_result.proposed_fix],
            )
            assert "Database fix" in remediation_result.code_patch

    @pytest.mark.asyncio
    async def test_legacy_adapter_integration(self, mock_llm_config, sample_logs):
        """Test integration using legacy adapters."""
        # Create legacy adapters
        triage_adapter = LegacyTriageAgentAdapter(
            project_id="test-project",
            location="us-central1",
            triage_model="test-model",
            llm_config=mock_llm_config,
        )
        
        analysis_adapter = LegacyAnalysisAgentAdapter(
            project_id="test-project",
            location="us-central1",
            analysis_model="test-model",
            llm_config=mock_llm_config,
        )
        
        # Mock the enhanced agents
        with patch.object(triage_adapter.enhanced_agent, 'analyze_logs') as mock_triage, \
             patch.object(analysis_adapter.enhanced_agent, 'analyze_issue') as mock_analysis:
            
            mock_triage_response = Mock()
            mock_triage_response.severity = "medium"
            mock_triage_response.description = "Test issue"
            mock_triage.return_value = mock_triage_response
            
            mock_analysis_response = Mock()
            mock_analysis_response.priority = "medium"
            mock_analysis.return_value = mock_analysis_response
            
            # Test legacy interface
            triage_result = await triage_adapter.analyze_logs(sample_logs, "test_flow")
            assert triage_result.severity == "medium"
            
            analysis_result = await analysis_adapter.analyze_issue(
                triage_result, sample_logs, {}, "test_flow"
            )
            assert analysis_result.priority == "medium"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_configuration(self):
        """Test handling of invalid configuration."""
        with pytest.raises(Exception):
            # This should raise an exception due to invalid config
            agent = EnhancedTriageAgent(llm_config=None)

    @pytest.mark.asyncio
    async def test_empty_logs(self, mock_llm_config):
        """Test handling of empty log input."""
        agent = EnhancedTriageAgent(llm_config=mock_llm_config)
        
        with patch.object(agent, 'process_request') as mock_process:
            mock_response = Mock()
            mock_response.severity = "low"
            mock_response.description = "No issues detected"
            mock_process.return_value = mock_response
            
            result = await agent.analyze_logs([], "test_flow")
            assert result.severity == "low"

    @pytest.mark.asyncio
    async def test_network_error_handling(self, mock_llm_config):
        """Test handling of network errors."""
        agent = EnhancedTriageAgent(llm_config=mock_llm_config)
        
        with patch.object(agent, 'process_request') as mock_process:
            mock_process.side_effect = Exception("Network error")
            
            with pytest.raises(Exception):
                await agent.analyze_logs(["test log"], "test_flow")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])