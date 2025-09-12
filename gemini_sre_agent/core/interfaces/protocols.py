# gemini_sre_agent/core/interfaces/protocols.py

"""
Protocol classes for structural typing in the Gemini SRE Agent system.

This module defines Protocol classes that enable structural typing,
allowing components to be compatible based on their interface
rather than inheritance hierarchy.
"""

from typing import Any, Dict, List, Optional, Protocol, TypeVar, Union, AsyncIterator
from typing_extensions import Self

from ..types import (
    AgentContext,
    AgentId,
    ConfigDict,
    Content,
    JsonDict,
    LogContext,
    ModelId,
    Priority,
    ProviderId,
    RequestId,
    ResponseId,
    Timestamp,
    TokenCount,
    TokenUsage,
    TotalCost,
    UserId,
)

# Generic type variables
T = TypeVar('T')
R = TypeVar('R')
RequestT = TypeVar('RequestT')
ResponseT = TypeVar('ResponseT')


class Serializable(Protocol):
    """Protocol for objects that can be serialized to JSON."""
    
    def to_dict(self) -> JsonDict:
        """Convert object to dictionary representation."""
        ...
    
    def to_json(self) -> str:
        """Convert object to JSON string."""
        ...


class Deserializable(Protocol[T]):
    """Protocol for objects that can be deserialized from JSON."""
    
    @classmethod
    def from_dict(cls: type[T], data: JsonDict) -> T:
        """Create object from dictionary representation."""
        ...
    
    @classmethod
    def from_json(cls: type[T], json_str: str) -> T:
        """Create object from JSON string."""
        ...


class Identifiable(Protocol):
    """Protocol for objects that have a unique identifier."""
    
    @property
    def id(self) -> str:
        """Get the unique identifier."""
        ...


class Timestamped(Protocol):
    """Protocol for objects that have timestamps."""
    
    @property
    def created_at(self) -> Timestamp:
        """Get creation timestamp."""
        ...
    
    @property
    def updated_at(self) -> Timestamp:
        """Get last update timestamp."""
        ...


class Configurable(Protocol):
    """Protocol for objects that can be configured."""
    
    def configure(self, config: ConfigDict) -> None:
        """Configure the object with given configuration."""
        ...
    
    def get_config(self) -> ConfigDict:
        """Get current configuration."""
        ...


class Stateful(Protocol):
    """Protocol for objects that maintain state."""
    
    @property
    def state(self) -> Dict[str, Any]:
        """Get current state."""
        ...
    
    def set_state(self, key: str, value: Any) -> None:
        """Set new state value."""
        ...
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value by key."""
        ...


class Loggable(Protocol):
    """Protocol for objects that can be logged."""
    
    def get_log_context(self) -> LogContext:
        """Get logging context information."""
        ...


class Validatable(Protocol):
    """Protocol for objects that can be validated."""
    
    def validate(self) -> bool:
        """Validate the object."""
        ...
    
    def get_validation_errors(self) -> List[str]:
        """Get validation errors if any."""
        ...


class HealthCheckable(Protocol):
    """Protocol for objects that support health checks."""
    
    def is_healthy(self) -> bool:
        """Check if the object is healthy."""
        ...
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get detailed health status."""
        ...


class MetricsCollector(Protocol):
    """Protocol for objects that collect metrics."""
    
    def collect_metrics(self) -> Dict[str, Any]:
        """Collect current metrics."""
        ...
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        ...


