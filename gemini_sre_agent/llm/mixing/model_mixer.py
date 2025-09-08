"""
Advanced Model Mixing System.

This module provides sophisticated model mixing capabilities for complex tasks,
including task decomposition, parallel execution, result aggregation, and
context sharing between multiple models.
"""

import asyncio
import logging
import re
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from ..base import LLMRequest, LLMResponse, ModelType
from ..constants import (
    MAX_CONCURRENT_REQUESTS,
    MAX_MODEL_CONFIGS,
    MAX_PROMPT_LENGTH,
)
from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry

logger = logging.getLogger(__name__)


class MixingStrategy(Enum):
    """Strategies for model mixing."""

    PARALLEL = "parallel"  # Execute all models simultaneously
    SEQUENTIAL = "sequential"  # Execute models one after another
    CASCADE = "cascade"  # Use results from one model as input to next
    VOTING = "voting"  # Use majority vote from multiple models
    WEIGHTED = "weighted"  # Weight results based on model confidence
    HIERARCHICAL = "hierarchical"  # Use different models for different aspects


class TaskType(Enum):
    """Types of tasks for specialized mixing."""

    CODE_GENERATION = "code_generation"
    ANALYSIS = "analysis"
    CREATIVE_WRITING = "creative_writing"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    QUESTION_ANSWERING = "question_answering"
    PROBLEM_SOLVING = "problem_solving"
    DATA_PROCESSING = "data_processing"


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
    specialized_for: Optional[TaskType] = None
    cost_limit: Optional[float] = None


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
    model_configs: List[ModelConfig] = field(default_factory=list)
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


class TaskDecomposer(ABC):
    """Abstract base class for task decomposition strategies."""

    @abstractmethod
    async def decompose_task(
        self, task: str, context: Dict[str, Any]
    ) -> TaskDecomposition:
        """Decompose a complex task into subtasks."""
        pass


class SimpleTaskDecomposer(TaskDecomposer):
    """Simple task decomposer for basic task splitting."""

    def __init__(self, model_registry: ModelRegistry):
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


class ResultAggregator(ABC):
    """Abstract base class for result aggregation strategies."""

    @abstractmethod
    async def aggregate_results(
        self,
        results: List[LLMResponse],
        configs: List[ModelConfig],
        strategy: MixingStrategy,
    ) -> Tuple[str, float]:
        """Aggregate multiple model results into a single result."""
        pass


class SimpleResultAggregator(ResultAggregator):
    """Simple result aggregator using basic strategies."""

    async def aggregate_results(
        self,
        results: List[LLMResponse],
        configs: List[ModelConfig],
        strategy: MixingStrategy,
    ) -> Tuple[str, float]:
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
        self, results: List[LLMResponse], configs: List[ModelConfig]
    ) -> Tuple[str, float]:
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
        self, results: List[LLMResponse], configs: List[ModelConfig]
    ) -> Tuple[str, float]:
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
        self, results: List[LLMResponse], configs: List[ModelConfig]
    ) -> Tuple[str, float]:
        """Aggregate results from cascade execution."""
        # In cascade mode, the last result is typically the final result
        if results:
            return results[-1].content, 0.9
        return "", 0.0


