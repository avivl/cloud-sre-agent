# gemini_sre_agent/agents/specialized/analysis_agent.py

"""
Enhanced Analysis Agent for analysis tasks.

This module provides the EnhancedAnalysisAgent class specialized for analysis
with multi-provider support and intelligent model selection.
"""

import logging
from typing import Any

from ...llm.base import ModelType
from ...llm.common.enums import ProviderType
from ...llm.config import LLMConfig
from ...llm.strategy_manager import OptimizationGoal
from ..enhanced_base import EnhancedBaseAgent
from ..response_models import AnalysisResponse

logger = logging.getLogger(__name__)


class EnhancedAnalysisAgent(EnhancedBaseAgent[AnalysisResponse]):
    """
    Enhanced agent specialized for analysis tasks with multi-provider support.

    Optimized for complex analysis tasks with intelligent model selection
    based on analysis complexity and accuracy requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "analysis_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced analysis agent.

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
            "EnhancedAnalysisAgent initialized with quality-focused optimization"
        )

    async def analyze(
        self,
        content: str,
        criteria: list[str],
        analysis_type: str = "general",
        depth: str = "detailed",
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform analysis with intelligent model selection.

        Args:
            content: Content to analyze
            criteria: Analysis criteria
            analysis_type: Type of analysis (general, technical, business, etc.)
            depth: Analysis depth (brief, detailed, comprehensive)
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with analysis results
        """
        prompt_args = {
            "content": content,
            "criteria": criteria,
            "analysis_type": analysis_type,
            "depth": depth,
            **kwargs,
        }

        return await self.execute(
            prompt_name="analyze",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def compare_analysis(
        self,
        items: list[str],
        comparison_criteria: list[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform comparative analysis with intelligent model selection.

        Args:
            items: Items to compare
            comparison_criteria: Criteria for comparison
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with comparison results
        """
        prompt_args = {
            "items": items,
            "comparison_criteria": comparison_criteria,
            "task": "compare",
            **kwargs,
        }

        return await self.execute(
            prompt_name="compare_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def trend_analysis(
        self,
        data: list[dict[str, Any]],
        time_period: str,
        metrics: list[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform trend analysis with intelligent model selection.

        Args:
            data: Data for trend analysis
            time_period: Time period for analysis
            metrics: Metrics to analyze
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with trend analysis results
        """
        prompt_args = {
            "data": data,
            "time_period": time_period,
            "metrics": metrics,
            "task": "trend_analysis",
            **kwargs,
        }

        return await self.execute(
            prompt_name="trend_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def root_cause_analysis(
        self,
        issue_description: str,
        context: dict[str, Any],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform root cause analysis with intelligent model selection.

        Args:
            issue_description: Description of the issue
            context: Additional context for analysis
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with root cause analysis results
        """
        prompt_args = {
            "issue_description": issue_description,
            "context": context,
            "task": "root_cause_analysis",
            **kwargs,
        }

        return await self.execute(
            prompt_name="root_cause_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def impact_analysis(
        self,
        change_description: str,
        affected_systems: list[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform impact analysis with intelligent model selection.

        Args:
            change_description: Description of the proposed change
            affected_systems: List of systems that may be affected
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with impact analysis results
        """
        prompt_args = {
            "change_description": change_description,
            "affected_systems": affected_systems,
            "task": "impact_analysis",
            **kwargs,
        }

        return await self.execute(
            prompt_name="impact_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    def get_agent_capabilities(self) -> dict[str, Any]:
        """
        Get the capabilities and configuration of this analysis agent.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "analysis",
            "optimization_goal": self.optimization_goal.value,
            "min_quality": self.min_quality,
            "supported_analysis_types": [
                "general",
                "technical",
                "business",
                "root_cause",
                "impact",
                "trend",
                "comparative",
            ],
            "supported_depths": ["brief", "detailed", "comprehensive"],
            "model_type_preference": ModelType.DEEP_THINKING.value,
        }
