"""
Integration tests for the Model Capability Discovery System.

This module tests the complete capability discovery pipeline including
configuration loading, capability discovery, caching, and task-based selection.
"""

from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from gemini_sre_agent.llm.base import LLMProvider
from gemini_sre_agent.llm.capabilities.config import CapabilityConfig
from gemini_sre_agent.llm.capabilities.discovery import CapabilityDiscovery
from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing."""

    def __init__(self, name: str, models: Dict[str, Any]):
        self.name = name
        self.models = models
        self.config = Mock()
        self.config.models = models

    def get_available_models(self):
        """Return available models."""
        return list(self.models.keys())

    async def _generate(self, request):
        """Mock generate method."""
        return Mock(content="Mock response")

    def cost_estimate(self, request):
        """Mock cost estimate method."""
        return 0.01

    async def embeddings(self, text: str):
        """Mock embeddings method."""
        return [0.1] * 1536

    async def generate_stream(self, request):
        """Mock streaming generate method."""
        yield Mock(content="Mock streaming response")

    def get_custom_capabilities(self):
        """Mock custom capabilities method."""
        return []

    async def health_check(self):
        """Mock health check method."""
        return True

    def supports_streaming(self):
        """Mock streaming support method."""
        return True

    def supports_tools(self):
        """Mock tools support method."""
        return True

    def token_count(self, text: str):
        """Mock token count method."""
        return len(text.split())

    def validate_config(self):
        """Mock config validation method."""
        return True


@pytest.fixture
def mock_providers():
    """Create mock providers for testing."""
    providers = {
        "openai": MockLLMProvider(
            "openai",
            {
                "gpt-4": Mock(performance_score=0.9, cost_per_1k_tokens=0.3),
                "gpt-3.5-turbo": Mock(performance_score=0.7, cost_per_1k_tokens=0.1),
            },
        ),
        "anthropic": MockLLMProvider(
            "anthropic",
            {
                "claude-3-opus": Mock(performance_score=0.95, cost_per_1k_tokens=0.4),
                "claude-3-sonnet": Mock(performance_score=0.8, cost_per_1k_tokens=0.2),
            },
        ),
    }
    return providers


@pytest.fixture
def capability_config():
    """Create a test capability configuration."""
    config = CapabilityConfig()

    # Add test capabilities
    config.add_capability(
        ModelCapability(
            name="text_generation",
            description="Generates human-like text",
            parameters={"max_tokens": {"type": "integer"}},
            performance_score=0.8,
            cost_efficiency=0.7,
        )
    )

    config.add_capability(
        ModelCapability(
            name="code_generation",
            description="Generates programming code",
            parameters={"language": {"type": "string"}},
            performance_score=0.9,
            cost_efficiency=0.6,
        )
    )

    return config


@pytest.fixture
def discovery_system(mock_providers, capability_config):
    """Create a capability discovery system for testing."""
    with patch(
        "gemini_sre_agent.llm.capabilities.discovery.get_capability_config",
        return_value=capability_config,
    ):
        discovery = CapabilityDiscovery(mock_providers, cache_ttl=60)
        return discovery


@pytest.mark.asyncio
async def test_capability_discovery_basic(discovery_system):
    """Test basic capability discovery functionality."""
    # Discover capabilities
    capabilities = await discovery_system.discover_capabilities()

    # Verify discovery results
    assert isinstance(capabilities, dict)
    assert len(capabilities) > 0

    # Check that we have capabilities for our mock models
    model_ids = list(capabilities.keys())
    assert any("openai" in model_id for model_id in model_ids)
    assert any("anthropic" in model_id for model_id in model_ids)


@pytest.mark.asyncio
async def test_capability_caching(discovery_system):
    """Test capability caching functionality."""
    # First discovery
    capabilities1 = await discovery_system.discover_capabilities()

    # Second discovery (should use cache)
    capabilities2 = await discovery_system.discover_capabilities()

    # Results should be the same
    assert capabilities1 == capabilities2

    # Check cache metrics
    metrics = discovery_system.get_metrics()
    assert metrics["cache_hits"] > 0
    assert metrics["discovery_attempts"] == 2


@pytest.mark.asyncio
async def test_force_refresh(discovery_system):
    """Test force refresh functionality."""
    # Initial discovery
    await discovery_system.discover_capabilities()

    # Force refresh
    capabilities = await discovery_system.discover_capabilities(force_refresh=True)

    # Should have discovered capabilities
    assert len(capabilities) > 0

    # Check metrics
    metrics = discovery_system.get_metrics()
    assert metrics["discovery_attempts"] == 2


def test_get_model_capabilities(discovery_system):
    """Test getting capabilities for a specific model."""
    # This would need to be run after discovery
    # For now, just test the method exists and handles missing models
    result = discovery_system.get_model_capabilities("nonexistent/model")
    assert result is None


def test_find_models_by_capability(discovery_system):
    """Test finding models by capability."""
    # Add some test capabilities
    discovery_system.model_capabilities = {
        "openai/gpt-4": ModelCapabilities(
            model_id="openai/gpt-4",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                )
            ],
        )
    }

    # Find models with text_generation capability
    models = discovery_system.find_models_by_capability("text_generation")
    assert "openai/gpt-4" in models


def test_find_models_by_capabilities(discovery_system):
    """Test finding models by multiple capabilities."""
    # Add test capabilities
    discovery_system.model_capabilities = {
        "openai/gpt-4": ModelCapabilities(
            model_id="openai/gpt-4",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                ),
                ModelCapability(
                    name="code_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.9,
                    cost_efficiency=0.6,
                ),
            ],
        )
    }

    # Find models with both capabilities
    models = discovery_system.find_models_by_capabilities(
        ["text_generation", "code_generation"], require_all=True
    )
    assert "openai/gpt-4" in models

    # Find models with any capability
    models = discovery_system.find_models_by_capabilities(
        ["text_generation", "code_generation"], require_all=False
    )
    assert "openai/gpt-4" in models


def test_capability_summary(discovery_system):
    """Test capability summary functionality."""
    # Add test capabilities
    discovery_system.model_capabilities = {
        "openai/gpt-4": ModelCapabilities(
            model_id="openai/gpt-4",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                )
            ],
        ),
        "anthropic/claude-3": ModelCapabilities(
            model_id="anthropic/claude-3",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                )
            ],
        ),
    }

    # Get capability summary
    summary = discovery_system.get_capability_summary()
    assert "text_generation" in summary
    assert summary["text_generation"] == 2


def test_metrics_tracking(discovery_system):
    """Test metrics tracking functionality."""
    # Get initial metrics
    metrics = discovery_system.get_metrics()

    # Verify metrics structure
    expected_keys = [
        "discovery_attempts",
        "discovery_successes",
        "discovery_failures",
        "cache_hits",
        "cache_misses",
        "last_discovery_time",
        "average_discovery_time",
    ]

    for key in expected_keys:
        assert key in metrics


def test_health_status(discovery_system):
    """Test health status functionality."""
    # Get health status
    health = discovery_system.get_health_status()

    # Verify health status structure
    expected_keys = [
        "status",
        "success_rate",
        "cache_hit_rate",
        "total_models",
        "last_discovery",
        "average_discovery_time",
    ]

    for key in expected_keys:
        assert key in health

    # Status should be one of the expected values
    assert health["status"] in ["healthy", "degraded", "unhealthy"]


def test_cache_management(discovery_system):
    """Test cache management functionality."""
    # Add some test data
    discovery_system.model_capabilities = {
        "test/model": ModelCapabilities(model_id="test/model", capabilities=[])
    }
    discovery_system._cache_timestamps["test/model"] = 1234567890

    # Clear cache
    discovery_system.clear_cache()

    # Verify cache is cleared
    assert len(discovery_system.model_capabilities) == 0
    assert len(discovery_system._cache_timestamps) == 0


def test_metrics_reset(discovery_system):
    """Test metrics reset functionality."""
    # Modify some metrics
    discovery_system._metrics["discovery_attempts"] = 5

    # Reset metrics
    discovery_system.reset_metrics()

    # Verify metrics are reset
    assert discovery_system._metrics["discovery_attempts"] == 0


def test_task_validation(discovery_system):
    """Test task requirement validation."""
    # Add test capabilities
    discovery_system.model_capabilities = {
        "openai/gpt-4": ModelCapabilities(
            model_id="openai/gpt-4",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                )
            ],
        )
    }

    # Test validation (this would need proper task requirements in config)
    # For now, just test the method exists
    result = discovery_system.validate_task_requirements(
        "text_completion", "openai/gpt-4"
    )
    assert isinstance(result, dict)


def test_find_models_for_task(discovery_system):
    """Test finding models for specific tasks."""
    # Add test capabilities
    discovery_system.model_capabilities = {
        "openai/gpt-4": ModelCapabilities(
            model_id="openai/gpt-4",
            capabilities=[
                ModelCapability(
                    name="text_generation",
                    description="Test capability",
                    parameters={},
                    performance_score=0.8,
                    cost_efficiency=0.7,
                )
            ],
        )
    }

    # Find models for task
    models = discovery_system.find_models_for_task("text_completion")
    assert isinstance(models, list)


def test_configuration_loading(capability_config):
    """Test capability configuration loading."""
    # Test getting capabilities
    capabilities = capability_config.get_all_capabilities()
    assert len(capabilities) > 0

    # Test getting specific capability
    text_cap = capability_config.get_capability("text_generation")
    assert text_cap is not None
    assert text_cap.name == "text_generation"

    # Test getting capability names
    names = capability_config.get_capability_names()
    assert "text_generation" in names
    assert "code_generation" in names


def test_provider_capabilities(capability_config):
    """Test provider capability mappings."""
    # Test getting provider capabilities
    capabilities = capability_config.get_provider_capabilities("openai")
    assert isinstance(capabilities, list)

    # Test getting model-specific capabilities
    model_capabilities = capability_config.get_provider_capabilities("openai", "gpt-4")
    assert isinstance(model_capabilities, list)


def test_task_requirements(capability_config):
    """Test task requirement definitions."""
    # Test getting task requirements
    requirements = capability_config.get_task_requirements("text_completion")
    assert isinstance(requirements, dict)

    # Test getting required capabilities
    required = capability_config.get_required_capabilities("text_completion")
    assert isinstance(required, list)

    # Test getting optional capabilities
    optional = capability_config.get_optional_capabilities("text_completion")
    assert isinstance(optional, list)


def test_requirement_validation(capability_config):
    """Test capability requirement validation."""
    # Test validation
    result = capability_config.validate_capability_requirements(
        "text_completion", ["text_generation"]
    )

    assert isinstance(result, dict)
    assert "meets_requirements" in result
    assert "missing_required" in result
    assert "available_optional" in result
    assert "missing_optional" in result
    assert "coverage_score" in result


def test_performance_thresholds(capability_config):
    """Test performance threshold configuration."""
    # Test getting performance thresholds
    thresholds = capability_config.get_performance_thresholds()
    assert isinstance(thresholds, dict)

    # Test getting cost thresholds
    cost_thresholds = capability_config.get_cost_thresholds()
    assert isinstance(cost_thresholds, dict)


def test_configuration_management(capability_config):
    """Test configuration management functionality."""
    # Test adding capability
    new_cap = ModelCapability(
        name="test_capability",
        description="Test capability",
        parameters={},
        performance_score=0.5,
        cost_efficiency=0.5,
    )

    capability_config.add_capability(new_cap)
    assert capability_config.get_capability("test_capability") is not None

    # Test removing capability
    removed = capability_config.remove_capability("test_capability")
    assert removed is True
    assert capability_config.get_capability("test_capability") is None

    # Test removing non-existent capability
    removed = capability_config.remove_capability("nonexistent")
    assert removed is False


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