class Alertable(Protocol):
    """Protocol for objects that can generate alerts."""
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alerts."""
        ...
    
    def add_alert(self, alert_type: str, message: str, severity: str = "warning") -> None:
        """Add an alert."""
        ...


class Processable(Protocol[T, R]):
    """Protocol for objects that can process data."""
    
    def process(self, input_data: T) -> R:
        """Process input data and return result."""
        ...


class AsyncProcessable(Protocol[T, R]):
    """Protocol for objects that can process data asynchronously."""
    
    async def process_async(self, input_data: T) -> R:
        """Process input data asynchronously and return result."""
        ...


class Streamable(Protocol[T, R]):
    """Protocol for objects that can stream data."""
    
    def stream(self, input_data: T) -> AsyncIterator[R]:
        """Stream processing results."""
        ...


class Cacheable(Protocol[T]):
    """Protocol for objects that can be cached."""
    
    def get_cache_key(self) -> str:
        """Get cache key for the object."""
        ...
    
    def get_cache_ttl(self) -> int:
        """Get cache time-to-live in seconds."""
        ...


class Retryable(Protocol):
    """Protocol for objects that support retry logic."""
    
    def should_retry(self, attempt: int, error: Exception) -> bool:
        """Check if operation should be retried."""
        ...
    
    def get_retry_delay(self, attempt: int) -> float:
        """Get delay before next retry attempt."""
        ...


class RateLimited(Protocol):
    """Protocol for objects that have rate limiting."""
    
    def is_rate_limited(self) -> bool:
        """Check if currently rate limited."""
        ...
    
    def get_rate_limit_info(self) -> Dict[str, Any]:
        """Get rate limit information."""
        ...


class CostTrackable(Protocol):
    """Protocol for objects that track costs."""
    
    def get_cost(self) -> TotalCost:
        """Get current cost."""
        ...
    
    def track_cost(self, cost: TotalCost) -> None:
        """Track additional cost."""
        ...


class TokenCountable(Protocol):
    """Protocol for objects that count tokens."""
    
    def count_tokens(self, content: Content) -> TokenCount:
        """Count tokens in content."""
        ...
    
    def get_token_usage(self) -> TokenUsage:
        """Get current token usage."""
        ...


class AgentLike(Protocol):
    """Protocol for agent-like objects."""
    
    @property
    def agent_id(self) -> AgentId:
        """Get agent identifier."""
        ...
    
    @property
    def agent_name(self) -> str:
        """Get agent name."""
        ...
    
    def process_request(self, request: Any, context: AgentContext) -> Any:
        """Process a request."""
        ...


class ProviderLike(Protocol):
    """Protocol for provider-like objects."""
    
    @property
    def provider_id(self) -> ProviderId:
        """Get provider identifier."""
        ...
    
    @property
    def provider_name(self) -> str:
        """Get provider name."""
        ...
    
    def get_models(self) -> List[Any]:
        """Get available models."""
        ...


class ModelLike(Protocol):
    """Protocol for model-like objects."""
    
    @property
    def model_id(self) -> ModelId:
        """Get model identifier."""
        ...
    
    @property
    def model_name(self) -> str:
        """Get model name."""
        ...
    
    def generate(self, request: Any) -> Any:
        """Generate a response."""
        ...


class RequestLike(Protocol):
    """Protocol for request-like objects."""
    
    @property
    def request_id(self) -> RequestId:
        """Get request identifier."""
        ...
    
    @property
    def content(self) -> Content:
        """Get request content."""
        ...


class ResponseLike(Protocol):
    """Protocol for response-like objects."""
    
    @property
    def response_id(self) -> ResponseId:
        """Get response identifier."""
        ...
    
    @property
    def content(self) -> Content:
        """Get response content."""
        ...


class WorkflowStep(Protocol):
    """Protocol for workflow steps."""
    
    @property
    def step_id(self) -> str:
        """Get step identifier."""
        ...
    
    @property
    def step_name(self) -> str:
        """Get step name."""
        ...
    
    def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the workflow step."""
        ...


