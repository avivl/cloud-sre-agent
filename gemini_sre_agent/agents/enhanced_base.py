"""
Enhanced Base Agent with Multi-Provider Support.

This module provides an enhanced BaseAgent class that supports multi-provider
model mixing, intelligent model selection, and advanced configuration options
while maintaining backward compatibility with the existing agent system.
"""

import logging
import time
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from pydantic import BaseModel

from ..llm.base import ModelType, ProviderType
from ..llm.config import LLMConfig
from ..llm.enhanced_service import EnhancedLLMService
from ..llm.model_selector import SelectionStrategy
from ..llm.strategy_manager import (
    OptimizationGoal,
    StrategyContext,
    StrategyManager,
    StrategyResult,
)
from .stats import AgentStats

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class EnhancedBaseAgent(Generic[T]):
    """
    Enhanced base class for all agents with multi-provider support.
    
    Provides intelligent model selection, provider mixing, and advanced
    configuration options while maintaining backward compatibility.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        response_model: Type[T],
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.HYBRID,
        max_retries: int = 2,
        collect_stats: bool = True,
        provider_preference: Optional[List[ProviderType]] = None,
        model_type_preference: Optional[ModelType] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_quality: Optional[float] = None,
        business_hours_only: bool = False,
        custom_weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize the enhanced base agent.
        
        Args:
            llm_config: LLM configuration for multi-provider support
            response_model: Pydantic model for structured responses
            primary_model: Primary model to use (overrides intelligent selection)
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection optimization
            max_retries: Maximum number of retry attempts
            collect_stats: Whether to collect performance statistics
            provider_preference: Preferred providers in order of preference
            model_type_preference: Preferred model type (fast, smart, etc.)
            max_cost: Maximum cost per 1k tokens
            min_performance: Minimum performance score required
            min_quality: Minimum quality score required
            business_hours_only: Whether to only use models during business hours
            custom_weights: Custom scoring weights for model selection
        """
        self.llm_config = llm_config
        self.response_model = response_model
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.optimization_goal = optimization_goal
        self.max_retries = max_retries
        self.collect_stats = collect_stats
        self.provider_preference = provider_preference
        self.model_type_preference = model_type_preference
        self.max_cost = max_cost
        self.min_performance = min_performance
        self.min_quality = min_quality
        self.business_hours_only = business_hours_only
        self.custom_weights = custom_weights
        
        # Initialize enhanced LLM service
        self.llm_service = EnhancedLLMService(llm_config)
        
        # Initialize strategy manager
        self.strategy_manager = StrategyManager(self.llm_service.model_scorer)
        
        # Initialize stats
        self.stats = AgentStats(agent_name=self.__class__.__name__)
        
        # Cache for prompts and model selections
        self._prompts = {}
        self._model_cache = {}
        self._conversation_context = []
        
        logger.info(f"EnhancedBaseAgent '{self.__class__.__name__}' initialized with multi-provider support")

    async def execute(
        self,
        prompt_name: str,
        prompt_args: Dict[str, Any],
        model: Optional[str] = None,
        provider: Optional[ProviderType] = None,
        optimization_goal: Optional[OptimizationGoal] = None,
        temperature: float = 0.7,
        use_fallback: bool = True,
        force_model_selection: bool = False,
        **kwargs: Any,
    ) -> T:
        """
        Execute a prompt with intelligent model selection and multi-provider support.
        
        Args:
            prompt_name: Name of the prompt template
            prompt_args: Arguments for prompt formatting
            model: Specific model to use (overrides intelligent selection)
            provider: Specific provider to use
            optimization_goal: Override the default optimization goal
            temperature: Temperature for generation
            use_fallback: Whether to use fallback models on failure
            force_model_selection: Force re-selection even if cached
            **kwargs: Additional arguments for the LLM service
            
        Returns:
            Structured response of type T
        """
        start_time = time.time()
        
        # Determine the model to use
        selected_model = await self._select_model(
            model=model,
            provider=provider,
            optimization_goal=optimization_goal,
            force_selection=force_model_selection,
        )
        
        # Get the prompt template
        prompt = self._get_prompt(prompt_name)
        
        try:
            # Format the prompt template with the provided arguments
            formatted_prompt = prompt.format(**prompt_args)
            
            # Generate structured response using enhanced LLM service
            response = await self.llm_service.generate_structured(
                prompt=formatted_prompt,
                response_model=self.response_model,
                model=selected_model,
                model_type=self.model_type_preference,
                provider=provider.value if provider else None,
                selection_strategy=SelectionStrategy(self._convert_optimization_goal(optimization_goal or self.optimization_goal)),
                max_cost=self.max_cost,
                min_performance=self.min_performance,
                min_reliability=self.min_quality,
                temperature=temperature,
                **kwargs,
            )
            
            # Record success statistics
            if self.collect_stats:
                self.stats.record_success(
                    model=selected_model,
                    latency_ms=int((time.time() - start_time) * 1000),
                    prompt_name=prompt_name,
                )
            
            # Update conversation context
            self._update_conversation_context(prompt_name, prompt_args, selected_model, response)
            
            return response
            
        except Exception as e:
            # Record error statistics
            if self.collect_stats:
                self.stats.record_error(
                    model=selected_model,
                    error=str(e),
                    prompt_name=prompt_name,
                )
            
            # Try fallback model if available and enabled
            if use_fallback and self.fallback_model and selected_model != self.fallback_model:
                logger.warning(f"Primary model {selected_model} failed, trying fallback {self.fallback_model}")
                return await self.execute(
                    prompt_name=prompt_name,
                    prompt_args=prompt_args,
                    model=self.fallback_model,
                    provider=provider,
                    optimization_goal=optimization_goal,
                    temperature=temperature,
                    use_fallback=False,  # Prevent cascading fallbacks
                    force_model_selection=True,
                    **kwargs,
                )
            
            # Try different provider if available
            if use_fallback and provider and len(self.provider_preference or []) > 1:
                alternative_providers = [p for p in (self.provider_preference or []) if p != provider]
                if alternative_providers:
                    logger.warning(f"Provider {provider} failed, trying alternative provider {alternative_providers[0]}")
                    return await self.execute(
                        prompt_name=prompt_name,
                        prompt_args=prompt_args,
                        model=model,
                        provider=alternative_providers[0],
                        optimization_goal=optimization_goal,
                        temperature=temperature,
                        use_fallback=False,  # Prevent cascading fallbacks
                        force_model_selection=True,
                        **kwargs,
                    )
            
            raise

    async def _select_model(
        self,
        model: Optional[str] = None,
        provider: Optional[ProviderType] = None,
        optimization_goal: Optional[OptimizationGoal] = None,
        force_selection: bool = False,
    ) -> str:
        """
        Select the best model based on current strategy and constraints.
        
        Args:
            model: Specific model to use (overrides selection)
            provider: Specific provider to use
            optimization_goal: Override the default optimization goal
            force_selection: Force re-selection even if cached
            
        Returns:
            Selected model name
        """
        # Use specific model if provided
        if model:
            return model
        
        # Use primary model if set and no force selection
        if self.primary_model and not force_selection:
            return self.primary_model
        
        # Create cache key for model selection
        cache_key = f"{optimization_goal or self.optimization_goal}_{provider}_{self.model_type_preference}_{self.max_cost}_{self.min_performance}"
        
        # Return cached selection if available and not forcing
        if not force_selection and cache_key in self._model_cache:
            return self._model_cache[cache_key]
        
        try:
            # Get available models from registry
            available_models = self.llm_service.model_registry.get_all_models()
            
            # Create strategy context
            strategy_context = StrategyContext(
                task_type=self.model_type_preference,
                max_cost=self.max_cost,
                min_performance=self.min_performance,
                min_quality=self.min_quality,
                business_hours_only=self.business_hours_only,
                provider_preference=self.provider_preference,
            )
            
            # Select model using strategy manager
            result: StrategyResult = self.strategy_manager.select_model(
                candidates=available_models,
                goal=optimization_goal or self.optimization_goal,
                context=strategy_context,
            )
            
            selected_model = result.selected_model.name
            
            # Cache the selection
            self._model_cache[cache_key] = selected_model
            
            logger.debug(f"Selected model '{selected_model}' using {result.strategy_used} strategy: {result.reasoning}")
            
            return selected_model
            
        except Exception as e:
            logger.warning(f"Model selection failed: {e}, falling back to primary model")
            return self.primary_model or "smart"

    def _convert_optimization_goal(self, goal: OptimizationGoal) -> str:
        """Convert OptimizationGoal to SelectionStrategy string."""
        goal_mapping = {
            OptimizationGoal.COST: "cheapest",
            OptimizationGoal.PERFORMANCE: "fastest", 
            OptimizationGoal.QUALITY: "best_score",
            OptimizationGoal.TIME_BASED: "balanced",
            OptimizationGoal.HYBRID: "balanced",
        }
        return goal_mapping.get(goal, "best_score")

    def _get_prompt(self, prompt_name: str) -> str:
        """Get or create a prompt template by name."""
        if prompt_name not in self._prompts:
            # For now, use simple templates
            # TODO: Integrate with Mirascope for advanced prompt management
            self._prompts[prompt_name] = self._create_default_prompt(prompt_name)
        
        return self._prompts[prompt_name]

    def _create_default_prompt(self, prompt_name: str) -> str:
        """Create a default prompt template for the given name."""
        # Simple default templates - these would be replaced with Mirascope integration
        default_prompts = {
            "generate_text": "Generate text based on the following input: {input}",
            "analyze": "Analyze the following content: {content}\nCriteria: {criteria}",
            "generate_code": "Generate {language} code for: {description}",
            "triage": "Triage the following issue: {issue}",
            "remediate": "Provide remediation for: {problem}",
        }
        
        return default_prompts.get(prompt_name, "Please process the following: {input}")

    def _update_conversation_context(
        self,
        prompt_name: str,
        prompt_args: Dict[str, Any],
        model: str,
        response: T,
    ) -> None:
        """Update the conversation context for multi-turn conversations."""
        context_entry = {
            "timestamp": time.time(),
            "prompt_name": prompt_name,
            "prompt_args": prompt_args,
            "model": model,
            "response_type": type(response).__name__,
        }
        
        self._conversation_context.append(context_entry)
        
        # Keep only the last 10 entries to prevent memory bloat
        if len(self._conversation_context) > 10:
            self._conversation_context = self._conversation_context[-10:]

    def get_conversation_context(self) -> List[Dict[str, Any]]:
        """Get the current conversation context."""
        return self._conversation_context.copy()

    def clear_conversation_context(self) -> None:
        """Clear the conversation context."""
        self._conversation_context.clear()

    def get_model_selection_stats(self) -> Dict[str, Any]:
        """Get statistics about model selection performance."""
        return self.strategy_manager.get_all_performance_metrics()

    def get_available_models(self) -> List[str]:
        """Get list of available models from the registry."""
        models = self.llm_service.model_registry.get_all_models()
        return [model.name for model in models]

    def get_available_providers(self) -> List[ProviderType]:
        """Get list of available providers."""
        return [ProviderType(key) for key in self.llm_service.providers.keys()]

    def update_optimization_goal(self, goal: OptimizationGoal) -> None:
        """Update the default optimization goal for model selection."""
        self.optimization_goal = goal
        logger.info(f"Updated optimization goal to {goal}")

    def update_provider_preference(self, providers: List[ProviderType]) -> None:
        """Update the provider preference list."""
        self.provider_preference = providers
        # Clear model cache to force re-selection with new preferences
        self._model_cache.clear()
        logger.info(f"Updated provider preference to {providers}")

    def update_cost_constraints(
        self,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = None,
        min_quality: Optional[float] = None,
    ) -> None:
        """Update cost and quality constraints."""
        self.max_cost = max_cost
        self.min_performance = min_performance
        self.min_quality = min_quality
        # Clear model cache to force re-selection with new constraints
        self._model_cache.clear()
        logger.info(f"Updated constraints: max_cost={max_cost}, min_performance={min_performance}, min_quality={min_quality}")

    def get_stats_summary(self) -> Dict[str, Any]:
        """Get comprehensive statistics summary."""
        base_stats = self.stats.get_summary()
        model_stats = self.get_model_selection_stats()
        
        return {
            "agent_stats": base_stats,
            "model_selection_stats": model_stats,
            "conversation_length": len(self._conversation_context),
            "cached_models": len(self._model_cache),
            "optimization_goal": self.optimization_goal.value,
            "provider_preference": [p.value for p in (self.provider_preference or [])],
            "constraints": {
                "max_cost": self.max_cost,
                "min_performance": self.min_performance,
                "min_quality": self.min_quality,
                "business_hours_only": self.business_hours_only,
            },
        }
