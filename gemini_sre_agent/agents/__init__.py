# gemini_sre_agent/agents/__init__.py

"""
Enhanced agent base classes with structured output support.

This module provides the foundation for all agents in the system, including
structured output capabilities, primary/fallback model logic, and integration
with Mirascope for prompt management. Now includes multi-provider support.
"""

from .base import AgentStats, BaseAgent
from .enhanced_base import EnhancedBaseAgent
from .enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedCodeAgent,
    EnhancedRemediationAgent,
    EnhancedTextAgent,
    EnhancedTriageAgent,
)
from .response_models import AnalysisResult, CodeResponse, TextResponse
from .specialized.analysis_agent import EnhancedAnalysisAgent
from .specialized.code_agent import EnhancedCodeAgent
from .specialized.text_agent import EnhancedTextAgent

__all__ = [
    # Base agents
    "BaseAgent",
    "AgentStats",
    "TextResponse",
    "AnalysisResult",
    "CodeResponse",
    "EnhancedTextAgent",
    "EnhancedAnalysisAgent",
    "EnhancedCodeAgent",
    # Enhanced agents (multi-provider support)
    "EnhancedBaseAgent",
    "EnhancedTriageAgent",
    "EnhancedRemediationAgent",
]
