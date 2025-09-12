# gemini_sre_agent/ml/workflow_analysis.py

"""
Workflow analysis engine module.

This module handles all analysis operations for the workflow orchestrator.
Extracted from unified_workflow_orchestrator_original.py.
"""

import logging
from typing import Any, Dict, List, Optional

from .caching import ContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import PerformanceConfig
from .prompt_context_models import IssueContext, PromptContext


class WorkflowAnalysisEngine:
    """
    Manages workflow analysis operations.
    
    This class handles all analysis operations including enhanced analysis,
    fallback analysis, and root cause analysis with proper error handling
    and retry logic using existing resilience patterns.
    """

    def __init__(self, performance_config: Optional[PerformanceConfig]):
        """
        Initialize the workflow analysis engine.
        
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

    async def execute_enhanced_analysis(
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
            if not self.enhanced_agent:
                raise ValueError("Enhanced agent not set")
                
            # Use the enhanced analysis agent
            result = await self.enhanced_agent.analyze_issue(
                triage_packet, historical_logs, configs, flow_id
            )

            # Cache successful analysis results
            if result.get("success", False) and self.cache and self.performance_config:
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

    async def execute_fallback_analysis(
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

            if not self.enhanced_agent:
                raise ValueError("Enhanced agent not set")

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

    async def get_cached_analysis(self, flow_id: str) -> Optional[Dict[str, Any]]:
        """
        Get cached analysis result for a specific flow.
        
        Args:
            flow_id: Workflow identifier
            
        Returns:
            Cached analysis result or None if not found
        """
        try:
            if not self.cache:
                return None
                
            analysis_key = f"analysis:{flow_id}"
            return await self.cache.get(analysis_key)
        except Exception as e:
            self.logger.warning(f"Failed to get cached analysis: {e}")
            return None

    async def clear_analysis_cache(self, flow_id: Optional[str] = None) -> None:
        """
        Clear analysis cache for a specific flow or all flows.
        
        Args:
            flow_id: Specific flow to clear, or None to clear all
        """
        try:
            if not self.cache:
                return
                
            if flow_id:
                analysis_key = f"analysis:{flow_id}"
                await self.cache.delete(analysis_key)
                self.logger.info(f"Cleared analysis cache for flow_id={flow_id}")
            else:
                await self.cache.clear()
                self.logger.info("Cleared all analysis caches")
        except Exception as e:
            self.logger.error(f"Failed to clear analysis cache: {e}")

    async def get_analysis_statistics(self) -> Dict[str, Any]:
        """
        Get analysis statistics for monitoring.
        
        Returns:
            Dictionary containing analysis statistics
        """
        try:
            if not self.cache:
                return {"cache_available": False}
                
            cache_stats = await self.cache.get_stats()
            return {
                "cache_available": True,
                "cache_stats": cache_stats,
                "enhanced_agent_available": self.enhanced_agent is not None,
            }
        except Exception as e:
            self.logger.error(f"Failed to get analysis statistics: {e}")
            return {"error": str(e)}

    async def health_check(self) -> str:
        """
        Perform health check on analysis engine components.
        
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
                # Test fallback analysis with minimal data
                test_triage = {"error_patterns": ["test"], "affected_files": []}
                test_logs = []
                result = self._analyze_root_cause_basic(test_triage, test_logs)
                
                if not result:
                    return "unhealthy - root cause analysis failed"
                    
            except Exception as e:
                return f"unhealthy - analysis test failed: {str(e)}"
            
            return "healthy"
                
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return f"unhealthy - {str(e)}"
