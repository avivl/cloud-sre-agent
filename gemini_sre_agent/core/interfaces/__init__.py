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
]
