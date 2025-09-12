# gemini_sre_agent/ml/workflow_metrics.py

"""
Workflow metrics module.

This module handles all metrics collection and tracking for the workflow orchestrator.
Extracted from unified_workflow_orchestrator_original.py.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .caching import ContextCache
from .performance import PerformanceConfig


@dataclass
class WorkflowMetrics:
    """Metrics for workflow performance tracking."""
    
    total_duration: float
    analysis_duration: float
    generation_duration: float
    cache_hit_rate: float
    context_building_duration: float
    validation_duration: float
    error_count: int
    success: bool


@dataclass
class WorkflowResult:
    """Result of the unified workflow execution."""
    
    success: bool
    analysis_result: Dict[str, Any]
    generated_code: str
    validation_result: Dict[str, Any]
    metrics: WorkflowMetrics
    error_message: Optional[str] = None
    fallback_used: bool = False


class WorkflowMetricsCollector:
    """
    Manages workflow metrics collection and tracking.
    
    This class handles all metrics operations including performance tracking,
    cache statistics, and workflow result management with proper error handling.
    """

    def __init__(self, performance_config: Optional[PerformanceConfig]):
        """
        Initialize the workflow metrics collector.
        
        Args:
            performance_config: Performance configuration
        """
        self.performance_config = performance_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize cache (will be injected)
        self.cache: Optional[ContextCache] = None
        self.workflow_history: List[WorkflowResult] = []

    def set_cache(self, cache: ContextCache) -> None:
        """Set the context cache."""
        self.cache = cache

    def add_workflow_result(self, result: WorkflowResult) -> None:
        """
        Add a workflow result to the history.
        
        Args:
            result: Workflow result to add
        """
        try:
            self.workflow_history.append(result)
            
            # Keep only recent results to prevent memory issues
            if len(self.workflow_history) > 1000:
                self.workflow_history = self.workflow_history[-1000:]
                
        except Exception as e:
            self.logger.error(f"Failed to add workflow result: {e}")

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive performance metrics.
        
        Returns:
            Dictionary containing performance metrics
        """
        try:
            cache_stats = {}
            if self.cache:
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
                "performance_config": self.performance_config.to_dict() if self.performance_config else None,
            }

        except Exception as e:
            self.logger.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}

    async def get_workflow_history(self) -> List[WorkflowResult]:
        """
        Get workflow execution history.
        
        Returns:
            List of workflow results
        """
        try:
            return self.workflow_history.copy()
        except Exception as e:
            self.logger.error(f"Failed to get workflow history: {e}")
            return []

    async def clear_workflow_history(self) -> None:
        """Clear workflow execution history."""
        try:
            self.workflow_history.clear()
            self.logger.info("Workflow history cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear workflow history: {e}")

    async def get_recent_workflows(self, limit: int = 10) -> List[WorkflowResult]:
        """
        Get recent workflow results.
        
        Args:
            limit: Maximum number of recent workflows to return
            
        Returns:
            List of recent workflow results
        """
        try:
            return self.workflow_history[-limit:] if self.workflow_history else []
        except Exception as e:
            self.logger.error(f"Failed to get recent workflows: {e}")
            return []

    async def get_success_rate(self, time_window_minutes: Optional[int] = None) -> float:
        """
        Get success rate for workflows.
        
        Args:
            time_window_minutes: Optional time window in minutes
            
        Returns:
            Success rate as a float between 0.0 and 1.0
        """
        try:
            if not self.workflow_history:
                return 0.0
                
            # Filter by time window if specified
            workflows = self.workflow_history
            if time_window_minutes:
                # This would require timestamps in WorkflowResult
                # For now, return overall success rate
                pass
                
            successful = len([w for w in workflows if w.success])
            total = len(workflows)
            
            return successful / total if total > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Failed to get success rate: {e}")
            return 0.0

    async def get_average_duration(self) -> float:
        """
        Get average workflow duration.
        
        Returns:
            Average duration in seconds
        """
        try:
            if not self.workflow_history:
                return 0.0
                
            total_duration = sum(w.metrics.total_duration for w in self.workflow_history)
            return total_duration / len(self.workflow_history)
            
        except Exception as e:
            self.logger.error(f"Failed to get average duration: {e}")
            return 0.0

    async def get_error_statistics(self) -> Dict[str, Any]:
        """
        Get error statistics for workflows.
        
        Returns:
            Dictionary containing error statistics
        """
        try:
            if not self.workflow_history:
                return {"total_errors": 0, "error_rate": 0.0, "common_errors": []}
                
            total_errors = sum(w.metrics.error_count for w in self.workflow_history)
            error_rate = total_errors / len(self.workflow_history) if self.workflow_history else 0.0
            
            # Count common error types
            error_types = {}
            for workflow in self.workflow_history:
                if not workflow.success and workflow.error_message:
                    error_type = workflow.error_message.split(":")[0]
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                    
            common_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]
            
            return {
                "total_errors": total_errors,
                "error_rate": error_rate,
                "common_errors": common_errors,
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get error statistics: {e}")
            return {"error": str(e)}

    async def get_metrics_statistics(self) -> Dict[str, Any]:
        """
        Get metrics collection statistics for monitoring.
        
        Returns:
            Dictionary containing metrics statistics
        """
        try:
            return {
                "cache_available": self.cache is not None,
                "workflow_history_size": len(self.workflow_history),
                "performance_config_available": self.performance_config is not None,
            }
        except Exception as e:
            self.logger.error(f"Failed to get metrics statistics: {e}")
            return {"error": str(e)}

    async def health_check(self) -> str:
        """
        Perform health check on metrics collector components.
        
        Returns:
            Health status string
        """
        try:
            # Check if essential components are available
            if not self.cache:
                return "degraded - cache not set"
            
            # Test basic functionality
            try:
                # Test metrics calculation
                metrics = await self.get_performance_metrics()
                
                if "error" in metrics:
                    return f"unhealthy - metrics calculation failed: {metrics['error']}"
                    
            except Exception as e:
                return f"unhealthy - metrics test failed: {str(e)}"
            
            return "healthy"
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return f"unhealthy - {str(e)}"