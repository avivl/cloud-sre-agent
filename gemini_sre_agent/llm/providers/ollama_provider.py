# gemini_sre_agent/llm/providers/ollama_provider.py

"""
Ollama provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for Ollama local models.
"""

import asyncio
import logging
from typing import Any, Dict, List

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama local provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.base_url = config.base_url or "http://localhost:11434"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Ollama API."""
        # TODO: Implement actual Ollama API call
        logger.info(f"Generating response with Ollama model: {self.model}")

        # Mock implementation for now
        return LLMResponse(
            content="Mock Ollama response",
            model=self.model,
            provider=self.provider_name,
            usage={"input_tokens": 10, "output_tokens": 5},
        )

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Ollama API."""
        # TODO: Implement actual Ollama streaming API call
        logger.info(f"Generating streaming response with Ollama model: {self.model}")

        # Mock implementation for now
        chunks = ["Mock", " Ollama", " streaming", " response"]
        for i, chunk in enumerate(chunks):
            yield LLMResponse(
                content=chunk,
                model=self.model,
                provider=self.provider_name,
                usage={"input_tokens": 10, "output_tokens": i + 1},
            )
            await asyncio.sleep(0.1)  # Simulate streaming delay

    async def health_check(self) -> bool:
        """Check if Ollama is accessible."""
        # TODO: Implement actual health check
        logger.debug("Performing Ollama health check")
        return True  # Mock implementation

    def supports_streaming(self) -> bool:
        """Check if Ollama supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Ollama supports tool calling."""
        return False  # Depends on the model

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Ollama models mapped to semantic types."""
        # Default mappings
        default_mappings = {
            ModelType.FAST: "llama3.1:8b",
            ModelType.SMART: "llama3.1:70b",
            ModelType.DEEP_THINKING: "llama3.1:70b",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Ollama API."""
        # TODO: Implement actual Ollama embeddings API call
        logger.info(f"Generating embeddings for text of length: {len(text)}")

        # Mock implementation - return a vector of zeros
        return [0.0] * 4096  # Typical Ollama embedding dimension

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        # TODO: Implement actual token counting
        # For now, use a rough approximation
        return int(len(text.split()) * 1.3)  # Rough approximation

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Ollama is free (local)
        return 0.0

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Ollama-specific configuration."""
        # Ollama doesn't require API keys
        if hasattr(config, "api_key") and config.api_key:
            raise ValueError("Ollama does not use API keys")
