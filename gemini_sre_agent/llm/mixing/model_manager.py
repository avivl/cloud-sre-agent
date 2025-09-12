# gemini_sre_agent/llm/mixing/model_manager.py

"""
Model manager module for the model mixer system.

This module provides model management capabilities including model instantiation,
configuration management, health monitoring, and circuit breaker patterns.
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..base import ModelType
from ..constants import MAX_MODEL_CONFIGS
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry

logger = logging.getLogger(__name__)


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
class ModelHealth:
    """Health status of a model."""

    provider: str
    model: str
    is_healthy: bool
    last_check: float
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    response_time_avg: float = 0.0
    success_rate: float = 100.0


@dataclass
class CircuitBreakerState:
    """State of a circuit breaker for a model."""

    provider: str
    model: str
    is_open: bool = False
    failure_count: int = 0
    last_failure_time: float = 0.0
    next_retry_time: float = 0.0
    failure_threshold: int = 5
    recovery_timeout: float = 60.0


class ModelManager:
    """Manages model configurations and health monitoring."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        max_concurrent_requests: int = 10,
    ):
        """
        Initialize the model manager.

        Args:
            provider_factory: Factory for creating providers
            model_registry: Registry for model information
            max_concurrent_requests: Maximum concurrent requests allowed
        """
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self._semaphore = asyncio.Semaphore(max_concurrent_requests)

        # Model health tracking
        self.model_health: Dict[str, ModelHealth] = {}
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}

        # Specialized model configurations
        self.specialized_configs: Dict[TaskType, List[ModelConfig]] = {}
        self._initialize_specialized_configs()

        # Performance tracking
        self.performance_metrics: Dict[str, Dict[str, Any]] = {}

        logger.info("ModelManager initialized with specialized configurations")

    def _initialize_specialized_configs(self) -> None:
        """Initialize specialized model configurations for different task types."""
        self.specialized_configs = {
            TaskType.CODE_GENERATION: self._create_code_generation_configs(),
            TaskType.ANALYSIS: self._create_analysis_configs(),
            TaskType.CREATIVE_WRITING: self._create_creative_writing_configs(),
            TaskType.TRANSLATION: self._create_translation_configs(),
            TaskType.SUMMARIZATION: self._create_summarization_configs(),
            TaskType.QUESTION_ANSWERING: self._create_qa_configs(),
            TaskType.PROBLEM_SOLVING: self._create_problem_solving_configs(),
            TaskType.DATA_PROCESSING: self._create_data_processing_configs(),
        }

    def _create_code_generation_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for code generation tasks."""
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

    def _create_analysis_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for analysis tasks."""
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

    def _create_creative_writing_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for creative writing tasks."""
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

    def _create_translation_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for translation tasks."""
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

    def _create_summarization_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for summarization tasks."""
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
                model="gemini-1.5-pro",
                model_type=ModelType.SMART,
                weight=0.2,
                specialized_for=TaskType.SUMMARIZATION,
            ),
        ]

    def _create_qa_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for question answering tasks."""
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

    def _create_problem_solving_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for problem solving tasks."""
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

    def _create_data_processing_configs(self) -> List[ModelConfig]:
        """Create specialized configurations for data processing tasks."""
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

    def get_specialized_configs(self, task_type: TaskType) -> List[ModelConfig]:
        """
        Get specialized model configurations for a task type.

        Args:
            task_type: Type of task to get configurations for

        Returns:
            List of model configurations
        """
        return self.specialized_configs.get(task_type, []).copy()

    def get_available_models(
        self, task_type: Optional[TaskType] = None
    ) -> List[ModelConfig]:
        """
        Get available model configurations.

        Args:
            task_type: Optional task type to filter by

        Returns:
            List of available model configurations
        """
        if task_type:
            return self.get_specialized_configs(task_type)

        # Return all configurations
        all_configs = []
        for configs in self.specialized_configs.values():
            all_configs.extend(configs)

        return all_configs

    def validate_configs(self, configs: List[ModelConfig]) -> None:
        """
        Validate model configuration list.

        Args:
            configs: List of model configurations to validate

        Raises:
            ValueError: If configurations are invalid
        """
        if not configs:
            raise ValueError("At least one model configuration is required")

        if len(configs) > MAX_MODEL_CONFIGS:
            raise ValueError(f"Too many model configurations (max {MAX_MODEL_CONFIGS})")

        # Validate each configuration
        for config in configs:
            if not config.provider or not config.model:
                raise ValueError("Provider and model must be specified")

            if config.weight <= 0:
                raise ValueError("Model weight must be positive")

            if config.max_tokens <= 0:
                raise ValueError("Max tokens must be positive")

            if config.temperature < 0 or config.temperature > 2:
                raise ValueError("Temperature must be between 0 and 2")

            if config.timeout <= 0:
                raise ValueError("Timeout must be positive")

    def get_model_key(self, provider: str, model: str) -> str:
        """
        Get a unique key for a model.

        Args:
            provider: Model provider
            model: Model name

        Returns:
            Unique model key
        """
        return f"{provider}:{model}"

    def check_model_health(self, provider: str, model: str) -> ModelHealth:
        """
        Check the health status of a model.

        Args:
            provider: Model provider
            model: Model name

        Returns:
            Model health status
        """
        model_key = self.get_model_key(provider, model)

        if model_key not in self.model_health:
            self.model_health[model_key] = ModelHealth(
                provider=provider,
                model=model,
                is_healthy=True,
                last_check=time.time(),
            )

        return self.model_health[model_key]

    def update_model_health(
        self,
        provider: str,
        model: str,
        success: bool,
        response_time: float,
        error: Optional[str] = None,
    ) -> None:
        """
        Update model health status.

        Args:
            provider: Model provider
            model: Model name
            success: Whether the request was successful
            response_time: Response time in seconds
            error: Error message if request failed
        """
        model_key = self.get_model_key(provider, model)

        if model_key not in self.model_health:
            self.model_health[model_key] = ModelHealth(
                provider=provider,
                model=model,
                is_healthy=True,
                last_check=time.time(),
            )

        health = self.model_health[model_key]
        health.last_check = time.time()

        if success:
            health.consecutive_failures = 0
            health.last_error = None
            health.is_healthy = True

            # Update response time average
            if health.response_time_avg == 0:
                health.response_time_avg = response_time
            else:
                health.response_time_avg = (
                    health.response_time_avg + response_time
                ) / 2
        else:
            health.consecutive_failures += 1
            health.last_error = error
            health.is_healthy = health.consecutive_failures < 3

    def is_circuit_breaker_open(self, provider: str, model: str) -> bool:
        """
        Check if circuit breaker is open for a model.

        Args:
            provider: Model provider
            model: Model name

        Returns:
            True if circuit breaker is open
        """
        model_key = self.get_model_key(provider, model)

        if model_key not in self.circuit_breakers:
            return False

        breaker = self.circuit_breakers[model_key]

        # Check if we should retry
        if breaker.is_open and time.time() > breaker.next_retry_time:
            breaker.is_open = False
            breaker.failure_count = 0
            logger.info(f"Circuit breaker closed for {model_key}")

        return breaker.is_open

    def record_circuit_breaker_failure(self, provider: str, model: str) -> None:
        """
        Record a failure for circuit breaker.

        Args:
            provider: Model provider
            model: Model name
        """
        model_key = self.get_model_key(provider, model)

        if model_key not in self.circuit_breakers:
            self.circuit_breakers[model_key] = CircuitBreakerState(
                provider=provider,
                model=model,
            )

        breaker = self.circuit_breakers[model_key]
        breaker.failure_count += 1
        breaker.last_failure_time = time.time()

        if breaker.failure_count >= breaker.failure_threshold:
            breaker.is_open = True
            breaker.next_retry_time = time.time() + breaker.recovery_timeout
            logger.warning(f"Circuit breaker opened for {model_key}")

    def record_circuit_breaker_success(self, provider: str, model: str) -> None:
        """
        Record a success for circuit breaker.

        Args:
            provider: Model provider
            model: Model name
        """
        model_key = self.get_model_key(provider, model)

        if model_key in self.circuit_breakers:
            breaker = self.circuit_breakers[model_key]
            breaker.failure_count = 0
            breaker.is_open = False

    def get_healthy_models(
        self, task_type: Optional[TaskType] = None
    ) -> List[ModelConfig]:
        """
        Get healthy model configurations.

        Args:
            task_type: Optional task type to filter by

        Returns:
            List of healthy model configurations
        """
        configs = self.get_available_models(task_type)
        healthy_configs = []

        for config in configs:
            self.get_model_key(config.provider, config.model)

            # Check if circuit breaker is open
            if self.is_circuit_breaker_open(config.provider, config.model):
                continue

            # Check health status
            health = self.check_model_health(config.provider, config.model)
            if health.is_healthy:
                healthy_configs.append(config)

        return healthy_configs

    def get_performance_metrics(self, provider: str, model: str) -> Dict[str, Any]:
        """
        Get performance metrics for a model.

        Args:
            provider: Model provider
            model: Model name

        Returns:
            Dictionary containing performance metrics
        """
        model_key = self.get_model_key(provider, model)
        return self.performance_metrics.get(model_key, {})

    def update_performance_metrics(
        self,
        provider: str,
        model: str,
        execution_time: float,
        success: bool,
    ) -> None:
        """
        Update performance metrics for a model.

        Args:
            provider: Model provider
            model: Model name
            execution_time: Execution time in seconds
            success: Whether the execution was successful
        """
        model_key = self.get_model_key(provider, model)

        if model_key not in self.performance_metrics:
            self.performance_metrics[model_key] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_execution_time": 0.0,
                "average_execution_time": 0.0,
                "success_rate": 0.0,
            }

        metrics = self.performance_metrics[model_key]
        metrics["total_requests"] += 1
        metrics["total_execution_time"] += execution_time

        if success:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1

        # Update derived metrics
        metrics["average_execution_time"] = (
            metrics["total_execution_time"] / metrics["total_requests"]
        )
        metrics["success_rate"] = (
            metrics["successful_requests"] / metrics["total_requests"] * 100
        )

    def get_semaphore(self) -> asyncio.Semaphore:
        """
        Get the semaphore for limiting concurrent requests.

        Returns:
            Semaphore instance
        """
        return self._semaphore

    def get_all_health_status(self) -> Dict[str, ModelHealth]:
        """
        Get health status for all models.

        Returns:
            Dictionary containing health status for all models
        """
        return self.model_health.copy()

    def get_all_circuit_breaker_status(self) -> Dict[str, CircuitBreakerState]:
        """
        Get circuit breaker status for all models.

        Returns:
            Dictionary containing circuit breaker status for all models
        """
        return self.circuit_breakers.copy()

    def reset_health_status(self) -> None:
        """Reset health status for all models."""
        self.model_health.clear()
        logger.info("Health status reset for all models")

    def reset_circuit_breakers(self) -> None:
        """Reset circuit breakers for all models."""
        self.circuit_breakers.clear()
        logger.info("Circuit breakers reset for all models")

    def reset_performance_metrics(self) -> None:
        """Reset performance metrics for all models."""
        self.performance_metrics.clear()
        logger.info("Performance metrics reset for all models")
