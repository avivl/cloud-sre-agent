# gemini_sre_agent/llm/testing/benchmark_models.py

"""
Data models and configuration for performance benchmarking.

This module defines the core data structures used throughout the
benchmarking system including results, configuration, and metadata.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark tests."""

    num_requests: int = 10
    concurrency: int = 1
    timeout_seconds: int = 30
    warmup_requests: int = 2
    test_prompt: Optional[str] = None
    max_tokens: int = 100
    temperature: float = 0.7
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class BenchmarkMetadata:
    """Metadata for benchmark execution."""

    test_id: str
    start_time: float
    end_time: Optional[float] = None
    environment: Dict[str, str] = field(default_factory=dict)
    system_info: Dict[str, str] = field(default_factory=dict)
    test_config: Optional[BenchmarkConfig] = None


@dataclass
class LatencyMetrics:
    """Latency-specific metrics."""

    latencies: List[float]
    avg_latency: float
    min_latency: float
    max_latency: float
    p50_latency: float
    p95_latency: float
    p99_latency: float
    std_deviation: float


@dataclass
class ThroughputMetrics:
    """Throughput-specific metrics."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    total_duration: float
    requests_per_second: float
    success_rate: float


@dataclass
class ResourceMetrics:
    """System resource usage metrics."""

    memory_usage_mb: float
    cpu_usage_percent: float
    peak_memory_mb: float
    avg_cpu_percent: float


@dataclass
class CostMetrics:
    """Cost-related metrics."""

    cost_per_request: float
    total_cost: float
    tokens_used: int
    cost_per_token: float
