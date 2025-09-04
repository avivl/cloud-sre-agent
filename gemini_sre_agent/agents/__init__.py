# gemini_sre_agent/agents/__init__.py

"""
Enhanced agent base classes with structured output support.

This module provides the foundation for all agents in the system, including
structured output capabilities, primary/fallback model logic, and integration
with Mirascope for prompt management. Now includes multi-provider support.
"""

from .base import AgentStats, BaseAgent
from .enhanced_adapter import (
    AgentMigrationHelper,
    BackwardCompatibilityWrapper,
    EnhancedAgentAdapter,
)
from .enhanced_base import EnhancedBaseAgent
from .enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedCodeAgent,
    EnhancedRemediationAgent,
    EnhancedTextAgent,
    EnhancedTriageAgent,
)
from .legacy_adapter import LegacyAgentAdapter
from .response_models import AnalysisResponse, CodeResponse, TextResponse
from .specialized import AnalysisAgent, CodeAgent, TextAgent

__all__ = [
    # Legacy agents (backward compatibility)
    "BaseAgent",
    "AgentStats",
    "TextResponse",
    "AnalysisResponse",
    "CodeResponse",
    "TextAgent",
    "AnalysisAgent",
    "CodeAgent",
    "LegacyAgentAdapter",
    # Enhanced agents (multi-provider support)
    "EnhancedBaseAgent",
    "EnhancedTextAgent",
    "EnhancedAnalysisAgent",
    "EnhancedCodeAgent",
    "EnhancedTriageAgent",
    "EnhancedRemediationAgent",
    # Migration and compatibility
    "EnhancedAgentAdapter",
    "AgentMigrationHelper",
    "BackwardCompatibilityWrapper",
]
