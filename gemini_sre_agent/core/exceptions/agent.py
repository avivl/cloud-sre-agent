# gemini_sre_agent/core/exceptions/agent.py

"""
Agent-specific exception classes.

This module defines exceptions specific to agent operations, including
prompt processing, response generation, and agent coordination errors.
"""


from .base import AgentError


class PromptError(AgentError):
    """
    Exception raised for prompt-related errors.

    This exception is raised when there are issues with prompt processing,
    such as invalid prompt format, missing required fields, or prompt validation failures.
    """

    pass


class ResponseError(AgentError):
    """
    Exception raised for response-related errors.

    This exception is raised when there are issues with response generation,
    such as invalid response format, missing required fields, or response validation failures.
    """

    pass


class AgentExecutionError(AgentError):
    """
    Exception raised for agent execution errors.

    This exception is raised when there are issues during agent execution,
    such as workflow failures, state management errors, or execution timeouts.
    """

    pass


class AgentConfigurationError(AgentError):
    """
    Exception raised for agent configuration errors.

    This exception is raised when there are issues with agent configuration,
    such as invalid parameters, missing required settings, or configuration conflicts.
    """

    pass


class AgentStateError(AgentError):
    """
    Exception raised for agent state management errors.

    This exception is raised when there are issues with agent state management,
    such as invalid state transitions, state corruption, or state persistence failures.
    """

    pass


class AgentCoordinationError(AgentError):
    """
    Exception raised for agent coordination errors.

    This exception is raised when there are issues with agent coordination,
    such as communication failures, workflow orchestration errors, or agent conflicts.
    """

    pass


class TriageAgentError(AgentError):
    """
    Exception raised for triage agent-specific errors.

    This exception is raised when there are issues specific to the triage agent,
    such as log analysis failures, priority assignment errors, or triage workflow issues.
    """

    pass


class AnalysisAgentError(AgentError):
    """
    Exception raised for analysis agent-specific errors.

    This exception is raised when there are issues specific to the analysis agent,
    such as pattern detection failures, analysis workflow errors, or insight generation issues.
    """

    pass


class RemediationAgentError(AgentError):
    """
    Exception raised for remediation agent-specific errors.

    This exception is raised when there are issues specific to the remediation agent,
    such as action generation failures, remediation workflow errors, or action execution issues.
    """

    pass
