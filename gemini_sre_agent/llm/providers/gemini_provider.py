# gemini_sre_agent/llm/providers/gemini_provider.py

"""
Google Gemini provider implementation using the official google-generativeai SDK.
"""

import logging
from typing import Any, Dict, List

from google import genai

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Google Gemini provider implementation using the official SDK."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.api_key = config.api_key
        self.base_url = (
            config.base_url or "https://generativelanguage.googleapis.com/v1"
        )
        self.project_id = (
            config.provider_specific.get("project_id")
            if config.provider_specific
            else None
        )

        # Set the model name from provider_specific or use default
        provider_specific = config.provider_specific or {}
        self.model = provider_specific.get("model", "gemini-1.5-flash")

        # Initialize the Gemini client
        self._client = genai.Client(api_key=self.api_key)
        self._model = None
        self._initialize_model()

    def _initialize_model(self) -> None:
        """Initialize the Gemini model with configuration."""
        try:
            # Get model name from config or use default
            model_name = self.model or "gemini-1.5-flash"

            # Store generation parameters for use in requests
            provider_specific = self.config.provider_specific or {}
            self.generation_config = {
                "temperature": provider_specific.get("temperature", 0.7),
                "top_p": provider_specific.get("top_p", 0.95),
                "top_k": provider_specific.get("top_k", 40),
                "max_output_tokens": provider_specific.get("max_tokens", 8192),
            }

            self._model = model_name
            logger.info(f"Initialized Gemini model: {model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {e}")
            raise

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Gemini API."""
        try:
            if self._model is None:
                raise RuntimeError("Model not initialized")

            # Convert messages to Gemini prompt format
            prompt = self._convert_messages_to_prompt(request.messages or [])

            # Generate content using new SDK
            response = self._client.models.generate_content(
                model=self._model, contents=prompt
            )

            # Extract usage information
            usage = self._extract_usage(response)

            return LLMResponse(
                content=response.text or "",
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Error generating response: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Gemini API."""
        try:
            if self._model is None:
                raise RuntimeError("Model not initialized")

            # Convert messages to Gemini prompt format
            prompt = self._convert_messages_to_prompt(request.messages or [])

            # Generate content with streaming using new SDK
            response_stream = self._client.models.generate_content_stream(
                model=self._model, contents=prompt
            )

            for chunk in response_stream:
                if chunk.text:
                    usage = self._extract_usage(chunk)

                    yield LLMResponse(
                        content=chunk.text,
                        model=self.model,
                        provider=self.provider_name,
                        usage=usage,
                    )

        except Exception as e:
            logger.error(f"Error generating streaming response: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            if self._model is None:
                return False

            # Perform a simple test generation
            test_response = self._client.models.generate_content(
                model=self._model, contents="Hello"
            )
            return test_response is not None
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if Gemini supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Gemini supports tool calling."""
        return True

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Gemini models mapped to semantic types."""
        default_mappings = {
            ModelType.FAST: "gemini-1.5-flash",
            ModelType.SMART: "gemini-1.5-pro",
            ModelType.DEEP_THINKING: "gemini-1.5-pro",
            ModelType.CODE: "gemini-1.5-pro",
            ModelType.ANALYSIS: "gemini-1.5-pro",
        }

        # Merge custom mappings with defaults
        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Gemini API."""
        try:
            # Use the embedding model with new SDK
            result = self._client.models.embed_content(
                model="models/embedding-001",
                contents=text,
            )
            if result.embeddings and len(result.embeddings) > 0 and result.embeddings[0].values:
                return result.embeddings[0].values
            return []
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        try:
            if self._model is None:
                # Fallback to rough approximation if model not initialized
                return int(len(text.split()) * 1.3)

            # Use the client's count_tokens method
            result = self._client.models.count_tokens(model=self._model, contents=text)
            return result.total_tokens or 0
        except Exception as e:
            logger.warning(f"Token counting failed, using approximation: {e}")
            # Fallback to rough approximation
            return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Gemini pricing (as of 2024)
        if "flash" in self.model.lower():
            input_cost_per_1k = 0.000075  # $0.075 per 1M input tokens
            output_cost_per_1k = 0.0003  # $0.30 per 1M output tokens
        else:  # Pro models
            input_cost_per_1k = 0.00125  # $1.25 per 1M input tokens
            output_cost_per_1k = 0.005  # $5.00 per 1M output tokens

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k

        return input_cost + output_cost

    def _convert_messages_to_prompt(self, messages: List[Dict[str, str]]) -> str:
        """Convert LLMRequest messages to Gemini prompt format."""
        prompt_parts = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")

        return "\n\n".join(prompt_parts)

    def _extract_usage(self, response: Any) -> Dict[str, int]:
        """Extract usage information from Gemini response."""
        usage = {"input_tokens": 0, "output_tokens": 0}

        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage["input_tokens"] = getattr(
                response.usage_metadata, "prompt_token_count", 0
            )
            usage["output_tokens"] = getattr(
                response.usage_metadata, "candidates_token_count", 0
            )
        elif hasattr(response, "usage") and response.usage:
            usage["input_tokens"] = getattr(response.usage, "prompt_token_count", 0)
            usage["output_tokens"] = getattr(
                response.usage, "candidates_token_count", 0
            )

        return usage

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Gemini-specific configuration."""
        if not hasattr(config, "api_key") or not config.api_key:
            raise ValueError("Gemini API key is required")

        if not config.api_key.startswith("AIza"):
            raise ValueError("Gemini API key must start with 'AIza'")

        # Validate model name if provided
        if hasattr(config, "model") and config.model:
            valid_models = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro",
                "gemini-1.0-ultra",
            ]
            if config.model not in valid_models:
                logger.warning(f"Model {config.model} may not be supported by Gemini")
