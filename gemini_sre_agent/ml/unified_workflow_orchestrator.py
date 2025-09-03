# gemini_sre_agent/ml/unified_workflow_orchestrator.py

"""
Unified Workflow Orchestrator for enhanced code generation.

This module orchestrates the entire workflow from issue detection to code generation,
coordinating the enhanced analysis agent, specialized generators, and performance
optimizations to provide a seamless, high-performance experience.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .caching import ContextCache, IssuePatternCache, RepositoryContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import PerformanceConfig, PerformanceRepositoryAnalyzer
from .prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)
from .validation import CodeValidationPipeline


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

        # Initialize specialized caches
        self.repo_cache = RepositoryContextCache(cache)
        self.pattern_cache = IssuePatternCache(cache)

        # Initialize performance analyzer
        self.repo_analyzer = PerformanceRepositoryAnalyzer(self.repo_cache, repo_path)

        # Initialize validation pipeline
        self.validation_pipeline = CodeValidationPipeline()

        self.logger = logging.getLogger(__name__)

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
        start_time = time.time()
        self.current_workflow_id = flow_id

        try:
            self.logger.info(
                f"[WORKFLOW] Starting unified workflow for flow_id={flow_id}"
            )

            # Phase 1: Context Building & Caching
            context_building_start = time.time()
            prompt_context = await self._build_enhanced_context(
                triage_packet, historical_logs, configs, flow_id, analysis_depth
            )
            context_building_duration = time.time() - context_building_start

            # Phase 2: Enhanced Analysis
            analysis_start = time.time()
            analysis_result = await self._execute_enhanced_analysis(
                triage_packet, historical_logs, configs, flow_id, prompt_context
            )
            analysis_duration = time.time() - analysis_start

            if not analysis_result.get("success", False):
                # Fallback to basic analysis
                self.logger.warning(
                    f"[WORKFLOW] Enhanced analysis failed, using fallback for flow_id={flow_id}"
                )
                analysis_result = await self._execute_fallback_analysis(
                    triage_packet, historical_logs, configs, flow_id
                )
                fallback_used = True
            else:
                fallback_used = False

            # Phase 3: Code Generation & Enhancement
            generation_start = time.time()
            generated_code = await self._generate_enhanced_code(
                analysis_result, prompt_context, enable_specialized_generators
            )
            generation_duration = time.time() - generation_start

            # Phase 4: Validation (if enabled)
            validation_duration = 0.0
            validation_result = {}

            if enable_validation and generated_code:
                validation_start = time.time()
                validation_result = await self._validate_generated_code(
                    analysis_result, prompt_context
                )
                validation_duration = time.time() - validation_start

            # Calculate metrics
            total_duration = time.time() - start_time
            cache_hit_rate = await self._calculate_cache_hit_rate()

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
            self.workflow_history.append(result)

            self.logger.info(
                f"[WORKFLOW] Unified workflow completed successfully for flow_id={flow_id} "
                f"in {total_duration:.2f}s (cache_hit_rate={cache_hit_rate:.2%})"
            )

            return result

        except Exception as e:
            error_duration = time.time() - start_time
            self.logger.error(f"[WORKFLOW] Workflow failed for flow_id={flow_id}: {e}")

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

            self.workflow_history.append(error_result)
            return error_result

    async def _build_enhanced_context(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
        analysis_depth: str,
    ) -> PromptContext:
        """
        Build enhanced context with performance optimizations.

        Args:
            triage_packet: Issue triage data
            historical_logs: Historical log data
            configs: Configuration data
            flow_id: Workflow identifier
            analysis_depth: Repository analysis depth

        Returns:
            Enhanced prompt context
        """
        # Initialize variables that might be needed in exception handling
        issue_context = None
        generator_type = "unknown"

        try:
            # Check cache for repository context
            cached_repo_context = await self.repo_cache.get_repository_context(
                str(self.repo_analyzer.repo_path), analysis_depth
            )

            if cached_repo_context:
                self.logger.debug(
                    f"[CONTEXT] Using cached repository context for flow_id={flow_id}"
                )
                repo_context = cached_repo_context
            else:
                # Perform repository analysis
                self.logger.info(
                    f"[CONTEXT] Analyzing repository for flow_id={flow_id}"
                )
                repo_context = await self.repo_analyzer.analyze_repository(
                    analysis_depth
                )

            # Check cache for issue patterns
            issue_context = self.enhanced_agent._extract_issue_context(triage_packet)
            generator_type = self.enhanced_agent._determine_generator_type(
                issue_context
            )
            pattern_key = f"{issue_context.issue_type.value}:{flow_id}"

            cached_pattern = await self.pattern_cache.get_issue_pattern(
                "issue_context", pattern_key
            )

            if cached_pattern:
                self.logger.debug(
                    f"[CONTEXT] Using cached issue pattern for flow_id={flow_id}"
                )
                issue_context = cached_pattern

            # Build comprehensive context
            context = PromptContext(
                issue_context=issue_context,
                repository_context=repo_context,
                generator_type=generator_type or "general",
            )

            # Cache the issue pattern for future use
            await self.pattern_cache.set_issue_pattern(
                "issue_context", pattern_key, issue_context
            )

            return context

        except Exception as e:
            self.logger.error(
                f"[CONTEXT] Context building failed for flow_id={flow_id}: {e}"
            )
            # Return minimal context on failure
            # Create fallback issue context with safe defaults
            fallback_issue_type = IssueType.UNKNOWN
            if issue_context and issue_context.issue_type:
                fallback_issue_type = issue_context.issue_type

            return PromptContext(
                issue_context=IssueContext(
                    issue_type=fallback_issue_type,
                    affected_files=triage_packet.get("affected_files", []),
                    error_patterns=triage_packet.get("error_patterns", []),
                    severity_level=triage_packet.get("severity_level", 5),
                    impact_analysis={},
                    related_services=triage_packet.get("related_services", []),
                    temporal_context={},
                    user_impact="",
                    business_impact="",
                ),
                repository_context=RepositoryContext(
                    architecture_type="unknown",
                    technology_stack={},
                    coding_standards={},
                    error_handling_patterns=[],
                    testing_patterns=[],
                    dependency_structure={},
                    recent_changes=[],
                    historical_fixes=[],
                    code_quality_metrics={},
                ),
                generator_type="unknown",
            )

    async def _execute_enhanced_analysis(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
        prompt_context: PromptContext,
    ) -> Dict[str, Any]:
        """
        Execute enhanced analysis with the enhanced analysis agent.

        Args:
            triage_packet: Issue triage data
            historical_logs: Historical log data
            configs: Configuration data
            flow_id: Workflow identifier
            prompt_context: Enhanced prompt context

        Returns:
            Analysis result
        """
        try:
            # Use the enhanced analysis agent
            result = await self.enhanced_agent.analyze_issue(
                triage_packet, historical_logs, configs, flow_id
            )

            # Cache successful analysis results
            if result.get("success", False):
                analysis_key = f"analysis:{flow_id}"
                await self.cache.set(
                    analysis_key,
                    result,
                    ttl_seconds=self.performance_config.cache.repo_context_ttl_seconds,
                )

            return result

        except Exception as e:
            self.logger.error(
                f"[ANALYSIS] Enhanced analysis failed for flow_id={flow_id}: {e}"
            )
            return {"success": False, "error": str(e)}

    async def _execute_fallback_analysis(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
    ) -> Dict[str, Any]:
        """
        Execute fallback analysis when enhanced analysis fails.

        Args:
            triage_packet: Issue triage data
            historical_logs: Historical log data
            configs: Configuration data
            flow_id: Workflow identifier

        Returns:
            Fallback analysis result
        """
        try:
            self.logger.info(
                f"[FALLBACK] Executing fallback analysis for flow_id={flow_id}"
            )

            # Simple fallback analysis
            issue_context = self.enhanced_agent._extract_issue_context(triage_packet)

            # Basic root cause analysis
            root_cause = self._analyze_root_cause_basic(triage_packet, historical_logs)

            # Basic fix proposal
            proposed_fix = self._propose_basic_fix(issue_context, root_cause)

            # Basic code patch
            code_patch = self._generate_basic_code_patch(issue_context, proposed_fix)

            return {
                "success": True,
                "fallback": True,
                "analysis": {
                    "root_cause_analysis": root_cause,
                    "proposed_fix": proposed_fix,
                    "code_patch": code_patch,
                },
            }

        except Exception as e:
            self.logger.error(
                f"[FALLBACK] Fallback analysis failed for flow_id={flow_id}: {e}"
            )
            return {"success": False, "error": str(e), "fallback": True}

    async def _generate_enhanced_code(
        self,
        analysis_result: Dict[str, Any],
        prompt_context: PromptContext,
        enable_specialized_generators: bool,
    ) -> str:
        """
        Generate enhanced code using specialized generators.

        Args:
            analysis_result: Analysis result from enhanced agent
            prompt_context: Enhanced prompt context
            enable_specialized_generators: Whether to use specialized generators

        Returns:
            Generated code
        """
        try:
            if not analysis_result.get("success", False):
                return ""

            analysis = analysis_result.get("analysis", {})
            base_code_patch = analysis.get("code_patch", "")

            if not base_code_patch:
                return ""

            if not enable_specialized_generators:
                return base_code_patch

            # Enhance code using specialized generators
            enhanced_code = await self._enhance_code_with_specialized_generators(
                base_code_patch, prompt_context
            )

            return enhanced_code or base_code_patch

        except Exception as e:
            self.logger.error(f"[GENERATION] Code generation failed: {e}")
            return analysis_result.get("analysis", {}).get("code_patch", "")

    async def _enhance_code_with_specialized_generators(
        self, base_code: str, prompt_context: PromptContext
    ) -> str:
        """
        Enhance code using specialized generators.

        Args:
            base_code: Base generated code
            prompt_context: Enhanced prompt context

        Returns:
            Enhanced code
        """
        try:
            if not hasattr(self.enhanced_agent, "code_generator_factory"):
                return base_code

            # Get appropriate generator
            generator_type = self.enhanced_agent._determine_generator_type(
                prompt_context.issue_context
            )

            if not generator_type:
                return base_code

            # Check if specialized generators are enabled
            if not self.enhanced_agent.code_generator_factory:
                self.logger.warning(
                    "Specialized generators not enabled, skipping enhancement"
                )
                return base_code

            # Convert string generator_type back to IssueType for the factory
            try:
                issue_type = IssueType(generator_type)
                generator = self.enhanced_agent.code_generator_factory.create_generator(
                    issue_type
                )
            except ValueError:
                # If conversion fails, use UNKNOWN type
                generator = self.enhanced_agent.code_generator_factory.create_generator(
                    IssueType.UNKNOWN
                )

            if not generator:
                return base_code

            # Enhance the code
            enhanced_code = await generator.enhance_code_patch(
                base_code, prompt_context
            )

            return enhanced_code

        except Exception as e:
            self.logger.error(f"[ENHANCEMENT] Code enhancement failed: {e}")
            return base_code

    async def _validate_generated_code(
        self, analysis_result: Dict[str, Any], prompt_context: PromptContext
    ) -> Dict[str, Any]:
        """
        Validate generated code for quality and correctness using the validation pipeline.

        Args:
            analysis_result: Analysis result containing generated code
            prompt_context: Context for validation

        Returns:
            Validation result
        """
        try:
            # Prepare code result for validation pipeline
            code_result = {
                "code_patch": analysis_result.get("analysis", {}).get("code_patch", ""),
                "file_path": analysis_result.get("analysis", {}).get(
                    "file_path", "unknown"
                ),
                "generator_type": prompt_context.generator_type,
                "issue_type": prompt_context.issue_context.issue_type.value,
            }

            # Use the validation pipeline
            validation_result = await self.validation_pipeline.validate_code(
                code_result,
                {
                    "repository_context": prompt_context.repository_context,
                    "issue_context": prompt_context.issue_context,
                },
            )

            # Convert to legacy format for compatibility
            return {
                "is_valid": validation_result.is_valid,
                "overall_score": validation_result.overall_score,
                "issues": [
                    {
                        "id": issue.issue_id,
                        "type": issue.validation_type.value,
                        "level": issue.level.value,
                        "message": issue.message,
                        "description": issue.description,
                        "line_number": issue.line_number,
                        "suggested_fix": issue.suggested_fix,
                    }
                    for issue in validation_result.issues
                ],
                "warnings": [
                    issue
                    for issue in validation_result.issues
                    if issue.level.value == "warning"
                ],
                "suggestions": [
                    {
                        "id": feedback.feedback_id,
                        "category": feedback.category,
                        "message": feedback.message,
                        "suggestion": feedback.suggestion,
                        "priority": feedback.priority,
                    }
                    for feedback in validation_result.feedback
                ],
                "validation_summary": validation_result.get_validation_summary(),
            }

        except Exception as e:
            self.logger.error(f"[VALIDATION] Code validation failed: {e}")
            return {
                "is_valid": False,
                "overall_score": 0.0,
                "issues": [f"Validation error: {e}"],
                "warnings": [],
                "suggestions": [],
                "validation_summary": {"error": str(e)},
            }

    async def _validate_python_code(self, code: str) -> Dict[str, Any]:
        """Validate Python code for syntax and common issues."""
        validation_result = {
            "is_valid": True,
            "issues": [],
            "warnings": [],
            "suggestions": [],
        }

        try:
            # Check Python syntax
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            validation_result["is_valid"] = False
            validation_result["issues"].append(f"Syntax error: {e}")

        # Check for common Python issues
        if "import *" in code:
            validation_result["warnings"].append("Avoid wildcard imports")

        if "global " in code:
            validation_result["suggestions"].append(
                "Consider avoiding global variables"
            )

        return validation_result

    async def _calculate_cache_hit_rate(self) -> float:
        """Calculate the current cache hit rate."""
        try:
            stats = await self.cache.get_stats()
            return stats.get("average_hit_rate", 0.0)
        except Exception:
            return 0.0

    def _analyze_root_cause_basic(
        self, triage_packet: Dict[str, Any], historical_logs: List[str]
    ) -> str:
        """Basic root cause analysis for fallback scenarios."""
        error_patterns = triage_packet.get("error_patterns", [])

        if "database" in str(error_patterns).lower():
            return "Database connection or query issue detected"
        elif "api" in str(error_patterns).lower():
            return "API endpoint or service communication issue"
        elif "timeout" in str(error_patterns).lower():
            return "Service timeout or performance issue"
        else:
            return "General service error requiring investigation"

    def _propose_basic_fix(self, issue_context: IssueContext, root_cause: str) -> str:
        """Propose basic fix for fallback scenarios."""
        if "database" in root_cause.lower():
            return "Implement proper database connection handling with retries and error logging"
        elif "api" in root_cause.lower():
            return "Add API error handling with proper status codes and retry logic"
        elif "timeout" in root_cause.lower():
            return "Implement timeout handling and circuit breaker pattern"
        else:
            return "Add comprehensive error handling and logging for better debugging"

    def _generate_basic_code_patch(
        self, issue_context: IssueContext, proposed_fix: str
    ) -> str:
        """Generate basic code patch for fallback scenarios."""
        affected_files = issue_context.affected_files

        if not affected_files:
            return "# Basic error handling implementation\n# TODO: Implement based on specific issue"

        # Generate basic code patch based on file type
        file_ext = (
            affected_files[0].split(".")[-1] if "." in affected_files[0] else "py"
        )

        if file_ext == "py":
            return f"""# Basic Python error handling
try:
    # TODO: Implement the actual fix based on: {proposed_fix}
    pass
except Exception as e:
    logging.error(f"Error occurred: {{e}}")
    # TODO: Implement proper error handling
    raise"""
        else:
            return f"# Basic error handling for {file_ext} files\n# TODO: Implement based on: {proposed_fix}"

    async def get_workflow_history(self) -> List[WorkflowResult]:
        """Get workflow execution history."""
        return self.workflow_history.copy()

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

    async def clear_cache(self):
        """Clear all caches."""
        try:
            await self.cache.clear()
            self.logger.info("All caches cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear caches: {e}")

    async def reset_workflow_history(self):
        """Reset workflow execution history."""
        self.workflow_history.clear()
        self.logger.info("Workflow history reset")
