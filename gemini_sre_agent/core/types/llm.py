# gemini_sre_agent/core/types/llm.py

"""
LLM-specific type definitions.

This module defines type aliases and protocols specific to LLM operations,
including provider types, model types, and response types.
"""

from typing import Any, Optional, Protocol, TypeAlias, TypeVar

from .base import (
    Content,
    ModelId,
    ProviderId,
    Timestamp,
)

# LLM-specific type variables
ProviderT = TypeVar("ProviderT", bound="LLMProvider")
ModelT = TypeVar("ModelT", bound="LLMModel")
ResponseT = TypeVar("ResponseT", bound="LLMResponse")

# Provider types
ProviderType: TypeAlias = str  # 'openai', 'anthropic', 'google', 'azure', etc.
ProviderStatus: TypeAlias = str  # 'active', 'inactive', 'error', 'maintenance'

# Model types
ModelType: TypeAlias = str  # 'chat', 'completion', 'embedding', 'image'
ModelStatus: TypeAlias = str  # 'available', 'deprecated', 'beta', 'alpha'
ModelCapability: TypeAlias = str  # 'text', 'vision', 'function_calling', 'streaming'

# Request/Response types
RequestRole: TypeAlias = str  # 'system', 'user', 'assistant', 'function'
ResponseRole: TypeAlias = str  # 'assistant', 'function'

# Content types
ContentType: TypeAlias = str  # 'text', 'image', 'function_call', 'function_result'
ContentFormat: TypeAlias = str  # 'plain', 'markdown', 'json', 'xml'

# Token types
TokenCount: TypeAlias = int
TokenUsage: TypeAlias = dict[
    str, TokenCount
]  # {'prompt': 100, 'completion': 50, 'total': 150}

# Cost types
CostPerToken: TypeAlias = float
TotalCost: TypeAlias = float
CostBreakdown: TypeAlias = dict[str, TotalCost]

# Performance types
Latency: TypeAlias = float  # milliseconds
Throughput: TypeAlias = float  # tokens per second
RateLimit: TypeAlias = int  # requests per minute

# Configuration types
ModelConfig: TypeAlias = dict[str, Any]
ProviderConfig: TypeAlias = dict[str, Any]
LLMConfig: TypeAlias = dict[str, Any]

# Error types
ErrorType: TypeAlias = str  # 'rate_limit', 'quota_exceeded', 'invalid_request', etc.
ErrorCode: TypeAlias = str
RetryAfter: TypeAlias = int  # seconds


# LLM protocols
class LLMProvider(Protocol):
    """Protocol for LLM providers."""

    @property
    def provider_id(self) -> ProviderId:
        """Get the provider's unique identifier."""
        ...

    @property
    def provider_type(self) -> ProviderType:
        """Get the provider type."""
        ...

    @property
    def status(self) -> ProviderStatus:
        """Get the provider status."""
        ...

    def get_models(self) -> list["LLMModel"]:
        """Get available models."""
        ...

    def get_model(self, model_id: ModelId) -> Optional["LLMModel"]:
        """Get a specific model by ID."""
        ...


class LLMModel(Protocol):
    """Protocol for LLM models."""

    @property
    def model_id(self) -> ModelId:
        """Get the model's unique identifier."""
        ...

    @property
    def model_type(self) -> ModelType:
        """Get the model type."""
        ...

    @property
    def provider_id(self) -> ProviderId:
        """Get the provider ID."""
        ...

    @property
    def capabilities(self) -> list[ModelCapability]:
        """Get model capabilities."""
        ...

    def generate(self, request: "LLMRequest") -> "LLMResponse":
        """Generate a response from the model."""
        ...


class LLMRequest(Protocol):
    """Protocol for LLM requests."""

    @property
    def messages(self) -> list["Message"]:
        """Get the conversation messages."""
        ...

    @property
    def model_id(self) -> ModelId:
        """Get the model ID."""
        ...

    @property
    def config(self) -> ModelConfig:
        """Get the model configuration."""
        ...

    @property
    def stream(self) -> bool:
        """Get whether to stream the response."""
        ...


class LLMResponse(Protocol):
    """Protocol for LLM responses."""

    @property
    def content(self) -> Content:
        """Get the response content."""
        ...

    @property
    def model_id(self) -> ModelId:
        """Get the model ID used."""
        ...

    @property
    def usage(self) -> TokenUsage:
        """Get token usage information."""
        ...

    @property
    def cost(self) -> TotalCost:
        """Get the total cost."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Get response metadata."""
        ...


class Message(Protocol):
    """Protocol for conversation messages."""

    @property
    def role(self) -> RequestRole:
        """Get the message role."""
        ...

    @property
    def content(self) -> Content:
        """Get the message content."""
        ...

    @property
    def content_type(self) -> ContentType:
        """Get the content type."""
        ...


