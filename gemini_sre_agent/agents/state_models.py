# gemini_sre_agent/agents/state_models.py

"""
State management models for agent execution and workflow context.

This module provides comprehensive state management models for tracking agent
execution state, workflow context, and persistent data structures needed for
multi-step agent operations.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# State Management Enums
# ============================================================================


class AgentState(str, Enum):
    """Agent execution states."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    PROCESSING = "processing"
    WAITING = "waiting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class WorkflowState(str, Enum):
    """Workflow execution states."""

    CREATED = "created"
    STARTED = "started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class StateTransition(str, Enum):
    """Valid state transitions."""

    # Agent state transitions
    IDLE_TO_INITIALIZING = "idle_to_initializing"
    INITIALIZING_TO_PROCESSING = "initializing_to_processing"
    PROCESSING_TO_WAITING = "processing_to_waiting"
    WAITING_TO_PROCESSING = "waiting_to_processing"
    PROCESSING_TO_COMPLETED = "processing_to_completed"
    PROCESSING_TO_FAILED = "processing_to_failed"
    ANY_TO_CANCELLED = "any_to_cancelled"
    ANY_TO_PAUSED = "any_to_paused"
    PAUSED_TO_PROCESSING = "paused_to_processing"

    # Workflow state transitions
    CREATED_TO_STARTED = "created_to_started"
    STARTED_TO_RUNNING = "started_to_running"
    RUNNING_TO_PAUSED = "running_to_paused"
    PAUSED_TO_RUNNING = "paused_to_running"
    RUNNING_TO_COMPLETED = "running_to_completed"
    RUNNING_TO_FAILED = "running_to_failed"
    ANY_TO_CANCELLED_WF = "any_to_cancelled_wf"
    FAILED_TO_ROLLED_BACK = "failed_to_rolled_back"


# ============================================================================
# Generic State Models
# ============================================================================

T = TypeVar("T")


class StateSnapshot(BaseModel, Generic[T]):
    """Generic state snapshot for serialization."""

    state_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique state identifier"
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Snapshot timestamp",
    )
    state_type: str = Field(..., description="Type of state being captured")
    data: T = Field(..., description="State data")
    version: str = Field("1.0", description="State schema version")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


class StateTransition(BaseModel):
    """Record of a state transition."""

    transition_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique transition identifier"
    )
    from_state: str = Field(..., description="Previous state")
    to_state: str = Field(..., description="New state")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Transition timestamp",
    )
    reason: Optional[str] = Field(None, description="Reason for transition")
    triggered_by: Optional[str] = Field(
        None, description="What triggered the transition"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Transition metadata"
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}


# ============================================================================
# Agent Execution State Models
# ============================================================================


class AgentExecutionContext(BaseModel):
    """Context for agent execution."""

    session_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Session identifier"
    )
    request_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Request identifier"
    )
    agent_id: str = Field(..., description="Agent identifier")
    agent_type: str = Field(..., description="Type of agent")
    user_id: Optional[str] = Field(None, description="User identifier")
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    environment: str = Field("production", description="Execution environment")
    priority: int = Field(1, ge=1, le=10, description="Execution priority")
    timeout_seconds: Optional[int] = Field(None, description="Execution timeout")
    retry_count: int = Field(0, ge=0, description="Number of retries attempted")
    max_retries: int = Field(3, ge=0, description="Maximum retries allowed")


class AgentExecutionMetrics(BaseModel):
    """Metrics for agent execution."""

    start_time: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Execution start time",
    )
    end_time: Optional[datetime] = Field(None, description="Execution end time")
    duration_ms: Optional[float] = Field(
        None, description="Execution duration in milliseconds"
    )
    tokens_used: int = Field(0, ge=0, description="Number of tokens used")
    cost_usd: Optional[float] = Field(None, ge=0.0, description="Cost in USD")
    memory_usage_mb: Optional[float] = Field(
        None, ge=0.0, description="Memory usage in MB"
    )
    cpu_usage_percent: Optional[float] = Field(
        None, ge=0.0, le=100.0, description="CPU usage percentage"
    )
    api_calls_made: int = Field(0, ge=0, description="Number of API calls made")
    errors_encountered: int = Field(0, ge=0, description="Number of errors encountered")
    warnings_generated: int = Field(0, ge=0, description="Number of warnings generated")

    @field_validator("duration_ms", mode="before")
    @classmethod
    def calculate_duration(cls, v, info):
        """Calculate duration from start and end times."""
        if hasattr(info, "data"):
            data = info.data
            if "start_time" in data and "end_time" in data:
                start = data["start_time"]
                end = data["end_time"]
                if isinstance(start, datetime) and isinstance(end, datetime):
                    return (end - start).total_seconds() * 1000
        return v


