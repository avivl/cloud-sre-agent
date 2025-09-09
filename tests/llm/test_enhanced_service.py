# tests/llm/test_enhanced_service.py

"""
Unit tests for the Enhanced LLM Service with intelligent model selection.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import BaseModel

# Mock external dependencies
with patch.dict(
    "sys.modules", {"mirascope": Mock(), "instructor": Mock(), "litellm": Mock()}
):
    from gemini_sre_agent.llm.enhanced_service import EnhancedLLMService

from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig, ModelConfig
from gemini_sre_agent.llm.model_registry import ModelInfo, ModelRegistry
from gemini_sre_agent.llm.model_scorer import ScoringWeights
from gemini_sre_agent.llm.model_selector import SelectionStrategy
from gemini_sre_agent.llm.performance_cache import MetricType, PerformanceMonitor


class MockResponse(BaseModel):
    """Mock response model for structured output."""

    text: str
    confidence: float


class TestEnhancedLLMService:
    """Test the EnhancedLLMService class."""

    def create_test_config(self) -> LLMConfig:
        """Create a test LLM configuration."""
        model_config = ModelConfig(
            name="gpt-4",
            model_type=ModelType.FAST,
            cost_per_1k_tokens=0.001,
            max_tokens=4096,
        )

        provider_config = LLMProviderConfig(
            provider="openai",
            models={"gpt-4": model_config},
            api_key="sk-test-key-123456789",
            base_url=None,
            region=None,
            timeout=30,
            max_retries=3,
            rate_limit=100,
        )

        return LLMConfig(
            providers={"openai": provider_config},
            default_provider="openai",
            default_model_type=ModelType.FAST,
            enable_fallback=True,
            enable_monitoring=True,
        )

    def create_test_model_info(self, name: str, **kwargs) -> ModelInfo:
        """Create a test model info."""
        defaults = {
            "provider": ProviderType.OPENAI,
            "semantic_type": ModelType.FAST,
            "capabilities": set(),
            "cost_per_1k_tokens": 0.001,
            "max_tokens": 4096,
            "context_window": 4096,
            "performance_score": 0.8,
            "reliability_score": 0.9,
            "fallback_models": [],
            "provider_specific": {},
        }
        defaults.update(kwargs)
        return ModelInfo(name=name, **defaults)

    def create_mock_provider(self) -> Mock:
        """Create a mock provider."""
        provider = Mock()
        provider.generate_structured = AsyncMock()
        provider.generate_text = AsyncMock()
        provider.health_check = AsyncMock(return_value=True)
        provider.get_available_models = Mock(return_value=["gpt-4", "gpt-3.5-turbo"])
        provider.estimate_cost = Mock(return_value=0.01)
        provider.validate_config = Mock(return_value=True)
        provider.is_initialized = True
        provider.provider_name = "openai"
        return provider

    def test_service_initialization(self):
        """Test enhanced service initialization."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        assert service.config == config
        # Check that the components are properly initialized
        assert service.model_registry is not None
        assert service.model_selector is not None
        assert service.performance_monitor is not None
        assert len(service._selection_stats) == 0

    def test_service_initialization_with_custom_components(self):
        """Test service initialization with custom components."""
        config = self.create_test_config()
        custom_registry = ModelRegistry()
        custom_monitor = PerformanceMonitor()

        service = EnhancedLLMService(config, custom_registry, custom_monitor)

        assert service.model_registry == custom_registry
        assert service.performance_monitor == custom_monitor

    @pytest.mark.asyncio
    async def test_generate_structured_with_model_selection(self):
        """Test structured generation with intelligent model selection."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_structured.return_value = MockResponse(
            text="Test response", confidence=0.95
        )
        service.providers = {"openai": mock_provider}

        # Add a test model to the registry
        test_model = self.create_test_model_info("gpt-4")
        service.model_registry.register_model(test_model)

        # Mock the model selector
        service.model_selector.select_model_with_fallback = Mock(
            return_value=(test_model, Mock())
        )

        result = await service.generate_structured(
            prompt="Test prompt", response_model=MockResponse, model_type=ModelType.FAST
        )

        assert isinstance(result, MockResponse)
        assert result.text == "Test response"
        assert result.confidence == 0.95

        # Verify provider was called
        mock_provider.generate_structured.assert_called_once()

        # Verify performance metrics were recorded
        assert service.performance_monitor.cache.get_model_stats("gpt-4") is not None

    @pytest.mark.asyncio
    async def test_generate_text_with_model_selection(self):
        """Test text generation with intelligent model selection."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.return_value = "Test response"
        service.providers = {"openai": mock_provider}

        # Add a test model to the registry
        test_model = self.create_test_model_info("gpt-4")
        service.model_registry.register_model(test_model)

        # Mock the model selector
        service.model_selector.select_model_with_fallback = Mock(
            return_value=(test_model, Mock())
        )

        result = await service.generate_text(
            prompt="Test prompt", model_type=ModelType.FAST
        )

        assert result == "Test response"

        # Verify provider was called
        mock_provider.generate_text.assert_called_once()

        # Verify performance metrics were recorded
        assert service.performance_monitor.cache.get_model_stats("gpt-4") is not None

    @pytest.mark.asyncio
    async def test_generate_with_fallback_success(self):
        """Test generation with fallback chain - success case."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock providers
        mock_provider = self.create_mock_provider()
        mock_provider.generate_structured.return_value = MockResponse(
            text="Test response", confidence=0.95
        )
        service.providers = {"openai": mock_provider}

        # Add test models to the registry
        primary_model = self.create_test_model_info("gpt-4")
        fallback_model = self.create_test_model_info("gpt-3.5-turbo")
        service.model_registry.register_model(primary_model)
        service.model_registry.register_model(fallback_model)

        # Mock the model selector to return a fallback chain
        mock_selection_result = Mock()
        mock_selection_result.fallback_chain = [primary_model, fallback_model]
        service.model_selector.select_model = Mock(return_value=mock_selection_result)

        result = await service.generate_with_fallback(
            prompt="Test prompt", response_model=MockResponse, model_type=ModelType.FAST
        )

        assert isinstance(result, MockResponse)
        assert result.text == "Test response"

        # Verify provider was called
        mock_provider.generate_structured.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_fallback_failure(self):
        """Test generation with fallback chain - failure case."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock providers that fail
        mock_provider = self.create_mock_provider()
        mock_provider.generate_structured.side_effect = Exception("Provider error")
        service.providers = {"openai": mock_provider}

        # Add test models to the registry
        primary_model = self.create_test_model_info("gpt-4")
        fallback_model = self.create_test_model_info("gpt-3.5-turbo")
        service.model_registry.register_model(primary_model)
        service.model_registry.register_model(fallback_model)

        # Mock the model selector to return a fallback chain
        mock_selection_result = Mock()
        mock_selection_result.fallback_chain = [primary_model, fallback_model]
        service.model_selector.select_model = Mock(return_value=mock_selection_result)

        # Should raise the last error
        with pytest.raises(Exception, match="Provider error"):
            await service.generate_with_fallback(
                prompt="Test prompt",
                response_model=MockResponse,
                model_type=ModelType.FAST,
                max_attempts=2,
            )

        # Verify provider was called multiple times (once for each model in fallback chain)
        assert mock_provider.generate_structured.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_with_explicit_model(self):
        """Test generation with explicitly specified model."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.return_value = "Test response"
        service.providers = {"openai": mock_provider}

        # Add a test model to the registry
        test_model = self.create_test_model_info("gpt-4")
        service.model_registry.register_model(test_model)

        result = await service.generate_text(prompt="Test prompt", model="gpt-4")

        assert result == "Test response"

        # Verify provider was called with the specific model
        mock_provider.generate_text.assert_called_once()
        call_args = mock_provider.generate_text.call_args
        assert call_args[1]["model"] == "gpt-4"

    @pytest.mark.asyncio
    async def test_generate_with_selection_strategy(self):
        """Test generation with different selection strategies."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.return_value = "Test response"
        service.providers = {"openai": mock_provider}

        # Add test models to the registry
        fast_model = self.create_test_model_info("gpt-3.5-turbo", max_tokens=1000)
        smart_model = self.create_test_model_info("gpt-4", max_tokens=4000)
        service.model_registry.register_model(fast_model)
        service.model_registry.register_model(smart_model)

        # Mock the model selector to return different models based on strategy
        service.model_selector.select_model_with_fallback = Mock(
            side_effect=[
                (fast_model, Mock()),  # For FASTEST strategy
                (smart_model, Mock()),  # For BEST_SCORE strategy
            ]
        )

        # Test FASTEST strategy
        result1 = await service.generate_text(
            prompt="Test prompt", selection_strategy=SelectionStrategy.FASTEST
        )
        assert result1 == "Test response"

        # Test BEST_SCORE strategy
        result2 = await service.generate_text(
            prompt="Test prompt", selection_strategy=SelectionStrategy.BEST_SCORE
        )
        assert result2 == "Test response"

        # Verify provider was called twice
        assert mock_provider.generate_text.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_with_custom_weights(self):
        """Test generation with custom scoring weights."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.return_value = "Test response"
        service.providers = {"openai": mock_provider}

        # Add a test model to the registry
        test_model = self.create_test_model_info("gpt-4")
        service.model_registry.register_model(test_model)

        # Mock the model selector
        service.model_selector.select_model_with_fallback = Mock(
            return_value=(test_model, Mock())
        )

        custom_weights = ScoringWeights(cost=0.8, performance=0.2)

        result = await service.generate_text(
            prompt="Test prompt", custom_weights=custom_weights
        )

        assert result == "Test response"

        # Verify provider was called
        mock_provider.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_cost_constraints(self):
        """Test generation with cost constraints."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.return_value = "Test response"
        service.providers = {"openai": mock_provider}

        # Add test models with different costs
        cheap_model = self.create_test_model_info(
            "gpt-3.5-turbo", cost_per_1k_tokens=0.001
        )
        expensive_model = self.create_test_model_info("gpt-4", cost_per_1k_tokens=0.01)
        service.model_registry.register_model(cheap_model)
        service.model_registry.register_model(expensive_model)

        # Mock the model selector
        service.model_selector.select_model_with_fallback = Mock(
            return_value=(cheap_model, Mock())
        )

        result = await service.generate_text(
            prompt="Test prompt", max_cost=0.005  # Should select cheap model
        )

        assert result == "Test response"

        # Verify provider was called
        mock_provider.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_single_provider(self):
        """Test health check for a single provider."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        mock_provider.health_check.return_value = True
        service.providers = {"openai": mock_provider}

        result = await service.health_check("openai")

        assert result is True
        mock_provider.health_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_check_all_providers(self):
        """Test health check for all providers."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock providers
        mock_provider1 = self.create_mock_provider()
        mock_provider1.health_check.return_value = True
        mock_provider2 = self.create_mock_provider()
        mock_provider2.health_check.return_value = False

        service.providers = {"openai": mock_provider1, "claude": mock_provider2}

        result = await service.health_check()

        assert result is False  # One provider is unhealthy

    def test_get_available_models(self):
        """Test getting available models."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider
        mock_provider = self.create_mock_provider()
        service.providers = {"openai": mock_provider}

        models = service.get_available_models("openai")

        assert "openai" in models
        assert models["openai"] == ["gpt-4", "gpt-3.5-turbo"]

    def test_get_model_performance(self):
        """Test getting model performance metrics."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Add some performance data
        service.performance_monitor.record_latency("gpt-4", 150.0, ProviderType.OPENAI)
        service.performance_monitor.record_success("gpt-4", True, ProviderType.OPENAI)

        performance = service.get_model_performance("gpt-4")

        assert performance["model_name"] == "gpt-4"
        assert "metrics" in performance
        assert MetricType.LATENCY.value in performance["metrics"]

    def test_get_best_models(self):
        """Test getting best performing models."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Add performance data for different models
        service.performance_monitor.record_latency(
            "gpt-3.5-turbo", 100.0, ProviderType.OPENAI
        )
        service.performance_monitor.record_latency("gpt-4", 200.0, ProviderType.OPENAI)

        best_models = service.get_best_models(MetricType.LATENCY, limit=2)

        assert len(best_models) <= 2
        if len(best_models) >= 1:
            assert best_models[0][0] == "gpt-3.5-turbo"  # Lower latency is better

    def test_get_selection_stats(self):
        """Test getting selection statistics."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Add some selection stats
        service._selection_stats["gpt-4:best_score"] = 5
        service._last_selection_time["gpt-4"] = 1234567890.0

        stats = service.get_selection_stats()

        assert "selection_counts" in stats
        assert "last_selection_times" in stats
        assert "performance_cache_stats" in stats
        assert stats["selection_counts"]["gpt-4:best_score"] == 5

    def test_get_model_rankings(self):
        """Test getting model rankings."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Add performance data
        service.performance_monitor.record_latency("gpt-4", 150.0, ProviderType.OPENAI)
        service.performance_monitor.record_throughput(
            "gpt-4", 25.0, ProviderType.OPENAI
        )

        rankings = service.get_model_rankings(
            [MetricType.LATENCY, MetricType.THROUGHPUT]
        )

        assert isinstance(rankings, list)
        if rankings:
            assert isinstance(rankings[0], tuple)
            assert len(rankings[0]) == 2  # (model_name, score)

    @pytest.mark.asyncio
    async def test_error_handling_and_metrics_recording(self):
        """Test error handling and performance metrics recording."""
        config = self.create_test_config()
        service = EnhancedLLMService(config)

        # Mock the provider to raise an error
        mock_provider = self.create_mock_provider()
        mock_provider.generate_text.side_effect = Exception("Test error")
        service.providers = {"openai": mock_provider}

        # Add a test model to the registry
        test_model = self.create_test_model_info("gpt-4")
        service.model_registry.register_model(test_model)

        # Mock the model selector
        service.model_selector.select_model_with_fallback = Mock(
            return_value=(test_model, Mock())
        )

        # Should raise the error
        with pytest.raises(Exception, match="Test error"):
            await service.generate_text(prompt="Test prompt")

        # Verify failure metrics were recorded
        stats = service.performance_monitor.cache.get_model_stats("gpt-4")
        assert stats is not None
        assert stats.metric_counts.get(MetricType.ERROR_RATE, 0) > 0
