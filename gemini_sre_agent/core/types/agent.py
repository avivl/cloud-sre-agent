# gemini_sre_agent/core/types/agent.py

"""
Agent-specific type definitions.

This module defines type aliases and protocols specific to agent operations,
including request/response types, state management, and agent coordination.
"""

from typing import Any, Dict, List, Optional, Protocol, TypeVar, Union
from typing_extensions import TypeAlias

from .base import (
    AgentId,
    AgentName,
    AgentStatus,
    ConfigDict,
    Content,
    JsonDict,
    Priority,
    RequestId,
    SessionId,
    Timestamp,
    UserId,
)

# Agent-specific type variables
AgentT = TypeVar('AgentT', bound='BaseAgent')
RequestT = TypeVar('RequestT', bound='AgentRequest')
ResponseT = TypeVar('ResponseT', bound='AgentResponse')

# Request/Response types
RequestType: TypeAlias = str  # 'triage', 'analysis', 'remediation'
ResponseType: TypeAlias = str  # 'success', 'error', 'partial'

# Agent operation types
OperationType: TypeAlias = str  # 'process', 'analyze', 'remediate', 'monitor'
OperationStatus: TypeAlias = str  # 'pending', 'running', 'completed', 'failed'

# Agent context types
AgentContext: TypeAlias = Dict[str, Any]
AgentMetadata: TypeAlias = Dict[str, Any]
AgentCapabilities: TypeAlias = List[str]

# Prompt types
PromptTemplate: TypeAlias = str
PromptVariables: TypeAlias = Dict[str, Any]
PromptContext: TypeAlias = Dict[str, Any]

# Response types
ResponseContent: TypeAlias = Content
ResponseMetadata: TypeAlias = Dict[str, Any]
ResponseConfidence: TypeAlias = float  # 0.0-1.0

# State management types
StateKey: TypeAlias = str
StateValue: TypeAlias = Any
StateSnapshot: TypeAlias = Dict[StateKey, StateValue]

# Agent coordination types
CoordinationMessage: TypeAlias = Dict[str, Any]
CoordinationChannel: TypeAlias = str
CoordinationEvent: TypeAlias = str

# Workflow types
WorkflowId: TypeAlias = str
WorkflowStep: TypeAlias = str
WorkflowStatus: TypeAlias = str  # 'pending', 'running', 'completed', 'failed', 'cancelled'

# Agent protocols
class BaseAgent(Protocol):
    """Base protocol for all agents."""
    
    @property
    def agent_id(self) -> AgentId:
        """Get the agent's unique identifier."""
        ...
    
    @property
    def agent_name(self) -> AgentName:
        """Get the agent's name."""
        ...
    
    @property
    def status(self) -> AgentStatus:
        """Get the agent's current status."""
        ...
    
    def process(self, request: 'AgentRequest') -> 'AgentResponse':
        """Process a request and return a response."""
        ...


class AgentRequest(Protocol):
    """Protocol for agent requests."""
    
    @property
    def request_id(self) -> RequestId:
        """Get the request's unique identifier."""
        ...
    
    @property
    def request_type(self) -> RequestType:
        """Get the request type."""
        ...
    
    @property
    def content(self) -> Content:
        """Get the request content."""
        ...
    
    @property
    def context(self) -> AgentContext:
        """Get the request context."""
        ...
    
    @property
    def priority(self) -> Priority:
        """Get the request priority."""
        ...


class AgentResponse(Protocol):
    """Protocol for agent responses."""
    
    @property
    def response_id(self) -> str:
        """Get the response's unique identifier."""
        ...
    
    @property
    def request_id(self) -> RequestId:
        """Get the associated request ID."""
        ...
    
    @property
    def response_type(self) -> ResponseType:
        """Get the response type."""
        ...
    
    @property
    def content(self) -> ResponseContent:
        """Get the response content."""
        ...
    
    @property
    def confidence(self) -> ResponseConfidence:
        """Get the response confidence score."""
        ...
    
    @property
    def metadata(self) -> ResponseMetadata:
        """Get the response metadata."""
        ...


class StatefulAgent(Protocol):
    """Protocol for agents that maintain state."""
    
    def get_state(self, key: StateKey) -> Optional[StateValue]:
        """Get state value by key."""
        ...
    
    def set_state(self, key: StateKey, value: StateValue) -> None:
        """Set state value by key."""
        ...
    
    def clear_state(self, key: StateKey) -> None:
        """Clear state value by key."""
        ...
    
    def get_state_snapshot(self) -> StateSnapshot:
        """Get complete state snapshot."""
        ...


