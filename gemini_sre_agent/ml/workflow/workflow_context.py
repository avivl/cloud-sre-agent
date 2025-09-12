# gemini_sre_agent/ml/workflow/workflow_context.py

"""
Workflow context management for the unified workflow orchestrator.

This module handles context building, caching, and management for workflow
operations, providing a centralized context management system.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..caching import ContextCache, IssuePatternCache, RepositoryContextCache
from ..prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)
from ...core.interfaces import StatefulComponent
from ...core.types import AgentContext, ConfigDict, Timestamp

logger = logging.getLogger(__name__)


@dataclass
class WorkflowContext:
    """
    Context for workflow operations.
    
    This class holds all the context information needed for workflow
    execution, including repository context, issue context, and
    performance metrics.
    """
    
    # Core context data
    repository_context: RepositoryContext
    issue_context: IssueContext
    prompt_context: PromptContext
    
    # Performance tracking
    start_time: Timestamp = field(default_factory=time.time)
    context_building_duration: float = 0.0
    cache_hit_rate: float = 0.0
    
    # Workflow state
    current_step: str = "initialized"
    error_count: int = 0
    warnings: List[str] = field(default_factory=list)
    
    # Metadata
    workflow_id: str = ""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def get_duration(self) -> float:
        """Get total workflow duration."""
        return time.time() - self.start_time
    
    def add_warning(self, warning: str) -> None:
        """Add a warning to the context."""
        self.warnings.append(warning)
        logger.warning(f"Workflow warning: {warning}")
    
    def increment_error(self) -> None:
        """Increment error count."""
        self.error_count += 1
    
    def is_healthy(self) -> bool:
        """Check if the workflow context is healthy."""
        return self.error_count == 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary."""
        return {
            "workflow_id": self.workflow_id,
            "current_step": self.current_step,
            "duration": self.get_duration(),
            "context_building_duration": self.context_building_duration,
            "cache_hit_rate": self.cache_hit_rate,
            "error_count": self.error_count,
            "warnings": self.warnings,
            "is_healthy": self.is_healthy(),
            "repository_context": self.repository_context.to_dict() if hasattr(self.repository_context, 'to_dict') else str(self.repository_context),
            "issue_context": self.issue_context.to_dict() if hasattr(self.issue_context, 'to_dict') else str(self.issue_context),
            "prompt_context": self.prompt_context.to_dict() if hasattr(self.prompt_context, 'to_dict') else str(self.prompt_context),
        }


