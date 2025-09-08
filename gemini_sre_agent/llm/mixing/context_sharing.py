"""
Context Sharing System for Model Mixing.

This module provides sophisticated context sharing capabilities between models,
including shared memory, context propagation, and result correlation.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single context entry with metadata."""

    key: str
    value: Any
    source_model: str
    source_provider: str
    timestamp: datetime = field(default_factory=datetime.now)
    confidence: float = 1.0
    tags: Set[str] = field(default_factory=set)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SharedContext:
    """Shared context between models in a mixing session."""

    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)
    entries: Dict[str, ContextEntry] = field(default_factory=dict)
    model_interactions: List[Tuple[str, str, str]] = field(
        default_factory=list
    )  # (from_model, to_model, interaction_type)
    correlation_graph: Dict[str, Set[str]] = field(
        default_factory=dict
    )  # model -> related_models


class ContextManager:
    """Manages shared context between models in mixing operations."""

    def __init__(self, max_context_age_hours: int = 24):
        """Initialize the context manager."""
        self.max_context_age = timedelta(hours=max_context_age_hours)
        self.active_contexts: Dict[str, SharedContext] = {}
        self.context_history: List[SharedContext] = []

        logger.info(
            f"ContextManager initialized with {max_context_age_hours}h max context age"
        )

    def create_context(self, session_id: str) -> SharedContext:
        """Create a new shared context session."""
        context = SharedContext(session_id=session_id)
        self.active_contexts[session_id] = context
        logger.info(f"Created new context session: {session_id}")
        return context

    def get_context(self, session_id: str) -> Optional[SharedContext]:
        """Get an existing context session."""
        return self.active_contexts.get(session_id)

    def add_context_entry(
        self,
        session_id: str,
        key: str,
        value: Any,
        source_model: str,
        source_provider: str,
        confidence: float = 1.0,
        tags: Optional[Set[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a context entry to a session."""
        context = self.get_context(session_id)
        if not context:
            logger.warning(f"Context session {session_id} not found")
            return False

        entry = ContextEntry(
            key=key,
            value=value,
            source_model=source_model,
            source_provider=source_provider,
            confidence=confidence,
            tags=tags or set(),
            metadata=metadata or {},
        )

        context.entries[key] = entry
        context.last_updated = datetime.now()

        logger.debug(f"Added context entry {key} from {source_provider}:{source_model}")
        return True

    def get_context_entry(self, session_id: str, key: str) -> Optional[ContextEntry]:
        """Get a specific context entry."""
        context = self.get_context(session_id)
        if not context:
            return None
        return context.entries.get(key)

    def get_context_by_tags(
        self, session_id: str, tags: Set[str]
    ) -> List[ContextEntry]:
        """Get context entries that match any of the given tags."""
        context = self.get_context(session_id)
        if not context:
            return []

        matching_entries = []
        for entry in context.entries.values():
            if entry.tags.intersection(tags):
                matching_entries.append(entry)

        return matching_entries

    def get_context_by_model(
        self, session_id: str, model: str, provider: str
    ) -> List[ContextEntry]:
        """Get context entries from a specific model."""
        context = self.get_context(session_id)
        if not context:
            return []

        matching_entries = []
        for entry in context.entries.values():
            if entry.source_model == model and entry.source_provider == provider:
                matching_entries.append(entry)

        return matching_entries

    def update_context_confidence(
        self, session_id: str, key: str, new_confidence: float
    ) -> bool:
        """Update the confidence of a context entry."""
        context = self.get_context(session_id)
        if not context or key not in context.entries:
            return False

        context.entries[key].confidence = new_confidence
        context.last_updated = datetime.now()
        return True

    def correlate_models(
        self,
        session_id: str,
        model1: str,
        model2: str,
        interaction_type: str = "shared_context",
    ):
        """Record correlation between two models."""
        context = self.get_context(session_id)
        if not context:
            return

        # Add to interaction history
        context.model_interactions.append((model1, model2, interaction_type))

        # Update correlation graph
        if model1 not in context.correlation_graph:
            context.correlation_graph[model1] = set()
        if model2 not in context.correlation_graph:
            context.correlation_graph[model2] = set()

        context.correlation_graph[model1].add(model2)
        context.correlation_graph[model2].add(model1)

        context.last_updated = datetime.now()

    def get_related_models(self, session_id: str, model: str) -> Set[str]:
        """Get models that are correlated with the given model."""
        context = self.get_context(session_id)
        if not context:
            return set()
        return context.correlation_graph.get(model, set())

    def build_context_prompt(
        self,
        session_id: str,
        base_prompt: str,
        include_tags: Optional[Set[str]] = None,
        exclude_tags: Optional[Set[str]] = None,
        max_context_length: int = 2000,
    ) -> str:
        """Build an enhanced prompt with relevant context."""
        context = self.get_context(session_id)
        if not context:
            return base_prompt

        # Collect relevant context entries
        relevant_entries = []

        for entry in context.entries.values():
            # Filter by tags if specified
            if include_tags and not entry.tags.intersection(include_tags):
                continue
            if exclude_tags and entry.tags.intersection(exclude_tags):
                continue

            # Add to relevant entries
            relevant_entries.append(entry)

        # Sort by confidence and timestamp
        relevant_entries.sort(key=lambda x: (x.confidence, x.timestamp), reverse=True)

        # Build context string
        context_parts = []
        current_length = len(base_prompt)

        for entry in relevant_entries:
            context_str = f"[{entry.source_provider}:{entry.source_model}] {entry.key}: {entry.value}"

            if current_length + len(context_str) > max_context_length:
                break

            context_parts.append(context_str)
            current_length += len(context_str)

        if context_parts:
            context_section = "\n\nRelevant Context:\n" + "\n".join(context_parts)
            return base_prompt + context_section

        return base_prompt

    def cleanup_expired_contexts(self):
        """Remove expired context sessions."""
        cutoff_time = datetime.now() - self.max_context_age
        expired_sessions = []

        for session_id, context in self.active_contexts.items():
            if context.last_updated < cutoff_time:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            context = self.active_contexts.pop(session_id)
            self.context_history.append(context)
            logger.info(f"Archived expired context session: {session_id}")

    def get_context_summary(self, session_id: str) -> Dict[str, Any]:
        """Get a summary of a context session."""
        context = self.get_context(session_id)
        if not context:
            return {"error": "Context session not found"}

        # Calculate statistics
        total_entries = len(context.entries)
        unique_models = set()
        unique_providers = set()
        avg_confidence = 0.0

        for entry in context.entries.values():
            unique_models.add(f"{entry.source_provider}:{entry.source_model}")
            unique_providers.add(entry.source_provider)
            avg_confidence += entry.confidence

        if total_entries > 0:
            avg_confidence /= total_entries

        return {
            "session_id": session_id,
            "created_at": context.created_at.isoformat(),
            "last_updated": context.last_updated.isoformat(),
            "total_entries": total_entries,
            "unique_models": len(unique_models),
            "unique_providers": len(unique_providers),
            "average_confidence": avg_confidence,
            "model_interactions": len(context.model_interactions),
            "correlation_graph_size": len(context.correlation_graph),
        }


class ContextPropagator:
    """Handles context propagation between models in mixing operations."""

    def __init__(self, context_manager: ContextManager):
        """Initialize the context propagator."""
        self.context_manager = context_manager

    async def propagate_context(
        self,
        session_id: str,
        from_model: str,
        from_provider: str,
        to_models: List[Tuple[str, str]],  # (model, provider) pairs
        context_keys: List[str],
        propagation_strategy: str = "direct",
    ) -> Dict[str, bool]:
        """Propagate context from one model to others."""
        results = {}

        for to_model, to_provider in to_models:
            try:
                success = await self._propagate_single_context(
                    session_id,
                    from_model,
                    from_provider,
                    to_model,
                    to_provider,
                    context_keys,
                    propagation_strategy,
                )
                results[f"{to_provider}:{to_model}"] = success

                if success:
                    self.context_manager.correlate_models(
                        session_id,
                        f"{from_provider}:{from_model}",
                        f"{to_provider}:{to_model}",
                        "context_propagation",
                    )
            except Exception as e:
                logger.error(
                    f"Failed to propagate context to {to_provider}:{to_model}: {e}"
                )
                results[f"{to_provider}:{to_model}"] = False

        return results

    async def _propagate_single_context(
        self,
        session_id: str,
        from_model: str,
        from_provider: str,
        to_model: str,
        to_provider: str,
        context_keys: List[str],
        propagation_strategy: str,
    ) -> bool:
        """Propagate context to a single model."""
        # Get source context entries
        source_entries = []
        for key in context_keys:
            entry = self.context_manager.get_context_entry(session_id, key)
            if (
                entry
                and entry.source_model == from_model
                and entry.source_provider == from_provider
            ):
                source_entries.append(entry)

        if not source_entries:
            logger.warning(
                f"No source context entries found for {from_provider}:{from_model}"
            )
            return False

        # Apply propagation strategy
        if propagation_strategy == "direct":
            # Direct propagation - copy entries as-is
            for entry in source_entries:
                self.context_manager.add_context_entry(
                    session_id,
                    f"{entry.key}_propagated",
                    entry.value,
                    to_model,
                    to_provider,
                    confidence=entry.confidence * 0.9,  # Slightly reduce confidence
                    tags=entry.tags.union({"propagated"}),
                    metadata={
                        **entry.metadata,
                        "propagated_from": f"{from_provider}:{from_model}",
                    },
                )

        elif propagation_strategy == "transformed":
            # Transformed propagation - modify entries for target model
            for entry in source_entries:
                transformed_value = await self._transform_context_for_model(
                    entry.value, to_model, to_provider
                )
                self.context_manager.add_context_entry(
                    session_id,
                    f"{entry.key}_transformed",
                    transformed_value,
                    to_model,
                    to_provider,
                    confidence=entry.confidence * 0.8,
                    tags=entry.tags.union({"propagated", "transformed"}),
                    metadata={
                        **entry.metadata,
                        "propagated_from": f"{from_provider}:{from_model}",
                    },
                )

        elif propagation_strategy == "summarized":
            # Summarized propagation - create summary of multiple entries
            if len(source_entries) > 1:
                summary = await self._summarize_context_entries(source_entries)
                self.context_manager.add_context_entry(
                    session_id,
                    f"summary_from_{from_provider}_{from_model}",
                    summary,
                    to_model,
                    to_provider,
                    confidence=0.7,  # Lower confidence for summaries
                    tags={"propagated", "summary"},
                    metadata={"propagated_from": f"{from_provider}:{from_model}"},
                )

        return True

    async def _transform_context_for_model(
        self, value: Any, target_model: str, target_provider: str
    ) -> Any:
        """Transform context value for a specific target model."""
        # Simple transformation - in a real implementation, this could be more sophisticated
        if isinstance(value, str):
            return f"[Transformed for {target_provider}:{target_model}] {value}"
        return value

    async def _summarize_context_entries(self, entries: List[ContextEntry]) -> str:
        """Create a summary of multiple context entries."""
        if not entries:
            return ""

        summary_parts = []
        for entry in entries:
            summary_parts.append(f"- {entry.key}: {str(entry.value)[:100]}...")

        return "Context Summary:\n" + "\n".join(summary_parts)


class FeedbackLoop:
    """Implements feedback loops between models for iterative improvement."""

    def __init__(self, context_manager: ContextManager):
        """Initialize the feedback loop system."""
        self.context_manager = context_manager
        self.feedback_history: Dict[str, List[Dict[str, Any]]] = {}

    async def create_feedback_loop(
        self,
        session_id: str,
        model_a: Tuple[str, str],  # (model, provider)
        model_b: Tuple[str, str],  # (model, provider)
        max_iterations: int = 3,
        improvement_threshold: float = 0.1,
    ) -> List[Dict[str, Any]]:
        """Create a feedback loop between two models."""
        loop_id = f"{session_id}_{model_a[1]}:{model_a[0]}_{model_b[1]}:{model_b[0]}"
        iterations = []

        for iteration in range(max_iterations):
            try:
                # Get current context
                context = self.context_manager.get_context(session_id)
                if not context:
                    break

                # Simulate feedback iteration
                iteration_result = await self._execute_feedback_iteration(
                    session_id, model_a, model_b, iteration, context
                )

                iterations.append(iteration_result)

                # Check for improvement
                if iteration > 0:
                    improvement = self._calculate_improvement(
                        iterations[-2], iteration_result
                    )
                    if improvement < improvement_threshold:
                        logger.info(
                            f"Feedback loop converged after {iteration + 1} iterations"
                        )
                        break

            except Exception as e:
                logger.error(f"Error in feedback loop iteration {iteration}: {e}")
                break

        self.feedback_history[loop_id] = iterations
        return iterations

    async def _execute_feedback_iteration(
        self,
        session_id: str,
        model_a: Tuple[str, str],
        model_b: Tuple[str, str],
        iteration: int,
        context: SharedContext,
    ) -> Dict[str, Any]:
        """Execute a single feedback iteration."""
        # This is a simplified implementation
        # In a real system, this would involve actual model calls

        iteration_result = {
            "iteration": iteration,
            "timestamp": datetime.now().isoformat(),
            "model_a": f"{model_a[1]}:{model_a[0]}",
            "model_b": f"{model_b[1]}:{model_b[0]}",
            "context_entries_used": len(context.entries),
            "improvement_score": 0.5 + (iteration * 0.1),  # Mock improvement
            "feedback_applied": True,
        }

        # Record feedback in context
        self.context_manager.add_context_entry(
            session_id,
            f"feedback_iteration_{iteration}",
            iteration_result,
            f"feedback_loop_{model_a[0]}_{model_b[0]}",
            "system",
            confidence=0.8,
            tags={"feedback", f"iteration_{iteration}"},
            metadata={"iteration": iteration},
        )

        return iteration_result

    def _calculate_improvement(
        self, prev_result: Dict[str, Any], current_result: Dict[str, Any]
    ) -> float:
        """Calculate improvement between iterations."""
        prev_score = prev_result.get("improvement_score", 0)
        current_score = current_result.get("improvement_score", 0)
        return abs(current_score - prev_score)

    def get_feedback_history(self, loop_id: str) -> List[Dict[str, Any]]:
        """Get feedback history for a specific loop."""
        return self.feedback_history.get(loop_id, [])


# Global instances
context_manager = ContextManager()
context_propagator = ContextPropagator(context_manager)
feedback_loop = FeedbackLoop(context_manager)
