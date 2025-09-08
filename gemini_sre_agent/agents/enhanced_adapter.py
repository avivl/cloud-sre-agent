"""
Enhanced Agent Adapter for Backward Compatibility.

This module provides adapters and migration utilities to help existing
agent implementations work with the enhanced multi-provider system
while maintaining backward compatibility.
"""

import logging
from typing import Any, Dict, List, Optional, TypeVar

from pydantic import BaseModel

from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .base import BaseAgent
from .enhanced_base import EnhancedBaseAgent
from .enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedCodeAgent,
    EnhancedTextAgent,
)

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class EnhancedAgentAdapter:
    """
    Adapter to bridge between legacy BaseAgent and enhanced multi-provider agents.

    Provides a seamless migration path for existing agent implementations
    while enabling access to enhanced multi-provider capabilities.
    """

    def __init__(
        self,
        legacy_agent: BaseAgent,
        llm_config: LLMConfig,
        enable_enhancements: bool = True,
    ):
        """
        Initialize the enhanced agent adapter.

        Args:
            legacy_agent: The legacy agent to adapt
            llm_config: LLM configuration for multi-provider support
            enable_enhancements: Whether to enable enhanced features
        """
        self.legacy_agent = legacy_agent
        self.llm_config = llm_config
        self.enable_enhancements = enable_enhancements

        # Create enhanced agent based on the legacy agent type
        self.enhanced_agent = self._create_enhanced_agent()

        logger.info(f"EnhancedAgentAdapter created for {type(legacy_agent).__name__}")

    def _create_enhanced_agent(self) -> EnhancedBaseAgent:
        """Create an enhanced agent based on the legacy agent type."""
        agent_type = type(self.legacy_agent).__name__

        # Map legacy agent types to enhanced agent types
        if agent_type == "TextAgent":
            return EnhancedTextAgent(
                llm_config=self.llm_config,
                primary_model=self.legacy_agent.primary_model,
                fallback_model=self.legacy_agent.fallback_model,
            )
        elif agent_type == "AnalysisAgent":
            return EnhancedAnalysisAgent(
                llm_config=self.llm_config,
                primary_model=self.legacy_agent.primary_model,
                fallback_model=self.legacy_agent.fallback_model,
            )
        elif agent_type == "CodeAgent":
            return EnhancedCodeAgent(
                llm_config=self.llm_config,
                primary_model=self.legacy_agent.primary_model,
                fallback_model=self.legacy_agent.fallback_model,
            )
        else:
            # Generic enhanced agent for unknown types
            return EnhancedBaseAgent(
                llm_config=self.llm_config,
                response_model=self.legacy_agent.response_model,  # type: ignore
                primary_model=self.legacy_agent.primary_model,
                fallback_model=self.legacy_agent.fallback_model,
            )

    async def execute(
        self,
        prompt_name: str,
        prompt_args: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Execute a prompt with backward compatibility and enhanced features.

        Args:
            prompt_name: Name of the prompt template
            prompt_args: Arguments for prompt formatting
            model: Specific model to use
            temperature: Temperature for generation
            use_fallback: Whether to use fallback models
            **kwargs: Additional arguments

        Returns:
            Structured response of type T
        """
        if self.enable_enhancements:
            # Use enhanced agent with intelligent model selection
            return await self.enhanced_agent.execute(
                prompt_name=prompt_name,
                prompt_args=prompt_args,
                model=model,
                temperature=temperature,
                use_fallback=use_fallback,
                **kwargs,
            )
        else:
            # Use legacy agent for backward compatibility
            return await self.legacy_agent.execute(
                prompt_name=prompt_name,
                prompt_args=prompt_args,
                model=model,
                temperature=temperature,
                use_fallback=use_fallback,
                **kwargs,
            )

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary."""
        if self.enable_enhancements:
            return self.enhanced_agent.get_stats_summary()
        else:
            return self.legacy_agent.get_stats_summary()

    def enable_enhanced_features(self) -> None:
        """Enable enhanced multi-provider features."""
        self.enable_enhancements = True
        logger.info("Enhanced features enabled")

    def disable_enhanced_features(self) -> None:
        """Disable enhanced features and use legacy behavior."""
        self.enable_enhancements = False
        logger.info("Enhanced features disabled, using legacy behavior")

    def update_optimization_goal(self, goal: OptimizationGoal) -> None:
        """Update the optimization goal for model selection."""
        if self.enable_enhancements:
            self.enhanced_agent.update_optimization_goal(goal)
        else:
            logger.warning(
                "Cannot update optimization goal when enhanced features are disabled"
            )

    def update_provider_preference(self, providers: List[ProviderType]) -> None:
        """Update the provider preference list."""
        if self.enable_enhancements:
            self.enhanced_agent.update_provider_preference(providers)
        else:
            logger.warning(
                "Cannot update provider preference when enhanced features are disabled"
            )

    def get_available_models(self) -> List[str]:
        """Get list of available models."""
        if self.enable_enhancements:
            return self.enhanced_agent.get_available_models()
        else:
            # Return basic model list for legacy agents
            models = []
            if self.legacy_agent.primary_model:
                models.append(self.legacy_agent.primary_model)
            if self.legacy_agent.fallback_model:
                models.append(self.legacy_agent.fallback_model)
            return models

    def get_available_providers(self) -> List[ProviderType]:
        """Get list of available providers."""
        if self.enable_enhancements:
            return self.enhanced_agent.get_available_providers()
        else:
            # Legacy agents only support Gemini
            return [ProviderType.GEMINI]


class AgentMigrationHelper:
    """
    Helper class for migrating from legacy agents to enhanced agents.

    Provides utilities for seamless migration and configuration conversion.
    """

    @staticmethod
    def create_enhanced_agent_from_legacy(
        legacy_agent: BaseAgent,
        llm_config: LLMConfig,
        migration_options: Optional[Dict[str, Any]] = None,
    ) -> EnhancedBaseAgent:
        """
        Create an enhanced agent from a legacy agent with migration options.

        Args:
            legacy_agent: The legacy agent to migrate
            llm_config: LLM configuration for multi-provider support
            migration_options: Options for migration behavior

        Returns:
            Enhanced agent instance
        """
        options = migration_options or {}

        # Extract configuration from legacy agent
        primary_model = getattr(legacy_agent, "primary_model", None)
        fallback_model = getattr(legacy_agent, "fallback_model", None)
        max_retries = getattr(legacy_agent, "max_retries", 2)
        collect_stats = getattr(legacy_agent, "collect_stats", True)

        # Determine optimization goal based on agent type
        agent_type = type(legacy_agent).__name__
        optimization_goal = options.get("optimization_goal")

        if not optimization_goal:
            if agent_type == "TextAgent":
                optimization_goal = OptimizationGoal.QUALITY
            elif agent_type == "AnalysisAgent":
                optimization_goal = OptimizationGoal.QUALITY
            elif agent_type == "CodeAgent":
                optimization_goal = OptimizationGoal.QUALITY
            else:
                optimization_goal = OptimizationGoal.HYBRID

        # Create enhanced agent based on type
        if agent_type == "TextAgent":
            return EnhancedTextAgent(
                llm_config=llm_config,
                primary_model=primary_model,
                fallback_model=fallback_model,
                optimization_goal=optimization_goal,
                max_retries=max_retries,
                collect_stats=collect_stats,
                **options.get("agent_kwargs", {}),
            )
        elif agent_type == "AnalysisAgent":
            return EnhancedAnalysisAgent(
                llm_config=llm_config,
                primary_model=primary_model,
                fallback_model=fallback_model,
                optimization_goal=optimization_goal,
                max_retries=max_retries,
                collect_stats=collect_stats,
                **options.get("agent_kwargs", {}),
            )
        elif agent_type == "CodeAgent":
            return EnhancedCodeAgent(
                llm_config=llm_config,
                primary_model=primary_model,
                fallback_model=fallback_model,
                optimization_goal=optimization_goal,
                max_retries=max_retries,
                collect_stats=collect_stats,
                **options.get("agent_kwargs", {}),
            )
        else:
            # Generic enhanced agent
            return EnhancedBaseAgent(
                llm_config=llm_config,
                response_model=legacy_agent.response_model,  # type: ignore
                primary_model=primary_model,
                fallback_model=fallback_model,
                optimization_goal=optimization_goal,
                max_retries=max_retries,
                collect_stats=collect_stats,
                **options.get("agent_kwargs", {}),
            )

    @staticmethod
    def validate_migration_compatibility(
        legacy_agent: BaseAgent,
        llm_config: LLMConfig,
    ) -> Dict[str, Any]:
        """
        Validate compatibility for migration from legacy to enhanced agent.

        Args:
            legacy_agent: The legacy agent to validate
            llm_config: LLM configuration for validation

        Returns:
            Validation results and recommendations
        """
        results = {
            "compatible": True,
            "warnings": [],
            "recommendations": [],
            "required_changes": [],
        }

        # Check if response model is compatible
        if not hasattr(legacy_agent, "response_model"):
            results["compatible"] = False
            results["required_changes"].append("Response model not found")

        # Check if LLM service is compatible
        if not hasattr(legacy_agent, "llm_service"):
            results["compatible"] = False
            results["required_changes"].append("LLM service not found")

        # Check configuration compatibility
        if not llm_config.providers:
            results["warnings"].append("No providers configured in LLM config")
            results["recommendations"].append(
                "Configure at least one provider for multi-provider support"
            )

        # Check for deprecated features
        if hasattr(legacy_agent, "_prompts") and legacy_agent._prompts:
            results["warnings"].append("Legacy prompt system detected")
            results["recommendations"].append(
                "Consider migrating to Mirascope for advanced prompt management"
            )

        return results

    @staticmethod
    def generate_migration_report(
        legacy_agents: List[BaseAgent],
        llm_config: LLMConfig,
    ) -> Dict[str, Any]:
        """
        Generate a comprehensive migration report for multiple agents.

        Args:
            legacy_agents: List of legacy agents to analyze
            llm_config: LLM configuration for analysis

        Returns:
            Comprehensive migration report
        """
        report = {
            "total_agents": len(legacy_agents),
            "compatible_agents": 0,
            "incompatible_agents": 0,
            "agent_details": [],
            "overall_recommendations": [],
            "migration_priority": [],
        }

        for agent in legacy_agents:
            validation = AgentMigrationHelper.validate_migration_compatibility(
                agent, llm_config
            )
            agent_detail = {
                "agent_type": type(agent).__name__,
                "compatible": validation["compatible"],
                "warnings": validation["warnings"],
                "recommendations": validation["recommendations"],
                "required_changes": validation["required_changes"],
            }

            report["agent_details"].append(agent_detail)

            if validation["compatible"]:
                report["compatible_agents"] += 1
            else:
                report["incompatible_agents"] += 1

        # Generate overall recommendations
        if report["incompatible_agents"] > 0:
            report["overall_recommendations"].append(
                f"Fix {report['incompatible_agents']} incompatible agents before migration"
            )

        if report["compatible_agents"] > 0:
            report["overall_recommendations"].append(
                f"Migrate {report['compatible_agents']} compatible agents to enhanced system"
            )

        # Prioritize migration based on agent types
        priority_order = ["TextAgent", "AnalysisAgent", "CodeAgent"]
        for priority_type in priority_order:
            for agent_detail in report["agent_details"]:
                if (
                    agent_detail["agent_type"] == priority_type
                    and agent_detail["compatible"]
                ):
                    report["migration_priority"].append(agent_detail["agent_type"])

        return report


class BackwardCompatibilityWrapper:
    """
    Wrapper to provide backward compatibility for existing agent interfaces.

    Allows existing code to work with enhanced agents without modification.
    """

    def __init__(self, enhanced_agent: EnhancedBaseAgent):
        """
        Initialize the backward compatibility wrapper.

        Args:
            enhanced_agent: The enhanced agent to wrap
        """
        self.enhanced_agent = enhanced_agent

        # Expose legacy interface attributes
        self.llm_service = enhanced_agent.llm_service
        self.response_model = enhanced_agent.response_model
        self.primary_model = enhanced_agent.primary_model
        self.fallback_model = enhanced_agent.fallback_model
        self.max_retries = enhanced_agent.max_retries
        self.collect_stats = enhanced_agent.collect_stats
        self.stats = enhanced_agent.stats
        self._prompts = enhanced_agent._prompts

    async def execute(
        self,
        prompt_name: str,
        prompt_args: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Execute with legacy interface compatibility.

        Args:
            prompt_name: Name of the prompt template
            prompt_args: Arguments for prompt formatting
            model: Specific model to use
            temperature: Temperature for generation
            use_fallback: Whether to use fallback models
            **kwargs: Additional arguments

        Returns:
            Structured response
        """
        return await self.enhanced_agent.execute(
            prompt_name=prompt_name,
            prompt_args=prompt_args,
            model=model,
            temperature=temperature,
            use_fallback=use_fallback,
            **kwargs,
        )

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get statistics summary with legacy interface."""
        return self.enhanced_agent.get_stats_summary()

    def _get_prompt(self, prompt_name: str) -> str:
        """Get prompt with legacy interface."""
        return self.enhanced_agent._get_prompt(prompt_name)