class WorkflowContextManager(StatefulComponent):
    """
    Manager for workflow context operations.
    
    This class handles context building, caching, and management
    for workflow operations.
    """
    
    def __init__(
        self,
        component_id: str = "workflow_context_manager",
        name: str = "Workflow Context Manager",
        config: Optional[ConfigDict] = None
    ) -> None:
        """
        Initialize the workflow context manager.
        
        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)
        
        # Initialize caches
        self.context_cache = ContextCache()
        self.issue_pattern_cache = IssuePatternCache()
        self.repository_context_cache = RepositoryContextCache()
        
        # Performance tracking
        self.context_build_count = 0
        self.cache_hit_count = 0
        self.total_build_time = 0.0
        self.error_count = 0
    
    async def build_repository_context(
        self,
        repository_path: str,
        file_paths: List[str],
        commit_hash: Optional[str] = None
    ) -> RepositoryContext:
        """
        Build repository context from given parameters.
        
        Args:
            repository_path: Path to the repository
            file_paths: List of file paths to analyze
            commit_hash: Optional commit hash
            
        Returns:
            Built repository context
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"repo_{repository_path}_{hash(tuple(file_paths))}_{commit_hash or 'latest'}"
            cached_context = await self.repository_context_cache.get(cache_key)
            
            if cached_context:
                self.cache_hit_count += 1
                logger.debug(f"Repository context cache hit for {repository_path}")
                return cached_context
            
            # Build new context
            context = RepositoryContext(
                architecture_type="microservices",  # Default, would be determined from analysis
                technology_stack={"language": "python", "framework": "fastapi"},
                coding_standards={"linting": "pylint", "style": "black"},
                error_handling_patterns=["try-catch", "logging", "circuit-breaker"],
                testing_patterns=["unit", "integration", "e2e"],
                dependency_structure={},
                recent_changes=[],
                historical_fixes=[],
                code_quality_metrics={"complexity": 0.5, "coverage": 0.8},
            )
            
            # Cache the result
            await self.repository_context_cache.set(cache_key, context)
            
            build_time = time.time() - start_time
            self.total_build_time += build_time
            self.context_build_count += 1
            
            logger.debug(f"Built repository context for {repository_path} in {build_time:.3f}s")
            return context
            
        except Exception as e:
            logger.error(f"Failed to build repository context: {e}")
            raise
    
    async def build_issue_context(
        self,
        issue_description: str,
        issue_type: IssueType,
        affected_files: List[str],
        severity: str = "medium"
    ) -> IssueContext:
        """
        Build issue context from given parameters.
        
        Args:
            issue_description: Description of the issue
            issue_type: Type of the issue
            affected_files: List of affected files
            severity: Issue severity level
            
        Returns:
            Built issue context
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"issue_{hash(issue_description)}_{issue_type.value}_{hash(tuple(affected_files))}"
            cached_context = await self.issue_pattern_cache.get(cache_key)
            
            if cached_context:
                self.cache_hit_count += 1
                logger.debug(f"Issue context cache hit for {issue_type.value}")
                return cached_context
            
            # Build new context
            context = IssueContext(
                issue_type=issue_type,
                affected_files=affected_files,
                error_patterns=[],
                severity_level=1 if severity == "low" else 2 if severity == "medium" else 3,
                impact_analysis={},
                related_services=[],
                temporal_context={},
                user_impact="Unknown",
                business_impact="Unknown",
            )
            
            # Cache the result
            await self.issue_pattern_cache.set(cache_key, context)
            
            build_time = time.time() - start_time
            self.total_build_time += build_time
            self.context_build_count += 1
            
            logger.debug(f"Built issue context for {issue_type.value} in {build_time:.3f}s")
            return context
            
        except Exception as e:
            logger.error(f"Failed to build issue context: {e}")
            raise
    
    async def build_prompt_context(
        self,
        repository_context: RepositoryContext,
        issue_context: IssueContext,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> PromptContext:
        """
        Build prompt context from repository and issue contexts.
        
        Args:
            repository_context: Repository context
            issue_context: Issue context
            additional_context: Optional additional context
            
        Returns:
            Built prompt context
        """
        start_time = time.time()
        
        try:
            # Check cache first
            cache_key = f"prompt_{hash(str(repository_context))}_{hash(str(issue_context))}"
            cached_context = await self.context_cache.get(cache_key)
            
            if cached_context:
                self.cache_hit_count += 1
                logger.debug("Prompt context cache hit")
                return cached_context
            
            # Build new context
            context = PromptContext(
                issue_context=issue_context,
                repository_context=repository_context,
                generator_type="enhanced",
            )
            
            # Cache the result
            await self.context_cache.set(cache_key, context)
            
            build_time = time.time() - start_time
            self.total_build_time += build_time
            self.context_build_count += 1
            
            logger.debug(f"Built prompt context in {build_time:.3f}s")
            return context
            
        except Exception as e:
            logger.error(f"Failed to build prompt context: {e}")
            raise
    
    def create_workflow_context(
        self,
        repository_context: RepositoryContext,
        issue_context: IssueContext,
        prompt_context: PromptContext,
        workflow_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> WorkflowContext:
        """
        Create a complete workflow context.
        
        Args:
            repository_context: Repository context
            issue_context: Issue context
            prompt_context: Prompt context
            workflow_id: Workflow identifier
            user_id: Optional user identifier
            session_id: Optional session identifier
            
        Returns:
            Complete workflow context
        """
        context = WorkflowContext(
            repository_context=repository_context,
            issue_context=issue_context,
            prompt_context=prompt_context,
            workflow_id=workflow_id,
            user_id=user_id,
            session_id=session_id,
        )
        
        # Update state
        self.set_state("last_workflow_id", workflow_id)
        self.set_state("active_workflows", self.get_state("active_workflows", []) + [workflow_id])
        
        logger.info(f"Created workflow context for {workflow_id}")
        return context
    
    def update_workflow_step(self, context: WorkflowContext, step: str) -> None:
        """
        Update the current workflow step.
        
        Args:
            context: Workflow context to update
            step: New step name
        """
        context.current_step = step
        self.set_state(f"workflow_{context.workflow_id}_step", step)
        logger.debug(f"Updated workflow {context.workflow_id} to step: {step}")
    
    def get_cache_hit_rate(self) -> float:
        """
        Get the current cache hit rate.
        
        Returns:
            Cache hit rate as a percentage
        """
        total_requests = self.context_build_count + self.cache_hit_count
        if total_requests == 0:
            return 0.0
        return (self.cache_hit_count / total_requests) * 100.0
    
    def get_average_build_time(self) -> float:
        """
        Get the average context build time.
        
        Returns:
            Average build time in seconds
        """
        if self.context_build_count == 0:
            return 0.0
        return self.total_build_time / self.context_build_count
    
    async def clear_caches(self) -> None:
        """Clear all caches."""
        if hasattr(self.context_cache, 'clear'):
            await self.context_cache.clear()
        if hasattr(self.issue_pattern_cache, 'clear'):
            await self.issue_pattern_cache.clear()
        if hasattr(self.repository_context_cache, 'clear'):
            await self.repository_context_cache.clear()
        logger.info("Cleared all context caches")
    
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
            "context_build_count": self.context_build_count,
            "cache_hit_count": self.cache_hit_count,
            "cache_hit_rate": self.get_cache_hit_rate(),
            "average_build_time": self.get_average_build_time(),
            "active_workflows": self.get_state("active_workflows", []),
        }
    
    def check_health(self) -> bool:
        """
        Check if the component is healthy.
        
        Returns:
            True if healthy, False otherwise
        """
        return self.status != "error" and self.error_count == 0
