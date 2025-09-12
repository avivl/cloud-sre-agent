# gemini_sre_agent/core/interfaces/__init__.py

"""
Core interfaces for the Gemini SRE Agent system.

This package provides abstract base classes and interfaces that form
the foundation for all major components in the system.
"""

from .base import (
    BaseComponent,
    ConfigurableComponent,
    MonitorableComponent,
    ProcessableComponent,
    StatefulComponent,
)
from .agent import (
    AgentCoordinator,
    AnalysisAgent,
    BaseAgent,
    RemediationAgent,
    TriageAgent,
)
from .llm import (
    ChatModel,
    CompletionModel,
    EmbeddingModel,
    LLMManager,
    LLMModel,
    LLMProvider,
)
from .protocols import (
    AgentLike,
    Alertable,
    AsyncBatchProcessor,
    AsyncProcessable,
    BatchProcessor,
    Cacheable,
    CircuitBreaker,
    Configurable,
    CostTrackable,
    Deserializable,
    EventEmitter,
    EventListener,
    FallbackProvider,
    Filter,
    HealthCheckable,
    Identifiable,
    LoadBalancer,
    LockManager,
    Loggable,
    MetricsCollector,
    ModelLike,
    Observer,
    Processable,
    ProviderLike,
    RateLimited,
    RequestLike,
    ResponseLike,
    Retryable,
    Serializable,
    Stateful,
    Streamable,
    Subject,
    Timestamped,
    TokenCountable,
    Transformer,
    Validatable,
    WorkflowOrchestrator,
    WorkflowStep,
    # Additional protocols
    ResourceManager,
    Pipeline,
    Aggregator,
    Scheduler,
    get_protocol_methods,
    implements_protocol,
    validate_protocol_implementation,
)

__all__ = [
    # Base interfaces
    "BaseComponent",
    "ConfigurableComponent",
    "StatefulComponent",
    "ProcessableComponent",
    "MonitorableComponent",
    
    # Agent interfaces
    "BaseAgent",
    "TriageAgent",
    "AnalysisAgent",
    "RemediationAgent",
    "AgentCoordinator",
    
    # LLM interfaces
    "LLMProvider",
    "LLMModel",
    "ChatModel",
    "CompletionModel",
    "EmbeddingModel",
    "LLMManager",
    
    # Protocol classes
    "Serializable",
    "Deserializable",
    "Identifiable",
    "Timestamped",
    "Configurable",
    "Stateful",
    "Loggable",
    "Validatable",
    "HealthCheckable",
    "MetricsCollector",
    "Alertable",
    "Processable",
    "AsyncProcessable",
    "Streamable",
    "Cacheable",
    "Retryable",
    "RateLimited",
    "CostTrackable",
    "TokenCountable",
    "AgentLike",
    "ProviderLike",
    "ModelLike",
    "RequestLike",
    "ResponseLike",
    "WorkflowStep",
    "WorkflowOrchestrator",
    "EventEmitter",
    "EventListener",
    "ResourceManager",
    "LoadBalancer",
    "CircuitBreaker",
    "FallbackProvider",
    "BatchProcessor",
    "AsyncBatchProcessor",
    "Pipeline",
    "Transformer",
    "Filter",
    "Aggregator",
    "Scheduler",
    "LockManager",
    "Observer",
    "Subject",
    
    # Protocol utilities
    "implements_protocol",
    "get_protocol_methods",
    "validate_protocol_implementation",
]
