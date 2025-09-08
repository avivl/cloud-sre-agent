# gemini_sre_agent/llm/testing/performance_benchmark.py

"""
Performance Benchmarking Tools for LLM Providers and Models.

This module provides comprehensive performance benchmarking capabilities
including latency, throughput, memory usage, and concurrency testing.
"""

import asyncio
import logging
import statistics
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import psutil

from ..base import LLMRequest, ModelType
from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry
from .test_data_generators import PromptType, TestDataGenerator

logger = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""

    test_name: str
    provider: str
    model: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration_ms: float
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    requests_per_second: float
    success_rate: float
    memory_usage_mb: float
    cpu_usage_percent: float
    cost_per_request: float = 0.0
    total_cost: float = 0.0
    errors: List[str] = field(default_factory=list)


@dataclass
class BenchmarkConfig:
    """Configuration for performance benchmarks."""

    duration_seconds: int = 60
    concurrent_requests: int = 10
    requests_per_second: Optional[int] = None
    warmup_requests: int = 5
    cooldown_seconds: int = 5
    timeout_seconds: int = 30
    enable_memory_monitoring: bool = True
    enable_cpu_monitoring: bool = True
    enable_cost_tracking: bool = True


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
        self.test_data_generator = TestDataGenerator()

        # Monitoring
        self.memory_monitor = MemoryMonitor() if psutil else None
        self.cpu_monitor = CPUMonitor() if psutil else None

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
                    result = await self._run_latency_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                except Exception as e:
                    logger.error(f"Latency benchmark failed for {test_name}: {e}")
                    results[test_name] = BenchmarkResult(
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
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    continue

                test_name = f"throughput_{provider_name}_{model_name}"
                logger.info(f"Running throughput benchmark: {test_name}")

                try:
                    result = await self._run_throughput_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                except Exception as e:
                    logger.error(f"Throughput benchmark failed for {test_name}: {e}")
                    results[test_name] = BenchmarkResult(
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

        return results

    async def run_memory_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run memory usage benchmarks."""
        config = config or BenchmarkConfig()
        results = {}

        if not self.memory_monitor:
            logger.warning(
                "Memory monitoring not available, skipping memory benchmarks"
            )
            return results

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    continue

                test_name = f"memory_{provider_name}_{model_name}"
                logger.info(f"Running memory benchmark: {test_name}")

                try:
                    result = await self._run_memory_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                except Exception as e:
                    logger.error(f"Memory benchmark failed for {test_name}: {e}")

        return results

    async def run_concurrency_benchmarks(
        self,
        providers: Optional[List[str]] = None,
        models: Optional[List[str]] = None,
        config: Optional[BenchmarkConfig] = None,
    ) -> Dict[str, BenchmarkResult]:
        """Run concurrency benchmarks."""
        config = config or BenchmarkConfig()
        results = {}

        # Get providers and models to test
        test_providers = providers or self.provider_factory.list_providers()
        test_models = models or [
            model.name for model in self.model_registry.get_all_models()
        ]

        for provider_name in test_providers:
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                continue

            for model_name in test_models:
                model_info = self.model_registry.get_model(model_name)
                if not model_info:
                    continue

                test_name = f"concurrency_{provider_name}_{model_name}"
                logger.info(f"Running concurrency benchmark: {test_name}")

                try:
                    result = await self._run_concurrency_benchmark(
                        provider_name, model_name, config
                    )
                    results[test_name] = result
                except Exception as e:
                    logger.error(f"Concurrency benchmark failed for {test_name}: {e}")

        return results

    async def _run_latency_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single latency benchmark."""
        provider = self.provider_factory.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not available")

        # Generate test requests
        requests = self.test_data_generator.generate_batch_requests(
            config.duration_seconds * 2,  # Generate more requests than needed
            PromptType.SIMPLE,
            ModelType.SMART,
        )

        # Start monitoring
        if self.memory_monitor:
            self.memory_monitor.start()
        if self.cpu_monitor:
            self.cpu_monitor.start()

        latencies = []
        successful_requests = 0
        failed_requests = 0
        errors = []
        total_cost = 0.0

        start_time = time.time()

        try:
            # Run requests sequentially for latency testing
            for i, request in enumerate(requests):
                if time.time() - start_time >= config.duration_seconds:
                    break

                request_start = time.time()

                try:
                    response = await asyncio.wait_for(
                        provider.generate(request), timeout=config.timeout_seconds
                    )

                    request_end = time.time()
                    latency_ms = (request_end - request_start) * 1000
                    latencies.append(latency_ms)
                    successful_requests += 1

                    # Track cost if available
                    if self.cost_manager and hasattr(response, "usage"):
                        cost = await self.cost_manager.estimate_request_cost(
                            provider=provider_name,
                            model=model_name,
                            input_tokens=(
                                response.usage.get("input_tokens", 0)
                                if response.usage
                                else 0
                            ),
                            output_tokens=(
                                response.usage.get("output_tokens", 0)
                                if response.usage
                                else 0
                            ),
                        )
                        total_cost += cost

                except Exception as e:
                    failed_requests += 1
                    errors.append(str(e))
                    logger.warning(f"Request {i} failed: {e}")

        finally:
            # Stop monitoring
            memory_usage = 0.0
            cpu_usage = 0.0

            if self.memory_monitor:
                memory_usage = self.memory_monitor.stop()
            if self.cpu_monitor:
                cpu_usage = self.cpu_monitor.stop()

        total_duration_ms = (time.time() - start_time) * 1000
        total_requests = successful_requests + failed_requests

        # Calculate statistics
        if latencies:
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p50_latency = statistics.median(latencies)
            p95_latency = (
                statistics.quantiles(latencies, n=20)[18]
                if len(latencies) > 20
                else max_latency
            )
            p99_latency = (
                statistics.quantiles(latencies, n=100)[98]
                if len(latencies) > 100
                else max_latency
            )
        else:
            avg_latency = min_latency = max_latency = p50_latency = p95_latency = (
                p99_latency
            ) = 0.0

        requests_per_second = (
            successful_requests / (total_duration_ms / 1000)
            if total_duration_ms > 0
            else 0.0
        )
        success_rate = (
            successful_requests / total_requests if total_requests > 0 else 0.0
        )
        cost_per_request = (
            total_cost / successful_requests if successful_requests > 0 else 0.0
        )

        return BenchmarkResult(
            test_name=f"latency_{provider_name}_{model_name}",
            provider=provider_name,
            model=model_name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_duration_ms=total_duration_ms,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            requests_per_second=requests_per_second,
            success_rate=success_rate,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            errors=errors,
        )

    async def _run_throughput_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single throughput benchmark."""
        provider = self.provider_factory.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider {provider_name} not available")

        # Generate test requests
        requests = self.test_data_generator.generate_batch_requests(
            config.duration_seconds * config.concurrent_requests,
            PromptType.SIMPLE,
            ModelType.SMART,
        )

        # Start monitoring
        if self.memory_monitor:
            self.memory_monitor.start()
        if self.cpu_monitor:
            self.cpu_monitor.start()

        latencies = []
        successful_requests = 0
        failed_requests = 0
        errors = []
        total_cost = 0.0

        start_time = time.time()

        try:
            # Run requests concurrently for throughput testing
            semaphore = asyncio.Semaphore(config.concurrent_requests)

            async def make_request(
                request: LLMRequest,
            ) -> Tuple[float, bool, Optional[str]]:
                nonlocal total_cost
                async with semaphore:
                    request_start = time.time()
                    try:
                        response = await asyncio.wait_for(
                            provider.generate(request), timeout=config.timeout_seconds
                        )
                        request_end = time.time()
                        latency_ms = (request_end - request_start) * 1000

                        # Track cost if available
                        if self.cost_manager and hasattr(response, "usage"):
                            cost = await self.cost_manager.estimate_request_cost(
                                provider=provider_name,
                                model=model_name,
                                input_tokens=(
                                    response.usage.get("input_tokens", 0)
                                    if response.usage
                                    else 0
                                ),
                                output_tokens=(
                                    response.usage.get("output_tokens", 0)
                                    if response.usage
                                    else 0
                                ),
                            )
                            total_cost += cost

                        return latency_ms, True, None
                    except Exception as e:
                        return 0.0, False, str(e)

            # Run requests until duration is reached
            request_index = 0
            while time.time() - start_time < config.duration_seconds:
                batch_requests = requests[
                    request_index : request_index + config.concurrent_requests
                ]
                if not batch_requests:
                    break

                # Run batch concurrently
                results = await asyncio.gather(
                    *[make_request(req) for req in batch_requests]
                )

                for latency, success, error in results:
                    if success:
                        latencies.append(latency)
                        successful_requests += 1
                    else:
                        failed_requests += 1
                        if error:
                            errors.append(error)

                request_index += len(batch_requests)

        finally:
            # Stop monitoring
            memory_usage = 0.0
            cpu_usage = 0.0

            if self.memory_monitor:
                memory_usage = self.memory_monitor.stop()
            if self.cpu_monitor:
                cpu_usage = self.cpu_monitor.stop()

        total_duration_ms = (time.time() - start_time) * 1000
        total_requests = successful_requests + failed_requests

        # Calculate statistics
        if latencies:
            avg_latency = statistics.mean(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            p50_latency = statistics.median(latencies)
            p95_latency = (
                statistics.quantiles(latencies, n=20)[18]
                if len(latencies) > 20
                else max_latency
            )
            p99_latency = (
                statistics.quantiles(latencies, n=100)[98]
                if len(latencies) > 100
                else max_latency
            )
        else:
            avg_latency = min_latency = max_latency = p50_latency = p95_latency = (
                p99_latency
            ) = 0.0

        requests_per_second = (
            successful_requests / (total_duration_ms / 1000)
            if total_duration_ms > 0
            else 0.0
        )
        success_rate = (
            successful_requests / total_requests if total_requests > 0 else 0.0
        )
        cost_per_request = (
            total_cost / successful_requests if successful_requests > 0 else 0.0
        )

        return BenchmarkResult(
            test_name=f"throughput_{provider_name}_{model_name}",
            provider=provider_name,
            model=model_name,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_duration_ms=total_duration_ms,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            requests_per_second=requests_per_second,
            success_rate=success_rate,
            memory_usage_mb=memory_usage,
            cpu_usage_percent=cpu_usage,
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            errors=errors,
        )

    async def _run_memory_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single memory benchmark."""
        # This is a simplified memory benchmark
        # In a real implementation, you would monitor memory usage during requests
        return BenchmarkResult(
            test_name=f"memory_{provider_name}_{model_name}",
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
        )

    async def _run_concurrency_benchmark(
        self,
        provider_name: str,
        model_name: str,
        config: BenchmarkConfig,
    ) -> BenchmarkResult:
        """Run a single concurrency benchmark."""
        # This is similar to throughput benchmark but focuses on concurrency limits
        return await self._run_throughput_benchmark(provider_name, model_name, config)


class MemoryMonitor:
    """Monitor memory usage during benchmarks."""

    def __init__(self):
        """Initialize memory monitor."""
        self.process = psutil.Process()
        self.initial_memory = 0.0
        self.max_memory = 0.0
        self.monitoring = False

    def start(self) -> None:
        """Start memory monitoring."""
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.max_memory = self.initial_memory
        self.monitoring = True

    def stop(self) -> float:
        """Stop memory monitoring and return peak memory usage."""
        self.monitoring = False
        return self.max_memory - self.initial_memory

    def update(self) -> None:
        """Update memory usage (call periodically during monitoring)."""
        if self.monitoring:
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.max_memory = max(self.max_memory, current_memory)


class CPUMonitor:
    """Monitor CPU usage during benchmarks."""

    def __init__(self):
        """Initialize CPU monitor."""
        self.process = psutil.Process()
        self.cpu_samples = []
        self.monitoring = False

    def start(self) -> None:
        """Start CPU monitoring."""
        self.cpu_samples = []
        self.monitoring = True

    def stop(self) -> float:
        """Stop CPU monitoring and return average CPU usage."""
        self.monitoring = False
        return statistics.mean(self.cpu_samples) if self.cpu_samples else 0.0

    def update(self) -> None:
        """Update CPU usage (call periodically during monitoring)."""
        if self.monitoring:
            cpu_percent = self.process.cpu_percent()
            self.cpu_samples.append(cpu_percent)
