# gemini_sre_agent/core/interfaces/agent.py

"""
Agent-specific interfaces for the Gemini SRE Agent system.

This module defines abstract base classes and interfaces specific
to agent operations and coordination.
"""

from abc import abstractmethod
from typing import Any, TypeVar

from ..types import (
    AgentContext,
    AgentId,
    AgentName,
    ConfigDict,
    Content,
    Priority,
    RequestId,
    UserId,
)
from .base import MonitorableComponent

# Generic type variables
RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class BaseAgent(MonitorableComponent[RequestT, ResponseT]):
    """
    Abstract base class for all agents.

    This class provides the core interface and functionality
    that all agents must implement.
    """

    def __init__(
        self,
        agent_id: AgentId,
        agent_name: AgentName,
        config: ConfigDict | None = None,
    ) -> None:
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            config: Optional initial configuration
        """
        super().__init__(agent_id, agent_name, config)
        self._agent_id = agent_id
        self._agent_name = agent_name
        self._capabilities = []
        self._current_request_id = None
        self._current_user_id = None

    @property
    def agent_id(self) -> AgentId:
        """Get the agent's unique identifier."""
        return self._agent_id

    @property
    def agent_name(self) -> AgentName:
        """Get the agent's name."""
        return self._agent_name

    @property
    def capabilities(self) -> list[str]:
        """Get the agent's capabilities."""
        return self._capabilities.copy()

    @property
    def current_request_id(self) -> RequestId | None:
        """Get the current request ID being processed."""
        return self._current_request_id

    @property
    def current_user_id(self) -> UserId | None:
        """Get the current user ID."""
        return self._current_user_id

    @abstractmethod
    def process_request(self, request: RequestT, context: AgentContext) -> ResponseT:
        """
        Process a request and return a response.

        Args:
            request: Request to process
            context: Agent context

        Returns:
            Processing response
        """
        pass

    @abstractmethod
    def validate_request(self, request: RequestT) -> bool:
        """
        Validate a request.

        Args:
            request: Request to validate

        Returns:
            True if valid, False otherwise
        """
        pass

    @abstractmethod
    def can_handle(self, request: RequestT) -> bool:
        """
        Check if the agent can handle a request.

        Args:
            request: Request to check

        Returns:
            True if can handle, False otherwise
        """
        pass

    def set_current_request(
        self, request_id: RequestId, user_id: UserId | None = None
    ) -> None:
        """
        Set the current request being processed.

        Args:
            request_id: Request identifier
            user_id: Optional user identifier
        """
        self._current_request_id = request_id
        self._current_user_id = user_id

    def clear_current_request(self) -> None:
        """Clear the current request."""
        self._current_request_id = None
        self._current_user_id = None

    def add_capability(self, capability: str) -> None:
        """
        Add a capability to the agent.

        Args:
            capability: Capability to add
        """
        if capability not in self._capabilities:
            self._capabilities.append(capability)

    def remove_capability(self, capability: str) -> None:
        """
        Remove a capability from the agent.

        Args:
            capability: Capability to remove
        """
        if capability in self._capabilities:
            self._capabilities.remove(capability)

    def has_capability(self, capability: str) -> bool:
        """
        Check if the agent has a specific capability.

        Args:
            capability: Capability to check

        Returns:
            True if has capability, False otherwise
        """
        return capability in self._capabilities

    def get_agent_context(self) -> AgentContext:
        """
        Get the agent's context information.

        Returns:
            Agent context dictionary
        """
        return {
            "agent_id": self._agent_id,
            "agent_name": self._agent_name,
            "capabilities": self._capabilities,
            "status": self._status,
            "current_request_id": self._current_request_id,
            "current_user_id": self._current_user_id,
            "processing_count": self._processing_count,
            "last_processed_at": self._last_processed_at,
        }


class TriageAgent(BaseAgent[RequestT, ResponseT]):
    """
    Abstract base class for triage agents.

    This class extends BaseAgent with triage-specific functionality.
    """

    def __init__(
        self,
        agent_id: AgentId,
        agent_name: AgentName,
        config: ConfigDict | None = None,
    ) -> None:
        """
        Initialize the triage agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            config: Optional initial configuration
        """
        super().__init__(agent_id, agent_name, config)
        self.add_capability("log_analysis")
        self.add_capability("priority_assignment")
        self.add_capability("categorization")

    @abstractmethod
    def triage_log(self, log_content: Content, context: AgentContext) -> ResponseT:
        """
        Triage a log entry.

        Args:
            log_content: Log content to triage
            context: Agent context

        Returns:
            Triage response
        """
        pass

    @abstractmethod
    def assign_priority(self, log_content: Content, context: AgentContext) -> Priority:
        """
        Assign priority to a log entry.

        Args:
            log_content: Log content
            context: Agent context

        Returns:
            Assigned priority level
        """
        pass

    @abstractmethod
    def categorize_issue(self, log_content: Content, context: AgentContext) -> str:
        """
        Categorize an issue from log content.

        Args:
            log_content: Log content
            context: Agent context

        Returns:
            Issue category
        """
        pass


