# gemini_sre_agent/ml/workflow_analysis_engine.py

"""
Workflow Analysis Engine for enhanced code generation.

This module handles analysis execution, fallback logic, and basic analysis
for the unified workflow orchestrator.
"""

import logging
from typing import Any, Dict, List

from .caching import ContextCache
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .performance import PerformanceConfig
from .prompt_context_models import IssueContext, PromptContext


class WorkflowAnalysisEngine:
    """
    Handles analysis execution and fallback logic for the workflow orchestrator.

    This class manages:
    - Enhanced analysis execution
    - Fallback analysis when enhanced analysis fails
    - Basic root cause analysis
    - Analysis result caching
    """

    def __init__(
        self,
        enhanced_agent: EnhancedAnalysisAgent,
        cache: ContextCache,
        performance_config: PerformanceConfig,
    ):
        """
        Initialize the analysis engine.

        Args:
            enhanced_agent: Enhanced analysis agent instance
            cache: Context cache instance
            performance_config: Performance configuration
        """
        self.enhanced_agent = enhanced_agent
        self.cache = cache
        self.performance_config = performance_config
        self.logger = logging.getLogger(__name__)

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
