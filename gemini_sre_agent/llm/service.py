# gemini_sre_agent/llm/service.py

"""
Core LLM service integrating LiteLLM, Instructor, and Mirascope.

This module provides the main LLMService class that unifies access to multiple
LLM providers through LiteLLM, structured output through Instructor, and
advanced prompt management through Mirascope.
"""

import logging
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar, Union

try:
    import instructor
    import litellm
    from mirascope import Prompt
except ImportError as e:
    raise ImportError(
        "Required dependencies not installed. Please install: "
        "pip install instructor litellm mirascope"
    ) from e

from pydantic import BaseModel

from .base import ModelType
from .config import LLMConfig
from .prompt_manager import PromptManager
from .utils import parse_structured_output

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMService(Generic[T]):
    """
    Core LLM service integrating LiteLLM, Instructor, and Mirascope.
    
    Provides unified access to multiple LLM providers with structured output
    and advanced prompt management capabilities.
    """

    def __init__(self, config: LLMConfig):
        """Initialize the LLM service with configuration."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Configure LiteLLM settings
        self._configure_litellm()
        
        # Set up instructor for structured outputs
        self.client = instructor.patch(litellm)
        
        # Initialize prompt manager
        self.prompt_manager = PromptManager()
        
        self.logger.info("LLMService initialized with LiteLLM + Instructor + Mirascope")

    def _configure_litellm(self) -> None:
        """Configure LiteLLM with provider settings."""
        # Set up provider API keys
        for provider_config in self.config.providers.values():
            if provider_config.api_key:
                # Set API key for the provider
                if provider_config.provider == "openai":
                    litellm.api_key = provider_config.api_key
                elif provider_config.provider == "anthropic":
                    litellm.anthropic_key = provider_config.api_key
                elif provider_config.provider == "gemini":
                    litellm.google_key = provider_config.api_key
                elif provider_config.provider == "grok":
                    litellm.xai_key = provider_config.api_key
                elif provider_config.provider == "bedrock":
                    litellm.aws_access_key_id = provider_config.provider_specific.get("aws_access_key_id")
                    litellm.aws_secret_access_key = provider_config.provider_specific.get("aws_secret_access_key")
                    litellm.aws_region_name = provider_config.region

        # Configure LiteLLM settings
        litellm.verbose = True  # Enable detailed logging
        litellm.drop_params = True  # Drop unsupported parameters

    async def generate_structured(
        self,
        prompt: Union[str, Prompt],
        response_model: Type[T],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        **kwargs: Any
    ) -> T:
        """Generate a structured response using the specified model and prompt."""
        try:
            # Determine the model to use
            model_name = self._resolve_model(model, model_type, provider)
            
            self.logger.info(f"Generating structured response using model: {model_name}")
            
            # Format the prompt if it's a Mirascope Prompt object
            if isinstance(prompt, Prompt):
                formatted_prompt = prompt.format(**kwargs)
            else:
                formatted_prompt = str(prompt)
            
            # Use Instructor to get structured output
            response = await self.client.chat.completions.create(
                model=model_name,
                response_model=response_model,
                messages=[{"role": "user", "content": formatted_prompt}],
                **kwargs
            )
            
            self.logger.debug(f"Generated structured response: {response}")
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating structured response: {str(e)}")
            self._handle_error(e)
            raise

    async def generate_text(
        self,
        prompt: Union[str, Prompt],
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None,
        **kwargs: Any
    ) -> str:
        """Generate a plain text response."""
        try:
            # Determine the model to use
            model_name = self._resolve_model(model, model_type, provider)
            
            self.logger.info(f"Generating text response using model: {model_name}")
            
            # Format the prompt if it's a Mirascope Prompt object
            if isinstance(prompt, Prompt):
                formatted_prompt = prompt.format(**kwargs)
            else:
                formatted_prompt = str(prompt)
            
            # Use LiteLLM directly for text generation
            response = await litellm.acompletion(
                model=model_name,
                messages=[{"role": "user", "content": formatted_prompt}],
                **kwargs
            )
            
            content = response.choices[0].message.content
            self.logger.debug(f"Generated text response: {content[:100]}...")
            return content
            
        except Exception as e:
            self.logger.error(f"Error generating text response: {str(e)}")
            self._handle_error(e)
            raise

    def _resolve_model(
        self,
        model: Optional[str] = None,
        model_type: Optional[ModelType] = None,
        provider: Optional[str] = None
    ) -> str:
        """Resolve the model name based on provided parameters."""
        # If specific model is provided, use it
        if model:
            return model
        
        # If provider is specified, use its default model for the type
        if provider and provider in self.config.providers:
            provider_config = self.config.providers[provider]
            if model_type and model_type in provider_config.model_type_mappings:
                return provider_config.model_type_mappings[model_type]
            # Fall back to first available model
            if provider_config.models:
                return list(provider_config.models.keys())[0]
        
        # Use default provider and model type
        default_provider = self.config.default_provider
        if default_provider in self.config.providers:
            provider_config = self.config.providers[default_provider]
            model_type_to_use = model_type or self.config.default_model_type
            if model_type_to_use in provider_config.model_type_mappings:
                return provider_config.model_type_mappings[model_type_to_use]
        
        raise ValueError(f"Could not resolve model for provider={provider}, model_type={model_type}")

    def _handle_error(self, error: Exception) -> None:
        """Handle different types of errors from LLM providers."""
        error_str = str(error).lower()
        
        if "rate limit" in error_str:
            self.logger.warning("Rate limit exceeded, implementing backoff")
        elif "authentication" in error_str or "unauthorized" in error_str:
            self.logger.error("Authentication error with provider")
        elif "quota" in error_str or "billing" in error_str:
            self.logger.error("Quota or billing error with provider")
        elif "timeout" in error_str:
            self.logger.warning("Request timeout occurred")
        else:
            self.logger.error(f"Unhandled error: {str(error)}")

    async def health_check(self, provider: Optional[str] = None) -> bool:
        """Check if the specified provider is healthy and accessible."""
        try:
            provider_to_check = provider or self.config.default_provider
            if provider_to_check not in self.config.providers:
                self.logger.error(f"Provider '{provider_to_check}' not configured")
                return False
            
            test_response = await self.generate_text(
                prompt="Hello",
                provider=provider_to_check,
                max_tokens=10
            )
            
            self.logger.info(f"Health check passed for provider: {provider_to_check}")
            return bool(test_response)
            
        except Exception as e:
            self.logger.error(f"Health check failed for provider {provider}: {str(e)}")
            return False

    def get_available_models(self, provider: Optional[str] = None) -> Dict[str, List[str]]:
        """Get available models for the specified provider or all providers."""
        if provider:
            if provider in self.config.providers:
                return {provider: list(self.config.providers[provider].models.keys())}
            return {}
        
        return {
            provider_name: list(provider_config.models.keys())
            for provider_name, provider_config in self.config.providers.items()
        }




def create_llm_service(config: LLMConfig) -> LLMService:
    """Factory function to create and configure an LLMService instance."""
    return LLMService(config)
