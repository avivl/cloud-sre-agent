"""Flow tracking system for the logging framework."""

from contextlib import contextmanager
from dataclasses import dataclass, field
from threading import local
import time
from typing import Any
import uuid

from .exceptions import FlowTrackingError


@dataclass
class FlowContext:
    """Context for a flow operation."""

    flow_id: str
    operation: str
    start_time: float
    parent_flow_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    duration: float | None = None
    status: str = "running"
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert flow context to dictionary.

        Returns:
            Dictionary representation of the flow context
        """
        return {
            "flow_id": self.flow_id,
            "operation": self.operation,
            "start_time": self.start_time,
            "parent_flow_id": self.parent_flow_id,
            "metadata": self.metadata,
            "tags": self.tags,
            "duration": self.duration,
            "status": self.status,
            "error": self.error,
        }


class FlowTracker:
    """Tracks operations and flows across the system."""

    def __init__(self, config: dict[str, Any] | None = None):
        """Initialize the flow tracker.

        Args:
            config: Optional configuration for flow tracking
        """
        self._config = config or {}
        self._thread_local = local()
        self._active_flows: dict[str, FlowContext] = {}
        self._flow_history: list[FlowContext] = []
        self._max_history = self._config.get("max_history", 1000)

    def start_flow(
        self,
        operation: str,
        flow_id: str | None = None,
        parent_flow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> FlowContext:
        """Start a new flow.

        Args:
            operation: Name of the operation
            flow_id: Optional custom flow ID
            parent_flow_id: Optional parent flow ID
            metadata: Optional metadata for the flow
            tags: Optional tags for the flow

        Returns:
            Flow context for the new flow

        Raises:
            FlowTrackingError: If flow tracking fails
        """
        try:
            if flow_id is None:
                flow_id = self._generate_flow_id(operation)

            # Check for circular references
            if parent_flow_id and self._has_circular_reference(flow_id, parent_flow_id):
                raise FlowTrackingError(
                    f"Circular reference detected: {flow_id} -> {parent_flow_id}",
                    flow_id=flow_id,
                    operation=operation,
                )

            # Create flow context
            flow_context = FlowContext(
                flow_id=flow_id,
                operation=operation,
                start_time=time.time(),
                parent_flow_id=parent_flow_id,
                metadata=metadata or {},
                tags=tags or [],
            )

            # Store flow context
            self._active_flows[flow_id] = flow_context

            # Set thread-local flow ID
            if not hasattr(self._thread_local, "flow_stack"):
                self._thread_local.flow_stack = []
            self._thread_local.flow_stack.append(flow_id)

            return flow_context

        except Exception as e:
            raise FlowTrackingError(
                f"Failed to start flow: {e!s}", flow_id=flow_id, operation=operation
            ) from e

    def end_flow(
        self,
        flow_id: str,
        status: str = "completed",
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> FlowContext:
        """End a flow.

        Args:
            flow_id: ID of the flow to end
            status: Status of the flow completion
            error: Optional error message
            metadata: Optional additional metadata

        Returns:
            Completed flow context

        Raises:
            FlowTrackingError: If flow tracking fails
        """
        try:
            if flow_id not in self._active_flows:
                raise FlowTrackingError(
                    f"Flow not found: {flow_id}", flow_id=flow_id, operation="end_flow"
                )

            flow_context = self._active_flows[flow_id]
            flow_context.duration = time.time() - flow_context.start_time
            flow_context.status = status
            flow_context.error = error

            if metadata:
                flow_context.metadata.update(metadata)

            # Remove from active flows
            del self._active_flows[flow_id]

            # Remove from thread-local stack
            if hasattr(self._thread_local, "flow_stack"):
                try:
                    self._thread_local.flow_stack.remove(flow_id)
                except ValueError:
                    pass  # Flow not in stack

            # Add to history
            self._flow_history.append(flow_context)

            # Trim history if needed
            if len(self._flow_history) > self._max_history:
                self._flow_history = self._flow_history[-self._max_history :]

            return flow_context

        except Exception as e:
            raise FlowTrackingError(
                f"Failed to end flow: {e!s}", flow_id=flow_id, operation="end_flow"
            ) from e

    def get_current_flow_id(self) -> str | None:
        """Get the current flow ID for this thread.

        Returns:
            Current flow ID or None
        """
        if hasattr(self._thread_local, "flow_stack") and self._thread_local.flow_stack:
            return self._thread_local.flow_stack[-1]
        return None

    def get_flow_context(self, flow_id: str) -> FlowContext | None:
        """Get flow context by ID.

        Args:
            flow_id: Flow ID to look up

        Returns:
            Flow context or None if not found
        """
        return self._active_flows.get(flow_id)

    def get_active_flows(self) -> list[FlowContext]:
        """Get all active flows.

        Returns:
            List of active flow contexts
        """
        return list(self._active_flows.values())

    def get_flow_history(self, limit: int | None = None) -> list[FlowContext]:
        """Get flow history.

        Args:
            limit: Optional limit on number of flows to return

        Returns:
            List of flow contexts from history
        """
        if limit is None:
            return self._flow_history.copy()
        return self._flow_history[-limit:]

    def get_flows_by_operation(self, operation: str) -> list[FlowContext]:
        """Get flows by operation name.

        Args:
            operation: Operation name to filter by

        Returns:
            List of flow contexts matching the operation
        """
        return [flow for flow in self._flow_history if flow.operation == operation]

    def get_flows_by_status(self, status: str) -> list[FlowContext]:
        """Get flows by status.

        Args:
            status: Status to filter by

        Returns:
            List of flow contexts matching the status
        """
        return [flow for flow in self._flow_history if flow.status == status]

    def get_flows_by_tag(self, tag: str) -> list[FlowContext]:
        """Get flows by tag.

        Args:
            tag: Tag to filter by

        Returns:
            List of flow contexts containing the tag
        """
        return [flow for flow in self._flow_history if tag in flow.tags]

    def get_flow_tree(self, root_flow_id: str) -> dict[str, Any]:
        """Get flow tree starting from a root flow.

        Args:
            root_flow_id: Root flow ID

        Returns:
            Dictionary representing the flow tree
        """

        def build_tree(flow_id: str) -> dict[str, Any]:
            flow = self.get_flow_context(flow_id)
            if not flow:
                # Try to find in history
                flow = next(
                    (f for f in self._flow_history if f.flow_id == flow_id), None
                )
                if not flow:
                    return {"flow_id": flow_id, "status": "not_found"}

            children = [
                build_tree(child_flow_id)
                for child_flow_id, child_flow in self._active_flows.items()
                if child_flow.parent_flow_id == flow_id
            ]

            return {
                "flow_id": flow_id,
                "operation": flow.operation,
                "status": flow.status,
                "duration": flow.duration,
                "start_time": flow.start_time,
                "children": children,
            }

        return build_tree(root_flow_id)

    def clear_history(self) -> None:
        """Clear flow history."""
        self._flow_history.clear()

    def clear_active_flows(self) -> None:
        """Clear all active flows."""
        self._active_flows.clear()
        if hasattr(self._thread_local, "flow_stack"):
            self._thread_local.flow_stack.clear()

    def _generate_flow_id(self, operation: str) -> str:
        """Generate a unique flow ID.

        Args:
            operation: Operation name

        Returns:
            Generated flow ID
        """
        timestamp = int(time.time() * 1000)
        random_part = str(uuid.uuid4())[:8]
        return f"flow-{operation}-{timestamp}-{random_part}"

    def _has_circular_reference(self, flow_id: str, parent_flow_id: str) -> bool:
        """Check for circular reference in flow hierarchy.

        Args:
            flow_id: Flow ID to check
            parent_flow_id: Parent flow ID to check

        Returns:
            True if circular reference exists
        """
        current_id = parent_flow_id
        visited = set()

        while current_id:
            if current_id == flow_id:
                return True

            if current_id in visited:
                break  # Prevent infinite loop

            visited.add(current_id)

            # Get parent of current flow
            current_flow = self.get_flow_context(current_id)
            if not current_flow:
                # Try to find in history
                current_flow = next(
                    (f for f in self._flow_history if f.flow_id == current_id), None
                )

            if not current_flow:
                break

            current_id = current_flow.parent_flow_id

        return False

    @contextmanager
    def flow(
        self,
        operation: str,
        flow_id: str | None = None,
        parent_flow_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ):
        """Context manager for flow tracking.

        Args:
            operation: Name of the operation
            flow_id: Optional custom flow ID
            parent_flow_id: Optional parent flow ID
            metadata: Optional metadata for the flow
            tags: Optional tags for the flow

        Yields:
            Flow context for the operation
        """
        flow_context = self.start_flow(
            operation=operation,
            flow_id=flow_id,
            parent_flow_id=parent_flow_id,
            metadata=metadata,
            tags=tags,
        )

        try:
            yield flow_context
        except Exception as e:
            self.end_flow(flow_context.flow_id, status="error", error=str(e))
            raise
        else:
            self.end_flow(flow_context.flow_id, status="completed")


# Global flow tracker instance
_flow_tracker: FlowTracker | None = None


def get_flow_tracker() -> FlowTracker:
    """Get the global flow tracker instance.

    Returns:
        Global flow tracker instance
    """
    global _flow_tracker
    if _flow_tracker is None:
        _flow_tracker = FlowTracker()
    return _flow_tracker


def set_flow_tracker(tracker: FlowTracker) -> None:
    """Set the global flow tracker instance.

    Args:
        tracker: Flow tracker instance to set
    """
    global _flow_tracker
    _flow_tracker = tracker
