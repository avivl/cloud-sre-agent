# gemini_sre_agent/llm/mixing/mixing_strategies.py

"""
Mixing strategies module for the model mixer system.

This module provides different strategies for mixing multiple LLM models,
including parallel execution, sequential execution, cascade execution,
voting, weighted aggregation, and hierarchical approaches.
"""

from abc import ABC, abstractmethod
import asyncio
from dataclasses import dataclass
from enum import Enum
import logging
from typing import Any

from ..base import LLMRequest, LLMResponse, ModelType

logger = logging.getLogger(__name__)


class MixingStrategy(Enum):
    """Strategies for model mixing."""

    PARALLEL = "parallel"  # Execute all models simultaneously
    SEQUENTIAL = "sequential"  # Execute models one after another
    CASCADE = "cascade"  # Use results from one model as input to next
    VOTING = "voting"  # Use majority vote from multiple models
    WEIGHTED = "weighted"  # Weight results based on model confidence
    HIERARCHICAL = "hierarchical"  # Use different models for different aspects


@dataclass
class ModelConfig:
    """Configuration for a model in the mixing process."""

    provider: str
    model: str
    model_type: ModelType
    weight: float = 1.0
    max_tokens: int = 4000
    temperature: float = 0.7
    timeout: int = 30
    retry_attempts: int = 2
    specialized_for: str | None = None
    cost_limit: float | None = None


class MixingStrategyExecutor(ABC):
    """Abstract base class for mixing strategy executors."""

    @abstractmethod
    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """
        Execute models using the specific strategy.

        Args:
            model_configs: List of model configurations
            prompt: Input prompt
            context: Optional context information
            provider_factory: Factory for creating providers
            semaphore: Semaphore for limiting concurrent requests

        Returns:
            List of responses (may contain None for failed models)
        """
        pass


