# tests/conftest.py

"""
pytest configuration and fixtures for LLM testing framework.

This module provides shared fixtures and configuration for all tests
in the testing framework.
"""

import asyncio

import pytest

# from gemini_sre_agent.llm.factory import LLMProviderFactory  # Imported when needed
# from gemini_sre_agent.llm.model_registry import ModelRegistry  # Imported when needed
from gemini_sre_agent.llm.cost_management_integration import IntegratedCostManager
from gemini_sre_agent.llm.testing.framework import TestingFramework
from gemini_sre_agent.llm.testing.mock_providers import (
    MockCostManager,
    MockModelRegistry,
    MockProviderFactory,
)

# from typing import Dict, Any, Optional  # Imported when needed


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_provider_factory():
    """Create a mock provider factory for testing."""
    return MockProviderFactory()


@pytest.fixture
def mock_model_registry():
    """Create a mock model registry for testing."""
    return MockModelRegistry()


@pytest.fixture
def mock_cost_manager():
    """Create a mock cost manager for testing."""
    return MockCostManager()


@pytest.fixture
def mock_integrated_cost_manager(
    mock_cost_manager, mock_model_registry, mock_provider_factory
):
    """Create a mock integrated cost manager for testing."""
    return IntegratedCostManager(
        model_registry=mock_model_registry,
        provider_factory=mock_provider_factory,
        cost_manager=mock_cost_manager,
    )


@pytest.fixture
def testing_framework(
    mock_provider_factory, mock_model_registry, mock_integrated_cost_manager
):
    """Create a testing framework instance for testing."""
    return TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        cost_manager=mock_integrated_cost_manager,
        enable_mock_testing=True,
    )


@pytest.fixture
def sample_llm_request():
    """Create a sample LLM request for testing."""
    from gemini_sre_agent.llm.base import LLMRequest, ModelType

    return LLMRequest(
        prompt="This is a test prompt for unit testing.",
        model_type=ModelType.SMART,
        max_tokens=100,
        temperature=0.7,
    )


@pytest.fixture
def sample_llm_response():
    """Create a sample LLM response for testing."""
    from gemini_sre_agent.llm.base import LLMResponse, ModelType

    return LLMResponse(
        content="This is a test response from the mock provider.",
        usage={
            "input_tokens": 10,
            "output_tokens": 15,
            "total_tokens": 25,
        },
        model_type=ModelType.SMART,
        provider="mock_openai",
    )


@pytest.fixture
def test_data_config():
    """Create test data configuration."""
    return {
        "min_length": 10,
        "max_length": 1000,
        "include_special_chars": True,
        "include_numbers": True,
        "include_unicode": False,
        "language": "en",
    }


@pytest.fixture
def benchmark_config():
    """Create benchmark configuration."""
    return {
        "duration_seconds": 10,  # Short duration for testing
        "concurrent_requests": 5,
        "requests_per_second": None,
        "warmup_requests": 2,
        "cooldown_seconds": 1,
        "timeout_seconds": 10,
        "enable_memory_monitoring": False,  # Disable for testing
        "enable_cpu_monitoring": False,  # Disable for testing
        "enable_cost_tracking": True,
    }


@pytest.fixture
def mock_provider_config():
    """Create mock provider configuration."""
    return {
        "response_time_ms": 50,
        "success_rate": 0.95,
        "error_rate": 0.05,
        "timeout_rate": 0.0,
        "custom_responses": {
            "test": "This is a custom test response",
            "error": "This is a custom error response",
        },
    }


# Pytest markers for different test types
pytest_plugins = []


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: mark test as a unit test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "cost: mark test as a cost analysis test")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "mock: mark test as using mock providers")
    config.addinivalue_line(
        "markers", "real: mark test as using real providers (requires API keys)"
    )


