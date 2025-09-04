"""
Unit tests for the Optimized Base Agent.

Tests the optimized base agent to ensure it meets performance requirements
and maintains compatibility with the enhanced base agent.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from gemini_sre_agent.agents.optimized_base import OptimizedBaseAgent
from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal


class TestResponse(BaseModel):
    """Test response model."""

    text: str
    confidence: float


class TestOptimizedBaseAgent:
    """Test the OptimizedBaseAgent class."""

    @pytest.fixture
    def mock_llm_config(self):
        """Create a mock LLMConfig."""
        return LLMConfig(
            default_provider=ProviderType.GEMINI,
            default_model_type=ModelType.SMART,
            enable_fallback=True,
            enable_monitoring=True,
            providers={
                ProviderType.GEMINI: LLMProviderConfig(
                    provider=ProviderType.GEMINI,
                    api_key="test_key",
                    base_url="https://api.gemini.com",
                    timeout=30,
                    max_retries=3,
                    rate_limit=100,
                ),
            },
        )

    @pytest.fixture
    def optimized_agent(self, mock_llm_config):
        """Create an OptimizedBaseAgent instance."""
        return OptimizedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TestResponse,
            optimization_goal=OptimizationGoal.HYBRID,
            enable_optimizations=True,
            batch_size=5,
            max_wait_ms=10.0,
        )

    @pytest.fixture
    def mock_llm_service(self):
        """Create a mock optimized LLM service."""
        service = AsyncMock()
        service.generate_structured = AsyncMock(
            return_value=TestResponse(text="test response", confidence=0.9)
        )
        service.batch_generate_structured = AsyncMock(
            return_value=[
                TestResponse(text="test response 1", confidence=0.9),
                TestResponse(text="test response 2", confidence=0.8),
            ]
        )
        service.get_available_models = AsyncMock(return_value=["model1", "model2"])
        service.get_performance_stats = MagicMock(return_value={"total_operations": 10})
        service.health_check = AsyncMock(return_value={"status": "healthy"})
        service.warmup = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_initialization(self, optimized_agent):
        """Test agent initialization."""
        assert optimized_agent.llm_config is not None
        assert optimized_agent.response_model == TestResponse
        assert optimized_agent.optimization_goal == OptimizationGoal.HYBRID
        assert optimized_agent.enable_optimizations is True
        assert optimized_agent.llm_service is not None
        assert optimized_agent.stats is not None

    @pytest.mark.asyncio
    async def test_execute_with_optimizations(self, optimized_agent, mock_llm_service):
        """Test execute method with optimizations enabled."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            result = await optimized_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test input"},
                model_type=ModelType.SMART,
            )

            assert isinstance(result, TestResponse)
            assert result.text == "test response"
            assert result.confidence == 0.9

            # Verify LLM service was called
            mock_llm_service.generate_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_with_fallback(self, optimized_agent, mock_llm_service):
        """Test execute method with fallback handling."""
        # Mock first call to fail, second to succeed
        mock_llm_service.generate_structured = AsyncMock(
            side_effect=[
                Exception("Primary model failed"),
                TestResponse(text="fallback response", confidence=0.8),
            ]
        )

        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            optimized_agent.fallback_model = "fallback-model"

            result = await optimized_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test input"},
                model="primary-model",
                use_fallback=True,
            )

            assert isinstance(result, TestResponse)
            assert result.text == "fallback response"
            assert result.confidence == 0.8

            # Verify both calls were made
            assert mock_llm_service.generate_structured.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_provider_fallback(
        self, optimized_agent, mock_llm_service
    ):
        """Test execute method with provider fallback."""
        # Mock first call to fail, second to succeed
        mock_llm_service.generate_structured = AsyncMock(
            side_effect=[
                Exception("Provider failed"),
                TestResponse(text="alternative response", confidence=0.7),
            ]
        )

        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            optimized_agent.provider_preference = [
                ProviderType.GEMINI,
                ProviderType.OPENAI,
            ]

            result = await optimized_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test input"},
                provider=ProviderType.GEMINI,
                use_fallback=True,
            )

            assert isinstance(result, TestResponse)
            assert result.text == "alternative response"
            assert result.confidence == 0.7

            # Verify both calls were made
            assert mock_llm_service.generate_structured.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_execute(self, optimized_agent, mock_llm_service):
        """Test batch execute method."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            requests = [
                {
                    "prompt_name": "test_prompt",
                    "prompt_args": {"input": "test input 1"},
                },
                {
                    "prompt_name": "test_prompt",
                    "prompt_args": {"input": "test input 2"},
                },
            ]

            results = await optimized_agent.batch_execute(requests)

            assert len(results) == 2
            assert all(isinstance(result, TestResponse) for result in results)
            assert results[0].text == "test response 1"
            assert results[1].text == "test response 2"

            # Verify batch service was called
            mock_llm_service.batch_generate_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_available_models(self, optimized_agent, mock_llm_service):
        """Test getting available models."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            models = await optimized_agent.get_available_models()

            assert models == ["model1", "model2"]
            mock_llm_service.get_available_models.assert_called_once()

    def test_get_available_providers(self, optimized_agent):
        """Test getting available providers."""
        providers = asyncio.run(optimized_agent.get_available_providers())

        assert len(providers) > 0
        assert ProviderType.GEMINI in providers

    def test_update_optimization_goal(self, optimized_agent):
        """Test updating optimization goal."""
        original_goal = optimized_agent.optimization_goal
        optimized_agent.update_optimization_goal(OptimizationGoal.COST_OPTIMIZED)

        assert optimized_agent.optimization_goal == OptimizationGoal.COST_OPTIMIZED
        assert optimized_agent.optimization_goal != original_goal

    def test_update_provider_preference(self, optimized_agent):
        """Test updating provider preference."""
        new_providers = [ProviderType.OPENAI, ProviderType.CLAUDE]
        optimized_agent.update_provider_preference(new_providers)

        assert optimized_agent.provider_preference == new_providers

    def test_update_cost_constraints(self, optimized_agent):
        """Test updating cost constraints."""
        optimized_agent.update_cost_constraints(
            max_cost=0.01,
            min_performance=0.8,
            min_quality=0.7,
        )

        assert optimized_agent.max_cost == 0.01
        assert optimized_agent.min_performance == 0.8
        assert optimized_agent.min_quality == 0.7

    def test_get_performance_stats(self, optimized_agent, mock_llm_service):
        """Test getting performance statistics."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            stats = optimized_agent.get_performance_stats()

            assert "agent_stats" in stats
            assert "llm_service_stats" in stats
            assert "operation_times" in stats
            assert "conversation_length" in stats
            assert "cached_models" in stats
            assert "optimization_goal" in stats
            assert "provider_preference" in stats
            assert "constraints" in stats
            assert "optimizations_enabled" in stats

    def test_conversation_context(self, optimized_agent, mock_llm_service):
        """Test conversation context management."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            # Initial context should be empty
            context = optimized_agent.get_conversation_context()
            assert len(context) == 0

            # Clear context
            optimized_agent.clear_conversation_context()
            context = optimized_agent.get_conversation_context()
            assert len(context) == 0

    @pytest.mark.asyncio
    async def test_warmup(self, optimized_agent, mock_llm_service):
        """Test agent warmup."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            await optimized_agent.warmup()

            # Verify warmup was called on the LLM service
            mock_llm_service.warmup.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check(self, optimized_agent, mock_llm_service):
        """Test health check."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            health = await optimized_agent.health_check()

            assert "agent_name" in health
            assert "status" in health
            assert "llm_service" in health
            assert "performance_stats" in health
            assert health["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_performance_tracking(self, optimized_agent, mock_llm_service):
        """Test that performance is tracked correctly."""
        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            # Perform an operation
            await optimized_agent.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test input"},
            )

            # Check that performance was tracked
            stats = optimized_agent.get_performance_stats()
            assert "operation_times" in stats
            # The operation should be tracked in the stats

    @pytest.mark.asyncio
    async def test_error_handling(self, optimized_agent, mock_llm_service):
        """Test error handling in optimized agent."""
        # Mock the service to raise an exception
        mock_llm_service.generate_structured = AsyncMock(
            side_effect=Exception("Test error")
        )

        with patch.object(optimized_agent, "llm_service", mock_llm_service):
            with pytest.raises(Exception, match="Test error"):
                await optimized_agent.execute(
                    prompt_name="test_prompt",
                    prompt_args={"input": "test input"},
                    use_fallback=False,  # Disable fallback to test error propagation
                )

    def test_prompt_caching(self, optimized_agent):
        """Test that prompts are cached."""
        # Get a prompt twice
        prompt1 = optimized_agent._get_prompt("test_prompt")
        prompt2 = optimized_agent._get_prompt("test_prompt")

        # Should be the same object (cached)
        assert prompt1 is prompt2
        assert "test_prompt" in optimized_agent._prompts

    def test_default_prompt_creation(self, optimized_agent):
        """Test default prompt creation."""
        prompt = optimized_agent._create_default_prompt("generate_text")
        assert "Generate text based on the following input" in prompt

        prompt = optimized_agent._create_default_prompt("unknown_prompt")
        assert "Please process the following" in prompt


