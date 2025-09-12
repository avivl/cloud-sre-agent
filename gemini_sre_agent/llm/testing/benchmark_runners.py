# gemini_sre_agent/llm/testing/benchmark_runners.py

"""
Core benchmark execution logic for performance testing.

This module contains the main benchmark runners that execute
different types of performance tests including latency, throughput,
memory, and concurrency benchmarks.
"""

import asyncio
import logging
import time
from typing import Optional

from ..base import LLMRequest
from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry
from .benchmark_metrics import MetricsCollector
from .benchmark_models import BenchmarkConfig, BenchmarkResult
from .benchmark_monitors import SystemMonitor
from .test_data_generators import PromptType, TestDataGenerator, TestScenario

logger = logging.getLogger(__name__)


class BenchmarkRunner:
    """Core benchmark execution engine."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        cost_manager: Optional[IntegratedCostManager] = None,
    ):
        """Initialize the benchmark runner."""
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self.cost_manager = cost_manager
        self.test_data_generator = TestDataGenerator()
        self.metrics_collector = MetricsCollector()

    async def run_latency_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single latency benchmark."""
        logger.info(f"Running latency benchmark: {provider_name}/{model_name}")

        provider = self.provider_factory.get_provider(provider_name)
        if not provider:
            raise RuntimeError(f"Provider {provider_name} not available")

        model_info = self.model_registry.get_model(model_name)
        if not model_info:
            raise RuntimeError(f"Model {model_name} not found")

        # Generate test prompt
        test_prompt = config.test_prompt or self.test_data_generator.generate_prompt(
            PromptType.SIMPLE, TestScenario.PERFORMANCE_TEST, custom_length=100
        )

        # Setup monitoring
        system_monitor = SystemMonitor()
        system_monitor.start()

        latencies = []
        successful_requests = 0
        errors = []
        total_cost = 0.0

        try:
            # Warmup requests
            for _ in range(config.warmup_requests):
                try:
                    await self._make_request(provider, model_name, test_prompt, config)
                except Exception as e:
                    logger.warning(f"Warmup request failed: {e}")

            # Actual benchmark
            start_time = time.time()

            for i in range(config.num_requests):
                try:
                    request_start = time.time()
                    response = await self._make_request(
                        provider, model_name, test_prompt, config
                    )
                    request_end = time.time()

                    latency_ms = (request_end - request_start) * 1000
                    latencies.append(latency_ms)
                    successful_requests += 1

                    # Track cost if available
                    if self.cost_manager and hasattr(response, "usage"):
                        cost = await self.cost_manager.estimate_request_cost(
                            provider_name, model_name, response.usage
                        )
                        total_cost += cost

                    # Update monitoring
                    system_monitor.update()

                except Exception as e:
                    error_msg = f"Request {i+1} failed: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            end_time = time.time()
            total_duration_ms = (end_time - start_time) * 1000

        finally:
            memory_usage, cpu_usage = system_monitor.stop()

        # Calculate metrics
        cost_per_request = (
            total_cost / config.num_requests if config.num_requests > 0 else 0.0
        )

        return self.metrics_collector.create_benchmark_result(
            test_name=f"latency_{provider_name}_{model_name}",
            provider=provider_name,
            model=model_name,
            latencies=latencies,
            total_requests=config.num_requests,
            successful_requests=successful_requests,
            total_duration_ms=total_duration_ms,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            errors=errors,
        )

    async def run_throughput_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single throughput benchmark."""
        logger.info(f"Running throughput benchmark: {provider_name}/{model_name}")

        provider = self.provider_factory.get_provider(provider_name)
        if not provider:
            raise RuntimeError(f"Provider {provider_name} not available")

        model_info = self.model_registry.get_model(model_name)
        if not model_info:
            raise RuntimeError(f"Model {model_name} not found")

        # Generate test prompt
        test_prompt = config.test_prompt or self.test_data_generator.generate_prompt(
            PromptType.SIMPLE, TestScenario.PERFORMANCE_TEST, custom_length=100
        )

        # Setup monitoring
        system_monitor = SystemMonitor()
        system_monitor.start()

        latencies = []
        successful_requests = 0
        errors = []
        total_cost = 0.0

        try:
            # Warmup requests
            for _ in range(config.warmup_requests):
                try:
                    await self._make_request(provider, model_name, test_prompt, config)
                except Exception as e:
                    logger.warning(f"Warmup request failed: {e}")

            # Actual benchmark with concurrency
            start_time = time.time()

            async def make_request(request_id: int) -> None:
                nonlocal successful_requests, total_cost
                try:
                    request_start = time.time()
                    response = await self._make_request(
                        provider, model_name, test_prompt, config
                    )
                    request_end = time.time()

                    latency_ms = (request_end - request_start) * 1000
                    latencies.append(latency_ms)
                    successful_requests += 1

                    # Track cost if available
                    if self.cost_manager and hasattr(response, "usage"):
                        cost = await self.cost_manager.estimate_request_cost(
                            provider_name, model_name, response.usage
                        )
                        total_cost += cost

                except Exception as e:
                    error_msg = f"Request {request_id} failed: {e}"
                    logger.warning(error_msg)
                    errors.append(error_msg)

            # Execute requests with concurrency
            semaphore = asyncio.Semaphore(config.concurrency)

            async def limited_request(request_id: int) -> None:
                async with semaphore:
                    await make_request(request_id)

            tasks = [limited_request(i) for i in range(config.num_requests)]
            await asyncio.gather(*tasks, return_exceptions=True)

            end_time = time.time()
            total_duration_ms = (end_time - start_time) * 1000

        finally:
            memory_usage, cpu_usage = system_monitor.stop()

        # Calculate metrics
        cost_per_request = (
            total_cost / config.num_requests if config.num_requests > 0 else 0.0
        )

        return self.metrics_collector.create_benchmark_result(
            test_name=f"throughput_{provider_name}_{model_name}",
            provider=provider_name,
            model=model_name,
            latencies=latencies,
            total_requests=config.num_requests,
            successful_requests=successful_requests,
            total_duration_ms=total_duration_ms,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            errors=errors,
        )

    async def run_memory_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a memory usage benchmark."""
        logger.info(f"Running memory benchmark: {provider_name}/{model_name}")

        # Memory benchmarks are similar to latency but focus on memory usage
        return await self.run_latency_benchmark(provider_name, model_name, config)

    async def run_concurrency_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a concurrency benchmark."""
        logger.info(f"Running concurrency benchmark: {provider_name}/{model_name}")

        # Concurrency benchmarks are similar to throughput but with higher concurrency
        return await self.run_throughput_benchmark(provider_name, model_name, config)

    async def _make_request(
        self,
        provider,
        model_name: str,
        prompt: str,
        config: BenchmarkConfig,
    ):
        """Make a single LLM request."""
        request = LLMRequest(
            prompt=prompt,
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )

        return await provider.generate(request)
