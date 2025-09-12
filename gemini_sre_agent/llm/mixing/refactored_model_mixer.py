# gemini_sre_agent/llm/mixing/refactored_model_mixer.py

"""
Refactored model mixer using the new modular architecture.

This module provides a clean, modular implementation of the model mixer
that uses the separated concerns from the refactored modules.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..base import LLMResponse
from ..constants import MAX_CONCURRENT_REQUESTS, MAX_PROMPT_LENGTH
from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry
from .context_manager import ContextManager
from .mixing_strategies import (
    MixingStrategy,
    MixingStrategyFactory,
    StrategyPerformanceMonitor,
)
from .model_manager import ModelManager, TaskType
from .performance_optimizer import (
    OptimizationStrategy,
    PerformanceOptimizer,
)

logger = logging.getLogger(__name__)


@dataclass
class MixingResult:
    """Result from model mixing operation."""

    primary_result: LLMResponse
    secondary_results: List[LLMResponse] = field(default_factory=list)
    aggregated_result: Optional[str] = None
    confidence_score: float = 0.0
    execution_time_ms: float = 0.0
    total_cost: float = 0.0
    strategy_used: MixingStrategy = MixingStrategy.PARALLEL
    model_configs: List[Any] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDecomposition:
    """Decomposition of a complex task into subtasks."""

    original_task: str
    subtasks: List[str]
    dependencies: Dict[int, List[int]] = field(default_factory=dict)
    priority_order: List[int] = field(default_factory=list)
    estimated_complexity: float = 1.0


class TaskDecomposer:
    """Simple task decomposer for basic task splitting."""

    def __init__(self, model_registry: ModelRegistry) -> None:
        """Initialize the simple task decomposer."""
        self.model_registry = model_registry

    async def decompose_task(
        self, task: str, context: Dict[str, Any]
    ) -> TaskDecomposition:
        """Decompose a task using simple heuristics."""
        # Simple decomposition based on task length and keywords
        subtasks = []

        # Split by sentences for long tasks
        if len(task) > 500:
            sentences = task.split(". ")
            subtasks = [s.strip() + "." for s in sentences if s.strip()]
        else:
            subtasks = [task]

        # Add priority order (simple: first to last)
        priority_order = list(range(len(subtasks)))

        return TaskDecomposition(
            original_task=task,
            subtasks=subtasks,
            priority_order=priority_order,
            estimated_complexity=len(subtasks) / 3.0,
        )


class ResultAggregator:
    """Simple result aggregator using basic strategies."""

    async def aggregate_results(
        self,
        results: List[LLMResponse],
        configs: List[Any],
        strategy: MixingStrategy,
    ) -> tuple[str, float]:
        """Aggregate results using simple strategies."""
        if not results:
            return "", 0.0

        if strategy == MixingStrategy.VOTING:
            return self._voting_aggregation(results, configs)
        elif strategy == MixingStrategy.WEIGHTED:
            return self._weighted_aggregation(results, configs)
        elif strategy == MixingStrategy.CASCADE:
            return self._cascade_aggregation(results, configs)
        else:
            # Default: use the first result
            return results[0].content, 0.8

    def _voting_aggregation(
        self, results: List[LLMResponse], configs: List[Any]
    ) -> tuple[str, float]:
        """Aggregate results using majority voting."""
        # Simple voting: count occurrences of each response
        response_counts = {}
        for result in results:
            content = result.content.strip()
            response_counts[content] = response_counts.get(content, 0) + 1

        # Find the most common response
        if response_counts:
            most_common = max(response_counts.items(), key=lambda x: x[1])
            confidence = most_common[1] / len(results)
            return most_common[0], confidence

        return "", 0.0

    def _weighted_aggregation(
        self, results: List[LLMResponse], configs: List[Any]
    ) -> tuple[str, float]:
        """Aggregate results using weighted combination."""
        if len(results) != len(configs):
            return results[0].content if results else "", 0.5

        # Weight responses by model weight
        weighted_responses = []
        total_weight = sum(config.weight for config in configs)

        for result, config in zip(results, configs, strict=True):
            weight = config.weight / total_weight
            weighted_responses.append((result.content, weight))

        # For now, return the highest weighted response
        # In a more sophisticated implementation, this could combine responses
        best_response = max(weighted_responses, key=lambda x: x[1])
        return best_response[0], best_response[1]

    def _cascade_aggregation(
        self, results: List[LLMResponse], configs: List[Any]
    ) -> tuple[str, float]:
        """Aggregate results from cascade execution."""
        # In cascade mode, the last result is typically the final result
        if results:
            return results[-1].content, 0.9
        return "", 0.0


class RefactoredModelMixer:
    """Refactored model mixer using modular architecture."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        cost_manager: Optional[IntegratedCostManager] = None,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
    ):
        """Initialize the refactored model mixer."""
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self.cost_manager = cost_manager

        # Initialize modular components
        self.model_manager = ModelManager(
            provider_factory, model_registry, max_concurrent_requests
        )
        self.context_manager = ContextManager()
        self.performance_optimizer = PerformanceOptimizer()
        self.strategy_factory = MixingStrategyFactory()
        self.strategy_monitor = StrategyPerformanceMonitor()

        # Initialize supporting components
        self.task_decomposer = TaskDecomposer(model_registry)
        self.result_aggregator = ResultAggregator()

        # Enable optimizations by default
        self.performance_optimizer.enable_optimization(OptimizationStrategy.CACHING)
        self.performance_optimizer.enable_optimization(
            OptimizationStrategy.LOAD_BALANCING
        )

        logger.info("RefactoredModelMixer initialized with modular architecture")

    def _validate_prompt(self, prompt: str) -> str:
        """Enhanced validation with security checks."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")

        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt too long (max {MAX_PROMPT_LENGTH} characters)")

        # Add security checks
        if self._contains_injection_patterns(prompt):
            raise ValueError("Prompt contains potentially harmful patterns")

        # Sanitize and return
        return self._sanitize_prompt(prompt.strip())

    def _contains_injection_patterns(self, prompt: str) -> bool:
        """Check for common injection patterns."""
        import re

        dangerous_patterns = [
            r"<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>",
            r"javascript:",
            r"data:text/html",
            r"vbscript:",
            r"onload\s*=",
            r"onerror\s*=",
            r"onclick\s*=",
            r"<iframe\b",
            r"<object\b",
            r"<embed\b",
            r"<link\b[^>]*javascript",
            r"<meta\b[^>]*http-equiv",
        ]
        return any(
            re.search(pattern, prompt, re.IGNORECASE) for pattern in dangerous_patterns
        )

    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize prompt by removing or escaping dangerous content."""
        import re

        # Remove null bytes and control characters
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", prompt)

        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized)

        return sanitized.strip()

    async def mix_models(
        self,
        prompt: str,
        task_type: TaskType,
        strategy: MixingStrategy = MixingStrategy.PARALLEL,
        custom_configs: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> MixingResult:
        """Mix multiple models for a complex task."""
        # Input validation
        prompt = self._validate_prompt(prompt)

        start_time = time.time()

        # Get model configurations
        if custom_configs:
            model_configs = custom_configs
        else:
            model_configs = self.model_manager.get_specialized_configs(task_type)

        # Validate model configurations
        self.model_manager.validate_configs(model_configs)

        if not model_configs:
            raise ValueError(
                f"No model configurations available for task type: {task_type}"
            )

        # Apply cost-aware filtering if cost manager is available
        if self.cost_manager:
            model_configs = await self._apply_cost_aware_filtering(
                model_configs, prompt
            )

        # Check for cached response
        cached_response = await self.performance_optimizer.get_cached_response(
            prompt, {"task_type": task_type.value}, context
        )

        if cached_response:
            execution_time = (time.time() - start_time) * 1000
            return MixingResult(
                primary_result=cached_response,
                aggregated_result=cached_response.content,
                confidence_score=0.9,  # High confidence for cached results
                execution_time_ms=execution_time,
                strategy_used=strategy,
                model_configs=model_configs,
                metadata={"cached": True, "task_type": task_type.value},
            )

        # Create context for sharing between models
        context_id = f"mix_{int(time.time())}"
        self.context_manager.create_context(
            context_id,
            "mixing_task",
            {
                "prompt": prompt,
                "task_type": task_type.value,
                "strategy": strategy.value,
            },
            context or {},
        )

        # Execute models based on strategy
        strategy_executor = self.strategy_factory.create_executor(strategy)
        results = await strategy_executor.execute(
            model_configs,  # type: ignore
            prompt,
            context,
            self.provider_factory,
            self.performance_optimizer.get_semaphore(),
        )

        # Update performance metrics
        execution_time = time.time() - start_time
        for result, config in zip(results, model_configs, strict=True):
            if result:
                self.performance_optimizer.update_model_performance(
                    f"{config.provider}:{config.model}",
                    execution_time,
                    True,
                )
            else:
                self.performance_optimizer.update_model_performance(
                    f"{config.provider}:{config.model}",
                    execution_time,
                    False,
                )

        # Aggregate results (filter out None values for aggregation)
        valid_results = []
        if results:
            valid_results = [r for r in results if r is not None]
            if valid_results:
                aggregated_result, confidence = (
                    await self.result_aggregator.aggregate_results(
                        valid_results, model_configs, strategy
                    )
                )
            else:
                aggregated_result = ""
                confidence = 0.0
        else:
            aggregated_result = ""
            confidence = 0.0

        # Cache the result
        if valid_results:
            primary_result = valid_results[0]
            self.performance_optimizer.cache_response(
                prompt,
                {"task_type": task_type.value},
                primary_result,
                context,
            )

        # Calculate total cost
        total_cost = 0.0
        if self.cost_manager and model_configs:
            for result, config in zip(results, model_configs, strict=True):
                if result and result.usage:
                    cost = await self.cost_manager.estimate_request_cost(
                        config.provider,
                        config.model,
                        result.usage.get("input_tokens", 0),
                        result.usage.get("output_tokens", 0),
                    )
                    total_cost += cost

        execution_time_ms = execution_time * 1000

        # Update strategy performance
        self.strategy_monitor.record_execution(
            strategy, execution_time, len(valid_results) > 0
        )

        return MixingResult(
            primary_result=(
                results[0]
                if results and results[0] is not None
                else LLMResponse(content="", usage=None)
            ),
            secondary_results=(
                [r for r in results[1:] if r is not None] if len(results) > 1 else []
            ),
            aggregated_result=aggregated_result,
            confidence_score=confidence,
            execution_time_ms=execution_time_ms,
            total_cost=total_cost,
            strategy_used=strategy,
            model_configs=model_configs,
            metadata={
                "task_type": task_type.value,
                "models_used": len(model_configs) if model_configs else 0,
                "successful_models": len(valid_results),
                "context_id": context_id,
            },
        )

    async def _apply_cost_aware_filtering(
        self, model_configs: List[Any], prompt: str
    ) -> List[Any]:
        """Apply cost-aware filtering to model configurations."""
        if not self.cost_manager:
            return model_configs

        # Estimate costs for each configuration
        estimated_costs = []
        for config in model_configs:
            try:
                # Rough token estimation (4 chars per token)
                estimated_tokens = len(prompt) // 4 + config.max_tokens
                cost = await self.cost_manager.estimate_request_cost(
                    config.provider,
                    config.model,
                    estimated_tokens // 2,
                    estimated_tokens // 2,
                )
                estimated_costs.append((config, cost))
            except Exception as e:
                logger.warning(
                    f"Failed to estimate cost for {config.provider}:{config.model}: {e}"
                )
                estimated_costs.append((config, float("inf")))

        # Filter out configurations that exceed cost limits
        filtered_configs = []
        for config, cost in estimated_costs:
            if config.cost_limit is None or cost <= config.cost_limit:
                filtered_configs.append(config)
            else:
                logger.info(
                    f"Filtered out {config.provider}:{config.model} due to cost limit"
                )

        return filtered_configs if filtered_configs else model_configs

    async def decompose_and_mix(
        self,
        complex_task: str,
        task_type: TaskType,
        strategy: MixingStrategy = MixingStrategy.PARALLEL,
        context: Optional[Dict[str, Any]] = None,
    ) -> List[MixingResult]:
        """Decompose a complex task and mix models for each subtask."""
        # Decompose the task
        decomposition = await self.task_decomposer.decompose_task(
            complex_task, context or {}
        )

        # Mix models for each subtask
        results = []
        for i, subtask in enumerate(decomposition.subtasks):
            try:
                result = await self.mix_models(
                    subtask, task_type, strategy, context=context
                )
                result.metadata["subtask_index"] = i
                result.metadata["original_task"] = complex_task
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to process subtask {i}: {e}")
                # Create error result
                error_result = MixingResult(
                    primary_result=LLMResponse(content="", usage=None),
                    aggregated_result=f"Error processing subtask: {str(e)}",
                    confidence_score=0.0,
                    strategy_used=strategy,
                    errors=[str(e)],
                    metadata={"subtask_index": i, "original_task": complex_task},
                )
                results.append(error_result)

        return results

    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        return {
            "model_mixer": self.performance_optimizer.get_performance_summary(),
            "strategy_performance": self.strategy_monitor.get_all_metrics(),
            "model_health": self.model_manager.get_all_health_status(),
            "context_summary": self.context_manager.get_context_summary(),
        }

    def reset_metrics(self) -> None:
        """Reset all performance metrics."""
        self.performance_optimizer.reset_performance_metrics()
        self.strategy_monitor.reset_metrics()
        self.model_manager.reset_health_status()
        self.context_manager.clear_all_contexts()
        logger.info("Reset all performance metrics")
