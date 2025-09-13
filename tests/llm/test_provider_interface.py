"""
Unit tests for the LLM Provider interface.
"""

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

# Mock the dependencies before importing the provider
mock_prompt_class = MagicMock()
with patch.dict(
    "sys.modules",
    {"instructor": MagicMock(), "litellm": MagicMock(), "mirascope": MagicMock()},
):
    # Patch the Prompt class in the provider module
    from gemini_sre_agent.llm.base import ModelType
    from gemini_sre_agent.llm.config import LLMProviderConfig, ModelConfig
    import gemini_sre_agent.llm.provider as provider_module
    from gemini_sre_agent.llm.provider import LLMProvider

    provider_module.Prompt = mock_prompt_class


class MockResponse(BaseModel):
    """Test response model for structured output testing."""

    message: str
    confidence: float


class MockLLMProvider(LLMProvider):
    """Test implementation of LLMProvider for testing the abstract interface."""

    def __init__(self, config: LLMProviderConfig) -> None:
        super().__init__(config)
        self._initialized = False

    async def initialize(self) -> None:
        self._initialized = True

    async def generate_text(self, prompt, model=None, **kwargs) -> str:
        return "Test response"

    async def generate_structured(self, prompt, response_model, model=None, **kwargs):
        return response_model(message="Test", confidence=0.95)

    def generate_stream(
        self, prompt: str, model: Optional[str] = None, **kwargs: str
    ) -> None:
        """
        Generate Stream.

        Args:
            prompt: Description of prompt.
            model: Description of model.

        """

        async def _stream():
            yield "Test"
            yield " response"

        return _stream()

    async def health_check(self) -> bool:
        return True

    def get_available_models(self) -> list:
        """
        Get Available Models.

        Returns:
            list: Description of return value.

        """
        return ["test-model"]

    def estimate_cost(self, prompt: str, model=None) -> float:
        """
        Estimate Cost.

        Args:
            prompt: str: Description of prompt: str.
            model: Description of model.

        Returns:
            float: Description of return value.

        """
        return 0.01

    def validate_config(self) -> bool:
        """
        Validate Config.

        Returns:
            bool: Description of return value.

        """
        return True


class TestProviderInterface:
    """Test the LLMProvider abstract interface."""

    def test_provider_initialization(self) -> None:
        """Test provider initialization with configuration."""
        config = LLMProviderConfig(
            provider="openai",
            models={
                "test-model": ModelConfig(name="test-model", model_type=ModelType.FAST)
            },
        )
        provider = MockLLMProvider(config)

        assert provider.config == config
        assert not provider.is_initialized
        assert provider.provider_name == "openai"

    def test_format_prompt_string(self) -> None:
        """Test formatting string prompts."""
        config = LLMProviderConfig(
            provider="openai",
            models={
                "test-model": ModelConfig(name="test-model", model_type=ModelType.FAST)
            },
        )
        provider = MockLLMProvider(config)

        result = provider._format_prompt("Hello {name}", name="World")
        assert result == "Hello World"

    def test_format_prompt_mirascope(self) -> None:
        """Test formatting Mirascope Prompt objects."""
        config = LLMProviderConfig(
            provider="openai",
            models={
                "test-model": ModelConfig(name="test-model", model_type=ModelType.FAST)
            },
        )
        provider = MockLLMProvider(config)

        # Mock Mirascope Prompt
        mock_prompt = MagicMock()
        mock_prompt.format.return_value = "Formatted prompt"

        result = provider._format_prompt(mock_prompt, name="World")
        assert result == "Formatted prompt"
        mock_prompt.format.assert_called_once_with(name="World")

    def test_resolve_model(self) -> None:
        """Test model resolution logic."""
        config = LLMProviderConfig(
            provider="openai",
            models={
                "model1": ModelConfig(name="model1", model_type=ModelType.FAST),
                "model2": ModelConfig(name="model2", model_type=ModelType.SMART),
            },
        )
        provider = MockLLMProvider(config)

        # Test with specific model
        result = provider._resolve_model("model1")
        assert result == "model1"

        # Test with no model (should return first available)
        result = provider._resolve_model(None)
        assert result in ["model1", "model2"]