class ConfigurableAgent(Protocol):
    """Protocol for agents that can be configured."""
    
    def configure(self, config: ConfigDict) -> None:
        """Configure the agent."""
        ...
    
    def get_config(self) -> ConfigDict:
        """Get current configuration."""
        ...


class LoggableAgent(Protocol):
    """Protocol for agents that support logging."""
    
    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """Log a message."""
        ...
    
    def get_log_context(self) -> Dict[str, Any]:
        """Get logging context."""
        ...


# Specialized agent types
class TriageAgent(BaseAgent, Protocol):
    """Protocol for triage agents."""
    
    def triage_log(self, log_content: Content, context: AgentContext) -> 'TriageResponse':
        """Triage a log entry."""
        ...


class AnalysisAgent(BaseAgent, Protocol):
    """Protocol for analysis agents."""
    
    def analyze_patterns(self, data: Content, context: AgentContext) -> 'AnalysisResponse':
        """Analyze patterns in data."""
        ...


class RemediationAgent(BaseAgent, Protocol):
    """Protocol for remediation agents."""
    
    def generate_remediation(self, issue: Content, context: AgentContext) -> 'RemediationResponse':
        """Generate remediation actions."""
        ...


# Response type definitions
class TriageResponse(Protocol):
    """Protocol for triage responses."""
    
    @property
    def priority(self) -> Priority:
        """Get the triage priority."""
        ...
    
    @property
    def category(self) -> str:
        """Get the issue category."""
        ...
    
    @property
    def severity(self) -> str:
        """Get the issue severity."""
        ...


class AnalysisResponse(Protocol):
    """Protocol for analysis responses."""
    
    @property
    def patterns(self) -> List[Dict[str, Any]]:
        """Get detected patterns."""
        ...
    
    @property
    def insights(self) -> List[str]:
        """Get analysis insights."""
        ...
    
    @property
    def recommendations(self) -> List[str]:
        """Get recommendations."""
        ...


class RemediationResponse(Protocol):
    """Protocol for remediation responses."""
    
    @property
    def actions(self) -> List[Dict[str, Any]]:
        """Get remediation actions."""
        ...
    
    @property
    def estimated_impact(self) -> str:
        """Get estimated impact."""
        ...
    
    @property
    def risk_level(self) -> str:
        """Get risk level."""
        ...


# Utility functions
def create_agent_context(
    user_id: Optional[UserId] = None,
    session_id: Optional[SessionId] = None,
    tenant_id: Optional[str] = None,
    **kwargs: Any
) -> AgentContext:
    """
    Create a standardized agent context.
    
    Args:
        user_id: User identifier
        session_id: Session identifier
        tenant_id: Tenant identifier
        **kwargs: Additional context data
        
    Returns:
        Standardized agent context
    """
    context: AgentContext = {
        'timestamp': Timestamp,
        **kwargs
    }
    
    if user_id:
        context['user_id'] = user_id
    if session_id:
        context['session_id'] = session_id
    if tenant_id:
        context['tenant_id'] = tenant_id
    
    return context


def validate_agent_request(request: AgentRequest) -> bool:
    """
    Validate an agent request.
    
    Args:
        request: Request to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required properties
        _ = request.request_id
        _ = request.request_type
        _ = request.content
        _ = request.context
        _ = request.priority
        
        # Validate priority range
        if not (1 <= request.priority <= 10):
            return False
        
        # Validate request type
        if request.request_type not in ['triage', 'analysis', 'remediation']:
            return False
        
        return True
    except (AttributeError, TypeError):
        return False


def validate_agent_response(response: AgentResponse) -> bool:
    """
    Validate an agent response.
    
    Args:
        response: Response to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        # Check required properties
        _ = response.response_id
        _ = response.request_id
        _ = response.response_type
        _ = response.content
        _ = response.confidence
        _ = response.metadata
        
        # Validate confidence range
        if not (0.0 <= response.confidence <= 1.0):
            return False
        
        # Validate response type
        if response.response_type not in ['success', 'error', 'partial']:
            return False
        
        return True
    except (AttributeError, TypeError):
        return False
