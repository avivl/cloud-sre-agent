import logging
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, List, Optional, Type, TypeVar

from pydantic import BaseModel

from .config import LLMProviderConfig

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """
    Simplified LLM Provider interface that works with LiteLLM.

    This interface is minimal since LiteLLM handles most of the complexity
    of different provider APIs and formats.
    """

    def __init__(self, config: LLMProviderConfig):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._client = None
        self._initialized = False

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the provider with LiteLLM configuration."""
        pass

    @abstractmethod
    async def generate_text(
        self, prompt: str, model: Optional[str] = None, **kwargs: Any
    ) -> str:
        """Generate text response using LiteLLM."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> T:
        """Generate structured response using Instructor + LiteLLM."""
        pass

    @abstractmethod
    def generate_stream(
        self, prompt: str, model: Optional[str] = None, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Generate streaming text response using LiteLLM."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is healthy and accessible."""
        pass

    @abstractmethod
    def get_available_models(self) -> List[str]:
        """Get list of available models for this provider."""
        pass

    @abstractmethod
    def estimate_cost(self, prompt: str, model: Optional[str] = None) -> float:
        """Estimate the cost for a given prompt and model."""
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """Validate the provider configuration."""
        pass

    def _format_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Format a prompt, handling both string and Mirascope Prompt objects."""
        return prompt

    def _resolve_model(self, model: Optional[str]) -> str:
        """Resolve the model name, using first available if not specified."""
        if model:
            return model
        return list(self.config.models.keys())[0]

    @property
    def is_initialized(self) -> bool:
        """Check if the provider has been initialized."""
        return self._initialized

    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.config.provider
