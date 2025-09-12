# gemini_sre_agent/llm/mixing/context_manager.py

"""
Context manager module for the model mixer system.

This module provides context management capabilities including context building,
sharing, validation, and optimization for multi-model interactions.
"""

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..constants import MAX_PROMPT_LENGTH

logger = logging.getLogger(__name__)


@dataclass
class ContextData:
    """Data structure for context information."""

    context_id: str
    context_type: str
    data: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        """Check if context has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def touch(self) -> None:
        """Update access information."""
        self.access_count += 1
        self.last_accessed = time.time()
        self.updated_at = time.time()


@dataclass
class ContextSharingRule:
    """Rule for sharing context between models."""

    source_model: str
    target_model: str
    context_types: List[str]
    sharing_mode: str = "full"  # full, filtered, summary
    filter_keys: Optional[List[str]] = None
    max_context_size: int = 1000


class ContextManager:
    """Manages context for multi-model interactions."""

    def __init__(self, max_contexts: int = 100, default_ttl: int = 3600):
        """
        Initialize the context manager.

        Args:
            max_contexts: Maximum number of contexts to store
            default_ttl: Default time-to-live for contexts in seconds
        """
        self.max_contexts = max_contexts
        self.default_ttl = default_ttl
        self.contexts: Dict[str, ContextData] = {}
        self.sharing_rules: List[ContextSharingRule] = []
        self.context_usage_stats: Dict[str, Dict[str, Any]] = {}

        logger.info(f"ContextManager initialized with max_contexts={max_contexts}")

    def create_context(
        self,
        context_id: str,
        context_type: str,
        data: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None,
    ) -> ContextData:
        """
        Create a new context.

        Args:
            context_id: Unique identifier for the context
            context_type: Type of context (e.g., 'task', 'analysis', 'result')
            data: Context data
            metadata: Optional metadata
            ttl: Time-to-live in seconds

        Returns:
            Created context data

        Raises:
            ValueError: If context ID already exists or data is invalid
        """
        if context_id in self.contexts:
            raise ValueError(f"Context {context_id} already exists")

        if not data:
            raise ValueError("Context data cannot be empty")

        # Clean up expired contexts
        self._cleanup_expired_contexts()

        # Enforce max contexts limit
        if len(self.contexts) >= self.max_contexts:
            self._evict_oldest_context()

        context = ContextData(
            context_id=context_id,
            context_type=context_type,
            data=data,
            metadata=metadata or {},
            expires_at=time.time() + (ttl or self.default_ttl),
        )

        self.contexts[context_id] = context
        self._update_usage_stats(context_id, "created")

        logger.info(f"Created context {context_id} of type {context_type}")
        return context

    def get_context(self, context_id: str) -> Optional[ContextData]:
        """
        Get context by ID.

        Args:
            context_id: Context identifier

        Returns:
            Context data or None if not found
        """
        context = self.contexts.get(context_id)
        if context and not context.is_expired():
            context.touch()
            self._update_usage_stats(context_id, "accessed")
            return context
        elif context and context.is_expired():
            del self.contexts[context_id]
            self._update_usage_stats(context_id, "expired")

        return None

    def update_context(
        self,
        context_id: str,
        data: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Update existing context.

        Args:
            context_id: Context identifier
            data: New context data
            metadata: New metadata

        Returns:
            True if updated successfully, False if context not found
        """
        context = self.get_context(context_id)
        if not context:
            return False

        if data is not None:
            context.data.update(data)

        if metadata is not None:
            context.metadata.update(metadata)

        context.updated_at = time.time()
        self._update_usage_stats(context_id, "updated")

        logger.info(f"Updated context {context_id}")
        return True

    def delete_context(self, context_id: str) -> bool:
        """
        Delete context by ID.

        Args:
            context_id: Context identifier

        Returns:
            True if deleted successfully, False if context not found
        """
        if context_id in self.contexts:
            del self.contexts[context_id]
            self._update_usage_stats(context_id, "deleted")
            logger.info(f"Deleted context {context_id}")
            return True

        return False

    def list_contexts(
        self,
        context_type: Optional[str] = None,
        include_expired: bool = False,
    ) -> List[ContextData]:
        """
        List contexts with optional filtering.

        Args:
            context_type: Optional context type filter
            include_expired: Whether to include expired contexts

        Returns:
            List of context data
        """
        contexts = []
        for context in self.contexts.values():
            if context.is_expired() and not include_expired:
                continue

            if context_type and context.context_type != context_type:
                continue

            contexts.append(context)

        return contexts

    def add_sharing_rule(self, rule: ContextSharingRule) -> None:
        """
        Add a context sharing rule.

        Args:
            rule: Context sharing rule
        """
        self.sharing_rules.append(rule)
        logger.info(f"Added sharing rule: {rule.source_model} -> {rule.target_model}")

    def get_shared_context(
        self,
        source_model: str,
        target_model: str,
        context_types: Optional[List[str]] = None,
    ) -> List[ContextData]:
        """
        Get contexts that should be shared between models.

        Args:
            source_model: Source model name
            target_model: Target model name
            context_types: Optional list of context types to filter by

        Returns:
            List of shared context data
        """
        shared_contexts = []

        for rule in self.sharing_rules:
            if rule.source_model == source_model and rule.target_model == target_model:

                # Filter by context types if specified
                rule_types = rule.context_types
                if context_types:
                    rule_types = [t for t in rule.context_types if t in context_types]

                # Get contexts of the specified types
                for context in self.list_contexts():
                    if context.context_type in rule_types:
                        # Apply sharing mode
                        shared_context = self._apply_sharing_mode(context, rule)
                        if shared_context:
                            shared_contexts.append(shared_context)

        return shared_contexts

    def _apply_sharing_mode(
        self, context: ContextData, rule: ContextSharingRule
    ) -> Optional[ContextData]:
        """
        Apply sharing mode to context data.

        Args:
            context: Original context
            rule: Sharing rule

        Returns:
            Modified context or None if filtered out
        """
        if rule.sharing_mode == "full":
            return context
        elif rule.sharing_mode == "filtered":
            if rule.filter_keys:
                filtered_data = {
                    key: context.data.get(key)
                    for key in rule.filter_keys
                    if key in context.data
                }
                if filtered_data:
                    return ContextData(
                        context_id=f"{context.context_id}_filtered",
                        context_type=context.context_type,
                        data=filtered_data,
                        metadata=context.metadata,
                        created_at=context.created_at,
                        updated_at=time.time(),
                    )
            return context
        elif rule.sharing_mode == "summary":
            # Create a summary of the context
            summary_data = self._create_context_summary(context)
            if summary_data:
                return ContextData(
                    context_id=f"{context.context_id}_summary",
                    context_type=f"{context.context_type}_summary",
                    data=summary_data,
                    metadata=context.metadata,
                    created_at=context.created_at,
                    updated_at=time.time(),
                )

        return None

    def _create_context_summary(self, context: ContextData) -> Dict[str, Any]:
        """
        Create a summary of context data.

        Args:
            context: Context to summarize

        Returns:
            Summary data dictionary
        """
        summary = {
            "context_id": context.context_id,
            "context_type": context.context_type,
            "created_at": context.created_at,
            "data_keys": list(context.data.keys()),
            "data_size": len(str(context.data)),
        }

        # Add key-value pairs for important data
        important_keys = ["summary", "result", "status", "error", "confidence"]
        for key in important_keys:
            if key in context.data:
                summary[key] = context.data[key]

        return summary

    def validate_context(self, context: ContextData) -> List[str]:
        """
        Validate context data.

        Args:
            context: Context to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        # Check required fields
        if not context.context_id:
            errors.append("Context ID is required")

        if not context.context_type:
            errors.append("Context type is required")

        if not context.data:
            errors.append("Context data is required")

        # Check data size
        data_str = str(context.data)
        if len(data_str) > MAX_PROMPT_LENGTH:
            errors.append(
                f"Context data too large (max {MAX_PROMPT_LENGTH} characters)"
            )

        # Check for dangerous patterns
        if self._contains_dangerous_patterns(data_str):
            errors.append("Context data contains potentially dangerous patterns")

        return errors

    def _contains_dangerous_patterns(self, data: str) -> bool:
        """
        Check for dangerous patterns in context data.

        Args:
            data: Data to check

        Returns:
            True if dangerous patterns found
        """
        dangerous_patterns = [
            r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe\b",
            r"<object\b",
            r"<embed\b",
            r"<link\b[^>]*javascript",
            r"<meta\b[^>]*http-equiv",
        ]

        return any(
            re.search(pattern, data, re.IGNORECASE) for pattern in dangerous_patterns
        )

    def _cleanup_expired_contexts(self) -> None:
        """Remove expired contexts."""
        expired_ids = [
            context_id
            for context_id, context in self.contexts.items()
            if context.is_expired()
        ]

        for context_id in expired_ids:
            del self.contexts[context_id]
            self._update_usage_stats(context_id, "expired")

        if expired_ids:
            logger.info(f"Cleaned up {len(expired_ids)} expired contexts")

    def _evict_oldest_context(self) -> None:
        """Evict the oldest context to make room for new ones."""
        if not self.contexts:
            return

        oldest_context_id = min(
            self.contexts.keys(), key=lambda k: self.contexts[k].last_accessed
        )

        del self.contexts[oldest_context_id]
        self._update_usage_stats(oldest_context_id, "evicted")
        logger.info(f"Evicted oldest context {oldest_context_id}")

    def _update_usage_stats(self, context_id: str, action: str) -> None:
        """
        Update usage statistics for a context.

        Args:
            context_id: Context identifier
            action: Action performed on context
        """
        if context_id not in self.context_usage_stats:
            self.context_usage_stats[context_id] = {
                "created": 0,
                "accessed": 0,
                "updated": 0,
                "deleted": 0,
                "expired": 0,
                "evicted": 0,
            }

        stats = self.context_usage_stats[context_id]
        if action in stats:
            stats[action] += 1

    def get_usage_stats(self, context_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get usage statistics.

        Args:
            context_id: Optional specific context ID

        Returns:
            Usage statistics dictionary
        """
        if context_id:
            return self.context_usage_stats.get(context_id, {})

        # Aggregate stats for all contexts
        total_stats = {
            "total_contexts": len(self.contexts),
            "total_created": 0,
            "total_accessed": 0,
            "total_updated": 0,
            "total_deleted": 0,
            "total_expired": 0,
            "total_evicted": 0,
        }

        for stats in self.context_usage_stats.values():
            for key, value in stats.items():
                total_stats[f"total_{key}"] += value

        return total_stats

    def clear_all_contexts(self) -> None:
        """Clear all contexts."""
        self.contexts.clear()
        self.context_usage_stats.clear()
        logger.info("Cleared all contexts")

    def get_context_summary(self) -> Dict[str, Any]:
        """
        Get summary of all contexts.

        Returns:
            Context summary dictionary
        """
        context_types = {}
        total_size = 0

        for context in self.contexts.values():
            context_type = context.context_type
            if context_type not in context_types:
                context_types[context_type] = 0
            context_types[context_type] += 1

            total_size += len(str(context.data))

        return {
            "total_contexts": len(self.contexts),
            "context_types": context_types,
            "total_size": total_size,
            "sharing_rules": len(self.sharing_rules),
            "usage_stats": self.get_usage_stats(),
        }
