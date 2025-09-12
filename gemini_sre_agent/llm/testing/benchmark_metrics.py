# gemini_sre_agent/llm/testing/benchmark_metrics.py

"""
Metrics collection and analysis for performance benchmarks.

This module provides utilities for collecting, analyzing, and
reporting performance metrics from benchmark runs.
"""

import statistics
from typing import Dict, List, Optional

from .benchmark_models import (
    BenchmarkResult,
    CostMetrics,
    LatencyMetrics,
    ResourceMetrics,
    ThroughputMetrics,
)


class MetricsCollector:
    """Collects and analyzes benchmark metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.results: List[BenchmarkResult] = []

    def add_result(self, result: BenchmarkResult) -> None:
        """Add a benchmark result to the collection."""
        self.results.append(result)

    def calculate_latency_metrics(self, latencies: List[float]) -> LatencyMetrics:
        """Calculate latency statistics from a list of latency measurements."""
        if not latencies:
            return LatencyMetrics(
                latencies=[],
                avg_latency=0.0,
                min_latency=0.0,
                max_latency=0.0,
                p50_latency=0.0,
                p95_latency=0.0,
                p99_latency=0.0,
                std_deviation=0.0,
            )

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        return LatencyMetrics(
            latencies=latencies,
            avg_latency=statistics.mean(latencies),
            min_latency=min(latencies),
            max_latency=max(latencies),
            p50_latency=sorted_latencies[int(n * 0.5)],
            p95_latency=sorted_latencies[int(n * 0.95)],
            p99_latency=sorted_latencies[int(n * 0.99)],
            std_deviation=statistics.stdev(latencies) if len(latencies) > 1 else 0.0,
        )

    def calculate_throughput_metrics(
        self,
        total_requests: int,
        successful_requests: int,
        total_duration: float,
    ) -> ThroughputMetrics:
        """Calculate throughput statistics."""
        failed_requests = total_requests - successful_requests
        success_rate = (
            (successful_requests / total_requests) if total_requests > 0 else 0.0
        )
        requests_per_second = (
            total_requests / total_duration if total_duration > 0 else 0.0
        )

        return ThroughputMetrics(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            total_duration=total_duration,
            requests_per_second=requests_per_second,
            success_rate=success_rate,
        )

    def calculate_resource_metrics(
        self,
        memory_usage_mb: float,
        cpu_usage_percent: float,
        peak_memory_mb: Optional[float] = None,
        avg_cpu_percent: Optional[float] = None,
    ) -> ResourceMetrics:
        """Calculate resource usage metrics."""
        return ResourceMetrics(
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            peak_memory_mb=peak_memory_mb or memory_usage_mb,
            avg_cpu_percent=avg_cpu_percent or cpu_usage_percent,
        )

    def calculate_cost_metrics(
        self,
        total_cost: float,
        total_requests: int,
        tokens_used: int = 0,
    ) -> CostMetrics:
        """Calculate cost-related metrics."""
        cost_per_request = total_cost / total_requests if total_requests > 0 else 0.0
        cost_per_token = total_cost / tokens_used if tokens_used > 0 else 0.0

        return CostMetrics(
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            tokens_used=tokens_used,
            cost_per_token=cost_per_token,
        )

    def create_benchmark_result(
        self,
        test_name: str,
        provider: str,
        model: str,
        latencies: List[float],
        total_requests: int,
        successful_requests: int,
        total_duration_ms: float,
        memory_usage_mb: float,
        cpu_usage_percent: float,
        cost_per_request: float = 0.0,
        total_cost: float = 0.0,
        errors: Optional[List[str]] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> BenchmarkResult:
        """Create a complete benchmark result from collected metrics."""
        latency_metrics = self.calculate_latency_metrics(latencies)
        throughput_metrics = self.calculate_throughput_metrics(
            total_requests, successful_requests, total_duration_ms / 1000.0
        )

        return BenchmarkResult(
            test_name=test_name,
            provider=provider,
            model=model,
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=throughput_metrics.failed_requests,
            total_duration_ms=total_duration_ms,
            avg_latency_ms=latency_metrics.avg_latency,
            min_latency_ms=latency_metrics.min_latency,
            max_latency_ms=latency_metrics.max_latency,
            p50_latency_ms=latency_metrics.p50_latency,
            p95_latency_ms=latency_metrics.p95_latency,
            p99_latency_ms=latency_metrics.p99_latency,
            requests_per_second=throughput_metrics.requests_per_second,
            success_rate=throughput_metrics.success_rate,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent,
            cost_per_request=cost_per_request,
            total_cost=total_cost,
            errors=errors or [],
            metadata=metadata or {},
        )

    def get_summary_stats(self) -> Dict[str, float]:
        """Get summary statistics across all collected results."""
        if not self.results:
            return {}

        all_latencies = []
        all_throughputs = []
        all_success_rates = []

        for result in self.results:
            all_latencies.append(result.avg_latency_ms)
            all_throughputs.append(result.requests_per_second)
            all_success_rates.append(result.success_rate)

        return {
            "avg_latency_ms": statistics.mean(all_latencies),
            "min_latency_ms": min(all_latencies),
            "max_latency_ms": max(all_latencies),
            "avg_throughput_rps": statistics.mean(all_throughputs),
            "min_throughput_rps": min(all_throughputs),
            "max_throughput_rps": max(all_throughputs),
            "avg_success_rate": statistics.mean(all_success_rates),
            "min_success_rate": min(all_success_rates),
            "max_success_rate": max(all_success_rates),
        }

    def get_results_by_provider(self) -> Dict[str, List[BenchmarkResult]]:
        """Group results by provider."""
        by_provider: Dict[str, List[BenchmarkResult]] = {}
        for result in self.results:
            if result.provider not in by_provider:
                by_provider[result.provider] = []
            by_provider[result.provider].append(result)
        return by_provider

    def get_results_by_model(self) -> Dict[str, List[BenchmarkResult]]:
        """Group results by model."""
        by_model: Dict[str, List[BenchmarkResult]] = {}
        for result in self.results:
            if result.model not in by_model:
                by_model[result.model] = []
            by_model[result.model].append(result)
        return by_model