def pytest_collection_modifyitems(config, items):
    """Modify test collection to add markers based on test names."""
    for item in items:
        # Add markers based on test file names
        if "unit" in item.nodeid:
            item.add_marker(pytest.mark.unit)
        elif "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        elif "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        elif "cost" in item.nodeid:
            item.add_marker(pytest.mark.cost)

        # Add markers based on test function names
        if "slow" in item.name:
            item.add_marker(pytest.mark.slow)
        if "mock" in item.name:
            item.add_marker(pytest.mark.mock)
        if "real" in item.name:
            item.add_marker(pytest.mark.real)


# Async test utilities
@pytest.fixture
async def async_test_runner():
    """Fixture for running async tests."""

    async def run_async_test(coro):
        """Run an async test coroutine."""
        return await coro

    return run_async_test


# Test data generators
@pytest.fixture
def test_prompts():
    """Generate various test prompts."""
    from gemini_sre_agent.llm.testing.test_data_generators import (
        PromptType,
        TestDataGenerator,
    )

    generator = TestDataGenerator()

    return {
        "simple": generator.generate_prompt(PromptType.SIMPLE),
        "complex": generator.generate_prompt(PromptType.COMPLEX),
        "technical": generator.generate_prompt(PromptType.TECHNICAL),
        "creative": generator.generate_prompt(PromptType.CREATIVE),
        "analytical": generator.generate_prompt(PromptType.ANALYTICAL),
        "conversational": generator.generate_prompt(PromptType.CONVERSATIONAL),
        "code_generation": generator.generate_prompt(PromptType.CODE_GENERATION),
        "data_processing": generator.generate_prompt(PromptType.DATA_PROCESSING),
    }


@pytest.fixture
def test_scenarios():
    """Generate various test scenarios."""
    from gemini_sre_agent.llm.testing.test_data_generators import (
        TestDataGenerator,
        TestScenario,
    )

    generator = TestDataGenerator()

    return {
        "normal": generator.generate_test_scenarios(TestScenario.NORMAL, 5),
        "edge_case": generator.generate_test_scenarios(TestScenario.EDGE_CASE, 3),
        "stress_test": generator.generate_test_scenarios(TestScenario.STRESS_TEST, 2),
        "error_condition": generator.generate_test_scenarios(
            TestScenario.ERROR_CONDITION, 3
        ),
        "performance_test": generator.generate_test_scenarios(
            TestScenario.PERFORMANCE_TEST, 2
        ),
    }


# Performance test utilities
@pytest.fixture
def performance_test_data():
    """Generate performance test data."""
    from gemini_sre_agent.llm.testing.test_data_generators import TestDataGenerator

    generator = TestDataGenerator()

    return {
        "latency": generator.generate_performance_test_data("latency", "small"),
        "throughput": generator.generate_performance_test_data("throughput", "small"),
        "concurrency": generator.generate_performance_test_data("concurrency", "small"),
    }


# Mock data for testing
@pytest.fixture
def mock_provider_stats():
    """Mock provider statistics."""
    return {
        "mock_openai_fast": {
            "provider_type": "openai",
            "request_count": 100,
            "total_tokens": 5000,
            "average_tokens_per_request": 50,
        },
        "mock_anthropic_reliable": {
            "provider_type": "anthropic",
            "request_count": 80,
            "total_tokens": 4000,
            "average_tokens_per_request": 50,
        },
        "mock_google": {
            "provider_type": "google",
            "request_count": 60,
            "total_tokens": 3000,
            "average_tokens_per_request": 50,
        },
    }


@pytest.fixture
def mock_cost_data():
    """Mock cost data for testing."""
    return {
        "total_cost": 0.15,
        "request_count": 100,
        "average_cost_per_request": 0.0015,
        "cost_history": [
            {"cost": 0.001, "timestamp": 1640995200, "request_count": 1},
            {"cost": 0.002, "timestamp": 1640995260, "request_count": 2},
            {"cost": 0.0015, "timestamp": 1640995320, "request_count": 3},
        ],
    }


# Test environment setup
@pytest.fixture(autouse=True)
def setup_test_environment():
    """Setup test environment before each test."""
    # This runs before each test
    pass


@pytest.fixture(autouse=True)
def cleanup_test_environment():
    """Cleanup test environment after each test."""
    # This runs after each test
    yield
    # Cleanup code here if needed
