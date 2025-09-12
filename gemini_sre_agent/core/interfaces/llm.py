# gemini_sre_agent/core/interfaces/llm.py

"""
LLM-specific interfaces for the Gemini SRE Agent system.

This module defines abstract base classes and interfaces specific
to LLM operations, providers, and models.
"""

from abc import abstractmethod
from typing import Any, AsyncIterator, Dict, List, Optional, TypeVar

from ..types import (
    ConfigDict,
    Content,
    ModelId,
    ProviderId,
    TokenCount,
    TokenUsage,
    TotalCost,
)
from .base import MonitorableComponent

# Generic type variables
RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class LLMProvider(MonitorableComponent[RequestT, ResponseT]):
    """
    Abstract base class for LLM providers.

    This class provides the core interface for LLM providers
    and manages provider-specific functionality.
    """

    def __init__(
        self,
        provider_id: ProviderId,
        provider_name: str,
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the LLM provider.

        Args:
            provider_id: Unique identifier for the provider
            provider_name: Human-readable name for the provider
            config: Optional initial configuration
        """
        super().__init__(provider_id, provider_name, config)
        self._provider_id = provider_id
        self._provider_name = provider_name
        self._models: Dict[ModelId, "LLMModel"] = {}
        self._rate_limits = {}
        self._cost_tracking = {}

    @property
    def provider_id(self) -> ProviderId:
        """Get the provider's unique identifier."""
        return self._provider_id

    @property
    def provider_name(self) -> str:
        """Get the provider's name."""
        return self._provider_name

    @property
    def models(self) -> Dict[ModelId, "LLMModel"]:
        """Get available models."""
        return self._models.copy()

    @abstractmethod
    def get_models(self) -> List["LLMModel"]:
        """
        Get all available models.

        Returns:
            List of available models
        """
        pass

    @abstractmethod
    def get_model(self, model_id: ModelId) -> Optional["LLMModel"]:
        """
        Get a specific model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model instance or None if not found
        """
        pass

    @abstractmethod
    def create_model(self, model_id: ModelId, config: ConfigDict) -> "LLMModel":
        """
        Create a new model instance.

        Args:
            model_id: Model identifier
            config: Model configuration

        Returns:
            Created model instance
        """
        pass

    @abstractmethod
    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate provider configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    def register_model(self, model: "LLMModel") -> None:
        """
        Register a model with the provider.

        Args:
            model: Model to register
        """
        self._models[model.model_id] = model

    def unregister_model(self, model_id: ModelId) -> None:
        """
        Unregister a model from the provider.

        Args:
            model_id: Model identifier to unregister
        """
        if model_id in self._models:
            del self._models[model_id]

    def get_rate_limit(self, model_id: ModelId) -> Dict[str, Any]:
        """
        Get rate limit information for a model.

        Args:
            model_id: Model identifier

        Returns:
            Rate limit information
        """
        return self._rate_limits.get(model_id, {})

    def update_rate_limit(self, model_id: ModelId, limit_info: Dict[str, Any]) -> None:
        """
        Update rate limit information for a model.

        Args:
            model_id: Model identifier
            limit_info: Rate limit information
        """
        self._rate_limits[model_id] = limit_info

    def track_cost(self, model_id: ModelId, cost: TotalCost) -> None:
        """
        Track cost for a model.

        Args:
            model_id: Model identifier
            cost: Cost to track
        """
        if model_id not in self._cost_tracking:
            self._cost_tracking[model_id] = 0.0
        self._cost_tracking[model_id] += cost

    def get_total_cost(self, model_id: Optional[ModelId] = None) -> TotalCost:
        """
        Get total cost for a model or all models.

        Args:
            model_id: Optional model identifier

        Returns:
            Total cost
        """
        if model_id:
            return self._cost_tracking.get(model_id, 0.0)
        return sum(self._cost_tracking.values())


class LLMModel(MonitorableComponent[RequestT, ResponseT]):
    """
    Abstract base class for LLM models.

    This class provides the core interface for LLM models
    and manages model-specific functionality.
    """

    def __init__(
        self,
        model_id: ModelId,
        model_name: str,
        provider_id: ProviderId,
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the LLM model.

        Args:
            model_id: Unique identifier for the model
            model_name: Human-readable name for the model
            provider_id: Provider identifier
            config: Optional initial configuration
        """
        super().__init__(model_id, model_name, config)
        self._model_id = model_id
        self._model_name = model_name
        self._provider_id = provider_id
        self._capabilities = []
        self._max_tokens = 0
        self._cost_per_token = 0.0

    @property
    def model_id(self) -> ModelId:
        """Get the model's unique identifier."""
        return self._model_id

    @property
    def model_name(self) -> str:
        """Get the model's name."""
        return self._model_name

    @property
    def provider_id(self) -> ProviderId:
        """Get the provider identifier."""
        return self._provider_id

    @property
    def capabilities(self) -> List[str]:
        """Get model capabilities."""
        return self._capabilities.copy()

    @property
    def max_tokens(self) -> int:
        """Get maximum tokens for the model."""
        return self._max_tokens

    @property
    def cost_per_token(self) -> float:
        """Get cost per token for the model."""
        return self._cost_per_token

    @abstractmethod
    def generate(self, request: RequestT) -> ResponseT:
        """
        Generate a response from the model.

        Args:
            request: Generation request

        Returns:
            Generated response
        """
        pass

    @abstractmethod
    def generate_stream(self, request: RequestT) -> AsyncIterator[ResponseT]:
        """
        Generate a streaming response from the model.

        Args:
            request: Generation request

        Yields:
            Streaming response chunks
        """
        pass

    @abstractmethod
    def validate_request(self, request: RequestT) -> bool:
        """
        Validate a request for this model.

        Args:
            request: Request to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def estimate_tokens(self, content: Content) -> TokenCount:
        """
        Estimate token count for content.

        Args:
            content: Content to estimate

        Returns:
            Estimated token count
        """
        pass

    def add_capability(self, capability: str) -> None:
        """
        Add a capability to the model.

        Args:
            capability: Capability to add
        """
        if capability not in self._capabilities:
            self._capabilities.append(capability)

    def has_capability(self, capability: str) -> bool:
        """
        Check if the model has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if has capability, False otherwise
        """
        return capability in self._capabilities

    def set_max_tokens(self, max_tokens: int) -> None:
        """
        Set the maximum tokens for the model.

        Args:
            max_tokens: Maximum token count
        """
        self._max_tokens = max_tokens

    def set_cost_per_token(self, cost: float) -> None:
        """
        Set the cost per token for the model.

        Args:
            cost: Cost per token
        """
        self._cost_per_token = cost

    def calculate_cost(self, token_usage: TokenUsage) -> TotalCost:
        """
        Calculate cost based on token usage.

        Args:
            token_usage: Token usage information

        Returns:
            Calculated cost
        """
        total_tokens = token_usage.get("total_tokens", 0)
        return total_tokens * self._cost_per_token


class ChatModel(LLMModel[RequestT, ResponseT]):
    """
    Abstract base class for chat-based models.

    This class extends LLMModel with chat-specific functionality.
    """

    def __init__(
        self,
        model_id: ModelId,
        model_name: str,
        provider_id: ProviderId,
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the chat model.

        Args:
            model_id: Unique identifier for the model
            model_name: Human-readable name for the model
            provider_id: Provider identifier
            config: Optional initial configuration
        """
        super().__init__(model_id, model_name, provider_id, config)
        self.add_capability("chat")
        self.add_capability("conversation")

    @abstractmethod
    def chat_completion(
        self, messages: List[Dict[str, Any]], **kwargs: Any
    ) -> ResponseT:
        """
        Generate a chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Returns:
            Chat completion response
        """
        pass

    @abstractmethod
    def chat_completion_stream(
        self, messages: List[Dict[str, Any]], **kwargs: Any
    ) -> AsyncIterator[ResponseT]:
        """
        Generate a streaming chat completion.

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters

        Yields:
            Streaming chat completion chunks
        """
        pass


class CompletionModel(LLMModel[RequestT, ResponseT]):
    """
    Abstract base class for completion-based models.

    This class extends LLMModel with completion-specific functionality.
    """

    def __init__(
        self,
        model_id: ModelId,
        model_name: str,
        provider_id: ProviderId,
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the completion model.

        Args:
            model_id: Unique identifier for the model
            model_name: Human-readable name for the model
            provider_id: Provider identifier
            config: Optional initial configuration
        """
        super().__init__(model_id, model_name, provider_id, config)
        self.add_capability("completion")
        self.add_capability("text_generation")

    @abstractmethod
    def text_completion(self, prompt: Content, **kwargs: Any) -> ResponseT:
        """
        Generate a text completion.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Returns:
            Text completion response
        """
        pass

    @abstractmethod
    def text_completion_stream(
        self, prompt: Content, **kwargs: Any
    ) -> AsyncIterator[ResponseT]:
        """
        Generate a streaming text completion.

        Args:
            prompt: Input prompt
            **kwargs: Additional parameters

        Yields:
            Streaming text completion chunks
        """
        pass


class EmbeddingModel(LLMModel[RequestT, ResponseT]):
    """
    Abstract base class for embedding models.

    This class extends LLMModel with embedding-specific functionality.
    """

    def __init__(
        self,
        model_id: ModelId,
        model_name: str,
        provider_id: ProviderId,
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the embedding model.

        Args:
            model_id: Unique identifier for the model
            model_name: Human-readable name for the model
            provider_id: Provider identifier
            config: Optional initial configuration
        """
        super().__init__(model_id, model_name, provider_id, config)
        self.add_capability("embedding")
        self.add_capability("vector_generation")
        self._embedding_dimensions = 0

    @property
    def embedding_dimensions(self) -> int:
        """Get the embedding dimensions."""
        return self._embedding_dimensions

    @abstractmethod
    def create_embedding(self, text: Content, **kwargs: Any) -> ResponseT:
        """
        Create an embedding for text.

        Args:
            text: Text to embed
            **kwargs: Additional parameters

        Returns:
            Embedding response
        """
        pass

    @abstractmethod
    def create_embeddings_batch(self, texts: List[Content], **kwargs: Any) -> ResponseT:
        """
        Create embeddings for multiple texts.

        Args:
            texts: List of texts to embed
            **kwargs: Additional parameters

        Returns:
            Batch embedding response
        """
        pass

    def set_embedding_dimensions(self, dimensions: int) -> None:
        """
        Set the embedding dimensions.

        Args:
            dimensions: Number of dimensions
        """
        self._embedding_dimensions = dimensions


class LLMManager(MonitorableComponent[RequestT, ResponseT]):
    """
    Abstract base class for LLM managers.

    This class provides functionality for managing multiple
    LLM providers and models.
    """

    def __init__(
        self, manager_id: str, name: str, config: Optional[ConfigDict] = None
    ) -> None:
        """
        Initialize the LLM manager.

        Args:
            manager_id: Unique identifier for the manager
            name: Human-readable name for the manager
            config: Optional initial configuration
        """
        super().__init__(manager_id, name, config)
        self._providers: Dict[ProviderId, LLMProvider] = {}
        self._model_registry: Dict[ModelId, LLMModel] = {}
        self._routing_strategy = "round_robin"

    @property
    def providers(self) -> Dict[ProviderId, LLMProvider]:
        """Get registered providers."""
        return self._providers.copy()

    @property
    def model_registry(self) -> Dict[ModelId, LLMModel]:
        """Get model registry."""
        return self._model_registry.copy()

    @abstractmethod
    def register_provider(self, provider: LLMProvider) -> None:
        """
        Register an LLM provider.

        Args:
            provider: Provider to register
        """
        pass

    @abstractmethod
    def unregister_provider(self, provider_id: ProviderId) -> None:
        """
        Unregister an LLM provider.

        Args:
            provider_id: Provider identifier to unregister
        """
        pass

    @abstractmethod
    def get_model(self, model_id: ModelId) -> Optional[LLMModel]:
        """
        Get a model by ID.

        Args:
            model_id: Model identifier

        Returns:
            Model instance or None if not found
        """
        pass

    @abstractmethod
    def route_request(
        self, request: RequestT, preferred_model: Optional[ModelId] = None
    ) -> ResponseT:
        """
        Route a request to an appropriate model.

        Args:
            request: Request to route
            preferred_model: Optional preferred model ID

        Returns:
            Response from the selected model
        """
        pass

    def set_routing_strategy(self, strategy: str) -> None:
        """
        Set the routing strategy.

        Args:
            strategy: Routing strategy name
        """
        self._routing_strategy = strategy

    def get_routing_strategy(self) -> str:
        """
        Get the current routing strategy.

        Returns:
            Current routing strategy
        """
        return self._routing_strategy

    def get_available_models(self) -> List[LLMModel]:
        """
        Get all available models.

        Returns:
            List of available models
        """
        return list(self._model_registry.values())

    def get_models_by_capability(self, capability: str) -> List[LLMModel]:
        """
        Get models with a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of models with the capability
        """
        return [
            model
            for model in self._model_registry.values()
            if model.has_capability(capability)
        ]
