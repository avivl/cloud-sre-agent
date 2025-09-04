# gemini_sre_agent/llm/providers/grok_provider.py

"""
Grok provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for xAI's Grok models.
"""

import json
import logging
from typing import Any, Dict, List

import httpx

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class GrokProvider(LLMProvider):
    """xAI Grok provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = (
            str(config.base_url) if config.base_url else "https://api.x.ai/v1"
        )

        # Initialize HTTP client
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=30.0,
        )

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Grok API."""
        logger.info(f"Generating response with Grok model: {self.model}")

        try:
            # Convert messages to Grok format
            messages = self._convert_messages_to_grok_format(request.messages or [])

            # Get generation parameters from provider_specific config
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": False,
            }

            response = await self.client.post("/chat/completions", json=payload)
            response.raise_for_status()

            data = response.json()

            # Extract usage information
            usage = self._extract_usage(data.get("usage"))

            return LLMResponse(
                content=data["choices"][0]["message"]["content"] or "",
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Grok generation error: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Grok API."""
        logger.info(f"Generating streaming response with Grok model: {self.model}")

        try:
            # Convert messages to Grok format
            messages = self._convert_messages_to_grok_format(request.messages or [])

            # Get generation parameters from provider_specific config
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": True,
            }

            async with self.client.stream(
                "POST", "/chat/completions", json=payload
            ) as response:
                response.raise_for_status()

                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]  # Remove "data: " prefix
                        if data_str.strip() == "[DONE]":
                            break

                        try:
                            data = json.loads(data_str)
                            if "choices" in data and data["choices"]:
                                delta = data["choices"][0].get("delta", {})
                                if "content" in delta:
                                    yield LLMResponse(
                                        content=delta["content"],
                                        model=self.model,
                                        provider=self.provider_name,
                                        usage=None,  # Usage info not available in streaming
                                    )
                        except json.JSONDecodeError:
                            continue

        except Exception as e:
            logger.error(f"Grok streaming error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Grok API is accessible."""
        logger.debug("Performing Grok health check")

        try:
            # Make a simple API call to test connectivity
            response = await self.client.get("/models")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Grok health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if Grok supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Grok supports tool calling."""
        return False  # Not yet supported

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Grok models mapped to semantic types."""
        # Default mappings
        default_mappings = {
            ModelType.FAST: "grok-beta",
            ModelType.SMART: "grok-beta",
            ModelType.DEEP_THINKING: "grok-beta",
            ModelType.CODE: "grok-beta",
            ModelType.ANALYSIS: "grok-beta",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Grok API."""
        logger.info(f"Generating embeddings for text of length: {len(text)}")

        try:
            payload = {
                "model": "grok-embedding",
                "input": text,
            }

            response = await self.client.post("/embeddings", json=payload)
            response.raise_for_status()

            data = response.json()
            return data["data"][0]["embedding"]
        except Exception as e:
            logger.error(f"Grok embeddings error: {e}")
            raise

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        # Use approximation since Grok doesn't provide a tokenizer
        return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Grok pricing (as of 2024) - estimated rates
        input_cost_per_1k = 0.0001  # $0.10 per 1M input tokens
        output_cost_per_1k = 0.0001  # $0.10 per 1M output tokens

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost

    def _convert_messages_to_grok_format(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Convert generic message format to Grok format."""
        grok_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # Grok expects specific role values
            if role not in ["system", "user", "assistant"]:
                role = "user"

            grok_messages.append(
                {
                    "role": role,
                    "content": content,
                }
            )

        return grok_messages

    def _extract_usage(self, usage: Any) -> Dict[str, int]:
        """Extract usage information from Grok response."""
        if not usage:
            return {"input_tokens": 0, "output_tokens": 0}

        return {
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
        }

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Grok-specific configuration."""
        if not hasattr(config, "api_key") or not config.api_key:
            raise ValueError("Grok API key is required")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()
