# gemini_sre_agent/ml/workflow_orchestrator.py

"""
Main workflow orchestrator for enhanced code generation.

This module provides the main coordination logic for the unified workflow,
delegating specific functionality to specialized modules while maintaining
a clean, focused interface under 200 LOC.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .caching import ContextCache
from .performance import PerformanceConfig
from .workflow_analysis import WorkflowAnalysisEngine
from .workflow_context import WorkflowContextManager
from .workflow_generation import WorkflowGenerationEngine
from .workflow_metrics import WorkflowMetrics, WorkflowMetricsCollector, WorkflowResult
from .workflow_validation import WorkflowValidationEngine


@dataclass
class WorkflowConfig:
    """Configuration for workflow orchestration."""

    analysis_depth: str = "standard"
    enable_validation: bool = True
    enable_specialized_generators: bool = True
    performance_config: Optional[PerformanceConfig] = None
    cache: Optional[ContextCache] = None
    repo_path: str = "."


class WorkflowOrchestrator:
    """
    Main orchestrator for the unified enhanced code generation workflow.

    This class coordinates all workflow components while delegating specific
    functionality to specialized modules. Keeps the main class focused and
    maintainable under 200 LOC.
    """

    def __init__(self, config: WorkflowConfig) -> None:
        """
        Initialize the workflow orchestrator.

        Args:
            config: Workflow configuration containing all necessary settings
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize specialized components
        self.context_manager = WorkflowContextManager(
            cache=config.cache,
            repo_path=config.repo_path,
            performance_config=config.performance_config,
        )

        self.analysis_engine = WorkflowAnalysisEngine(
            performance_config=config.performance_config
        )

        self.generation_engine = WorkflowGenerationEngine(
            performance_config=config.performance_config
        )

        self.validation_engine = WorkflowValidationEngine(
            performance_config=config.performance_config
        )

        self.metrics_collector = WorkflowMetricsCollector()

        # Workflow state
        self.current_workflow_id: Optional[str] = None
        self.workflow_history: List[WorkflowResult] = []

    async def execute_workflow(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
        analysis_depth: str = "standard",
        enable_validation: bool = True,
        enable_specialized_generators: bool = True,
    ) -> WorkflowResult:
        """
        Execute the complete unified workflow.

        Args:
            triage_packet: Issue triage data
            historical_logs: Historical log data
            configs: Configuration data
            flow_id: Unique workflow identifier
            analysis_depth: Repository analysis depth
            enable_validation: Enable code validation
            enable_specialized_generators: Enable specialized generators

        Returns:
            WorkflowResult with complete execution details
        """
        self.current_workflow_id = flow_id

        try:
            self.logger.info(
                f"[WORKFLOW] Starting unified workflow for flow_id={flow_id}"
            )

            # Phase 1: Context Building
            prompt_context = await self.context_manager.build_enhanced_context(
                triage_packet, historical_logs, configs, flow_id, analysis_depth
            )

            # Phase 2: Enhanced Analysis
            analysis_result = await self.analysis_engine.execute_enhanced_analysis(
                triage_packet, historical_logs, configs, flow_id, prompt_context
            )

            # Phase 3: Code Generation
            generated_code = await self.generation_engine.generate_enhanced_code(
                analysis_result, prompt_context, enable_specialized_generators
            )

            # Phase 4: Validation (if enabled)
            validation_result = {}
            if enable_validation and generated_code:
                validation_result = (
                    await self.validation_engine.validate_generated_code(
                        analysis_result, prompt_context
                    )
                )

            # Phase 5: Collect Metrics
            metrics = await self.metrics_collector.collect_workflow_metrics(
                self.context_manager,
                self.analysis_engine,
                self.generation_engine,
                self.validation_engine,
                flow_id,
            )

            # Create workflow result
            result = WorkflowResult(
                success=True,
                generated_code=generated_code,
                analysis_result=analysis_result,
                validation_result=validation_result,
                metrics=metrics,
                workflow_id=flow_id,
                error_message=None,
            )

            # Store in history
            self.workflow_history.append(result)

            self.logger.info(f"[WORKFLOW] Completed successfully for flow_id={flow_id}")
            return result

        except Exception as e:
            self.logger.error(f"[WORKFLOW] Failed for flow_id={flow_id}: {e}")

            # Create error result
            error_result = WorkflowResult(
                success=False,
                generated_code=None,
                analysis_result={},
                validation_result={},
                metrics=WorkflowMetrics(
                    total_duration=0.0,
                    analysis_duration=0.0,
                    generation_duration=0.0,
                    cache_hit_rate=0.0,
                    context_building_duration=0.0,
                    validation_duration=0.0,
                    error_count=1,
                    success=False,
                ),
                workflow_id=flow_id,
                error_message=str(e),
            )

            # Store in history
            self.workflow_history.append(error_result)

            return error_result

    async def get_workflow_status(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the status of a specific workflow.

        Args:
            flow_id: Workflow identifier

        Returns:
            Workflow status information or None if not found
        """
        for result in self.workflow_history:
            if result.workflow_id == flow_id:
                return {
                    "workflow_id": flow_id,
                    "success": result.success,
                    "error_message": result.error_message,
                    "metrics": result.metrics,
                    "has_generated_code": bool(result.generated_code),
                    "has_validation": bool(result.validation_result),
                }
        return None

    async def get_workflow_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent workflow history.

        Args:
            limit: Maximum number of workflows to return

        Returns:
            List of workflow status information
        """
        recent_workflows = self.workflow_history[-limit:]
        return [
            {
                "workflow_id": result.workflow_id,
                "success": result.success,
                "error_message": result.error_message,
                "metrics": result.metrics,
                "has_generated_code": bool(result.generated_code),
                "has_validation": bool(result.validation_result),
            }
            for result in recent_workflows
        ]

    async def reset_workflow_state(self) -> None:
        """Reset the workflow state and clear history."""
        self.current_workflow_id = None
        self.workflow_history.clear()
        self.logger.info("[WORKFLOW] Workflow state reset")

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """
        Get aggregated performance metrics across all workflows.

        Returns:
            Dictionary containing performance metrics
        """
        return await self.metrics_collector.get_aggregated_metrics(
            self.workflow_history
        )

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check on all workflow components.

        Returns:
            Health status of all components
        """
        health_status = {
            "orchestrator": "healthy",
            "context_manager": await self.context_manager.health_check(),
            "analysis_engine": await self.analysis_engine.health_check(),
            "generation_engine": await self.generation_engine.health_check(),
            "validation_engine": await self.validation_engine.health_check(),
            "metrics_collector": await self.metrics_collector.health_check(),
        }

        overall_health = all(status == "healthy" for status in health_status.values())

        return {
            "overall_health": "healthy" if overall_health else "degraded",
            "components": health_status,
            "workflow_count": len(self.workflow_history),
            "current_workflow": self.current_workflow_id,
        }