class TestPerformanceBenchmarks:
    """Test performance benchmarks for the optimized agent."""

    @pytest.fixture
    def mock_llm_config(self):
        """Create a mock LLMConfig."""
        return LLMConfig(
            default_provider=ProviderType.GEMINI,
            default_model_type=ModelType.SMART,
            enable_fallback=True,
            enable_monitoring=True,
            providers={
                ProviderType.GEMINI: LLMProviderConfig(
                    provider=ProviderType.GEMINI,
                    api_key="test_key",
                    base_url="https://api.gemini.com",
                    timeout=30,
                    max_retries=3,
                    rate_limit=100,
                ),
            },
        )

    @pytest.mark.asyncio
    async def test_initialization_performance(self, mock_llm_config):
        """Test that agent initialization is fast."""
        start_time = time.time()
        OptimizedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TestResponse,
            enable_optimizations=True,
        )
        init_time = (time.time() - start_time) * 1000

        assert (
            init_time < 10.0
        ), f"Initialization took {init_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_execute_overhead(self, mock_llm_config):
        """Test that execute method overhead is minimal."""
        agent = OptimizedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TestResponse,
            enable_optimizations=True,
        )

        mock_llm_service = AsyncMock()
        mock_llm_service.generate_structured = AsyncMock(
            return_value=TestResponse(text="test response", confidence=0.9)
        )

        with patch.object(agent, "llm_service", mock_llm_service):
            # Measure operation overhead
            start_time = time.time()
            await agent.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test input"},
            )
            operation_time = (time.time() - start_time) * 1000

            # The overhead should be minimal (excluding the actual LLM call)
            assert (
                operation_time < 10.0
            ), f"Operation overhead was {operation_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_batch_execute_performance(self, mock_llm_config):
        """Test that batch execution is efficient."""
        agent = OptimizedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TestResponse,
            enable_optimizations=True,
            batch_size=10,
        )

        mock_llm_service = AsyncMock()
        mock_llm_service.batch_generate_structured = AsyncMock(
            return_value=[
                TestResponse(text=f"test response {i}", confidence=0.9)
                for i in range(20)
            ]
        )

        with patch.object(agent, "llm_service", mock_llm_service):
            requests = [
                {
                    "prompt_name": "test_prompt",
                    "prompt_args": {"input": f"test input {i}"},
                }
                for i in range(20)
            ]

            start_time = time.time()
            results = await agent.batch_execute(requests)
            batch_time = (time.time() - start_time) * 1000

            assert len(results) == 20
            # Batch processing should be more efficient than sequential
            assert (
                batch_time < 100.0
            ), f"Batch processing took {batch_time:.2f}ms, expected < 100ms"

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, mock_llm_config):
        """Test that concurrent executions work efficiently."""
        agent = OptimizedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TestResponse,
            enable_optimizations=True,
        )

        mock_llm_service = AsyncMock()
        mock_llm_service.generate_structured = AsyncMock(
            return_value=TestResponse(text="test response", confidence=0.9)
        )

        with patch.object(agent, "llm_service", mock_llm_service):
            # Execute multiple operations concurrently
            start_time = time.time()
            tasks = [
                agent.execute(
                    prompt_name="test_prompt",
                    prompt_args={"input": f"test input {i}"},
                )
                for i in range(10)
            ]
            results = await asyncio.gather(*tasks)
            concurrent_time = (time.time() - start_time) * 1000

            assert len(results) == 10
            assert all(isinstance(result, TestResponse) for result in results)
            # Concurrent execution should be efficient
            assert (
                concurrent_time < 50.0
            ), f"Concurrent execution took {concurrent_time:.2f}ms, expected < 50ms"
