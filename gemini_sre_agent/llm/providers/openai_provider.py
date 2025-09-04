# gemini_sre_agent/llm/providers/openai_provider.py

"""
OpenAI provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for OpenAI's GPT models.
"""

import logging
from typing import Any, Dict, List

from openai import AsyncOpenAI

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = config.base_url or "https://api.openai.com/v1"
        self.organization = (
            config.provider_specific.get("organization_id")
            if config.provider_specific
            else None
        )

        # Initialize OpenAI client
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=str(self.base_url),
            organization=self.organization,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using OpenAI API."""
        logger.info(f"Generating response with OpenAI model: {self.model}")

        try:
            # Convert messages to OpenAI format
            messages = self._convert_messages_to_openai_format(request.messages or [])

            # Get generation parameters from provider_specific config
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            response = await self.client.chat.completions.create(  # type: ignore
                model=self.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
            )

            # Extract usage information
            usage = self._extract_usage(response.usage)

            return LLMResponse(
                content=response.choices[0].message.content or "",
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"OpenAI generation error: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using OpenAI API."""
        logger.info(f"Generating streaming response with OpenAI model: {self.model}")

        try:
            # Convert messages to OpenAI format
            messages = self._convert_messages_to_openai_format(request.messages or [])

            # Get generation parameters from provider_specific config
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            stream = await self.client.chat.completions.create(  # type: ignore
                model=self.model,
                messages=messages,  # type: ignore
                temperature=temperature,
                max_tokens=max_tokens,
                top_p=top_p,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield LLMResponse(
                        content=chunk.choices[0].delta.content,
                        model=self.model,
                        provider=self.provider_name,
                        usage=None,  # Usage info not available in streaming
                    )

        except Exception as e:
            logger.error(f"OpenAI streaming error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        logger.debug("Performing OpenAI health check")

        try:
            # Make a simple API call to test connectivity
            await self.client.models.list()
            return True
        except Exception as e:
            logger.error(f"OpenAI health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if OpenAI supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if OpenAI supports tool calling."""
        return True

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available OpenAI models mapped to semantic types."""
        # Default mappings
        default_mappings = {
            ModelType.FAST: "gpt-3.5-turbo",
            ModelType.SMART: "gpt-4o-mini",
            ModelType.DEEP_THINKING: "gpt-4o",
            ModelType.CODE: "gpt-4o",
            ModelType.ANALYSIS: "gpt-4o",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using OpenAI API."""
        logger.info(f"Generating embeddings for text of length: {len(text)}")

        try:
            response = await self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embeddings error: {e}")
            raise

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        try:
            # Use tiktoken for accurate token counting
            import tiktoken  # type: ignore

            encoding = tiktoken.get_encoding("cl100k_base")
            return len(encoding.encode(text))
        except ImportError:
            # Fallback to approximation if tiktoken not available
            logger.warning("tiktoken not available, using approximation")
            return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # OpenAI pricing (as of 2024) - using GPT-4o pricing as default
        input_cost_per_1k = 0.0025  # $2.50 per 1M input tokens
        output_cost_per_1k = 0.01  # $10.00 per 1M output tokens

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost

    def _convert_messages_to_openai_format(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Convert generic message format to OpenAI format."""
        openai_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # OpenAI expects specific role values
            if role not in ["system", "user", "assistant"]:
                role = "user"

            openai_messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        return openai_messages

    def _extract_usage(self, usage: Any) -> Dict[str, int]:
        """Extract usage information from OpenAI response."""
        if not usage:
            return {"input_tokens": 0, "output_tokens": 0}

        return {
            "input_tokens": getattr(usage, "prompt_tokens", 0),
            "output_tokens": getattr(usage, "completion_tokens", 0),
        }

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate OpenAI-specific configuration."""
        if not hasattr(config, "api_key") or not config.api_key:
            raise ValueError("OpenAI API key is required")

        if not config.api_key.startswith("sk-"):
            raise ValueError("OpenAI API key must start with 'sk-'")
