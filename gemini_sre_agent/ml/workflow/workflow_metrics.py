# gemini_sre_agent/ml/workflow/workflow_metrics.py

"""
Workflow metrics module for the unified workflow orchestrator.

This module handles metrics collection and monitoring within the workflow,
including performance metrics, health metrics, and operational metrics.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ...core.interfaces import ProcessableComponent
from ...core.types import ConfigDict, Timestamp

logger = logging.getLogger(__name__)


@dataclass
class MetricData:
    """
    Individual metric data point.

    This class represents a single metric data point with
    timestamp, value, and metadata.
    """

    name: str
    value: float
    timestamp: Timestamp
    tags: Dict[str, str] = field(default_factory=dict)
    unit: str = "count"
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert metric data to dictionary."""
        return {
            "name": self.name,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
            "unit": self.unit,
            "description": self.description,
        }


@dataclass
class WorkflowMetrics:
    """
    Comprehensive workflow metrics collection.

    This class holds all metrics related to a workflow execution,
    including performance, health, and operational metrics.
    """

    # Workflow metadata
    workflow_id: str
    start_time: Timestamp
    end_time: Optional[Timestamp] = None
    duration: Optional[float] = None

    # Performance metrics
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    average_operation_time: float = 0.0

    # Component metrics
    context_builds: int = 0
    analyses_performed: int = 0
    generations_created: int = 0
    validations_run: int = 0

    # Quality metrics
    overall_confidence: float = 0.0
    error_rate: float = 0.0
    success_rate: float = 0.0

    # Resource metrics
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    cache_hits: int = 0
    cache_misses: int = 0

    # Custom metrics
    custom_metrics: List[MetricData] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert workflow metrics to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "average_operation_time": self.average_operation_time,
            "context_builds": self.context_builds,
            "analyses_performed": self.analyses_performed,
            "generations_created": self.generations_created,
            "validations_run": self.validations_run,
            "overall_confidence": self.overall_confidence,
            "error_rate": self.error_rate,
            "success_rate": self.success_rate,
            "memory_usage": self.memory_usage,
            "cpu_usage": self.cpu_usage,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "custom_metrics": [metric.to_dict() for metric in self.custom_metrics],
        }


