"""
Example: Custom Provider Implementation

This example shows how to create a custom provider with specific requirements
using the base template and customizing only what's needed.
"""

import asyncio
from typing import Any, Dict, List

from ...base import LLMRequest, LLMResponse, ModelType
from ...config import LLMProviderConfig
from ..base_template import BaseProviderTemplate


class CustomProvider(BaseProviderTemplate):
    """
    Custom provider implementation with specific requirements.

    This provider demonstrates how to create a provider with custom logic
    while still leveraging the framework's base functionality.
    """

    def _get_default_base_url(self) -> str:
        """Set the default base URL for this provider."""
        return "https://api.custom-llm.com/v2"

    def _initialize_provider(self) -> None:
        """Initialize provider-specific components."""
        # Custom initialization logic
        self.custom_config = self._get_provider_specific_config(
            "custom_setting", "default"
        )
        self.rate_limit = self._get_provider_specific_config("rate_limit", 100)

        # Initialize custom client or components here
        self._custom_client = None

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make custom API request with provider-specific logic."""
        # Simulate API call (replace with actual implementation)
        await asyncio.sleep(0.1)  # Simulate network delay

        # Return mock response (replace with actual API call)
        return {
            "id": "custom-response-123",
            "object": "text_completion",
            "created": 1234567890,
            "model": "custom-model",
            "choices": [
                {
                    "text": f"Custom response for: {(request.messages or [{}])[-1].get('content', '')}",
                    "index": 0,
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            },
        }

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse custom API response format."""
        choice = response_data["choices"][0]

        return LLMResponse(
            content=choice["text"],
            model=response_data["model"],
            usage=response_data["usage"],
            finish_reason=choice["finish_reason"],
        )

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Define the model mapping for this provider."""
        return {
            ModelType.FAST: "custom-fast-v1",
            ModelType.SMART: "custom-smart-v2",
        }

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Convert messages to custom format."""
        formatted = []
        for msg in messages:
            role = msg["role"]
            content = msg["content"]
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def supports_streaming(self) -> bool:
        """This provider supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """This provider supports tools."""
        return True

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using custom method."""
        # Custom embedding logic
        return [0.1, 0.2, 0.3] * 100  # Mock embedding

    def token_count(self, text: str) -> int:
        """Custom token counting logic."""
        # Custom tokenization logic
        return len(text.split()) * 2  # Rough approximation

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Custom cost estimation."""
        # Custom pricing logic
        return (input_tokens * 0.001 + output_tokens * 0.002) / 1000

    @classmethod
    def validate_config(cls, config: LLMProviderConfig) -> None:
        """Validate custom provider configuration."""
        super().validate_config(config)

        # Custom validation
        custom_setting = (
            config.provider_specific.get("custom_setting")
            if config.provider_specific
            else None
        )
        if custom_setting and custom_setting not in ["option1", "option2", "option3"]:
            raise ValueError("custom_setting must be one of: option1, option2, option3")


# This custom provider demonstrates:
# - Custom API request format
# - Custom response parsing
# - Custom initialization logic
# - Custom validation rules
# - Custom capabilities (streaming, tools, embeddings)
# - Custom pricing and token counting
# All while leveraging the framework's base functionality!
