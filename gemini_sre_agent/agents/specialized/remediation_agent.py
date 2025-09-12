# gemini_sre_agent/agents/specialized/remediation_agent.py

"""
Enhanced Remediation Agent for remediation tasks.

This module provides the EnhancedRemediationAgent and EnhancedRemediationAgentV2
classes specialized for remediation with multi-provider support and intelligent model selection.
"""

import logging
from typing import Any, Dict, List, Optional

from ...llm.base import ModelType
from ...llm.common.enums import ProviderType
from ...llm.config import LLMConfig
from ...llm.strategy_manager import OptimizationGoal
from ..enhanced_base import EnhancedBaseAgent
from ..response_models import AnalysisResponse, RemediationResponse

logger = logging.getLogger(__name__)


class EnhancedRemediationAgent(EnhancedBaseAgent[AnalysisResponse]):
    """
    Enhanced agent specialized for remediation tasks with multi-provider support.

    Optimized for comprehensive remediation with intelligent model selection
    based on problem complexity and solution quality requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "remediation_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced remediation agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=AnalysisResponse,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.DEEP_THINKING,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info(
            "EnhancedRemediationAgent initialized with quality-focused optimization"
        )

    async def provide_remediation(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None,
        remediation_type: str = "general",
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Provide remediation with intelligent model selection.

        Args:
            problem: Problem description
            context: Additional context information
            remediation_type: Type of remediation (technical, process, etc.)
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with remediation recommendations
        """
        prompt_args = {
            "problem": problem,
            "context": context or {},
            "remediation_type": remediation_type,
            "task": "remediate",
            **kwargs,
        }

        return await self.execute(
            prompt_name="remediate",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def create_action_plan(
        self,
        problem: str,
        constraints: List[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Create a detailed action plan for remediation.

        Args:
            problem: Problem description
            constraints: List of constraints to consider
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with action plan
        """
        prompt_args = {
            "problem": problem,
            "constraints": constraints,
            "task": "action_plan",
            **kwargs,
        }

        return await self.execute(
            prompt_name="create_action_plan",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    def get_agent_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities and configuration of this remediation agent.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "remediation",
            "optimization_goal": self.optimization_goal.value,
            "min_quality": self.min_quality,
            "supported_remediation_types": [
                "technical",
                "process",
                "configuration",
                "security",
                "performance",
            ],
            "model_type_preference": ModelType.DEEP_THINKING.value,
        }


class EnhancedRemediationAgentV2(EnhancedBaseAgent[RemediationResponse]):
    """
    Enhanced Remediation Agent for generating code patches and remediation plans.

    This agent specializes in creating detailed remediation plans including:
    - Root cause analysis
    - Proposed fixes
    - Code patches
    - Priority assessment
    - Effort estimation
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "remediation_agent_v2",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Enhanced Remediation Agent.

        Args:
            llm_config: LLM configuration
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Optimization strategy
            provider_preference: Preferred LLM provider
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=RemediationResponse,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.CODE,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info(
            "EnhancedRemediationAgent initialized with code generation optimization"
        )

    async def create_remediation_plan(
        self,
        issue_description: str,
        error_context: str,
        target_file: str,
        **kwargs: Any,
    ) -> RemediationResponse:
        """
        Create a comprehensive remediation plan for an issue.

        Args:
            issue_description: Description of the issue to fix
            error_context: Context about the error (logs, stack traces, etc.)
            target_file: Target file path for the fix
            **kwargs: Additional context

        Returns:
            RemediationResponse with detailed remediation plan
        """
        prompt_args = {
            "problem": f"Issue: {issue_description}\nError Context: {error_context}\nTarget File: {target_file}\nAnalysis: {kwargs.get('analysis_summary', '')}\nKey Points: {', '.join(kwargs.get('key_points', []))}",
            **kwargs,
        }

        return await self.execute(
            prompt_name="remediate",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def generate_code_patch(
        self,
        issue_description: str,
        current_code: str,
        target_file: str,
        **kwargs: Any,
    ) -> RemediationResponse:
        """
        Generate a code patch for a specific issue.

        Args:
            issue_description: Description of the issue
            current_code: Current code that needs to be fixed
            target_file: Target file path
            **kwargs: Additional context

        Returns:
            RemediationResponse with code patch
        """
        prompt_args = {
            "issue_description": issue_description,
            "current_code": current_code,
            "target_file": target_file,
            "task": "code_patch",
            **kwargs,
        }

        return await self.execute(
            prompt_name="generate_code_patch",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def assess_priority(
        self,
        issue_description: str,
        impact_analysis: Dict[str, Any],
        **kwargs: Any,
    ) -> RemediationResponse:
        """
        Assess the priority of a remediation task.

        Args:
            issue_description: Description of the issue
            impact_analysis: Impact analysis data
            **kwargs: Additional context

        Returns:
            RemediationResponse with priority assessment
        """
        prompt_args = {
            "issue_description": issue_description,
            "impact_analysis": impact_analysis,
            "task": "priority_assessment",
            **kwargs,
        }

        return await self.execute(
            prompt_name="assess_priority",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    def get_agent_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities and configuration of this remediation agent v2.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "remediation_v2",
            "optimization_goal": self.optimization_goal.value,
            "min_quality": getattr(self, "min_quality", None),
            "supported_tasks": [
                "remediation_planning",
                "code_patch_generation",
                "priority_assessment",
                "root_cause_analysis",
            ],
            "model_type_preference": ModelType.CODE.value,
        }