class AnalysisAgent(BaseAgent[RequestT, ResponseT]):
    """
    Abstract base class for analysis agents.

    This class extends BaseAgent with analysis-specific functionality.
    """

    def __init__(
        self,
        agent_id: AgentId,
        agent_name: AgentName,
        config: ConfigDict | None = None,
    ) -> None:
        """
        Initialize the analysis agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            config: Optional initial configuration
        """
        super().__init__(agent_id, agent_name, config)
        self.add_capability("pattern_detection")
        self.add_capability("trend_analysis")
        self.add_capability("insight_generation")

    @abstractmethod
    def analyze_patterns(self, data: Content, context: AgentContext) -> ResponseT:
        """
        Analyze patterns in data.

        Args:
            data: Data to analyze
            context: Agent context

        Returns:
            Analysis response
        """
        pass

    @abstractmethod
    def detect_trends(
        self, data: Content, context: AgentContext
    ) -> list[dict[str, Any]]:
        """
        Detect trends in data.

        Args:
            data: Data to analyze
            context: Agent context

        Returns:
            List of detected trends
        """
        pass

    @abstractmethod
    def generate_insights(
        self, analysis_result: Any, context: AgentContext
    ) -> list[str]:
        """
        Generate insights from analysis results.

        Args:
            analysis_result: Analysis result
            context: Agent context

        Returns:
            List of insights
        """
        pass


class RemediationAgent(BaseAgent[RequestT, ResponseT]):
    """
    Abstract base class for remediation agents.

    This class extends BaseAgent with remediation-specific functionality.
    """

    def __init__(
        self,
        agent_id: AgentId,
        agent_name: AgentName,
        config: ConfigDict | None = None,
    ) -> None:
        """
        Initialize the remediation agent.

        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name for the agent
            config: Optional initial configuration
        """
        super().__init__(agent_id, agent_name, config)
        self.add_capability("action_generation")
        self.add_capability("risk_assessment")
        self.add_capability("impact_analysis")

    @abstractmethod
    def generate_remediation(self, issue: Content, context: AgentContext) -> ResponseT:
        """
        Generate remediation actions for an issue.

        Args:
            issue: Issue to remediate
            context: Agent context

        Returns:
            Remediation response
        """
        pass

    @abstractmethod
    def assess_risk(self, issue: Content, context: AgentContext) -> str:
        """
        Assess the risk level of an issue.

        Args:
            issue: Issue to assess
            context: Agent context

        Returns:
            Risk level assessment
        """
        pass

    @abstractmethod
    def analyze_impact(
        self, remediation_action: Any, context: AgentContext
    ) -> dict[str, Any]:
        """
        Analyze the impact of a remediation action.

        Args:
            remediation_action: Remediation action
            context: Agent context

        Returns:
            Impact analysis results
        """
        pass


class AgentCoordinator(MonitorableComponent[RequestT, ResponseT]):
    """
    Abstract base class for agent coordinators.

    This class provides functionality for coordinating multiple agents.
    """

    def __init__(
        self, coordinator_id: str, name: str, config: ConfigDict | None = None
    ) -> None:
        """
        Initialize the agent coordinator.

        Args:
            coordinator_id: Unique identifier for the coordinator
            name: Human-readable name for the coordinator
            config: Optional initial configuration
        """
        super().__init__(coordinator_id, name, config)
        self._agents: dict[AgentId, BaseAgent] = {}
        self._workflow_state = {}

    @property
    def agents(self) -> dict[AgentId, BaseAgent]:
        """Get registered agents."""
        return self._agents.copy()

    @abstractmethod
    def register_agent(self, agent: BaseAgent) -> None:
        """
        Register an agent with the coordinator.

        Args:
            agent: Agent to register
        """
        pass

    @abstractmethod
    def unregister_agent(self, agent_id: AgentId) -> None:
        """
        Unregister an agent from the coordinator.

        Args:
            agent_id: Agent identifier to unregister
        """
        pass

    @abstractmethod
    def route_request(self, request: RequestT, context: AgentContext) -> ResponseT:
        """
        Route a request to the appropriate agent.

        Args:
            request: Request to route
            context: Agent context

        Returns:
            Response from the selected agent
        """
        pass

    @abstractmethod
    def coordinate_workflow(
        self, workflow: dict[str, Any], context: AgentContext
    ) -> ResponseT:
        """
        Coordinate a multi-agent workflow.

        Args:
            workflow: Workflow definition
            context: Agent context

        Returns:
            Workflow result
        """
        pass

    def get_agent_by_id(self, agent_id: AgentId) -> BaseAgent | None:
        """
        Get an agent by its ID.

        Args:
            agent_id: Agent identifier

        Returns:
            Agent instance or None if not found
        """
        return self._agents.get(agent_id)

    def get_agents_by_capability(self, capability: str) -> list[BaseAgent]:
        """
        Get agents that have a specific capability.

        Args:
            capability: Capability to search for

        Returns:
            List of agents with the capability
        """
        return [
            agent for agent in self._agents.values() if agent.has_capability(capability)
        ]

    def get_workflow_state(self) -> dict[str, Any]:
        """
        Get the current workflow state.

        Returns:
            Workflow state dictionary
        """
        return self._workflow_state.copy()

    def set_workflow_state(self, key: str, value: Any) -> None:
        """
        Set a workflow state value.

        Args:
            key: State key
            value: State value
        """
        self._workflow_state[key] = value
