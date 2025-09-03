# gemini_sre_agent/ml/unified_workflow_orchestrator_refactored.py

"""
Unified Workflow Orchestrator for enhanced code generation.

This module orchestrates the entire workflow from issue detection to code generation,
coordinating the enhanced analysis agent, specialized generators, and performance
optimizations to provide a seamless, high-performance experience.

Refactored version using modular components for better maintainability.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .caching import ContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import PerformanceConfig, record_performance
from .workflow_analysis_engine import WorkflowAnalysisEngine
from .workflow_code_generator import WorkflowCodeGenerator
from .workflow_context_manager import WorkflowContextManager
from .workflow_metrics_collector import WorkflowMetricsCollector
from .workflow_validation_engine import WorkflowValidationEngine


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


class UnifiedWorkflowOrchestrator:
    """
    Orchestrates the unified enhanced code generation workflow.

    This class coordinates all components to provide a seamless experience:
    - Intelligent caching and performance optimization
    - Enhanced analysis with specialized generators
    - Workflow orchestration and error handling
    - Performance monitoring and metrics collection

    Refactored to use modular components for better maintainability.
    """

    def __init__(
        self,
        enhanced_agent: EnhancedAnalysisAgent,
        performance_config: PerformanceConfig,
        cache: ContextCache,
        repo_path: str = ".",
    ):
        """
        Initialize the workflow orchestrator.

        Args:
            enhanced_agent: Enhanced analysis agent instance
            performance_config: Performance configuration
            cache: Context cache instance
            repo_path: Path to repository for analysis
        """
        self.enhanced_agent = enhanced_agent
        self.performance_config = performance_config
        self.cache = cache
        self.repo_path = repo_path

        # Initialize modular components
        self.context_manager = WorkflowContextManager(enhanced_agent, repo_path)
        self.analysis_engine = WorkflowAnalysisEngine(
            enhanced_agent, cache, performance_config
        )
        self.code_generator = WorkflowCodeGenerator(enhanced_agent)
        self.validation_engine = WorkflowValidationEngine()
        self.metrics_collector = WorkflowMetricsCollector(
            cache, self.context_manager, performance_config
        )

        self.logger = logging.getLogger(__name__)

        # Workflow state
        self.current_workflow_id: Optional[str] = None

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
        start_time = time.time()
        self.current_workflow_id = flow_id

        # Record workflow start
        await record_performance(
            "workflow_execution",
            start_time,
            success=True,
            metadata={"flow_id": flow_id, "analysis_depth": analysis_depth},
        )

        try:
            self.logger.info(
                f"[WORKFLOW] Starting unified workflow for flow_id={flow_id}"
            )

            # Phase 1: Context Building & Caching
            context_building_start = time.time()
            prompt_context = await self.context_manager.build_enhanced_context(
                triage_packet, flow_id, analysis_depth
            )
            context_building_duration = time.time() - context_building_start

            # Record context building performance
            await record_performance(
                "context_building",
                context_building_duration * 1000,  # Convert to milliseconds
                success=True,
                metadata={"flow_id": flow_id, "analysis_depth": analysis_depth},
            )

            # Phase 2: Enhanced Analysis
            analysis_start = time.time()
            analysis_result = await self.analysis_engine.execute_enhanced_analysis(
                triage_packet, historical_logs, configs, flow_id, prompt_context
            )
            analysis_duration = time.time() - analysis_start

            # Record analysis performance
            await record_performance(
                "enhanced_analysis",
                analysis_duration * 1000,  # Convert to milliseconds
                success=analysis_result.get("success", False),
                metadata={
                    "flow_id": flow_id,
                    "generator_type": prompt_context.generator_type,
                },
            )

            # Handle fallback if enhanced analysis fails
            fallback_used = False
            if not analysis_result.get("success", False):
                self.logger.warning(
                    f"[WORKFLOW] Enhanced analysis failed, using fallback for flow_id={flow_id}"
                )
                analysis_result = await self.analysis_engine.execute_fallback_analysis(
                    triage_packet, historical_logs, configs, flow_id
                )
                fallback_used = True

            # Phase 3: Code Generation & Enhancement
            generation_start = time.time()
            generated_code = await self.code_generator.generate_enhanced_code(
                analysis_result, prompt_context, enable_specialized_generators
            )
            generation_duration = time.time() - generation_start

            # Record code generation performance
            await record_performance(
                "code_generation",
                generation_duration * 1000,  # Convert to milliseconds
                success=bool(generated_code),
                metadata={
                    "flow_id": flow_id,
                    "generator_type": prompt_context.generator_type,
                },
            )

            # Phase 4: Validation (if enabled)
            validation_duration = 0.0
            validation_result = {}

            if enable_validation and generated_code:
                validation_start = time.time()
                validation_result = (
                    await self.validation_engine.validate_generated_code(
                        analysis_result, prompt_context
                    )
                )
                validation_duration = time.time() - validation_start

                # Record validation performance
                await record_performance(
                    "code_validation",
                    validation_duration * 1000,  # Convert to milliseconds
                    success=validation_result.get("is_valid", False),
                    metadata={
                        "flow_id": flow_id,
                        "validation_score": validation_result.get("overall_score", 0),
                    },
                )

            # Calculate metrics
            total_duration = time.time() - start_time
            cache_hit_rate = await self.metrics_collector.calculate_cache_hit_rate()

            metrics = WorkflowMetrics(
                total_duration=total_duration,
                analysis_duration=analysis_duration,
                generation_duration=generation_duration,
                cache_hit_rate=cache_hit_rate,
                context_building_duration=context_building_duration,
                validation_duration=validation_duration,
                error_count=0,
                success=True,
            )

            # Create result
            result = WorkflowResult(
                success=True,
                analysis_result=analysis_result,
                generated_code=generated_code,
                validation_result=validation_result,
                metrics=metrics,
                fallback_used=fallback_used,
            )

            # Store in history
            self.metrics_collector.add_workflow_result(result)

            # Record final workflow performance
            await record_performance(
                "workflow_completion",
                total_duration * 1000,  # Convert to milliseconds
                success=True,
                metadata={
                    "flow_id": flow_id,
                    "cache_hit_rate": cache_hit_rate,
                    "validation_enabled": enable_validation,
                    "specialized_generators_enabled": enable_specialized_generators,
                },
            )

            self.logger.info(
                f"[WORKFLOW] Unified workflow completed successfully for flow_id={flow_id} "
                f"in {total_duration:.2f}s (cache_hit_rate={cache_hit_rate:.2%})"
            )

            return result

        except Exception as e:
            error_duration = time.time() - start_time
            self.logger.error(f"[WORKFLOW] Workflow failed for flow_id={flow_id}: {e}")

            # Record error performance
            await record_performance(
                "workflow_error",
                error_duration * 1000,  # Convert to milliseconds
                success=False,
                error_message=str(e),
                metadata={"flow_id": flow_id},
            )

            # Create error result
            metrics = WorkflowMetrics(
                total_duration=error_duration,
                analysis_duration=0.0,
                generation_duration=0.0,
                cache_hit_rate=0.0,
                context_building_duration=0.0,
                validation_duration=0.0,
                error_count=1,
                success=False,
            )

            error_result = WorkflowResult(
                success=False,
                analysis_result={},
                generated_code="",
                validation_result={},
                metrics=metrics,
                error_message=str(e),
                fallback_used=False,
            )

            self.metrics_collector.add_workflow_result(error_result)
            return error_result

    # Delegate methods to appropriate components
    async def get_workflow_history(self) -> List[WorkflowResult]:
        """Get workflow execution history."""
        return await self.metrics_collector.get_workflow_history()

    async def get_performance_metrics(self) -> Dict[str, Any]:
        """Get comprehensive performance metrics."""
        return await self.metrics_collector.get_performance_metrics()

    async def get_performance_insights(self) -> Dict[str, Any]:
        """Get comprehensive performance insights from the monitoring system."""
        return await self.metrics_collector.get_performance_insights()

    async def clear_cache(self):
        """Clear all caches."""
        await self.metrics_collector.clear_cache()

    async def reset_workflow_history(self):
        """Reset workflow execution history."""
        self.metrics_collector.reset_workflow_history()
