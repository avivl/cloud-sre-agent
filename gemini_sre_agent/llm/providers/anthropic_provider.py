# gemini_sre_agent/llm/providers/anthropic_provider.py

"""
Anthropic provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for Anthropic's Claude models.
"""

import logging
from typing import Any, Dict, List

import anthropic

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = (
            str(config.base_url) if config.base_url else "https://api.anthropic.com"
        )

        # Initialize Anthropic client
        self.client = anthropic.AsyncAnthropic(
            api_key=self.api_key, base_url=self.base_url
        )

        # Get model from provider_specific config
        provider_specific = config.provider_specific or {}
        self.model = provider_specific.get("model", "claude-3-5-sonnet-20241022")

    async def _generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Anthropic API."""
        try:
            logger.info(f"Generating response with Anthropic model: {self.model}")

            # Convert messages to Anthropic format
            messages = self._convert_messages_to_anthropic_format(
                request.messages or []
            )

            # Get generation parameters
            provider_specific = self.config.provider_specific or {}

            # Make the API call
            response = await self.client.messages.create(  # type: ignore
                model=self.model,
                messages=messages,  # type: ignore
                max_tokens=provider_specific.get("max_tokens", 1000),
                temperature=provider_specific.get("temperature", 0.7),
                top_p=provider_specific.get("top_p", 1.0),
            )

            # Extract usage information
            usage = self._extract_usage(response)

            # Extract text content from response
            content = ""
            if response.content and len(response.content) > 0:
                if hasattr(response.content[0], "text"):
                    content = response.content[0].text  # type: ignore
                else:
                    content = str(response.content[0])

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Anthropic API."""
        try:
            logger.info(
                f"Generating streaming response with Anthropic model: {self.model}"
            )

            # Convert messages to Anthropic format
            messages = self._convert_messages_to_anthropic_format(
                request.messages or []
            )

            # Get generation parameters
            provider_specific = self.config.provider_specific or {}

            # Make the streaming API call
            stream = await self.client.messages.create(  # type: ignore
                model=self.model,
                messages=messages,  # type: ignore
                max_tokens=provider_specific.get("max_tokens", 1000),
                temperature=provider_specific.get("temperature", 0.7),
                top_p=provider_specific.get("top_p", 1.0),
                stream=True,
            )

            # Process streaming response
            async for chunk in stream:
                if hasattr(chunk, "type") and chunk.type == "content_block_delta":
                    if hasattr(chunk, "delta") and hasattr(chunk.delta, "text"):
                        usage = (
                            self._extract_usage(chunk)
                            if hasattr(chunk, "usage")
                            else {"input_tokens": 0, "output_tokens": 0}
                        )
                        yield LLMResponse(
                            content=chunk.delta.text,
                            model=self.model,
                            provider=self.provider_name,
                            usage=usage,
                        )

        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Anthropic API is accessible."""
        try:
            logger.debug("Performing Anthropic health check")
            # Make a simple API call to test connectivity
            await self.client.messages.create(  # type: ignore
                model=self.model,
                messages=[{"role": "user", "content": "Hello"}],
                max_tokens=1,
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if Anthropic supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Anthropic supports tool calling."""
        return True

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Anthropic models mapped to semantic types."""
        # Default mappings
        default_mappings = {
            ModelType.FAST: "claude-3-5-haiku-20241022",
            ModelType.SMART: "claude-3-5-sonnet-20241022",
            ModelType.DEEP_THINKING: "claude-3-5-sonnet-20241022",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Anthropic API."""
        try:
            logger.info(f"Generating embeddings for text of length: {len(text)}")

            # Anthropic doesn't have a direct embeddings API
            # For now, return a mock embedding since Anthropic doesn't provide embeddings
            # In a real implementation, you might use a different service for embeddings
            return [0.0] * 1024  # Anthropic doesn't provide embeddings

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Fallback to mock implementation
            return [0.0] * 1024

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        # Anthropic doesn't provide a direct token counting function
        # Use a rough approximation based on word count
        return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Anthropic pricing (as of 2024)
        input_cost_per_1k = 0.003  # $3.00 per 1M input tokens
        output_cost_per_1k = 0.015  # $15.00 per 1M output tokens

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost

    def _convert_messages_to_anthropic_format(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Convert messages to Anthropic format."""
        anthropic_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # Anthropic uses "user" and "assistant" roles
            if role in ["user", "assistant"]:
                anthropic_messages.append({"role": role, "content": content})
            elif role == "system":
                # Anthropic handles system messages differently
                # For now, we'll prepend to the first user message
                if anthropic_messages and anthropic_messages[0]["role"] == "user":
                    anthropic_messages[0][
                        "content"
                    ] = f"System: {content}\n\n{anthropic_messages[0]['content']}"
                else:
                    # If no user message yet, create one
                    anthropic_messages.append(
                        {"role": "user", "content": f"System: {content}"}
                    )

        return anthropic_messages

    def _extract_usage(self, response: Any) -> Dict[str, int]:
        """Extract usage information from Anthropic response."""
        usage = {"input_tokens": 0, "output_tokens": 0}

        if hasattr(response, "usage"):
            usage["input_tokens"] = getattr(response.usage, "input_tokens", 0)
            usage["output_tokens"] = getattr(response.usage, "output_tokens", 0)

        return usage

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Anthropic-specific configuration."""
        if not hasattr(config, "api_key") or not config.api_key:
            raise ValueError("Anthropic API key is required")

        if not config.api_key.startswith("sk-ant-"):
            raise ValueError("Anthropic API key must start with 'sk-ant-'")