class WorkflowMetricsCollector(ProcessableComponent[Dict[str, Any], WorkflowMetrics]):
    """
    Metrics collector for workflow operations.

    This class handles all metrics collection and monitoring within the workflow,
    including performance metrics, health metrics, and operational metrics.
    """

    def __init__(
        self,
        component_id: str = "workflow_metrics_collector",
        name: str = "Workflow Metrics Collector",
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the workflow metrics collector.

        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)

        # Metrics tracking
        self.active_workflows: Dict[str, WorkflowMetrics] = {}
        self.completed_workflows: List[WorkflowMetrics] = []
        self.metrics_history: List[MetricData] = []

        # Collection settings
        self.metrics_retention_days = (
            config.get("metrics_retention_days", 30) if config else 30
        )
        self.collection_interval = (
            config.get("collection_interval", 1.0) if config else 1.0
        )

        # Performance tracking
        self.collection_count = 0
        self.total_collection_time = 0.0
        self.error_count = 0

    def start_workflow_metrics(self, workflow_id: str) -> WorkflowMetrics:
        """
        Start collecting metrics for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow metrics object
        """
        logger.info(f"Starting metrics collection for workflow {workflow_id}")

        metrics = WorkflowMetrics(workflow_id=workflow_id, start_time=time.time())

        self.active_workflows[workflow_id] = metrics
        return metrics

    def end_workflow_metrics(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """
        End metrics collection for a workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Completed workflow metrics or None if not found
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"No active metrics found for workflow {workflow_id}")
            return None

        logger.info(f"Ending metrics collection for workflow {workflow_id}")

        metrics = self.active_workflows[workflow_id]
        metrics.end_time = time.time()
        metrics.duration = metrics.end_time - metrics.start_time

        # Calculate derived metrics
        self._calculate_derived_metrics(metrics)

        # Move to completed workflows
        self.completed_workflows.append(metrics)
        del self.active_workflows[workflow_id]

        return metrics

    def record_operation(
        self,
        workflow_id: str,
        operation_type: str,
        success: bool,
        duration: float,
        confidence: float = 0.0,
    ) -> None:
        """
        Record an operation metric.

        Args:
            workflow_id: Workflow identifier
            operation_type: Type of operation performed
            success: Whether the operation was successful
            duration: Operation duration in seconds
            confidence: Confidence score for the operation
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"No active metrics found for workflow {workflow_id}")
            return

        metrics = self.active_workflows[workflow_id]
        metrics.total_operations += 1

        if success:
            metrics.successful_operations += 1
        else:
            metrics.failed_operations += 1

        # Update operation-specific counters
        if operation_type == "context_build":
            metrics.context_builds += 1
        elif operation_type == "analysis":
            metrics.analyses_performed += 1
        elif operation_type == "generation":
            metrics.generations_created += 1
        elif operation_type == "validation":
            metrics.validations_run += 1

        # Add custom metric
        metric_data = MetricData(
            name=f"{operation_type}_duration",
            value=duration,
            timestamp=time.time(),
            tags={"workflow_id": workflow_id, "operation_type": operation_type},
            unit="seconds",
            description=f"Duration of {operation_type} operation",
        )
        metrics.custom_metrics.append(metric_data)

        # Update confidence
        if confidence > 0:
            metrics.overall_confidence = (metrics.overall_confidence + confidence) / 2

    def record_cache_operation(self, workflow_id: str, hit: bool) -> None:
        """
        Record a cache operation.

        Args:
            workflow_id: Workflow identifier
            hit: Whether it was a cache hit
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"No active metrics found for workflow {workflow_id}")
            return

        metrics = self.active_workflows[workflow_id]

        if hit:
            metrics.cache_hits += 1
        else:
            metrics.cache_misses += 1

    def record_resource_usage(
        self, workflow_id: str, memory_usage: float, cpu_usage: float
    ) -> None:
        """
        Record resource usage metrics.

        Args:
            workflow_id: Workflow identifier
            memory_usage: Memory usage in MB
            cpu_usage: CPU usage percentage
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"No active metrics found for workflow {workflow_id}")
            return

        metrics = self.active_workflows[workflow_id]
        metrics.memory_usage = memory_usage
        metrics.cpu_usage = cpu_usage

    def add_custom_metric(
        self,
        workflow_id: str,
        name: str,
        value: float,
        unit: str = "count",
        description: str = "",
        tags: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Add a custom metric to a workflow.

        Args:
            workflow_id: Workflow identifier
            name: Metric name
            value: Metric value
            unit: Metric unit
            description: Metric description
            tags: Optional metric tags
        """
        if workflow_id not in self.active_workflows:
            logger.warning(f"No active metrics found for workflow {workflow_id}")
            return

        metrics = self.active_workflows[workflow_id]

        metric_data = MetricData(
            name=name,
            value=value,
            timestamp=time.time(),
            tags=tags or {},
            unit=unit,
            description=description,
        )

        metrics.custom_metrics.append(metric_data)

    def get_workflow_metrics(self, workflow_id: str) -> Optional[WorkflowMetrics]:
        """
        Get metrics for a specific workflow.

        Args:
            workflow_id: Workflow identifier

        Returns:
            Workflow metrics or None if not found
        """
        if workflow_id in self.active_workflows:
            return self.active_workflows[workflow_id]

        # Search in completed workflows
        for metrics in self.completed_workflows:
            if metrics.workflow_id == workflow_id:
                return metrics

        return None

    def get_all_metrics(self) -> Dict[str, Any]:
        """
        Get all collected metrics.

        Returns:
            Dictionary containing all metrics
        """
        return {
            "active_workflows": len(self.active_workflows),
            "completed_workflows": len(self.completed_workflows),
            "total_metrics_collected": len(self.metrics_history),
            "collection_count": self.collection_count,
            "total_collection_time": self.total_collection_time,
            "average_collection_time": (
                (self.total_collection_time / self.collection_count)
                if self.collection_count > 0
                else 0.0
            ),
        }

    def process(self, input_data: Dict[str, Any]) -> WorkflowMetrics:
        """
        Process metrics collection request (synchronous wrapper).

        Args:
            input_data: Metrics collection request data

        Returns:
            Workflow metrics
        """
        # This is a synchronous wrapper for the async methods
        # In practice, this would be called from an async context
        raise NotImplementedError("Use specific methods for metrics operations")

    def initialize(self) -> None:
        """Initialize the component."""
        self._status = "initialized"
        logger.info(f"Initialized {self.name}")

    def shutdown(self) -> None:
        """Shutdown the component."""
        self._status = "shutdown"
        logger.info(f"Shutdown {self.name}")

    def configure(self, config: ConfigDict) -> None:
        """
        Configure the component with new settings.

        Args:
            config: Configuration dictionary
        """
        self._config.update(config)
        logger.info(f"Configured {self.name}")

    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate a configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        return isinstance(config, dict)

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.

        Args:
            key: State key
            value: State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any : Optional[str] = None) -> Any:
        """
        Get a state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self, key: Optional[str] = None) -> None:
        """
        Clear state values.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._state.clear()
        else:
            self._state.pop(key, None)

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect component metrics.

        Returns:
            Dictionary containing metrics
        """
        return self.get_all_metrics()

    def _calculate_derived_metrics(self, metrics: WorkflowMetrics) -> None:
        """
        Calculate derived metrics for a workflow.

        Args:
            metrics: Workflow metrics to calculate derived metrics for
        """
        if metrics.total_operations > 0:
            metrics.success_rate = (
                metrics.successful_operations / metrics.total_operations
            ) * 100
            metrics.error_rate = (
                metrics.failed_operations / metrics.total_operations
            ) * 100

        if metrics.total_operations > 0 and metrics.duration:
            metrics.average_operation_time = metrics.duration / metrics.total_operations

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the component's health status.

        Returns:
            Dictionary containing health status information
        """
        return {
            "component_id": self.component_id,
            "name": self.name,
            "status": self.status,
            "healthy": self.check_health(),
            "metrics_summary": self.get_all_metrics(),
            "processing_count": self.processing_count,
            "last_processed_at": self.last_processed_at,
        }

    def check_health(self) -> bool:
        """
        Check if the component is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return self.status != "error" and self.error_count == 0
