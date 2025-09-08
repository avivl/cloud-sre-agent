from typing import Any, Optional
from unittest.mock import AsyncMock

import pytest

from gemini_sre_agent.llm.capabilities.testing import (
    CapabilityTester,
    CodeGenerationTest,
    TextGenerationTest,
)
from gemini_sre_agent.llm.common.enums import ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig
from gemini_sre_agent.llm.provider import LLMProvider


@pytest.fixture
def mock_llm_provider():
    """Fixture for a mocked LLMProvider."""
    mock_provider = AsyncMock(spec=LLMProvider)
    mock_provider.provider_name = "gemini"

    # Mock config for accessing model details
    mock_provider.config = LLMProviderConfig(
        provider="gemini",
        api_key="test_key",
        models={
            "gemini-pro": ModelConfig(
                name="gemini-pro",
                model_type=ModelType.SMART,
                cost_per_1k_tokens=0.001,
                max_tokens=1000,
            ),
            "gemini-code": ModelConfig(
                name="gemini-code",
                model_type=ModelType.CODE,
                cost_per_1k_tokens=0.005,
                max_tokens=2000,
            ),
        },
    )
    mock_provider.get_available_models.return_value = {
        ModelType.SMART: "gemini-pro",
        ModelType.CODE: "gemini-code",
    }

    # Explicitly mock abstract methods
    mock_provider.supports_streaming = AsyncMock(return_value=True)
    mock_provider.supports_tools = AsyncMock(return_value=False)

    async def mock_generate_text(
        prompt: str, model: Optional[str] = None, **kwargs: Any
    ) -> str:
        if model == "gemini-pro":
            if "cat" in prompt:  # For success test
                return "This is a test about a cat."
            else:  # For failure test
                return "This is a test about a dog."
        elif model == "gemini-code":
            if "Python function" in prompt:  # For success test
                return """def add_numbers(a, b):
    return a + b"""
            else:  # For failure test
                return "function add(a, b) { return a + b; }"
        return ""

    mock_provider.generate_text.side_effect = mock_generate_text

    return mock_provider


@pytest.fixture
def mock_llm_providers(mock_llm_provider):
    """Fixture for a dictionary of mocked LLMProviders."""
    return {"gemini": mock_llm_provider}


@pytest.mark.asyncio
async def test_text_generation_test_success(mock_llm_provider):
    test = TextGenerationTest()

    passed = await test.run_test(mock_llm_provider, "gemini-pro")
    assert passed
    mock_llm_provider.generate_text.assert_called_once_with(
        prompt="Write a short sentence about a cat.", model="gemini-pro"
    )


@pytest.mark.asyncio
async def test_text_generation_test_failure(mock_llm_provider):
    test = TextGenerationTest()

    # Override the mock to return a response that doesn't contain "cat"
    async def mock_generate_text_failure(
        prompt: str, model: Optional[str] = None, **kwargs: Any
    ) -> str:
        return "This is a test about a dog."  # No "cat" in response

    mock_llm_provider.generate_text.side_effect = mock_generate_text_failure

    passed = await test.run_test(mock_llm_provider, "gemini-pro")
    assert not passed


@pytest.mark.asyncio
async def test_code_generation_test_success(mock_llm_provider):
    test = CodeGenerationTest()

    passed = await test.run_test(mock_llm_provider, "gemini-code")
    assert passed
    mock_llm_provider.generate_text.assert_called_once_with(
        prompt="Write a Python function that adds two numbers.", model="gemini-code"
    )


@pytest.mark.asyncio
async def test_code_generation_test_failure(mock_llm_provider):
    test = CodeGenerationTest()

    # Override the mock to return a response that doesn't contain the expected Python function
    async def mock_generate_text_failure(
        prompt: str, model: Optional[str] = None, **kwargs: Any
    ) -> str:
        return "function add(a, b) { return a + b; }"  # JavaScript, not Python

    mock_llm_provider.generate_text.side_effect = mock_generate_text_failure

    passed = await test.run_test(mock_llm_provider, "gemini-code")
    assert not passed


@pytest.mark.asyncio
async def test_capability_tester_run_all_tests(mock_llm_providers):
    text_test = TextGenerationTest()
    code_test = CodeGenerationTest()

    text_test = TextGenerationTest()
    code_test = CodeGenerationTest()

    # Mock run_test for TextGenerationTest
    text_test.run_test = AsyncMock(return_value=True)  # Always pass text generation

    # Mock run_test for CodeGenerationTest
    # gemini-pro should fail code generation, gemini-code should pass
    async def mock_code_run_test(provider, model_name):
        if model_name == "gemini-pro":
            return False
        elif model_name == "gemini-code":
            return True
        return False

    code_test.run_test = AsyncMock(side_effect=mock_code_run_test)

    tester = CapabilityTester(mock_llm_providers, [text_test, code_test])
    results = await tester.run_all_tests()

    assert "gemini/gemini-pro" in results
    assert "gemini/gemini-code" in results

    assert results["gemini/gemini-pro"]["text_generation"] is True
    assert (
        results["gemini/gemini-pro"]["code_generation"] is False
    )  # This should be False

    assert results["gemini/gemini-code"]["text_generation"] is True
    assert results["gemini/gemini-code"]["code_generation"] is True
