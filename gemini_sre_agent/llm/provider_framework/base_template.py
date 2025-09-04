"""
Base Provider Template for Easy Provider Implementation.

This module provides a base template class that handles common provider functionality,
making it easy to implement new providers with minimal code.
"""

import asyncio
import logging
from abc import abstractmethod
from typing import Any, Dict, List

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class BaseProviderTemplate(LLMProvider):
    """
    Base template class for implementing LLM providers with minimal code.

    This class provides common functionality and sensible defaults, allowing
    new providers to be implemented with < 50 lines of code.
    """

    def __init__(self, config: LLMProviderConfig):
        """Initialize the provider with configuration."""
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = (
            str(config.base_url) if config.base_url else self._get_default_base_url()
        )
        self.timeout = config.timeout or 30
        self.max_retries = config.max_retries or 3

        # Provider-specific configuration
        self.provider_specific = config.provider_specific or {}

        # Initialize provider-specific components
        self._initialize_provider()

    def _get_default_base_url(self) -> str:
        """Get the default base URL for this provider. Override in subclasses."""
        return "https://api.example.com/v1"

    def _initialize_provider(self) -> None:
        """Initialize provider-specific components. Override in subclasses."""
        pass

    # Abstract methods that must be implemented by subclasses
    @abstractmethod
    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make the actual API request to the provider. Must be implemented."""
        pass

    @abstractmethod
    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse the API response into LLMResponse format. Must be implemented."""
        pass

    @abstractmethod
    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get the mapping of semantic types to actual model names. Must be implemented."""
        pass

    # Common implementation methods with sensible defaults
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response with retry logic."""
        for attempt in range(self.max_retries):
            try:
                response_data = await self._make_api_request(request)
                response = self._parse_response(response_data)
                return response

            except Exception as e:
                logger.warning(
                    f"Attempt {attempt + 1} failed for {self.provider_name}: {e}"
                )

                if attempt == self.max_retries - 1:
                    raise

                # Exponential backoff
                await asyncio.sleep(2**attempt)

        # This should never be reached, but satisfy type checker
        raise Exception("Max retries exceeded")

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response. Override if provider supports streaming."""
        # Default implementation: fallback to non-streaming
        response = await self.generate(request)
        yield response

    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        try:
            # Simple health check - try to make a minimal request
            test_request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model_type=ModelType.FAST,
                max_tokens=1,
                temperature=0.0,
            )

            # Use a short timeout for health checks
            response = await asyncio.wait_for(
                self._make_api_request(test_request), timeout=5.0
            )
            return response is not None

        except Exception as e:
            logger.debug(f"Health check failed for {self.provider_name}: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming. Override in subclasses."""
        return False

    def supports_tools(self) -> bool:
        """Check if provider supports tool calling. Override in subclasses."""
        return False

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available models mapped to semantic types."""
        return self._get_model_mapping()

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings for the given text. Override if supported."""
        raise NotImplementedError(f"Embeddings not supported by {self.provider_name}")

    def token_count(self, text: str) -> int:
        """Count tokens in the given text. Override for accurate counting."""
        # Simple approximation: 4 characters per token
        return len(text) // 4

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage. Override for accurate pricing."""
        # Default: $0.001 per 1k tokens
        return (input_tokens + output_tokens) * 0.001 / 1000

    @classmethod
    def validate_config(cls, config: LLMProviderConfig) -> None:
        """Validate provider-specific configuration."""
        if not config.api_key:
            raise ValueError(f"API key is required for {cls.__name__}")

        if config.base_url and not str(config.base_url).startswith(
            ("http://", "https://")
        ):
            raise ValueError("Base URL must start with http:// or https://")

    # Helper methods for common functionality
    def _get_headers(self) -> Dict[str, str]:
        """Get common HTTP headers for API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": f"gemini-sre-agent/{self.provider_name}",
        }

    def _get_request_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Convert LLMRequest to provider-specific payload format."""
        # Default OpenAI-compatible format
        return {
            "model": "default-model",
            "messages": request.messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": False,
        }

    def _parse_openai_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-compatible response format."""
        choices = response_data.get("choices", [])
        if not choices:
            raise ValueError("No choices in response")

        choice = choices[0]
        message = choice.get("message", {})

        return LLMResponse(
            content=message.get("content", ""),
            model=response_data.get("model", ""),
            usage=response_data.get("usage", {}),
            finish_reason=choice.get("finish_reason", "stop"),
        )

    def _get_provider_specific_config(self, key: str, default: Any = None) -> Any:
        """Get provider-specific configuration value."""
        return self.provider_specific.get(key, default)