class AgentExecutionState(BaseModel):
    """Complete agent execution state."""

    state_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique state identifier"
    )
    current_state: AgentState = Field(
        AgentState.IDLE, description="Current agent state"
    )
    context: AgentExecutionContext = Field(..., description="Execution context")
    metrics: AgentExecutionMetrics = Field(
        default_factory=AgentExecutionMetrics, description="Execution metrics"
    )
    state_history: List[StateTransition] = Field(
        default_factory=list, description="History of state transitions"
    )
    error_history: List[Dict[str, Any]] = Field(
        default_factory=list, description="History of errors encountered"
    )
    warnings: List[str] = Field(default_factory=list, description="Current warnings")
    data: Dict[str, Any] = Field(
        default_factory=dict, description="Agent-specific data"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )

    class Config:
        frozen = True
        json_encoders = {datetime: lambda v: v.isoformat()}

    def transition_to(
        self, new_state: AgentState, reason: Optional[str] = None
    ) -> "AgentExecutionState":
        """Create a new state with transition to new_state."""
        transition = StateTransition(
            from_state=self.current_state.value,
            to_state=new_state.value,
            reason=reason,
            triggered_by="agent_execution",
        )

        new_state_history = self.state_history + [transition]

        return AgentExecutionState(
            state_id=str(uuid4()),
            current_state=new_state,
            context=self.context,
            metrics=self.metrics,
            state_history=new_state_history,
            error_history=self.error_history,
            warnings=self.warnings,
            data=self.data,
            last_updated=datetime.now(timezone.utc),
            created_at=self.created_at,
        )

    def add_error(self, error: Dict[str, Any]) -> "AgentExecutionState":
        """Add an error to the state."""
        new_error_history = self.error_history + [error]
        return AgentExecutionState(
            state_id=str(uuid4()),
            current_state=self.current_state,
            context=self.context,
            metrics=self.metrics,
            state_history=self.state_history,
            error_history=new_error_history,
            warnings=self.warnings,
            data=self.data,
            last_updated=datetime.now(timezone.utc),
            created_at=self.created_at,
        )

    def add_warning(self, warning: str) -> "AgentExecutionState":
        """Add a warning to the state."""
        new_warnings = self.warnings + [warning]
        return AgentExecutionState(
            state_id=str(uuid4()),
            current_state=self.current_state,
            context=self.context,
            metrics=self.metrics,
            state_history=self.state_history,
            error_history=self.error_history,
            warnings=new_warnings,
            data=self.data,
            last_updated=datetime.now(timezone.utc),
            created_at=self.created_at,
        )


# ============================================================================
# Workflow Context Models
# ============================================================================


