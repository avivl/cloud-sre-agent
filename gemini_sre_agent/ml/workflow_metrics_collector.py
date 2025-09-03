# gemini_sre_agent/ml/workflow_metrics_collector.py

"""
Workflow Metrics Collector for enhanced code generation.

This module handles metrics collection, performance insights, and workflow
history management for the unified workflow orchestrator.
"""

import logging
from typing import Any, Dict, List

from .caching import ContextCache
from .performance import get_performance_monitor
from .workflow_context_manager import WorkflowContextManager


class WorkflowMetricsCollector:
    """
    Handles metrics collection and performance insights for the workflow orchestrator.

    This class manages:
    - Workflow execution metrics
    - Performance monitoring and insights
    - Cache statistics and hit rates
    - Workflow history management
    """

    def __init__(
        self,
        cache: ContextCache,
        context_manager: WorkflowContextManager,
        performance_config: Any,
    ):
        """
        Initialize the metrics collector.

        Args:
            cache: Context cache instance
            context_manager: Workflow context manager instance
            performance_config: Performance configuration
        """
        self.cache = cache
        self.context_manager = context_manager
        self.performance_config = performance_config
        self.performance_monitor = get_performance_monitor()
        self.logger = logging.getLogger(__name__)

        # Workflow history
        self.workflow_history: List[Any] = []

    async def calculate_cache_hit_rate(self) -> float:
        """Calculate the current cache hit rate."""
        try:
            stats = await self.cache.get_stats()
            return stats.get("average_hit_rate", 0.0)
        except Exception:
            return 0.0

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        try:
            cache_stats = await self.cache.get_stats()

            # Calculate workflow metrics
            total_workflows = len(self.workflow_history)
            successful_workflows = len([w for w in self.workflow_history if w.success])
            failed_workflows = total_workflows - successful_workflows

            if total_workflows > 0:
                success_rate = successful_workflows / total_workflows
                avg_duration = (
                    sum(w.metrics.total_duration for w in self.workflow_history)
                    / total_workflows
                )
                avg_cache_hit_rate = (
                    sum(w.metrics.cache_hit_rate for w in self.workflow_history)
                    / total_workflows
                )
            else:
                success_rate = 0.0
                avg_duration = 0.0
                avg_cache_hit_rate = 0.0

            return {
                "workflow_metrics": {
                    "total_workflows": total_workflows,
                    "successful_workflows": successful_workflows,
                    "failed_workflows": failed_workflows,
                    "success_rate": success_rate,
                    "average_duration": avg_duration,
                    "average_cache_hit_rate": avg_cache_hit_rate,
                },
                "cache_metrics": cache_stats,
                "performance_config": self.performance_config.to_dict(),
            }

        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}

    async def get_performance_insights(self) -> Dict[str, Any]:
        """Get comprehensive performance insights from the monitoring system."""
        try:
            # Get performance summaries for all operations
            summaries = await self.performance_monitor.get_all_performance_summaries()

            # Get performance trends for key operations
            trends = {}
            for operation in [
                "workflow_execution",
                "context_building",
                "enhanced_analysis",
                "code_generation",
            ]:
                try:
                    trends[operation] = (
                        await self.performance_monitor.get_performance_trends(operation)
                    )
                except Exception:
                    # Operation might not have data yet
                    trends[operation] = {}

            # Get monitor statistics
            monitor_stats = self.performance_monitor.get_monitor_stats()

            # Get cache statistics
            cache_stats = await self.context_manager.get_cache_stats()

            return {
                "performance_summaries": summaries,
                "performance_trends": trends,
                "monitor_statistics": monitor_stats,
                "workflow_history_count": len(self.workflow_history),
                "cache_statistics": cache_stats,
            }
        except Exception as e:
            self.logger.error(f"Failed to get performance insights: {e}")
            return {"error": str(e)}

    def add_workflow_result(self, result: Any):
        """Add a workflow result to the history."""
        self.workflow_history.append(result)

    async def get_workflow_history(self) -> List[Any]:
        """Get workflow execution history."""
        return self.workflow_history.copy()

    def reset_workflow_history(self):
        """Reset workflow execution history."""
        self.workflow_history.clear()
        self.logger.info("Workflow history reset")

    async def clear_cache(self):
        """Clear all caches."""
        try:
            await self.cache.clear()
            await self.context_manager.clear_caches()
            self.logger.info("All caches cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear caches: {e}")

    def get_workflow_count(self) -> int:
        """Get the total number of workflows executed."""
        return len(self.workflow_history)

    def get_success_rate(self) -> float:
        """Get the success rate of workflows."""
        if not self.workflow_history:
            return 0.0

        successful_workflows = len([w for w in self.workflow_history if w.success])
        return successful_workflows / len(self.workflow_history)

    def get_average_duration(self) -> float:
        """Get the average workflow duration."""
        if not self.workflow_history:
            return 0.0

        total_duration = sum(w.metrics.total_duration for w in self.workflow_history)
        return total_duration / len(self.workflow_history)

    def get_recent_workflows(self, count: int = 10) -> List[Any]:
        """Get the most recent workflows."""
        return self.workflow_history[-count:] if self.workflow_history else []

    def get_failed_workflows(self) -> List[Any]:
        """Get all failed workflows."""
        return [w for w in self.workflow_history if not w.success]

    def get_successful_workflows(self) -> List[Any]:
        """Get all successful workflows."""
        return [w for w in self.workflow_history if w.success]
