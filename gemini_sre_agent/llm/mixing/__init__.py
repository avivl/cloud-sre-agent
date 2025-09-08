"""
Advanced Model Mixing Module.

This module provides sophisticated model mixing capabilities for complex tasks,
including task decomposition, parallel execution, result aggregation, and
context sharing between multiple models.
"""

from .context_sharing import (
    ContextEntry,
    ContextManager,
    ContextPropagator,
    FeedbackLoop,
    SharedContext,
    context_manager,
    context_propagator,
    feedback_loop,
)
from .intelligent_cache import IntelligentCache
from .model_mixer import (
    MixingResult,
    MixingStrategy,
    ModelConfig,
    ModelMixer,
    ResultAggregator,
    SimpleResultAggregator,
    SimpleTaskDecomposer,
    TaskDecomposer,
    TaskDecomposition,
    TaskType,
)

__all__ = [
    # Model mixing
    "MixingStrategy",
    "TaskType",
    "ModelConfig",
    "MixingResult",
    "TaskDecomposition",
    "TaskDecomposer",
    "SimpleTaskDecomposer",
    "ResultAggregator",
    "SimpleResultAggregator",
    "ModelMixer",
    # Context sharing
    "ContextManager",
    "ContextPropagator",
    "FeedbackLoop",
    "SharedContext",
    "ContextEntry",
    "context_manager",
    "context_propagator",
    "feedback_loop",
    # Intelligent caching
    "IntelligentCache",
]
