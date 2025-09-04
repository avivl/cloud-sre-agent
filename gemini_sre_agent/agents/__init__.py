# gemini_sre_agent/agents/__init__.py

"""
Enhanced agent base classes with structured output support.

This module provides the foundation for all agents in the system, including
structured output capabilities, primary/fallback model logic, and integration
with Mirascope for prompt management.
"""

from .base import BaseAgent, AgentStats
from .response_models import TextResponse, AnalysisResponse, CodeResponse
from .specialized import TextAgent, AnalysisAgent, CodeAgent
from .legacy_adapter import LegacyAgentAdapter

__all__ = [
    "BaseAgent",
    "AgentStats", 
    "TextResponse",
    "AnalysisResponse",
    "CodeResponse",
    "TextAgent",
    "AnalysisAgent", 
    "CodeAgent",
    "LegacyAgentAdapter",
]