class ParallelStrategyExecutor(MixingStrategyExecutor):
    """Executor for parallel model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models in parallel."""
        tasks = []
        for config in model_configs:
            task = self._execute_single_model(
                config, prompt, context, provider_factory, semaphore
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Preserve alignment between results and model_configs
        aligned_results: list[LLMResponse | None] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Model {model_configs[i].provider}:{model_configs[i].model} failed: {result}"
                )
                aligned_results.append(None)
            else:
                aligned_results.append(result)  # type: ignore

        return aligned_results

    async def _execute_single_model(
        self,
        config: ModelConfig,
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> LLMResponse:
        """Execute a single model with the given configuration."""
        async with semaphore:  # Limit concurrent requests
            provider = provider_factory.get_provider(config.provider)
            if not provider:
                raise ValueError(f"Provider {config.provider} not available")

            request = LLMRequest(
                prompt=prompt,
                model_type=config.model_type,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            # Execute with timeout
            try:
                response = await asyncio.wait_for(
                    provider.generate(request), timeout=config.timeout
                )
                return response
            except TimeoutError as e:
                raise TimeoutError(
                    f"Model {config.provider}:{config.model} timed out after {config.timeout}s"
                ) from e


class SequentialStrategyExecutor(MixingStrategyExecutor):
    """Executor for sequential model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models sequentially."""
        results = []
        for config in model_configs:
            try:
                result = await self._execute_single_model(
                    config, prompt, context, provider_factory, semaphore
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Model {config.provider}:{config.model} failed: {e}")
                results.append(None)

        return results

    async def _execute_single_model(
        self,
        config: ModelConfig,
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> LLMResponse:
        """Execute a single model with the given configuration."""
        async with semaphore:  # Limit concurrent requests
            provider = provider_factory.get_provider(config.provider)
            if not provider:
                raise ValueError(f"Provider {config.provider} not available")

            request = LLMRequest(
                prompt=prompt,
                model_type=config.model_type,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            # Execute with timeout
            try:
                response = await asyncio.wait_for(
                    provider.generate(request), timeout=config.timeout
                )
                return response
            except TimeoutError as e:
                raise TimeoutError(
                    f"Model {config.provider}:{config.model} timed out after {config.timeout}s"
                ) from e


class CascadeStrategyExecutor(MixingStrategyExecutor):
    """Executor for cascade model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models in cascade (results feed into next model)."""
        results = []
        current_prompt = prompt

        for config in model_configs:
            try:
                result = await self._execute_single_model(
                    config, current_prompt, context, provider_factory, semaphore
                )
                results.append(result)

                # Use result as input for next model (with some context)
                if result and result.content:
                    current_prompt = (
                        f"Previous result: {result.content}\n\nOriginal task: {prompt}"
                    )
            except Exception as e:
                logger.error(f"Model {config.provider}:{config.model} failed: {e}")
                results.append(None)
                break  # Stop cascade on failure

        return results

    async def _execute_single_model(
        self,
        config: ModelConfig,
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> LLMResponse:
        """Execute a single model with the given configuration."""
        async with semaphore:  # Limit concurrent requests
            provider = provider_factory.get_provider(config.provider)
            if not provider:
                raise ValueError(f"Provider {config.provider} not available")

            request = LLMRequest(
                prompt=prompt,
                model_type=config.model_type,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            # Execute with timeout
            try:
                response = await asyncio.wait_for(
                    provider.generate(request), timeout=config.timeout
                )
                return response
            except TimeoutError as e:
                raise TimeoutError(
                    f"Model {config.provider}:{config.model} timed out after {config.timeout}s"
                ) from e


class VotingStrategyExecutor(MixingStrategyExecutor):
    """Executor for voting model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models in parallel and use voting for aggregation."""
        # Use parallel execution for voting
        parallel_executor = ParallelStrategyExecutor()
        return await parallel_executor.execute(
            model_configs, prompt, context, provider_factory, semaphore
        )


class WeightedStrategyExecutor(MixingStrategyExecutor):
    """Executor for weighted model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models in parallel and use weighted aggregation."""
        # Use parallel execution for weighted strategy
        parallel_executor = ParallelStrategyExecutor()
        return await parallel_executor.execute(
            model_configs, prompt, context, provider_factory, semaphore
        )


class HierarchicalStrategyExecutor(MixingStrategyExecutor):
    """Executor for hierarchical model mixing strategy."""

    async def execute(
        self,
        model_configs: list[ModelConfig],
        prompt: str,
        context: dict[str, Any] | None,
        provider_factory: Any,
        semaphore: asyncio.Semaphore,
    ) -> list[LLMResponse | None]:
        """Execute models hierarchically based on their specialization."""
        # Group models by specialization
        specialized_groups = self._group_by_specialization(model_configs)

        results = []
        for specialization, configs in specialized_groups.items():
            if specialization:
                # Execute specialized models in parallel
                parallel_executor = ParallelStrategyExecutor()
                group_results = await parallel_executor.execute(
                    configs, prompt, context, provider_factory, semaphore
                )
                results.extend(group_results)
            else:
                # Execute general models sequentially
                sequential_executor = SequentialStrategyExecutor()
                group_results = await sequential_executor.execute(
                    configs, prompt, context, provider_factory, semaphore
                )
                results.extend(group_results)

        return results

    def _group_by_specialization(
        self, model_configs: list[ModelConfig]
    ) -> dict[str | None, list[ModelConfig]]:
        """Group model configurations by their specialization."""
        groups: dict[str | None, list[ModelConfig]] = {}

        for config in model_configs:
            specialization = config.specialized_for
            if specialization not in groups:
                groups[specialization] = []
            groups[specialization].append(config)

        return groups


class MixingStrategyFactory:
    """Factory for creating mixing strategy executors."""

    _executors = {
        MixingStrategy.PARALLEL: ParallelStrategyExecutor,
        MixingStrategy.SEQUENTIAL: SequentialStrategyExecutor,
        MixingStrategy.CASCADE: CascadeStrategyExecutor,
        MixingStrategy.VOTING: VotingStrategyExecutor,
        MixingStrategy.WEIGHTED: WeightedStrategyExecutor,
        MixingStrategy.HIERARCHICAL: HierarchicalStrategyExecutor,
    }

    @classmethod
    def create_executor(cls, strategy: MixingStrategy) -> MixingStrategyExecutor:
        """
        Create a strategy executor for the given strategy.

        Args:
            strategy: The mixing strategy to create an executor for

        Returns:
            Strategy executor instance

        Raises:
            ValueError: If the strategy is not supported
        """
        if strategy not in cls._executors:
            raise ValueError(f"Unsupported mixing strategy: {strategy}")

        executor_class = cls._executors[strategy]
        return executor_class()

    @classmethod
    def get_supported_strategies(cls) -> list[MixingStrategy]:
        """
        Get list of supported mixing strategies.

        Returns:
            List of supported strategies
        """
        return list(cls._executors.keys())


class StrategyPerformanceMonitor:
    """Monitor performance of different mixing strategies."""

    def __init__(self) -> None:
        """Initialize the performance monitor."""
        self.strategy_metrics: dict[MixingStrategy, dict[str, Any]] = {}
        self.reset_metrics()

    def reset_metrics(self) -> None:
        """Reset all strategy metrics."""
        for strategy in MixingStrategy:
            self.strategy_metrics[strategy] = {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "total_execution_time": 0.0,
                "average_execution_time": 0.0,
                "success_rate": 0.0,
            }

    def record_execution(
        self,
        strategy: MixingStrategy,
        execution_time: float,
        success: bool,
    ) -> None:
        """
        Record execution metrics for a strategy.

        Args:
            strategy: The strategy that was executed
            execution_time: Time taken for execution in seconds
            success: Whether the execution was successful
        """
        metrics = self.strategy_metrics[strategy]
        metrics["total_executions"] += 1
        metrics["total_execution_time"] += execution_time

        if success:
            metrics["successful_executions"] += 1
        else:
            metrics["failed_executions"] += 1

        # Update derived metrics
        metrics["average_execution_time"] = (
            metrics["total_execution_time"] / metrics["total_executions"]
        )
        metrics["success_rate"] = (
            metrics["successful_executions"] / metrics["total_executions"] * 100
        )

    def get_strategy_metrics(self, strategy: MixingStrategy) -> dict[str, Any]:
        """
        Get metrics for a specific strategy.

        Args:
            strategy: The strategy to get metrics for

        Returns:
            Dictionary containing strategy metrics
        """
        return self.strategy_metrics[strategy].copy()

    def get_all_metrics(self) -> dict[MixingStrategy, dict[str, Any]]:
        """
        Get metrics for all strategies.

        Returns:
            Dictionary containing metrics for all strategies
        """
        return {
            strategy: metrics.copy()
            for strategy, metrics in self.strategy_metrics.items()
        }

    def get_best_strategy(self) -> MixingStrategy | None:
        """
        Get the best performing strategy based on success rate and execution time.

        Returns:
            Best performing strategy or None if no data available
        """
        if not any(
            metrics["total_executions"] > 0
            for metrics in self.strategy_metrics.values()
        ):
            return None

        # Score strategies based on success rate and inverse execution time
        scored_strategies = []
        for strategy, metrics in self.strategy_metrics.items():
            if metrics["total_executions"] > 0:
                # Higher success rate is better, lower execution time is better
                score = (
                    metrics["success_rate"] * 0.7
                    + (100 - metrics["average_execution_time"] * 10) * 0.3
                )
                scored_strategies.append((strategy, score))

        if not scored_strategies:
            return None

        # Return strategy with highest score
        return max(scored_strategies, key=lambda x: x[1])[0]
