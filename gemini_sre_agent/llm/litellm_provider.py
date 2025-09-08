"""
LiteLLM Provider implementation.

This module contains the concrete implementation of LLMProvider using LiteLLM.
"""

import logging
from typing import Any, AsyncGenerator, List, Optional, Type, TypeVar, Union

try:
    import instructor
    import litellm
    from mirascope import Prompt
    LITELLM_AVAILABLE = True
except ImportError:
    # Set fallback values for when dependencies are not available
    instructor = None  # type: ignore
    litellm = None  # type: ignore
    Prompt = None  # type: ignore
    LITELLM_AVAILABLE = False

from pydantic import BaseModel

from .config import LLMProviderConfig
from .provider import LLMProvider

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LiteLLMProvider(LLMProvider):
    """
    Concrete implementation of LLMProvider using LiteLLM.

    This provider leverages LiteLLM's unified interface to work with
    multiple LLM providers through a single implementation.
    """

    def __init__(self, config: LLMProviderConfig):
        if not LITELLM_AVAILABLE:
            raise ImportError(
                "LiteLLM is not available. Please install: pip install litellm"
            )
        super().__init__(config)
        self._configure_litellm()

    def _configure_litellm(self) -> None:
        """Configure LiteLLM with provider-specific settings."""
        if self.config.api_key and litellm is not None:
            key_mapping = {
                "openai": "api_key",
                "anthropic": "anthropic_key",
                "gemini": "google_key",
                "grok": "xai_key",
            }
            if self.config.provider in key_mapping:
                setattr(litellm, key_mapping[self.config.provider], self.config.api_key)
            elif self.config.provider == "bedrock":
                litellm.aws_access_key_id = self.config.provider_specific.get(
                    "aws_access_key_id"
                )
                litellm.aws_secret_access_key = self.config.provider_specific.get(
                    "aws_secret_access_key"
                )
                litellm.aws_region_name = self.config.region

        if litellm is not None:
            litellm.verbose = True
            litellm.drop_params = True

    async def initialize(self) -> None:
        """Initialize the provider with LiteLLM configuration."""
        try:
            await self.health_check()
            self._initialized = True
            self.logger.info(
                f"LiteLLM provider '{self.provider_name}' initialized successfully"
            )
        except Exception as e:
            self.logger.error(
                f"Failed to initialize LiteLLM provider '{self.provider_name}': {str(e)}"
            )
            raise

    async def generate_text(
        self, prompt: Union[str, Any], model: Optional[str] = None, **kwargs: Any
    ) -> str:
        """Generate text response using LiteLLM."""
        if not self._initialized:
            await self.initialize()

        model_name = self._resolve_model(model)
        formatted_prompt = self._format_prompt(prompt, **kwargs)

        try:
            if litellm is None:
                raise ImportError("LiteLLM is not available")
            response = await litellm.acompletion(
                model=model_name,
                messages=[{"role": "user", "content": formatted_prompt}],
                **kwargs,
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"Error generating text with {model_name}: {str(e)}")
            raise

    async def generate_structured(
        self,
        prompt: Union[str, Any],
        response_model: Type[T],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """Generate structured response using Instructor + LiteLLM."""
        if not self._initialized:
            await self.initialize()

        model_name = self._resolve_model(model)
        formatted_prompt = self._format_prompt(prompt, **kwargs)

        try:
            if instructor is None:
                raise ImportError("Instructor is not available. Please install: pip install instructor")
            client = instructor.from_litellm(litellm)
            response = await client.chat.completions.create(
                model=model_name,
                response_model=response_model,
                messages=[{"role": "user", "content": formatted_prompt}],
                **kwargs,
            )
            return response
        except Exception as e:
            self.logger.error(
                f"Error generating structured response with {model_name}: {str(e)}"
            )
            raise

    def generate_stream(
        self, prompt: Union[str, Any], model: Optional[str] = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text response using LiteLLM."""

        async def _stream():
            if not self._initialized:
                await self.initialize()

            model_name = self._resolve_model(model)
            formatted_prompt = self._format_prompt(prompt, **kwargs)

            try:
                if litellm is None:
                    raise ImportError("LiteLLM is not available")
                response = await litellm.acompletion(
                    model=model_name,
                    messages=[{"role": "user", "content": formatted_prompt}],
                    stream=True,
                    **kwargs,
                )

                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content
            except Exception as e:
                self.logger.error(
                    f"Error generating stream with {model_name}: {str(e)}"
                )
                raise

        return _stream()

    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        try:
            test_response = await self.generate_text(prompt="Hello", max_tokens=10)
            return bool(test_response)
        except Exception as e:
            self.logger.error(
                f"Health check failed for provider '{self.provider_name}': {str(e)}"
            )
            return False

    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        return list(self.config.models.keys())

    def estimate_cost(self, prompt: str, model: Optional[str] = None) -> float:
        """Estimate the cost for a given prompt and model."""
        model_name = self._resolve_model(model)
        if model_name in self.config.models:
            model_config = self.config.models[model_name]
            estimated_tokens = len(prompt.split()) * 1.3
            return (estimated_tokens / 1000) * model_config.cost_per_1k_tokens
        return 0.0

    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        if not self.config.provider or not self.config.models:
            return False

        if (
            self.config.provider in ["openai", "anthropic", "gemini", "grok"]
            and not self.config.api_key
        ):
            return False

        return True