class WorkflowStep(BaseModel):
    """Individual step in a workflow."""

    step_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique step identifier"
    )
    step_name: str = Field(..., description="Name of the step")
    step_type: str = Field(..., description="Type of step")
    agent_id: Optional[str] = Field(None, description="Agent responsible for this step")
    status: AgentState = Field(AgentState.IDLE, description="Step status")
    input_data: Dict[str, Any] = Field(
        default_factory=dict, description="Input data for the step"
    )
    output_data: Dict[str, Any] = Field(
        default_factory=dict, description="Output data from the step"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Step IDs this step depends on"
    )
    started_at: Optional[datetime] = Field(None, description="Step start time")
    completed_at: Optional[datetime] = Field(None, description="Step completion time")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, ge=0, description="Number of retries for this step")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Step-specific metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class WorkflowContext(BaseModel):
    """Context for workflow execution."""

    workflow_id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique workflow identifier"
    )
    workflow_name: str = Field(..., description="Name of the workflow")
    workflow_type: str = Field(..., description="Type of workflow")
    current_state: WorkflowState = Field(
        WorkflowState.CREATED, description="Current workflow state"
    )
    steps: List[WorkflowStep] = Field(
        default_factory=list, description="Workflow steps"
    )
    global_data: Dict[str, Any] = Field(
        default_factory=dict, description="Global workflow data"
    )
    variables: Dict[str, Any] = Field(
        default_factory=dict, description="Workflow variables"
    )
    created_by: Optional[str] = Field(None, description="User who created the workflow")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    started_at: Optional[datetime] = Field(None, description="Workflow start time")
    completed_at: Optional[datetime] = Field(
        None, description="Workflow completion time"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
    error_message: Optional[str] = Field(None, description="Error message if failed")
    retry_count: int = Field(0, ge=0, description="Number of workflow retries")
    max_retries: int = Field(3, ge=0, description="Maximum workflow retries")
    timeout_seconds: Optional[int] = Field(None, description="Workflow timeout")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Workflow metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def transition_to(
        self, new_state: WorkflowState, reason: Optional[str] = None
    ) -> "WorkflowContext":
        """Create a new workflow context with transition to new_state."""
        return WorkflowContext(
            workflow_id=self.workflow_id,
            workflow_name=self.workflow_name,
            workflow_type=self.workflow_type,
            current_state=new_state,
            steps=self.steps,
            global_data=self.global_data,
            variables=self.variables,
            created_by=self.created_by,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            last_updated=datetime.now(timezone.utc),
            error_message=self.error_message,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            metadata=self.metadata,
        )

    def add_step(self, step: WorkflowStep) -> "WorkflowContext":
        """Add a step to the workflow."""
        new_steps = self.steps + [step]
        return WorkflowContext(
            workflow_id=self.workflow_id,
            workflow_name=self.workflow_name,
            workflow_type=self.workflow_type,
            current_state=self.current_state,
            steps=new_steps,
            global_data=self.global_data,
            variables=self.variables,
            created_by=self.created_by,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            last_updated=datetime.now(timezone.utc),
            error_message=self.error_message,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            metadata=self.metadata,
        )

    def update_step(self, step_id: str, updates: Dict[str, Any]) -> "WorkflowContext":
        """Update a specific step in the workflow."""
        updated_steps = []
        for step in self.steps:
            if step.step_id == step_id:
                updated_step = step.model_copy(update=updates)
                updated_steps.append(updated_step)
            else:
                updated_steps.append(step)

        return WorkflowContext(
            workflow_id=self.workflow_id,
            workflow_name=self.workflow_name,
            workflow_type=self.workflow_type,
            current_state=self.current_state,
            steps=updated_steps,
            global_data=self.global_data,
            variables=self.variables,
            created_by=self.created_by,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            last_updated=datetime.now(timezone.utc),
            error_message=self.error_message,
            retry_count=self.retry_count,
            max_retries=self.max_retries,
            timeout_seconds=self.timeout_seconds,
            metadata=self.metadata,
        )


# ============================================================================
# Persistent Agent Data Models
# ============================================================================


class ConversationHistory(BaseModel):
    """History of agent conversations."""

    conversation_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique conversation identifier",
    )
    agent_id: str = Field(..., description="Agent identifier")
    user_id: Optional[str] = Field(None, description="User identifier")
    messages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Conversation messages"
    )
    started_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Conversation start time",
    )
    last_message_at: Optional[datetime] = Field(
        None, description="Last message timestamp"
    )
    total_messages: int = Field(0, ge=0, description="Total number of messages")
    total_tokens: int = Field(0, ge=0, description="Total tokens used")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Conversation metadata"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def add_message(self, message: Dict[str, Any]) -> "ConversationHistory":
        """Add a message to the conversation history."""
        new_messages = self.messages + [message]
        return ConversationHistory(
            conversation_id=self.conversation_id,
            agent_id=self.agent_id,
            user_id=self.user_id,
            messages=new_messages,
            started_at=self.started_at,
            last_message_at=datetime.now(timezone.utc),
            total_messages=self.total_messages + 1,
            total_tokens=self.total_tokens + message.get("tokens", 0),
            metadata=self.metadata,
        )


