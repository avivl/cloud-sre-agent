# gemini_sre_agent/agents/specialized/triage_agent.py

"""
Enhanced Triage Agent for triage tasks.

This module provides the EnhancedTriageAgent class specialized for triage
with multi-provider support and intelligent model selection.
"""

import logging
from typing import Any

from ...llm.base import ModelType
from ...llm.common.enums import ProviderType
from ...llm.config import LLMConfig
from ...llm.strategy_manager import OptimizationGoal
from ..enhanced_base import EnhancedBaseAgent
from ..response_models import TriageResult

logger = logging.getLogger(__name__)


class EnhancedTriageAgent(EnhancedBaseAgent[TriageResult]):
    """
    Enhanced agent specialized for triage tasks with multi-provider support.

    Optimized for fast triage with intelligent model selection
    based on urgency and complexity requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "triage_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.PERFORMANCE,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_performance: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced triage agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Strategy for model selection (default: PERFORMANCE)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_performance: Minimum performance score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=TriageResult,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.FAST,
            max_cost=max_cost,
            min_performance=min_performance,
            **kwargs,
        )

        logger.info(
            "EnhancedTriageAgent initialized with performance-focused optimization"
        )

    async def triage_issue(
        self,
        issue: str,
        context: dict[str, Any] | None = None,
        urgency_level: str = "medium",
        **kwargs: Any,
    ) -> TriageResult:
        """
        Triage an issue with intelligent model selection.

        Args:
            issue: Issue description
            context: Additional context information
            urgency_level: Urgency level (low, medium, high, critical)
            **kwargs: Additional arguments

        Returns:
            TriageResult with triage results
        """
        prompt_args = {
            "issue": issue,
            "context": context or {},
            "urgency_level": urgency_level,
            "task": "triage",
            **kwargs,
        }

        return await self.execute(
            prompt_name="triage_issue",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )

    async def categorize_issue(
        self,
        issue: str,
        categories: list[str],
        **kwargs: Any,
    ) -> TriageResult:
        """
        Categorize an issue into predefined categories.

        Args:
            issue: Issue description
            categories: Available categories
            **kwargs: Additional arguments

        Returns:
            TriageResult with categorization results
        """
        prompt_args = {
            "issue": issue,
            "categories": categories,
            "task": "categorize",
            **kwargs,
        }

        return await self.execute(
            prompt_name="categorize_issue",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )

    async def prioritize_issues(
        self,
        issues: list[dict[str, Any]],
        priority_criteria: list[str],
        **kwargs: Any,
    ) -> TriageResult:
        """
        Prioritize a list of issues based on criteria.

        Args:
            issues: List of issues to prioritize
            priority_criteria: Criteria for prioritization
            **kwargs: Additional arguments

        Returns:
            TriageResult with prioritization results
        """
        prompt_args = {
            "issues": issues,
            "priority_criteria": priority_criteria,
            "task": "prioritize",
            **kwargs,
        }

        return await self.execute(
            prompt_name="prioritize_issues",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )

    async def assess_impact(
        self,
        issue: str,
        affected_systems: list[str],
        **kwargs: Any,
    ) -> TriageResult:
        """
        Assess the impact of an issue on affected systems.

        Args:
            issue: Issue description
            affected_systems: List of affected systems
            **kwargs: Additional arguments

        Returns:
            TriageResult with impact assessment
        """
        prompt_args = {
            "issue": issue,
            "affected_systems": affected_systems,
            "task": "assess_impact",
            **kwargs,
        }

        return await self.execute(
            prompt_name="assess_impact",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )

    def get_agent_capabilities(self) -> dict[str, Any]:
        """
        Get the capabilities and configuration of this triage agent.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "triage",
            "optimization_goal": self.optimization_goal.value,
            "min_performance": getattr(self, "min_performance", 0.8),
            "supported_urgency_levels": ["low", "medium", "high", "critical"],
            "supported_tasks": [
                "issue_triage",
                "categorization",
                "prioritization",
                "impact_assessment",
            ],
            "model_type_preference": ModelType.FAST.value,
        }
