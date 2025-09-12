# gemini_sre_agent/llm/testing/performance_benchmark_refactored.py

"""
Refactored Performance Benchmarking Tool for LLM Providers and Models.

This module provides comprehensive performance benchmarking capabilities
including latency, throughput, memory usage, and concurrency testing.
The original monolithic implementation has been broken down into modular
components for better maintainability and testability.
"""

import logging
from typing import Dict, List, Optional

from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry
from .benchmark_metrics import MetricsCollector
from .benchmark_models import BenchmarkConfig, BenchmarkResult

# Backward compatibility imports
from .benchmark_monitors import CPUMonitor, MemoryMonitor
from .benchmark_runners import BenchmarkRunner

logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Performance benchmarking tool for LLM providers and models."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        cost_manager: Optional[IntegratedCostManager] = None,
    ):
        """Initialize the performance benchmark tool."""
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self.cost_manager = cost_manager

        # Initialize modular components
        self.benchmark_runner = BenchmarkRunner(
            provider_factory, model_registry, cost_manager
        )
        self.metrics_collector = MetricsCollector()

    async def run_latency_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run latency benchmarks across providers and models."""
        config = config or BenchmarkConfig()
        results = {}

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        logger.info(
            f"Running latency benchmarks for {len(test_providers)} providers and {len(test_models)} models"
        )

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                logger.warning(f"Provider {provider_name} not available, skipping")
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    logger.warning(f"Model {model_name} not found, skipping")
                    continue

                test_name = f"latency_{provider_name}_{model_name}"
                logger.info(f"Running latency benchmark: {test_name}")

                try:
                    result = await self.benchmark_runner.run_latency_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                    self.metrics_collector.add_result(result)
                except Exception as e:
                    logger.error(f"Latency benchmark failed for {test_name}: {e}")
                    error_result = BenchmarkResult(
                        test_name=test_name,
                        provider=provider_name,
                        model=model_name,
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        total_duration_ms=0.0,
                        avg_latency_ms=0.0,
                        min_latency_ms=0.0,
                        max_latency_ms=0.0,
                        p50_latency_ms=0.0,
                        p95_latency_ms=0.0,
                        p99_latency_ms=0.0,
                        requests_per_second=0.0,
                        success_rate=0.0,
                        memory_usage_mb=0.0,
                        cpu_usage_percent=0.0,
                        errors=[str(e)],
                    )
                    results[test_name] = error_result
                    self.metrics_collector.add_result(error_result)

        return results

    async def run_throughput_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run throughput benchmarks across providers and models."""
        config = config or BenchmarkConfig()
        results = {}

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        logger.info(
            f"Running throughput benchmarks for {len(test_providers)} providers and {len(test_models)} models"
        )

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                logger.warning(f"Provider {provider_name} not available, skipping")
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    logger.warning(f"Model {model_name} not found, skipping")
                    continue

                test_name = f"throughput_{provider_name}_{model_name}"
                logger.info(f"Running throughput benchmark: {test_name}")

                try:
                    result = await self.benchmark_runner.run_throughput_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                    self.metrics_collector.add_result(result)
                except Exception as e:
                    logger.error(f"Throughput benchmark failed for {test_name}: {e}")
                    error_result = BenchmarkResult(
                        test_name=test_name,
                        provider=provider_name,
                        model=model_name,
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        total_duration_ms=0.0,
                        avg_latency_ms=0.0,
                        min_latency_ms=0.0,
                        max_latency_ms=0.0,
                        p50_latency_ms=0.0,
                        p95_latency_ms=0.0,
                        p99_latency_ms=0.0,
                        requests_per_second=0.0,
                        success_rate=0.0,
                        memory_usage_mb=0.0,
                        cpu_usage_percent=0.0,
                        errors=[str(e)],
                    )
                    results[test_name] = error_result
                    self.metrics_collector.add_result(error_result)

        return results

    async def run_memory_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run memory usage benchmarks across providers and models."""
        config = config or BenchmarkConfig()
        results = {}

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        logger.info(
            f"Running memory benchmarks for {len(test_providers)} providers and {len(test_models)} models"
        )

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                logger.warning(f"Provider {provider_name} not available, skipping")
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    logger.warning(f"Model {model_name} not found, skipping")
                    continue

                test_name = f"memory_{provider_name}_{model_name}"
                logger.info(f"Running memory benchmark: {test_name}")

                try:
                    result = await self.benchmark_runner.run_memory_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                    self.metrics_collector.add_result(result)
                except Exception as e:
                    logger.error(f"Memory benchmark failed for {test_name}: {e}")
                    error_result = BenchmarkResult(
                        test_name=test_name,
                        provider=provider_name,
                        model=model_name,
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        total_duration_ms=0.0,
                        avg_latency_ms=0.0,
                        min_latency_ms=0.0,
                        max_latency_ms=0.0,
                        p50_latency_ms=0.0,
                        p95_latency_ms=0.0,
                        p99_latency_ms=0.0,
                        requests_per_second=0.0,
                        success_rate=0.0,
                        memory_usage_mb=0.0,
                        cpu_usage_percent=0.0,
                        errors=[str(e)],
                    )
                    results[test_name] = error_result
                    self.metrics_collector.add_result(error_result)

        return results

    async def run_concurrency_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run concurrency benchmarks across providers and models."""
        config = config or BenchmarkConfig()
        results = {}

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        logger.info(
            f"Running concurrency benchmarks for {len(test_providers)} providers and {len(test_models)} models"
        )

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                logger.warning(f"Provider {provider_name} not available, skipping")
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    logger.warning(f"Model {model_name} not found, skipping")
                    continue

                test_name = f"concurrency_{provider_name}_{model_name}"
                logger.info(f"Running concurrency benchmark: {test_name}")

                try:
                    result = await self.benchmark_runner.run_concurrency_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                    self.metrics_collector.add_result(result)
                except Exception as e:
                    logger.error(f"Concurrency benchmark failed for {test_name}: {e}")
                    error_result = BenchmarkResult(
                        test_name=test_name,
                        provider=provider_name,
                        model=model_name,
                        total_requests=0,
                        successful_requests=0,
                        failed_requests=0,
                        total_duration_ms=0.0,
                        avg_latency_ms=0.0,
                        min_latency_ms=0.0,
                        max_latency_ms=0.0,
                        p50_latency_ms=0.0,
                        p95_latency_ms=0.0,
                        p99_latency_ms=0.0,
                        requests_per_second=0.0,
                        success_rate=0.0,
                        memory_usage_mb=0.0,
                        cpu_usage_percent=0.0,
                        errors=[str(e)],
                    )
                    results[test_name] = error_result
                    self.metrics_collector.add_result(error_result)

        return results

    def get_summary_stats(self) -> Dict[str, float]:
        """Get summary statistics across all benchmark results."""
        return self.metrics_collector.get_summary_stats()

    def get_results_by_provider(self) -> Dict[str, List[BenchmarkResult]]:
        """Group results by provider."""
        return self.metrics_collector.get_results_by_provider()

    def get_results_by_model(self) -> Dict[str, List[BenchmarkResult]]:
        """Group results by model."""
        return self.metrics_collector.get_results_by_model()

    def clear_results(self) -> None:
        """Clear all collected results."""
        self.metrics_collector.results.clear()


# Backward compatibility - re-export the main class and models

__all__ = [
    "PerformanceBenchmark",
    "BenchmarkResult",
    "BenchmarkConfig",
    "MemoryMonitor",
    "CPUMonitor",
]
