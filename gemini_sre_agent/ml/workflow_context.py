# gemini_sre_agent/ml/workflow_context.py

"""
Workflow context management module.

This module handles all context building, repository analysis, and issue extraction
logic for the workflow orchestrator. Extracted from unified_workflow_orchestrator_original.py.
"""

import logging
from typing import Any

from .caching import ContextCache, IssuePatternCache, RepositoryContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import (
    AsyncTask,
    PerformanceConfig,
    PerformanceRepositoryAnalyzer,
    get_async_optimizer,
)
from .prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)


class WorkflowContextManager:
    """
    Manages workflow context building and repository analysis.

    This class handles all context-related operations including repository analysis,
    issue context extraction, and context caching with performance optimizations.
    """

    def __init__(
        self,
        cache: ContextCache | None,
        repo_path: str,
        performance_config: PerformanceConfig | None,
    ):
        """
        Initialize the workflow context manager.

        Args:
            cache: Context cache instance
            repo_path: Path to repository for analysis
            performance_config: Performance configuration
        """
        self.cache = cache
        self.repo_path = repo_path
        self.performance_config = performance_config
        self.logger = logging.getLogger(__name__)

        # Initialize specialized caches
        self.repo_cache = RepositoryContextCache(
            max_size_mb=50, default_ttl_seconds=3600
        )
        self.pattern_cache = IssuePatternCache(max_size_mb=30, default_ttl_seconds=1800)

        # Initialize performance analyzer
        self.repo_analyzer = PerformanceRepositoryAnalyzer(self.repo_cache, repo_path)

        # Initialize async optimizer
        self.async_optimizer = get_async_optimizer()

        # Initialize enhanced agent (will be injected)
        self.enhanced_agent: EnhancedAnalysisAgent | None = None

    def set_enhanced_agent(self, enhanced_agent: EnhancedAnalysisAgent) -> None:
        """Set the enhanced analysis agent."""
        self.enhanced_agent = enhanced_agent

    async def build_enhanced_context(
        self,
        triage_packet: dict[str, Any],
        historical_logs: list[str],
        configs: dict[str, Any],
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
            # Create async tasks for concurrent execution
            context_tasks = []

            # Task 1: Repository context (cached or analyzed)
            repo_task = AsyncTask(
                task_id=f"repo_context_{flow_id}",
                coroutine=self._get_repository_context,
                args=(analysis_depth, flow_id),
                priority=1,  # High priority
            )
            context_tasks.append(repo_task)

            # Task 2: Issue context extraction
            issue_task = AsyncTask(
                task_id=f"issue_context_{flow_id}",
                coroutine=self._extract_issue_context_async,
                args=(triage_packet,),
                priority=1,  # High priority
            )
            context_tasks.append(issue_task)

            # Execute tasks concurrently
            context_results = await self.async_optimizer.execute_concurrent_tasks(
                context_tasks, wait_for_all=True
            )

            # Extract results
            repo_context = context_results.get(f"repo_context_{flow_id}")
            issue_context = context_results.get(f"issue_context_{flow_id}")

            if isinstance(issue_context, Exception):
                raise issue_context
            if isinstance(repo_context, Exception):
                raise repo_context

            # Ensure we have valid contexts
            if issue_context is None:
                raise ValueError("Failed to extract issue context")
            if repo_context is None:
                raise ValueError("Failed to get repository context")

            # Determine generator type
            if self.enhanced_agent:
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
                # Convert cached pattern back to IssueContext if needed
                if isinstance(cached_pattern, dict):
                    # Reconstruct IssueContext from cached data
                    issue_context = IssueContext(**cached_pattern)
                else:
                    issue_context = cached_pattern

            # Build comprehensive context
            # Ensure repo_context is a RepositoryContext object
            if isinstance(repo_context, dict):
                repo_context = RepositoryContext(**repo_context)

            context = PromptContext(
                issue_context=issue_context,
                repository_context=repo_context,
                generator_type=generator_type or "general",
            )

            # Cache the issue pattern for future use
            await self.pattern_cache.set_issue_pattern(
                "issue_context", pattern_key, issue_context.to_dict()
            )

            return context

        except Exception as e:
            self.logger.error(
                f"[CONTEXT] Context building failed for flow_id={flow_id}: {e}"
            )
            # Return minimal context on failure
            # Create fallback issue context with safe defaults
            fallback_issue_type = IssueType.UNKNOWN
            if (
                issue_context
                and not isinstance(issue_context, Exception)
                and hasattr(issue_context, "issue_type")
            ):
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

    async def _get_repository_context(
        self, analysis_depth: str, flow_id: str
    ) -> RepositoryContext:
        """Helper method for async repository context retrieval."""
        try:
            # Check cache first
            cached_repo_context = await self.repo_cache.get_repository_context(
                str(self.repo_analyzer.repo_path), analysis_depth
            )

            if cached_repo_context:
                self.logger.debug(
                    f"[CONTEXT] Using cached repository context for flow_id={flow_id}"
                )
                # Convert cached dict back to RepositoryContext
                if isinstance(cached_repo_context, dict):
                    return RepositoryContext(**cached_repo_context)
                return cached_repo_context
            else:
                # Perform repository analysis
                self.logger.info(
                    f"[CONTEXT] Analyzing repository for flow_id={flow_id}"
                )
                return await self.repo_analyzer.analyze_repository(analysis_depth)

        except Exception as e:
            self.logger.error(f"Failed to get repository context: {e}")
            raise

    async def _extract_issue_context_async(
        self, triage_packet: dict[str, Any]
    ) -> IssueContext:
        """Helper method for async issue context extraction."""
        try:
            if not self.enhanced_agent:
                raise ValueError("Enhanced agent not set")
            return self.enhanced_agent._extract_issue_context(triage_packet)
        except Exception as e:
            self.logger.error(f"Failed to extract issue context: {e}")
            raise

    async def get_cached_context(self, flow_id: str) -> PromptContext | None:
        """
        Get cached context for a specific flow.

        Args:
            flow_id: Workflow identifier

        Returns:
            Cached context or None if not found
        """
        try:
            # Try to get cached issue context
            pattern_key = f"issue_context:{flow_id}"
            cached_pattern = await self.pattern_cache.get_issue_pattern(
                "issue_context", pattern_key
            )

            if cached_pattern:
                # Try to get cached repository context
                cached_repo_context = await self.repo_cache.get_repository_context(
                    str(self.repo_analyzer.repo_path), "standard"
                )

                if cached_repo_context:
                    if isinstance(cached_repo_context, dict):
                        repo_context = RepositoryContext(**cached_repo_context)
                    else:
                        repo_context = cached_repo_context

                    if isinstance(cached_pattern, dict):
                        issue_context = IssueContext(**cached_pattern)
                    else:
                        issue_context = cached_pattern

                    return PromptContext(
                        issue_context=issue_context,
                        repository_context=repo_context,
                        generator_type="cached",
                    )

            return None
        except Exception as e:
            self.logger.warning(f"Failed to get cached context: {e}")
            return None

    async def clear_context_cache(self, flow_id: str | None = None) -> None:
        """
        Clear context cache for a specific flow or all flows.

        Args:
            flow_id: Specific flow to clear, or None to clear all
        """
        try:
            if flow_id:
                # Clear specific flow cache
                # Clear specific pattern - use clear method for now
                await self.pattern_cache.clear()
                self.logger.info(f"Cleared context cache for flow_id={flow_id}")
            else:
                # Clear all caches
                await self.pattern_cache.clear()
                await self.repo_cache.clear()
                self.logger.info("Cleared all context caches")
        except Exception as e:
            self.logger.error(f"Failed to clear context cache: {e}")

    async def get_cache_statistics(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary containing cache statistics
        """
        try:
            repo_stats = await self.repo_cache.get_stats()
            pattern_stats = await self.pattern_cache.get_stats()

            return {
                "repository_cache": {
                    "size_mb": repo_stats.get("current_size_bytes", 0) / (1024 * 1024),
                    "max_size_mb": repo_stats.get("max_size_mb", 0),
                    "hit_rate": repo_stats.get("average_hit_rate", 0.0),
                },
                "pattern_cache": {
                    "size_mb": pattern_stats.get("current_size_bytes", 0)
                    / (1024 * 1024),
                    "max_size_mb": pattern_stats.get("max_size_mb", 0),
                    "hit_rate": pattern_stats.get("average_hit_rate", 0.0),
                },
            }
        except Exception as e:
            self.logger.error(f"Failed to get cache statistics: {e}")
            return {}

    async def health_check(self) -> str:
        """
        Perform health check on context manager components.

        Returns:
            Health status string
        """
        try:
            # Check if essential components are available
            if not self.enhanced_agent:
                return "degraded - enhanced agent not set"

            # Check cache health
            repo_cache_health = "healthy"
            pattern_cache_health = "healthy"

            try:
                await self.repo_cache.get_repository_context("test", "standard")
            except Exception:
                repo_cache_health = "degraded"

            try:
                await self.pattern_cache.get_issue_pattern("test", "test")
            except Exception:
                pattern_cache_health = "degraded"

            if repo_cache_health == "healthy" and pattern_cache_health == "healthy":
                return "healthy"
            else:
                return f"degraded - repo_cache: {repo_cache_health}, pattern_cache: {pattern_cache_health}"

        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return f"unhealthy - {e!s}"
