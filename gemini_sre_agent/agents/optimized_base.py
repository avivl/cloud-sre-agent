"""
Optimized Base Agent with Performance Enhancements.

This module provides a high-performance version of the enhanced base agent
that integrates with the performance optimization system to meet the < 10ms
overhead requirement.
"""

import logging
import time
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel

from ..llm.base import ModelType, ProviderType
from ..llm.config import LLMConfig
from ..llm.optimized_service import OptimizedLLMService
from ..llm.strategy_manager import OptimizationGoal, StrategyManager
from .stats import AgentStats

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class OptimizedBaseAgent(Generic[T]):
    """
    High-performance base agent with comprehensive optimizations.
    
    Integrates performance optimization system to meet < 10ms overhead requirement
    while maintaining all functionality of the enhanced base agent.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        response_model: type[T],
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
        enable_optimizations: bool = True,
        batch_size: int = 10,
        max_wait_ms: float = 5.0,
    ):
        """
        Initialize the optimized base agent.
        
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
            enable_optimizations: Whether to enable performance optimizations
            batch_size: Batch size for concurrent operations
            max_wait_ms: Maximum wait time for batch processing
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
        self.enable_optimizations = enable_optimizations
        
        # Initialize optimized LLM service
        self.llm_service = OptimizedLLMService(
            llm_config,
            enable_optimizations=enable_optimizations,
            batch_size=batch_size,
            max_wait_ms=max_wait_ms,
        )
        
        # Initialize strategy manager (lazy loaded)
        self._strategy_manager_loader = None
        
        # Initialize stats
        self.stats = AgentStats(agent_name=self.__class__.__name__)
        
        # Cache for prompts and model selections
        self._prompts = {}
        self._model_cache = {}
        self._conversation_context = []
        
        # Performance tracking
        self._operation_times: Dict[str, List[float]] = {}
        self._total_operations = 0
        
        logger.info(f"OptimizedBaseAgent '{self.__class__.__name__}' initialized with performance optimizations")

    async def _get_strategy_manager(self) -> StrategyManager:
        """Lazy load strategy manager."""
        if self._strategy_manager_loader is None:
            # Get the enhanced service to access model scorer
            enhanced_service = await self.llm_service._enhanced_service_loader.get()
            self._strategy_manager_loader = StrategyManager(enhanced_service.model_scorer)
        
        return self._strategy_manager_loader

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
        Execute a prompt with optimized performance and intelligent model selection.
        
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
        
        try:
            # Get the prompt template (cached)
            prompt = self._get_prompt(prompt_name)
            
            # Format the prompt template with the provided arguments
            formatted_prompt = prompt.format(**prompt_args)
            
            # Generate structured response using optimized LLM service
            response = await self.llm_service.generate_structured(
                prompt=formatted_prompt,
                response_model=self.response_model,
                model=model,
                model_type=self.model_type_preference,
                provider=provider.value if provider else None,
                max_cost=self.max_cost,
                min_performance=self.min_performance,
                min_reliability=self.min_quality,
                temperature=temperature,
                **kwargs,
            )
            
            # Record success statistics
            if self.collect_stats:
                execution_time = (time.time() - start_time) * 1000
                self.stats.record_success(
                    model=model or "auto-selected",
                    latency_ms=int(execution_time),
                    prompt_name=prompt_name,
                )
            
            # Update conversation context
            self._update_conversation_context(prompt_name, prompt_args, model or "auto-selected", response)
            
            # Track performance
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("execute_success", execution_time)
            
            return response
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            
            # Record error statistics
            if self.collect_stats:
                self.stats.record_error(
                    model=model or "auto-selected",
                    error=str(e),
                    prompt_name=prompt_name,
                )
            
            # Try fallback model if available and enabled
            if use_fallback and self.fallback_model and model != self.fallback_model:
                logger.warning(f"Primary model {model} failed, trying fallback {self.fallback_model}")
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
            
            # Track error performance
            self._track_operation_time("execute_error", execution_time)
            raise

    async def batch_execute(
        self,
        requests: List[Dict[str, Any]],
        **kwargs: Any,
    ) -> List[T]:
        """
        Execute multiple prompts in batch with optimizations.
        
        Args:
            requests: List of request dictionaries with prompt_name and prompt_args
            **kwargs: Additional arguments for the LLM service
            
        Returns:
            List of structured responses
        """
        start_time = time.time()
        
        try:
            # Prepare batch requests
            batch_requests = []
            for request in requests:
                prompt_name = request["prompt_name"]
                prompt_args = request["prompt_args"]
                prompt = self._get_prompt(prompt_name)
                formatted_prompt = prompt.format(**prompt_args)
                
                batch_requests.append({
                    "prompt": formatted_prompt,
                    "options": request.get("options", {}),
                })
            
            # Use batch processing
            results = await self.llm_service.batch_generate_structured(
                requests=batch_requests,
                response_model=self.response_model,
                **kwargs,
            )
            
            # Track performance
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("batch_execute", execution_time)
            
            return results
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            self._track_operation_time("batch_execute_error", execution_time)
            logger.error(f"Error in batch_execute: {e}")
            raise

    def _get_prompt(self, prompt_name: str) -> str:
        """Get or create a prompt template by name (cached)."""
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

    def _track_operation_time(self, operation: str, execution_time_ms: float) -> None:
        """Track operation execution times for performance monitoring."""
        if operation not in self._operation_times:
            self._operation_times[operation] = []
        
        self._operation_times[operation].append(execution_time_ms)
        self._total_operations += 1
        
        # Keep only last 100 measurements to prevent memory growth
        if len(self._operation_times[operation]) > 100:
            self._operation_times[operation] = self._operation_times[operation][-100:]

    def get_conversation_context(self) -> List[Dict[str, Any]]:
        """Get the current conversation context."""
        return self._conversation_context.copy()

    def clear_conversation_context(self) -> None:
        """Clear the conversation context."""
        self._conversation_context.clear()

    async def get_available_models(self) -> List[str]:
        """Get list of available models from the registry (cached)."""
        return await self.llm_service.get_available_models(
            model_type=self.model_type_preference,
        )

    async def get_available_providers(self) -> List[ProviderType]:
        """Get list of available providers."""
        # This would need to be implemented in the optimized service
        return [ProviderType.GEMINI, ProviderType.OPENAI, ProviderType.CLAUDE]

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

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get comprehensive performance statistics."""
        base_stats = self.stats.get_summary()
        llm_stats = self.llm_service.get_performance_stats()
        
        # Calculate operation time statistics
        operation_stats = {}
        for operation, times in self._operation_times.items():
            if times:
                operation_stats[operation] = {
                    "count": len(times),
                    "avg_ms": round(sum(times) / len(times), 2),
                    "min_ms": round(min(times), 2),
                    "max_ms": round(max(times), 2),
                    "p95_ms": round(sorted(times)[int(len(times) * 0.95)], 2) if len(times) > 1 else times[0],
                }
        
        return {
            "agent_stats": base_stats,
            "llm_service_stats": llm_stats,
            "operation_times": operation_stats,
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
            "optimizations_enabled": self.enable_optimizations,
        }

    async def warmup(self) -> None:
        """Warm up the agent by pre-initializing components."""
        await self.llm_service.warmup()
        logger.info(f"OptimizedBaseAgent '{self.__class__.__name__}' warmup completed")

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check with performance metrics."""
        llm_health = await self.llm_service.health_check()
        
        return {
            "agent_name": self.__class__.__name__,
            "status": "healthy" if llm_health["status"] == "healthy" else "unhealthy",
            "llm_service": llm_health,
            "performance_stats": self.get_performance_stats(),
        }