class ModelMixer:
    """Advanced model mixer for complex task processing."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        cost_manager: Optional[IntegratedCostManager] = None,
        max_concurrent_requests: int = MAX_CONCURRENT_REQUESTS,
    ):
        """Initialize the model mixer."""
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self.cost_manager = cost_manager
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Initialize components
        self.task_decomposer = SimpleTaskDecomposer(model_registry)
        self.result_aggregator = SimpleResultAggregator()

        # Specialized mixers for different task types
        self.specialized_mixers = {
            TaskType.CODE_GENERATION: self._create_code_generation_mixer(),
            TaskType.ANALYSIS: self._create_analysis_mixer(),
            TaskType.CREATIVE_WRITING: self._create_creative_writing_mixer(),
            TaskType.TRANSLATION: self._create_translation_mixer(),
            TaskType.SUMMARIZATION: self._create_summarization_mixer(),
            TaskType.QUESTION_ANSWERING: self._create_qa_mixer(),
            TaskType.PROBLEM_SOLVING: self._create_problem_solving_mixer(),
            TaskType.DATA_PROCESSING: self._create_data_processing_mixer(),
        }

        logger.info("ModelMixer initialized with specialized mixers")

    def _create_code_generation_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for code generation tasks."""
        return [
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.CODE,
                weight=0.4,
                specialized_for=TaskType.CODE_GENERATION,
            ),
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.CODE,
                weight=0.3,
                specialized_for=TaskType.CODE_GENERATION,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.CODE,
                weight=0.3,
                specialized_for=TaskType.CODE_GENERATION,
            ),
        ]

    def _create_analysis_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for analysis tasks."""
        return [
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.ANALYSIS,
                weight=0.4,
                specialized_for=TaskType.ANALYSIS,
            ),
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.ANALYSIS,
                weight=0.4,
                specialized_for=TaskType.ANALYSIS,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.ANALYSIS,
                weight=0.2,
                specialized_for=TaskType.ANALYSIS,
            ),
        ]

    def _create_creative_writing_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for creative writing tasks."""
        return [
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.SMART,
                weight=0.5,
                temperature=0.8,
                specialized_for=TaskType.CREATIVE_WRITING,
            ),
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.SMART,
                weight=0.3,
                temperature=0.8,
                specialized_for=TaskType.CREATIVE_WRITING,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.SMART,
                weight=0.2,
                temperature=0.8,
                specialized_for=TaskType.CREATIVE_WRITING,
            ),
        ]

    def _create_translation_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for translation tasks."""
        return [
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.SMART,
                weight=0.4,
                specialized_for=TaskType.TRANSLATION,
            ),
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.SMART,
                weight=0.3,
                specialized_for=TaskType.TRANSLATION,
            ),
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.SMART,
                weight=0.3,
                specialized_for=TaskType.TRANSLATION,
            ),
        ]

    def _create_summarization_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for summarization tasks."""
        return [
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.SMART,
                weight=0.4,
                specialized_for=TaskType.SUMMARIZATION,
            ),
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.SMART,
                weight=0.4,
                specialized_for=TaskType.SUMMARIZATION,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-flash",
                model_type=ModelType.FAST,
                weight=0.2,
                specialized_for=TaskType.SUMMARIZATION,
            ),
        ]

    def _create_qa_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for question answering tasks."""
        return [
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.SMART,
                weight=0.4,
                specialized_for=TaskType.QUESTION_ANSWERING,
            ),
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.SMART,
                weight=0.4,
                specialized_for=TaskType.QUESTION_ANSWERING,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.SMART,
                weight=0.2,
                specialized_for=TaskType.QUESTION_ANSWERING,
            ),
        ]

    def _create_problem_solving_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for problem solving tasks."""
        return [
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.DEEP_THINKING,
                weight=0.4,
                specialized_for=TaskType.PROBLEM_SOLVING,
            ),
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.DEEP_THINKING,
                weight=0.3,
                specialized_for=TaskType.PROBLEM_SOLVING,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.DEEP_THINKING,
                weight=0.3,
                specialized_for=TaskType.PROBLEM_SOLVING,
            ),
        ]

    def _create_data_processing_mixer(self) -> List[ModelConfig]:
        """Create specialized mixer for data processing tasks."""
        return [
            ModelConfig(
                provider="openai",
                model="gpt-4o",
                model_type=ModelType.ANALYSIS,
                weight=0.4,
                specialized_for=TaskType.DATA_PROCESSING,
            ),
            ModelConfig(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                model_type=ModelType.ANALYSIS,
                weight=0.3,
                specialized_for=TaskType.DATA_PROCESSING,
            ),
            ModelConfig(
                provider="google",
                model="gemini-1.5-pro",
                model_type=ModelType.ANALYSIS,
                weight=0.3,
                specialized_for=TaskType.DATA_PROCESSING,
            ),
        ]

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
        # Remove null bytes and control characters
        sanitized = re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]", "", prompt)

        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized)

        return sanitized.strip()

    def _validate_model_configs(self, model_configs: List[ModelConfig]) -> None:
        """Validate model configuration list."""
        if not model_configs:
            raise ValueError("At least one model configuration is required")

        if len(model_configs) > MAX_MODEL_CONFIGS:
            raise ValueError(f"Too many model configurations (max {MAX_MODEL_CONFIGS})")

    async def mix_models(
        self,
        prompt: str,
        task_type: TaskType,
        strategy: MixingStrategy = MixingStrategy.PARALLEL,
        custom_configs: Optional[List[ModelConfig]] = None,
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
            model_configs = self.specialized_mixers.get(task_type, [])

        # Validate model configurations
        self._validate_model_configs(model_configs)

        if not model_configs:
            raise ValueError(
                f"No model configurations available for task type: {task_type}"
            )

        # Apply cost-aware filtering if cost manager is available
        if self.cost_manager:
            model_configs = await self._apply_cost_aware_filtering(
                model_configs, prompt
            )

        # Execute models based on strategy
        if strategy == MixingStrategy.PARALLEL:
            results = await self._execute_parallel(model_configs, prompt, context)
        elif strategy == MixingStrategy.SEQUENTIAL:
            results = await self._execute_sequential(model_configs, prompt, context)
        elif strategy == MixingStrategy.CASCADE:
            results = await self._execute_cascade(model_configs, prompt, context)
        else:
            results = await self._execute_parallel(model_configs, prompt, context)

        # Aggregate results (filter out None values for aggregation)
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

        execution_time = (time.time() - start_time) * 1000

        return MixingResult(
            primary_result=(
                results[0]
                if results and results[0] is not None
                else LLMResponse(content="", usage=None)
            ),
            secondary_results=(
                [r for r in results[1:] if r is not None] if len(results) > 1 else []
            ),
            aggregated_result=(
                aggregated_result
                if isinstance(aggregated_result, str)
                else (aggregated_result.content if aggregated_result else "")
            ),
            confidence_score=confidence,
            execution_time_ms=execution_time,
            total_cost=total_cost,
            strategy_used=strategy,
            model_configs=model_configs if model_configs is not None else [],
            metadata={
                "task_type": task_type.value,
                "models_used": len(model_configs) if model_configs else 0,
                "successful_models": len([r for r in results if r is not None]),
            },
        )

    async def _apply_cost_aware_filtering(
        self, model_configs: List[ModelConfig], prompt: str
    ) -> List[ModelConfig]:
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

    async def _execute_parallel(
        self,
        model_configs: List[ModelConfig],
        prompt: str,
        context: Optional[Dict[str, Any]],
    ) -> List[Optional[LLMResponse]]:
        """Execute models in parallel."""
        tasks = []
        for config in model_configs:
            task = self._execute_single_model(config, prompt, context)
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Preserve alignment between results and model_configs
        aligned_results: List[Optional[LLMResponse]] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(
                    f"Model {model_configs[i].provider}:{model_configs[i].model} failed: {result}"
                )
                aligned_results.append(None)
            else:
                aligned_results.append(result)  # type: ignore

        return aligned_results

    async def _execute_sequential(
        self,
        model_configs: List[ModelConfig],
        prompt: str,
        context: Optional[Dict[str, Any]],
    ) -> List[Optional[LLMResponse]]:
        """Execute models sequentially."""
        results = []
        for config in model_configs:
            try:
                result = await self._execute_single_model(config, prompt, context)
                results.append(result)
            except Exception as e:
                logger.error(f"Model {config.provider}:{config.model} failed: {e}")
                results.append(None)

        return results

    async def _execute_cascade(
        self,
        model_configs: List[ModelConfig],
        prompt: str,
        context: Optional[Dict[str, Any]],
    ) -> List[Optional[LLMResponse]]:
        """Execute models in cascade (results feed into next model)."""
        results = []
        current_prompt = prompt

        for config in model_configs:
            try:
                result = await self._execute_single_model(
                    config, current_prompt, context
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
        self, config: ModelConfig, prompt: str, context: Optional[Dict[str, Any]]
    ) -> LLMResponse:
        """Execute a single model with the given configuration."""
        async with self._semaphore:  # Limit concurrent requests
            provider = self.provider_factory.get_provider(config.provider)
            if not provider:
                raise ValueError(f"Provider {config.provider} not available")

            request = LLMRequest(
                prompt=prompt,
                model_type=config.model_type,
                max_tokens=config.max_tokens,
                temperature=config.temperature,
            )

            # Add context if provided
            if context:
                # Note: LLMRequest doesn't have metadata field, using context instead
                # request.metadata = context
                pass

            # Execute with timeout
            try:
                response = await asyncio.wait_for(
                    provider.generate(request), timeout=config.timeout
                )
                return response
            except asyncio.TimeoutError as e:
                raise TimeoutError(
                    f"Model {config.provider}:{config.model} timed out after {config.timeout}s"
                ) from e

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
