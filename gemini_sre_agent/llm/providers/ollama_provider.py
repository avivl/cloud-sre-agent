# gemini_sre_agent/llm/providers/ollama_provider.py

"""
Ollama provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for Ollama local models.
"""

import asyncio
import logging
from typing import Any, Dict, List

import ollama

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):
    """Ollama local provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.base_url = str(config.base_url or "http://localhost:11434")
        self.timeout = config.timeout or 30

        # Configure Ollama client
        self.client = ollama.Client(host=self.base_url)

        # Get model from provider_specific config
        provider_specific = config.provider_specific or {}
        self.model = provider_specific.get("model", "llama3.1:8b")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Ollama API."""
        try:
            logger.info(f"Generating response with Ollama model: {self.model}")

            # Convert messages to Ollama format
            messages = self._convert_messages_to_ollama_format(request.messages or [])

            # Get generation parameters
            provider_specific = self.config.provider_specific or {}
            options = {
                "temperature": provider_specific.get("temperature", 0.7),
                "top_p": provider_specific.get("top_p", 0.9),
                "top_k": provider_specific.get("top_k", 40),
                "num_predict": provider_specific.get("max_tokens", 2048),
            }

            # Make the API call
            response = await asyncio.to_thread(
                self.client.chat, model=self.model, messages=messages, options=options
            )

            # Extract usage information
            usage = self._extract_usage(response)

            return LLMResponse(
                content=response["message"]["content"],
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Ollama API."""
        try:
            logger.info(
                f"Generating streaming response with Ollama model: {self.model}"
            )

            # Convert messages to Ollama format
            messages = self._convert_messages_to_ollama_format(request.messages or [])

            # Get generation parameters
            provider_specific = self.config.provider_specific or {}
            options = {
                "temperature": provider_specific.get("temperature", 0.7),
                "top_p": provider_specific.get("top_p", 0.9),
                "top_k": provider_specific.get("top_k", 40),
                "num_predict": provider_specific.get("max_tokens", 2048),
            }

            # Make the streaming API call
            stream = await asyncio.to_thread(
                self.client.chat,
                model=self.model,
                messages=messages,
                options=options,
                stream=True,
            )

            # Process streaming response
            for chunk in stream:
                if chunk.get("message", {}).get("content"):
                    usage = self._extract_usage(chunk)
                    yield LLMResponse(
                        content=chunk["message"]["content"],
                        model=self.model,
                        provider=self.provider_name,
                        usage=usage,
                    )

        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Ollama is accessible."""
        try:
            logger.debug("Performing Ollama health check")

            # Try to list models to check if Ollama is accessible
            await asyncio.to_thread(self.client.list)
            return True

        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if Ollama supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Ollama supports tool calling."""
        return False  # Depends on the model

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Ollama models mapped to semantic types."""
        # Default mappings for common Ollama models
        default_mappings = {
            ModelType.FAST: "llama3.1:8b",
            ModelType.SMART: "llama3.1:70b",
            ModelType.DEEP_THINKING: "llama3.1:70b",
            ModelType.CODE: "codellama:34b",
            ModelType.ANALYSIS: "llama3.1:70b",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Ollama API."""
        try:
            logger.info(f"Generating embeddings for text of length: {len(text)}")

            # Use the embeddings endpoint
            response = await asyncio.to_thread(
                self.client.embeddings, model=self.model, prompt=text
            )

            return response["embedding"]

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Fallback to mock implementation
            return [0.0] * 4096

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        try:
            # Use Ollama's token counting endpoint
            response = self.client.chat(
                model=self.model,
                messages=[{"role": "user", "content": text}],
                options={"num_predict": 0},  # Don't generate, just count tokens
            )

            # Extract token count from response
            if "prompt_eval_count" in response:
                return response["prompt_eval_count"]
            elif "eval_count" in response:
                return response["eval_count"]
            else:
                # Fallback to approximation
                return int(len(text.split()) * 1.3)

        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {e}")
            # Fallback to rough approximation
            return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Ollama is free (local)
        return 0.0

    def _convert_messages_to_ollama_format(
        self, messages: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        """Convert messages to Ollama format."""
        ollama_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            # Map roles to Ollama format
            if role == "system":
                ollama_messages.append({"role": "system", "content": content})
            elif role == "user":
                ollama_messages.append({"role": "user", "content": content})
            elif role == "assistant":
                ollama_messages.append({"role": "assistant", "content": content})

        return ollama_messages

    def _extract_usage(self, response: Any) -> Dict[str, int]:
        """Extract usage information from Ollama response."""
        usage = {"input_tokens": 0, "output_tokens": 0}

        # Handle both dict and object responses
        if hasattr(response, "prompt_eval_count"):
            usage["input_tokens"] = getattr(response, "prompt_eval_count", 0)
        elif isinstance(response, dict) and "prompt_eval_count" in response:
            usage["input_tokens"] = response.get("prompt_eval_count", 0)

        if hasattr(response, "eval_count"):
            usage["output_tokens"] = getattr(response, "eval_count", 0)
        elif isinstance(response, dict) and "eval_count" in response:
            usage["output_tokens"] = response.get("eval_count", 0)

        return usage

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Ollama-specific configuration."""
        # Ollama doesn't require API keys
        if hasattr(config, "api_key") and config.api_key:
            raise ValueError("Ollama does not use API keys")
