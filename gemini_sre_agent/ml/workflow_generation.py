# gemini_sre_agent/ml/workflow_generation.py

"""
Workflow generation engine module.

This module handles all code generation operations for the workflow orchestrator.
Extracted from unified_workflow_orchestrator_original.py.
"""

import logging
from typing import Any, Dict, Optional

from .caching import ContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import PerformanceConfig
from .prompt_context_models import IssueContext, IssueType, PromptContext


class WorkflowGenerationEngine:
    """
    Manages workflow code generation operations.
    
    This class handles all code generation operations including enhanced code
    generation, specialized generator enhancement, and basic code patch generation
    with proper error handling and caching.
    """

    def __init__(self, performance_config: Optional[PerformanceConfig]):
        """
        Initialize the workflow generation engine.
        
        Args:
            performance_config: Performance configuration
        """
        self.performance_config = performance_config
        self.logger = logging.getLogger(__name__)
        
        # Initialize enhanced agent (will be injected)
        self.enhanced_agent: Optional[EnhancedAnalysisAgent] = None
        self.cache: Optional[ContextCache] = None

    def set_enhanced_agent(self, enhanced_agent: EnhancedAnalysisAgent) -> None:
        """Set the enhanced analysis agent."""
        self.enhanced_agent = enhanced_agent

    def set_cache(self, cache: ContextCache) -> None:
        """Set the context cache."""
        self.cache = cache

    async def generate_enhanced_code(
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
            if not self.enhanced_agent:
                return base_code
                
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

    def generate_basic_code_patch(
        self, issue_context: IssueContext, proposed_fix: str
    ) -> str:
        """
        Generate basic code patch for fallback scenarios.
        
        Args:
            issue_context: Issue context information
            proposed_fix: Proposed fix description
            
        Returns:
            Basic code patch
        """
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

    async def get_cached_generation(self, flow_id: str) -> Optional[str]:
        """
        Get cached generation result for a specific flow.
        
        Args:
            flow_id: Workflow identifier
            
        Returns:
            Cached generation result or None if not found
        """
        try:
            if not self.cache:
                return None
                
            generation_key = f"generation:{flow_id}"
            return await self.cache.get(generation_key)
        except Exception as e:
            self.logger.warning(f"Failed to get cached generation: {e}")
            return None

    async def cache_generation(self, flow_id: str, generated_code: str) -> None:
        """
        Cache generation result for a specific flow.
        
        Args:
            flow_id: Workflow identifier
            generated_code: Generated code to cache
        """
        try:
            if not self.cache or not self.performance_config:
                return
                
            generation_key = f"generation:{flow_id}"
            await self.cache.set(
                generation_key,
                generated_code,
                ttl_seconds=self.performance_config.cache.repo_context_ttl_seconds,
            )
            self.logger.debug(f"Cached generation for flow_id={flow_id}")
        except Exception as e:
            self.logger.warning(f"Failed to cache generation: {e}")

    async def clear_generation_cache(self, flow_id: Optional[str] = None) -> None:
        """
        Clear generation cache for a specific flow or all flows.
        
        Args:
            flow_id: Specific flow to clear, or None to clear all
        """
        try:
            if not self.cache:
                return
                
            if flow_id:
                generation_key = f"generation:{flow_id}"
                await self.cache.delete(generation_key)
                self.logger.info(f"Cleared generation cache for flow_id={flow_id}")
            else:
                await self.cache.clear()
                self.logger.info("Cleared all generation caches")
        except Exception as e:
            self.logger.error(f"Failed to clear generation cache: {e}")

    async def get_generation_statistics(self) -> Dict[str, Any]:
        """
        Get generation statistics for monitoring.
        
        Returns:
            Dictionary containing generation statistics
        """
        try:
            if not self.cache:
                return {"cache_available": False}
                
            cache_stats = await self.cache.get_stats()
            return {
                "cache_available": True,
                "cache_stats": cache_stats,
                "enhanced_agent_available": self.enhanced_agent is not None,
                "specialized_generators_available": (
                    self.enhanced_agent is not None and
                    hasattr(self.enhanced_agent, "code_generator_factory") and
                    self.enhanced_agent.code_generator_factory is not None
                ),
            }
        except Exception as e:
            self.logger.error(f"Failed to get generation statistics: {e}")
            return {"error": str(e)}

    async def health_check(self) -> str:
        """
        Perform health check on generation engine components.
        
        Returns:
            Health status string
        """
        try:
            # Check if essential components are available
            if not self.enhanced_agent:
                return "degraded - enhanced agent not set"
            
            if not self.cache:
                return "degraded - cache not set"
            
            # Test basic functionality
            try:
                # Test basic code generation with minimal data
                test_issue_context = IssueContext(
                    issue_type=IssueType.UNKNOWN,
                    affected_files=["test.py"],
                    error_patterns=["test"],
                    severity_level=2,
                    impact_analysis={"test": "test"},
                    related_services=["test"],
                    temporal_context={"test": "test"},
                    user_impact="test",
                    business_impact="test"
                )
                test_fix = "Test fix"
                result = self.generate_basic_code_patch(test_issue_context, test_fix)
                
                if not result:
                    return "unhealthy - basic code generation failed"
                    
            except Exception as e:
                return f"unhealthy - generation test failed: {str(e)}"
            
            return "healthy"
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return f"unhealthy - {str(e)}"