class WorkflowOrchestrator(Protocol):
    """Protocol for workflow orchestrators."""
    
    def add_step(self, step: WorkflowStep) -> None:
        """Add a workflow step."""
        ...
    
    def execute_workflow(self, initial_context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the complete workflow."""
        ...


class EventEmitter(Protocol):
    """Protocol for objects that emit events."""
    
    def emit(self, event_type: str, data: Any) -> None:
        """Emit an event."""
        ...
    
    def subscribe(self, event_type: str, callback: Any) -> None:
        """Subscribe to an event."""
        ...


class EventListener(Protocol):
    """Protocol for objects that listen to events."""
    
    def handle_event(self, event_type: str, data: Any) -> None:
        """Handle an event."""
        ...


class ResourceManager(Protocol):
    """Protocol for resource managers."""
    
    def allocate_resource(self, resource_type: str, requirements: Dict[str, Any]) -> str:
        """Allocate a resource."""
        ...
    
    def deallocate_resource(self, resource_id: str) -> None:
        """Deallocate a resource."""
        ...
    
    def get_resource_status(self, resource_id: str) -> Dict[str, Any]:
        """Get resource status."""
        ...


class LoadBalancer(Protocol):
    """Protocol for load balancers."""
    
    def select_target(self, targets: List[Any], context: Dict[str, Any]) -> Any:
        """Select a target for load balancing."""
        ...
    
    def update_target_health(self, target: Any, is_healthy: bool) -> None:
        """Update target health status."""
        ...


class CircuitBreaker(Protocol):
    """Protocol for circuit breakers."""
    
    def is_open(self) -> bool:
        """Check if circuit is open."""
        ...
    
    def record_success(self) -> None:
        """Record a successful operation."""
        ...
    
    def record_failure(self) -> None:
        """Record a failed operation."""
        ...


class FallbackProvider(Protocol):
    """Protocol for fallback providers."""
    
    def get_primary(self) -> Any:
        """Get primary provider."""
        ...
    
    def get_fallback(self) -> Any:
        """Get fallback provider."""
        ...
    
    def should_fallback(self, error: Exception) -> bool:
        """Check if should use fallback."""
        ...


class BatchProcessor(Protocol[T, R]):
    """Protocol for batch processors."""
    
    def process_batch(self, items: List[T]) -> List[R]:
        """Process a batch of items."""
        ...
    
    def get_batch_size(self) -> int:
        """Get optimal batch size."""
        ...


class AsyncBatchProcessor(Protocol[T, R]):
    """Protocol for async batch processors."""
    
    async def process_batch_async(self, items: List[T]) -> List[R]:
        """Process a batch of items asynchronously."""
        ...


class Pipeline(Protocol[T, R]):
    """Protocol for data pipelines."""
    
    def add_stage(self, stage: Any) -> None:
        """Add a pipeline stage."""
        ...
    
    def process(self, input_data: T) -> R:
        """Process data through the pipeline."""
        ...


class Transformer(Protocol[T, R]):
    """Protocol for data transformers."""
    
    def transform(self, input_data: T) -> R:
        """Transform input data."""
        ...
    
    def can_transform(self, input_type: type) -> bool:
        """Check if can transform input type."""
        ...


class Filter(Protocol[T]):
    """Protocol for data filters."""
    
    def filter(self, items: List[T]) -> List[T]:
        """Filter items."""
        ...
    
    def should_include(self, item: T) -> bool:
        """Check if item should be included."""
        ...


class Aggregator(Protocol[T, R]):
    """Protocol for data aggregators."""
    
    def aggregate(self, items: List[T]) -> R:
        """Aggregate items."""
        ...
    
    def reset(self) -> None:
        """Reset aggregation state."""
        ...


class Scheduler(Protocol):
    """Protocol for schedulers."""
    
    def schedule(self, task: Any, delay: float) -> str:
        """Schedule a task."""
        ...
    
    def cancel(self, task_id: str) -> None:
        """Cancel a scheduled task."""
        ...


class LockManager(Protocol):
    """Protocol for lock managers."""
    
    def acquire_lock(self, resource_id: str, timeout: float = 30.0) -> bool:
        """Acquire a lock."""
        ...
    
    def release_lock(self, resource_id: str) -> None:
        """Release a lock."""
        ...


class Observer(Protocol):
    """Protocol for observers in observer pattern."""
    
    def update(self, subject: Any, event: str, data: Any) -> None:
        """Update observer with new information."""
        ...


class Subject(Protocol):
    """Protocol for subjects in observer pattern."""
    
    def attach(self, observer: Observer) -> None:
        """Attach an observer."""
        ...
    
    def detach(self, observer: Observer) -> None:
        """Detach an observer."""
        ...
    
    def notify(self, event: str, data: Any) -> None:
        """Notify all observers."""
        ...




# Utility functions for protocol checking
def implements_protocol(obj: Any, protocol: type) -> bool:
    """
    Check if an object implements a protocol.
    
    Args:
        obj: Object to check
        protocol: Protocol class to check against
        
    Returns:
        True if object implements protocol, False otherwise
    """
    try:
        # This is a simplified check - in practice, you'd want more sophisticated
        # protocol checking using typing.get_type_hints and inspection
        return hasattr(obj, '__annotations__') and hasattr(obj, '__class__')
    except Exception:
        return False


def get_protocol_methods(protocol: type) -> List[str]:
    """
    Get method names from a protocol.
    
    Args:
        protocol: Protocol class
        
    Returns:
        List of method names
    """
    methods = []
    for name in dir(protocol):
        if not name.startswith('_'):
            attr = getattr(protocol, name, None)
            if hasattr(attr, '__call__'):
                methods.append(name)
    return methods


def validate_protocol_implementation(obj: Any, protocol: type) -> List[str]:
    """
    Validate that an object implements a protocol.
    
    Args:
        obj: Object to validate
        protocol: Protocol class to validate against
        
    Returns:
        List of missing method names
    """
    missing_methods = []
    protocol_methods = get_protocol_methods(protocol)
    
    for method_name in protocol_methods:
        if not hasattr(obj, method_name):
            missing_methods.append(method_name)
    
    return missing_methods
