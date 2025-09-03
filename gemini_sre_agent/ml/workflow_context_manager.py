# gemini_sre_agent/ml/workflow_context_manager.py

"""
Workflow Context Manager for enhanced code generation.

This module handles context building, caching, and repository analysis
for the unified workflow orchestrator.
"""

import logging
from typing import Any, Dict, Optional

from .caching import IssuePatternCache, RepositoryContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import AsyncTask, PerformanceRepositoryAnalyzer, get_async_optimizer
from .prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)


class WorkflowContextManager:
    """
    Manages context building and caching for the workflow orchestrator.

    This class handles:
    - Repository context analysis and caching
    - Issue context extraction and pattern caching
    - Concurrent context building with async optimization
    - Fallback context creation
    """

    def __init__(
        self,
        enhanced_agent: EnhancedAnalysisAgent,
        repo_path: str = ".",
        repo_cache: Optional[RepositoryContextCache] = None,
        pattern_cache: Optional[IssuePatternCache] = None,
    ):
        """
        Initialize the context manager.

        Args:
            enhanced_agent: Enhanced analysis agent instance
            repo_path: Path to repository for analysis
            repo_cache: Repository context cache instance
            pattern_cache: Issue pattern cache instance
        """
        self.enhanced_agent = enhanced_agent
        self.repo_path = repo_path

        # Initialize caches if not provided
        self.repo_cache = repo_cache or RepositoryContextCache(
            max_size_mb=50, default_ttl_seconds=3600
        )
        self.pattern_cache = pattern_cache or IssuePatternCache(
            max_size_mb=30, default_ttl_seconds=1800
        )

        # Initialize repository analyzer
        self.repo_analyzer = PerformanceRepositoryAnalyzer(self.repo_cache, repo_path)

        # Initialize async optimizer
        self.async_optimizer = get_async_optimizer()

        self.logger = logging.getLogger(__name__)

    async def build_enhanced_context(
        self,
        triage_packet: Dict[str, Any],
        flow_id: str,
        analysis_depth: str,
    ) -> PromptContext:
        """
        Build enhanced context with performance optimizations.

        Args:
            triage_packet: Issue triage data
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
            # Ensure issue_context is not an Exception before passing to fallback
            safe_issue_context = None
            if issue_context and not isinstance(issue_context, Exception):
                safe_issue_context = issue_context
            return self._create_fallback_context(triage_packet, safe_issue_context)

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
        self, triage_packet: Dict[str, Any]
    ) -> IssueContext:
        """Helper method for async issue context extraction."""
        try:
            return self.enhanced_agent._extract_issue_context(triage_packet)
        except Exception as e:
            self.logger.error(f"Failed to extract issue context: {e}")
            raise

    def _create_fallback_context(
        self, triage_packet: Dict[str, Any], issue_context: Optional[IssueContext]
    ) -> PromptContext:
        """Create fallback context when context building fails."""
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

    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "repo_cache_stats": self.repo_cache.get_cache_stats(),
            "pattern_cache_stats": self.pattern_cache.get_cache_stats(),
        }

    async def clear_caches(self):
        """Clear all caches."""
        try:
            await self.repo_cache.clear()
            await self.pattern_cache.clear()
            self.logger.info("All context caches cleared")
        except Exception as e:
            self.logger.error(f"Failed to clear context caches: {e}")