class PersistentAgentData(BaseModel):
    """Persistent data for agent operations."""

    agent_id: str = Field(..., description="Agent identifier")
    agent_type: str = Field(..., description="Type of agent")
    data_type: str = Field(..., description="Type of persistent data")
    data: Dict[str, Any] = Field(..., description="Persistent data")
    version: str = Field("1.0", description="Data schema version")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Creation timestamp",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Last update timestamp",
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    access_count: int = Field(0, ge=0, description="Number of times accessed")
    last_accessed: Optional[datetime] = Field(None, description="Last access timestamp")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Data metadata")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}

    def update_data(self, new_data: Dict[str, Any]) -> "PersistentAgentData":
        """Update the persistent data."""
        return PersistentAgentData(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            data_type=self.data_type,
            data=new_data,
            version=self.version,
            created_at=self.created_at,
            last_updated=datetime.now(timezone.utc),
            expires_at=self.expires_at,
            access_count=self.access_count,
            last_accessed=self.last_accessed,
            metadata=self.metadata,
        )

    def mark_accessed(self) -> "PersistentAgentData":
        """Mark the data as accessed."""
        return PersistentAgentData(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            data_type=self.data_type,
            data=self.data,
            version=self.version,
            created_at=self.created_at,
            last_updated=self.last_updated,
            expires_at=self.expires_at,
            access_count=self.access_count + 1,
            last_accessed=datetime.now(timezone.utc),
            metadata=self.metadata,
        )


# ============================================================================
# State Management Utilities
# ============================================================================


class StateManager(BaseModel):
    """Utility class for state management operations."""

    @staticmethod
    def validate_state_transition(
        from_state: Union[AgentState, WorkflowState],
        to_state: Union[AgentState, WorkflowState],
    ) -> bool:
        """Validate if a state transition is allowed."""
        # Define valid transitions
        valid_transitions = {
            # Agent state transitions
            (AgentState.IDLE, AgentState.INITIALIZING),
            (AgentState.INITIALIZING, AgentState.PROCESSING),
            (AgentState.PROCESSING, AgentState.WAITING),
            (AgentState.WAITING, AgentState.PROCESSING),
            (AgentState.PROCESSING, AgentState.COMPLETED),
            (AgentState.PROCESSING, AgentState.FAILED),
            (AgentState.ANY, AgentState.CANCELLED),
            (AgentState.ANY, AgentState.PAUSED),
            (AgentState.PAUSED, AgentState.PROCESSING),
            # Workflow state transitions
            (WorkflowState.CREATED, WorkflowState.STARTED),
            (WorkflowState.STARTED, WorkflowState.RUNNING),
            (WorkflowState.RUNNING, WorkflowState.PAUSED),
            (WorkflowState.PAUSED, WorkflowState.RUNNING),
            (WorkflowState.RUNNING, WorkflowState.COMPLETED),
            (WorkflowState.RUNNING, WorkflowState.FAILED),
            (WorkflowState.ANY, WorkflowState.CANCELLED),
            (WorkflowState.FAILED, WorkflowState.ROLLED_BACK),
        }

        return (from_state, to_state) in valid_transitions

    @staticmethod
    def create_state_snapshot(
        state: Union[AgentExecutionState, WorkflowContext],
    ) -> StateSnapshot:
        """Create a snapshot of the current state."""
        if isinstance(state, AgentExecutionState):
            return StateSnapshot(
                state_type="agent_execution",
                data=state.model_dump(),
                metadata={"agent_id": state.context.agent_id},
            )
        elif isinstance(state, WorkflowContext):
            return StateSnapshot(
                state_type="workflow",
                data=state.model_dump(),
                metadata={"workflow_id": state.workflow_id},
            )
        else:
            raise ValueError(f"Unsupported state type: {type(state)}")

    @staticmethod
    def restore_state_from_snapshot(
        snapshot: StateSnapshot,
    ) -> Union[AgentExecutionState, WorkflowContext]:
        """Restore state from a snapshot."""
        if snapshot.state_type == "agent_execution":
            return AgentExecutionState.model_validate(snapshot.data)
        elif snapshot.state_type == "workflow":
            return WorkflowContext.model_validate(snapshot.data)
        else:
            raise ValueError(f"Unsupported snapshot type: {snapshot.state_type}")
