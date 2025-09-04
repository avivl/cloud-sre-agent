"""
Unit tests for the Optimized LLM Service.

Tests the optimized LLM service to ensure it meets performance requirements
and maintains compatibility with the enhanced LLM service.
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel

from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig
from gemini_sre_agent.llm.model_registry import ModelInfo
from gemini_sre_agent.llm.optimized_service import OptimizedLLMService


class TestResponse(BaseModel):
    """Test response model."""
    text: str
    confidence: float


class TestOptimizedLLMService:
    """Test the OptimizedLLMService class."""

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
    def optimized_service(self, mock_llm_config):
        """Create an OptimizedLLMService instance."""
        return OptimizedLLMService(
            mock_llm_config,
            enable_optimizations=True,
            batch_size=5,
            max_wait_ms=10.0,
        )

    @pytest.fixture
    def mock_enhanced_service(self):
        """Create a mock enhanced service."""
        service = AsyncMock()
        service.generate_structured = AsyncMock(return_value=TestResponse(text="test response", confidence=0.9))
        service.generate_text = AsyncMock(return_value="test text response")
        service.model_registry = MagicMock()
        service.model_scorer = MagicMock()
        service.model_selector = MagicMock()
        return service

    @pytest.mark.asyncio
    async def test_initialization(self, optimized_service):
        """Test service initialization."""
        assert optimized_service.config is not None
        assert optimized_service.enable_optimizations is True
        assert optimized_service.performance_optimizer is not None
        assert optimized_service.batch_processor is not None

    @pytest.mark.asyncio
    async def test_generate_structured_with_optimizations(self, optimized_service, mock_enhanced_service):
        """Test structured generation with optimizations enabled."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock the performance optimizer
            mock_model = ModelInfo(
                name="test-model",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.SMART,
                capabilities=["streaming"],
                cost_per_1k_tokens=0.001,
                max_tokens=4096,
                context_window=8192,
                performance_score=0.8,
                reliability_score=0.9,
                fallback_models=[],
            )
            
            optimized_service.performance_optimizer.get_optimized_model_selection = AsyncMock(
                return_value=(mock_model, MagicMock())
            )
            
            result = await optimized_service.generate_structured(
                prompt="Test prompt",
                response_model=TestResponse,
                model_type=ModelType.SMART,
            )
            
            assert isinstance(result, TestResponse)
            assert result.text == "test response"
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_generate_structured_without_optimizations(self, mock_llm_config):
        """Test structured generation with optimizations disabled."""
        service = OptimizedLLMService(mock_llm_config, enable_optimizations=False)
        
        with patch.object(service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service = AsyncMock()
            mock_enhanced_service.generate_structured = AsyncMock(
                return_value=TestResponse(text="test response", confidence=0.9)
            )
            mock_loader.get.return_value = mock_enhanced_service
            
            result = await service.generate_structured(
                prompt="Test prompt",
                response_model=TestResponse,
            )
            
            assert isinstance(result, TestResponse)
            assert result.text == "test response"

    @pytest.mark.asyncio
    async def test_generate_text(self, optimized_service, mock_enhanced_service):
        """Test text generation."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock the performance optimizer
            mock_model = ModelInfo(
                name="test-model",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.SMART,
                capabilities=["streaming"],
                cost_per_1k_tokens=0.001,
                max_tokens=4096,
                context_window=8192,
                performance_score=0.8,
                reliability_score=0.9,
                fallback_models=[],
            )
            
            optimized_service.performance_optimizer.get_optimized_model_selection = AsyncMock(
                return_value=(mock_model, MagicMock())
            )
            
            result = await optimized_service.generate_text(
                prompt="Test prompt",
                model_type=ModelType.SMART,
            )
            
            assert result == "test text response"

    @pytest.mark.asyncio
    async def test_get_available_models(self, optimized_service, mock_enhanced_service):
        """Test getting available models."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock the performance optimizer
            mock_models = [
                ModelInfo(
                    name="model1",
                    provider=ProviderType.GEMINI,
                    semantic_type=ModelType.SMART,
                    capabilities=["streaming"],
                    cost_per_1k_tokens=0.001,
                    max_tokens=4096,
                    context_window=8192,
                    performance_score=0.8,
                    reliability_score=0.9,
                    fallback_models=[],
                ),
                ModelInfo(
                    name="model2",
                    provider=ProviderType.OPENAI,
                    semantic_type=ModelType.FAST,
                    capabilities=["streaming"],
                    cost_per_1k_tokens=0.002,
                    max_tokens=2048,
                    context_window=4096,
                    performance_score=0.7,
                    reliability_score=0.8,
                    fallback_models=[],
                ),
            ]
            
            optimized_service.performance_optimizer.optimized_registry.get_models_by_type = AsyncMock(
                return_value=mock_models
            )
            
            models = await optimized_service.get_available_models(model_type=ModelType.SMART)
            
            assert len(models) == 2
            assert "model1" in models
            assert "model2" in models

    @pytest.mark.asyncio
    async def test_batch_generate_structured(self, optimized_service, mock_enhanced_service):
        """Test batch structured generation."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            requests = [
                {"prompt": "Test prompt 1", "options": {}},
                {"prompt": "Test prompt 2", "options": {}},
                {"prompt": "Test prompt 3", "options": {}},
            ]
            
            # Mock batch processor
            optimized_service.batch_processor.add_operation = AsyncMock(
                side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
            )
            
            results = await optimized_service.batch_generate_structured(
                requests=requests,
                response_model=TestResponse,
            )
            
            assert len(results) == 3
            assert all(isinstance(result, TestResponse) for result in results)

    @pytest.mark.asyncio
    async def test_batch_generate_structured_without_optimizations(self, mock_llm_config):
        """Test batch generation without optimizations (sequential fallback)."""
        service = OptimizedLLMService(mock_llm_config, enable_optimizations=False)
        
        with patch.object(service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service = AsyncMock()
            mock_enhanced_service.generate_structured = AsyncMock(
                return_value=TestResponse(text="test response", confidence=0.9)
            )
            mock_loader.get.return_value = mock_enhanced_service
            
            requests = [
                {"prompt": "Test prompt 1", "options": {}},
                {"prompt": "Test prompt 2", "options": {}},
            ]
            
            results = await service.batch_generate_structured(
                requests=requests,
                response_model=TestResponse,
            )
            
            assert len(results) == 2
            assert all(isinstance(result, TestResponse) for result in results)

    def test_get_performance_stats(self, optimized_service):
        """Test getting performance statistics."""
        stats = optimized_service.get_performance_stats()
        
        assert "total_operations" in stats
        assert "optimizations_enabled" in stats
        assert "operation_times" in stats
        assert stats["optimizations_enabled"] is True

    @pytest.mark.asyncio
    async def test_health_check(self, optimized_service, mock_enhanced_service):
        """Test health check."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            health = await optimized_service.health_check()
            
            assert "status" in health
            assert "initialization_time_ms" in health
            assert "optimizations_enabled" in health
            assert "performance_stats" in health

    @pytest.mark.asyncio
    async def test_clear_caches(self, optimized_service):
        """Test clearing caches."""
        # Mock the cache clear methods
        optimized_service.performance_optimizer.model_selection_cache._cache.clear = AsyncMock()
        optimized_service.performance_optimizer.optimized_registry._model_cache.clear = AsyncMock()
        
        await optimized_service.clear_caches()
        
        # Verify cache clear methods were called
        optimized_service.performance_optimizer.model_selection_cache._cache.clear.assert_called_once()
        optimized_service.performance_optimizer.optimized_registry._model_cache.clear.assert_called_once()

    @pytest.mark.asyncio
    async def test_warmup(self, optimized_service, mock_enhanced_service):
        """Test service warmup."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service.model_registry.get_model = MagicMock(return_value=ModelInfo(
                name="test-model",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.SMART,
                capabilities=["streaming"],
                cost_per_1k_tokens=0.001,
                max_tokens=4096,
                context_window=8192,
                performance_score=0.8,
                reliability_score=0.9,
                fallback_models=[],
            ))
            mock_enhanced_service.model_scorer.score_model = MagicMock(return_value=MagicMock())
            mock_loader.get.return_value = mock_enhanced_service
            
            await optimized_service.warmup()
            
            # Verify warmup completed without errors
            assert True  # If we get here, warmup succeeded

    @pytest.mark.asyncio
    async def test_performance_tracking(self, optimized_service, mock_enhanced_service):
        """Test that performance is tracked correctly."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock the performance optimizer
            mock_model = ModelInfo(
                name="test-model",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.SMART,
                capabilities=["streaming"],
                cost_per_1k_tokens=0.001,
                max_tokens=4096,
                context_window=8192,
                performance_score=0.8,
                reliability_score=0.9,
                fallback_models=[],
            )
            
            optimized_service.performance_optimizer.get_optimized_model_selection = AsyncMock(
                return_value=(mock_model, MagicMock())
            )
            
            # Perform an operation
            await optimized_service.generate_structured(
                prompt="Test prompt",
                response_model=TestResponse,
            )
            
            # Check that performance was tracked
            stats = optimized_service.get_performance_stats()
            assert stats["total_operations"] > 0
            assert "generate_structured" in stats["operation_times"]

    @pytest.mark.asyncio
    async def test_error_handling(self, optimized_service):
        """Test error handling in optimized service."""
        with patch.object(optimized_service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service = AsyncMock()
            mock_enhanced_service.generate_structured = AsyncMock(
                side_effect=Exception("Test error")
            )
            mock_loader.get.return_value = mock_enhanced_service
            
            with pytest.raises(Exception, match="Test error"):
                await optimized_service.generate_structured(
                    prompt="Test prompt",
                    response_model=TestResponse,
                )
            
            # Check that error was tracked
            stats = optimized_service.get_performance_stats()
            assert "generate_structured_error" in stats["operation_times"]


class TestPerformanceBenchmarks:
    """Test performance benchmarks for the optimized service."""

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
        """Test that service initialization is fast."""
        start_time = time.time()
        service = OptimizedLLMService(mock_llm_config, enable_optimizations=True)
        init_time = (time.time() - start_time) * 1000
        
        assert init_time < 10.0, f"Initialization took {init_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_operation_overhead(self, mock_llm_config):
        """Test that operation overhead is minimal."""
        service = OptimizedLLMService(mock_llm_config, enable_optimizations=True)
        
        with patch.object(service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service = AsyncMock()
            mock_enhanced_service.generate_structured = AsyncMock(
                return_value=TestResponse(text="test response", confidence=0.9)
            )
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock the performance optimizer to return quickly
            mock_model = ModelInfo(
                name="test-model",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.SMART,
                capabilities=["streaming"],
                cost_per_1k_tokens=0.001,
                max_tokens=4096,
                context_window=8192,
                performance_score=0.8,
                reliability_score=0.9,
                fallback_models=[],
            )
            
            service.performance_optimizer.get_optimized_model_selection = AsyncMock(
                return_value=(mock_model, MagicMock())
            )
            
            # Measure operation overhead
            start_time = time.time()
            await service.generate_structured(
                prompt="Test prompt",
                response_model=TestResponse,
            )
            operation_time = (time.time() - start_time) * 1000
            
            # The overhead should be minimal (excluding the actual LLM call)
            assert operation_time < 10.0, f"Operation overhead was {operation_time:.2f}ms, expected < 10ms"

    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, mock_llm_config):
        """Test that batch processing is efficient."""
        service = OptimizedLLMService(mock_llm_config, enable_optimizations=True, batch_size=10)
        
        with patch.object(service, '_enhanced_service_loader') as mock_loader:
            mock_enhanced_service = AsyncMock()
            mock_enhanced_service.generate_structured = AsyncMock(
                return_value=TestResponse(text="test response", confidence=0.9)
            )
            mock_loader.get.return_value = mock_enhanced_service
            
            # Mock batch processor to simulate concurrent execution
            service.batch_processor.add_operation = AsyncMock(
                side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
            )
            
            requests = [{"prompt": f"Test prompt {i}", "options": {}} for i in range(20)]
            
            start_time = time.time()
            results = await service.batch_generate_structured(
                requests=requests,
                response_model=TestResponse,
            )
            batch_time = (time.time() - start_time) * 1000
            
            assert len(results) == 20
            # Batch processing should be more efficient than sequential
            assert batch_time < 100.0, f"Batch processing took {batch_time:.2f}ms, expected < 100ms"
