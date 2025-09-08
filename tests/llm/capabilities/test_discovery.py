from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.llm.capabilities.discovery import CapabilityDiscovery
from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability
from gemini_sre_agent.llm.common.enums import ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig


@pytest.fixture
def mock_llm_provider():
    """Fixture for a mocked LLMProvider."""
    mock_provider = MagicMock()
    mock_provider.provider_name = "gemini"

    # Mock config for accessing model details
    mock_provider.config = LLMProviderConfig(
        provider="gemini",
        api_key="test_key",
        models={
            "model_fast": ModelConfig(
                name="model_fast",
                model_type=ModelType.FAST,
                cost_per_1k_tokens=0.001,
                max_tokens=1000,
            ),
            "model_code": ModelConfig(
                name="model_code",
                model_type=ModelType.CODE,
                cost_per_1k_tokens=0.005,
                max_tokens=2000,
            ),
        },
    )

    mock_provider.get_available_models.return_value = {
        ModelType.FAST: "model_fast",
        ModelType.CODE: "model_code",
    }
    mock_provider.supports_streaming.return_value = True
    mock_provider.supports_tools.return_value = False
    return mock_provider


@pytest.fixture
def mock_llm_providers(mock_llm_provider):
    """Fixture for a dictionary of mocked LLMProviders."""
    return {"test_provider": mock_llm_provider}


@pytest.mark.asyncio
async def test_discover_capabilities(mock_llm_providers):
    discovery = CapabilityDiscovery(mock_llm_providers)
    capabilities = await discovery.discover_capabilities()

    assert "test_provider/model_fast" in capabilities
    assert "test_provider/model_code" in capabilities

    fast_model_caps = capabilities["test_provider/model_fast"]
    assert len(fast_model_caps.capabilities) == 1  # Only text_generation
    assert fast_model_caps.capabilities[0].name == "text_generation"

    code_model_caps = capabilities["test_provider/model_code"]
    assert len(code_model_caps.capabilities) == 2  # text_generation and code_generation
    assert any(c.name == "text_generation" for c in code_model_caps.capabilities)
    assert any(c.name == "code_generation" for c in code_model_caps.capabilities)


def test_get_model_capabilities(mock_llm_providers):
    discovery = CapabilityDiscovery(mock_llm_providers)
    # Manually add some capabilities for testing retrieval
    discovery.model_capabilities["test_provider/model_fast"] = ModelCapabilities(
        model_id="test_provider/model_fast",
        capabilities=[
            ModelCapability(name="text_generation", description="...", parameters={})
        ],
    )

    caps = discovery.get_model_capabilities("test_provider/model_fast")
    assert caps is not None
    assert caps.model_id == "test_provider/model_fast"
    assert len(caps.capabilities) == 1

    assert discovery.get_model_capabilities("non_existent_model") is None


def test_find_models_by_capability(mock_llm_providers):
    discovery = CapabilityDiscovery(mock_llm_providers)
    # Manually add some capabilities for testing search
    discovery.model_capabilities["provider1/model_A"] = ModelCapabilities(
        model_id="provider1/model_A",
        capabilities=[
            ModelCapability(name="text_generation", description="...", parameters={})
        ],
    )
    discovery.model_capabilities["provider2/model_B"] = ModelCapabilities(
        model_id="provider2/model_B",
        capabilities=[
            ModelCapability(name="code_generation", description="...", parameters={})
        ],
    )
    discovery.model_capabilities["provider3/model_C"] = ModelCapabilities(
        model_id="provider3/model_C",
        capabilities=[
            ModelCapability(name="text_generation", description="...", parameters={}),
            ModelCapability(name="code_generation", description="...", parameters={}),
        ],
    )

    text_gen_models = discovery.find_models_by_capability("text_generation")
    assert "provider1/model_A" in text_gen_models
    assert "provider3/model_C" in text_gen_models
    assert "provider2/model_B" not in text_gen_models

    code_gen_models = discovery.find_models_by_capability("code_generation")
    assert "provider2/model_B" in code_gen_models
    assert "provider3/model_C" in code_gen_models
    assert "provider1/model_A" not in code_gen_models

    non_existent_models = discovery.find_models_by_capability("image_recognition")
    assert len(non_existent_models) == 0
