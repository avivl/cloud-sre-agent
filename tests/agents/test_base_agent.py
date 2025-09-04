# tests/agents/test_base_agent.py

"""
Tests for the enhanced agent base classes.

This module provides comprehensive tests for the BaseAgent class and related
components, including structured output, fallback logic, and statistics collection.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel

from gemini_sre_agent.agents.base import BaseAgent
from gemini_sre_agent.agents.stats import AgentStats
from gemini_sre_agent.agents.response_models import TextResponse


class MockResponseModel(BaseModel):
    """Mock response model for testing."""
    answer: str
    confidence: float


@pytest.fixture
def mock_llm_service():
    """Mock LLM service for testing."""
    service = AsyncMock()
    service.generate_structured = AsyncMock()
    return service


@pytest.fixture
def test_agent(mock_llm_service):
    """Test agent instance."""
    return BaseAgent(
        llm_service=mock_llm_service,
        response_model=MockResponseModel,
        primary_model="smart",
        fallback_model="fast"
    )


class TestAgentStats:
    """Test the AgentStats class."""
    
    def test_stats_initialization(self):
        """Test stats initialization."""
        stats = AgentStats("test_agent")
        assert stats.agent_name == "test_agent"
        assert stats.request_count == 0
        assert stats.success_count == 0
        assert stats.error_count == 0
    
    def test_record_success(self):
        """Test recording successful execution."""
        stats = AgentStats("test_agent")
        stats.record_success("smart", 100, "test_prompt")
        
        assert stats.request_count == 1
        assert stats.success_count == 1
        assert stats.error_count == 0
        assert stats.latencies_ms["smart"] == [100]
        assert stats.model_usage["smart"] == 1
        assert stats.prompt_usage["test_prompt"] == 1
    
    def test_record_error(self):
        """Test recording failed execution."""
        stats = AgentStats("test_agent")
        stats.record_error("smart", "Test error", "test_prompt")
        
        assert stats.request_count == 1
        assert stats.success_count == 0
        assert stats.error_count == 1
        assert stats.errors["smart"] == ["Test error"]
        assert stats.model_usage["smart"] == 1
        assert stats.prompt_usage["test_prompt"] == 1
    
    def test_get_summary(self):
        """Test getting stats summary."""
        stats = AgentStats("test_agent")
        stats.record_success("smart", 100)
        stats.record_success("smart", 200)
        stats.record_error("fast", "Error")
        
        summary = stats.get_summary()
        
        assert summary["agent_name"] == "test_agent"
        assert summary["request_count"] == 3
        assert summary["success_rate"] == 2/3
        assert summary["avg_latency_ms"]["smart"] == 150
        assert summary["model_usage"]["smart"] == 2
        assert summary["model_usage"]["fast"] == 1
        assert summary["error_count_by_model"]["fast"] == 1
    
    def test_reset(self):
        """Test resetting stats."""
        stats = AgentStats("test_agent")
        stats.record_success("smart", 100)
        stats.record_error("fast", "Error")
        
        stats.reset()
        
        assert stats.request_count == 0
        assert stats.success_count == 0
        assert stats.error_count == 0
        assert len(stats.latencies_ms) == 0
        assert len(stats.errors) == 0


class TestBaseAgent:
    """Test the BaseAgent class."""
    
    def test_agent_initialization(self, test_agent):
        """Test agent initialization."""
        assert test_agent.primary_model == "smart"
        assert test_agent.fallback_model == "fast"
        assert test_agent.max_retries == 2
        assert test_agent.collect_stats is True
        assert isinstance(test_agent.stats, AgentStats)
        assert test_agent.stats.agent_name == "BaseAgent"
    
    @pytest.mark.asyncio
    async def test_execute_success(self, test_agent, mock_llm_service):
        """Test successful agent execution."""
        # Setup mock response
        mock_response = MockResponseModel(answer="Test answer", confidence=0.95)
        mock_llm_service.generate_structured.return_value = mock_response
        
        # Mock prompt
        with patch.object(test_agent, '_get_prompt') as mock_get_prompt:
            mock_prompt = MagicMock()
            mock_prompt.format.return_value = "Formatted prompt"
            mock_get_prompt.return_value = mock_prompt
            
            # Execute agent
            result = await test_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"query": "test query"}
            )
        
        # Verify result
        assert result == mock_response
        assert test_agent.stats.success_count == 1
        assert test_agent.stats.error_count == 0
        assert len(test_agent.stats.latencies_ms["smart"]) == 1
    
    @pytest.mark.asyncio
    async def test_execute_fallback(self, test_agent, mock_llm_service):
        """Test agent execution with fallback."""
        # Setup mock to fail on first call, succeed on second
        mock_response = MockResponseModel(answer="Fallback answer", confidence=0.8)
        mock_llm_service.generate_structured.side_effect = [
            Exception("Primary model failed"),
            mock_response
        ]
        
        # Mock prompt
        with patch.object(test_agent, '_get_prompt') as mock_get_prompt:
            mock_prompt = MagicMock()
            mock_prompt.format.return_value = "Formatted prompt"
            mock_get_prompt.return_value = mock_prompt
            
            # Execute agent
            result = await test_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"query": "test query"}
            )
        
        # Verify fallback was used
        assert result == mock_response
        assert test_agent.stats.success_count == 1
        assert test_agent.stats.error_count == 1
        assert len(test_agent.stats.errors["smart"]) == 1
        assert len(test_agent.stats.latencies_ms["fast"]) == 1
    
    @pytest.mark.asyncio
    async def test_execute_no_fallback(self, test_agent, mock_llm_service):
        """Test agent execution without fallback."""
        # Setup mock to fail
        mock_llm_service.generate_structured.side_effect = Exception("API Error")
        
        # Mock prompt
        with patch.object(test_agent, '_get_prompt') as mock_get_prompt:
            mock_prompt = MagicMock()
            mock_prompt.format.return_value = "Formatted prompt"
            mock_get_prompt.return_value = mock_prompt
            
            # Execute agent without fallback
            with pytest.raises(Exception, match="API Error"):
                await test_agent.execute(
                    prompt_name="test_prompt",
                    prompt_args={"query": "test query"},
                    use_fallback=False
                )
        
        # Verify error was recorded
        assert test_agent.stats.success_count == 0
        assert test_agent.stats.error_count == 1
    
    def test_get_stats_summary(self, test_agent):
        """Test getting stats summary."""
        summary = test_agent.get_stats_summary()
        assert summary["agent_name"] == "BaseAgent"
        assert summary["request_count"] == 0
    
    def test_reset_stats(self, test_agent):
        """Test resetting stats."""
        # Add some stats
        test_agent.stats.record_success("smart", 100)
        
        # Reset
        test_agent.reset_stats()
        
        # Verify reset
        assert test_agent.stats.request_count == 0
        assert test_agent.stats.success_count == 0