class StreamingResponse(Protocol):
    """Protocol for streaming responses."""

    def __iter__(self) -> "StreamingResponse":
        """Make the response iterable."""
        ...

    def __next__(self) -> "StreamingChunk":
        """Get the next streaming chunk."""
        ...


class StreamingChunk(Protocol):
    """Protocol for streaming chunks."""

    @property
    def content(self) -> str:
        """Get the chunk content."""
        ...

    @property
    def finished(self) -> bool:
        """Get whether this is the final chunk."""
        ...

    @property
    def metadata(self) -> dict[str, Any]:
        """Get chunk metadata."""
        ...


# Specialized provider types
class ChatProvider(LLMProvider, Protocol):
    """Protocol for chat-based providers."""

    def chat_completion(self, request: "ChatRequest") -> "ChatResponse":
        """Generate a chat completion."""
        ...


class CompletionProvider(LLMProvider, Protocol):
    """Protocol for completion-based providers."""

    def text_completion(self, request: "CompletionRequest") -> "CompletionResponse":
        """Generate a text completion."""
        ...


class EmbeddingProvider(LLMProvider, Protocol):
    """Protocol for embedding providers."""

    def create_embedding(self, request: "EmbeddingRequest") -> "EmbeddingResponse":
        """Create an embedding."""
        ...


# Request/Response type definitions
class ChatRequest(LLMRequest, Protocol):
    """Protocol for chat requests."""

    @property
    def messages(self) -> list[Message]:
        """Get the conversation messages."""
        ...

    @property
    def temperature(self) -> float:
        """Get the temperature setting."""
        ...

    @property
    def max_tokens(self) -> int | None:
        """Get the maximum tokens."""
        ...


class ChatResponse(LLMResponse, Protocol):
    """Protocol for chat responses."""

    @property
    def message(self) -> Message:
        """Get the response message."""
        ...

    @property
    def finish_reason(self) -> str:
        """Get the finish reason."""
        ...


class CompletionRequest(LLMRequest, Protocol):
    """Protocol for completion requests."""

    @property
    def prompt(self) -> Content:
        """Get the prompt."""
        ...

    @property
    def temperature(self) -> float:
        """Get the temperature setting."""
        ...

    @property
    def max_tokens(self) -> int | None:
        """Get the maximum tokens."""
        ...


class CompletionResponse(LLMResponse, Protocol):
    """Protocol for completion responses."""

    @property
    def text(self) -> Content:
        """Get the completed text."""
        ...


class EmbeddingRequest(LLMRequest, Protocol):
    """Protocol for embedding requests."""

    @property
    def input(self) -> Content | list[Content]:
        """Get the input to embed."""
        ...


class EmbeddingResponse(LLMResponse, Protocol):
    """Protocol for embedding responses."""

    @property
    def embeddings(self) -> list[list[float]]:
        """Get the embeddings."""
        ...

    @property
    def dimensions(self) -> int:
        """Get the embedding dimensions."""
        ...


# Utility functions
def create_message(
    role: RequestRole, content: Content, content_type: ContentType = "text"
) -> dict[str, Any]:
    """
    Create a message dictionary.

    Args:
        role: Message role
        content: Message content
        content_type: Content type

    Returns:
        Message dictionary
    """
    return {
        "role": role,
        "content": content,
        "content_type": content_type,
        "timestamp": Timestamp,
    }


def calculate_token_cost(
    prompt_tokens: TokenCount,
    completion_tokens: TokenCount,
    prompt_cost_per_token: CostPerToken,
    completion_cost_per_token: CostPerToken,
) -> TotalCost:
    """
    Calculate the total cost for token usage.

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        prompt_cost_per_token: Cost per prompt token
        completion_cost_per_token: Cost per completion token

    Returns:
        Total cost
    """
    prompt_cost = prompt_tokens * prompt_cost_per_token
    completion_cost = completion_tokens * completion_cost_per_token
    return prompt_cost + completion_cost


def validate_model_config(config: ModelConfig) -> bool:
    """
    Validate a model configuration.

    Args:
        config: Configuration to validate

    Returns:
        True if valid, False otherwise
    """
    required_fields = ["model_id", "provider_id", "model_type"]

    for field in required_fields:
        if field not in config:
            return False

    # Validate temperature if present
    if "temperature" in config:
        temp = config["temperature"]
        if not isinstance(temp, (int, float)) or not (0.0 <= temp <= 2.0):
            return False

    # Validate max_tokens if present
    if "max_tokens" in config:
        max_tokens = config["max_tokens"]
        if not isinstance(max_tokens, int) or max_tokens <= 0:
            return False

    return True


def create_usage_dict(
    prompt_tokens: TokenCount,
    completion_tokens: TokenCount,
    total_tokens: TokenCount | None = None,
) -> TokenUsage:
    """
    Create a token usage dictionary.

    Args:
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        total_tokens: Total tokens (calculated if not provided)

    Returns:
        Token usage dictionary
    """
    if total_tokens is None:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }
