"""
LLM-Specific Metrics Collection System.

This module provides comprehensive metrics collection for LLM operations,
including provider performance, cost tracking, reliability metrics, and
custom business metrics.
"""

import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from ..base import LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class LLMMetricType(Enum):
    """Types of LLM-specific metrics."""

    # Request metrics
    REQUEST_COUNT = "request_count"
    REQUEST_DURATION = "request_duration"
    REQUEST_SIZE = "request_size"
    RESPONSE_SIZE = "response_size"

    # Token metrics
    INPUT_TOKENS = "input_tokens"
    OUTPUT_TOKENS = "output_tokens"
    TOTAL_TOKENS = "total_tokens"

    # Cost metrics
    COST_PER_REQUEST = "cost_per_request"
    COST_PER_TOKEN = "cost_per_token"  # nosec B105
    TOTAL_COST = "total_cost"

    # Performance metrics
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    THROUGHPUT = "throughput"

    # Reliability metrics
    SUCCESS_RATE = "success_rate"
    ERROR_RATE = "error_rate"
    CIRCUIT_BREAKER_TRIPS = "circuit_breaker_trips"
    RATE_LIMIT_HITS = "rate_limit_hits"

    # Quality metrics
    RESPONSE_QUALITY_SCORE = "response_quality_score"
    HALLUCINATION_RATE = "hallucination_rate"
    CONSISTENCY_SCORE = "consistency_score"


@dataclass
class LLMMetricValue:
    """Represents an LLM metric value with metadata."""

    name: str
    value: Union[int, float]
    metric_type: LLMMetricType
    provider: str
    model: str
    model_type: str
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)
    unit: Optional[str] = None


@dataclass
class ProviderMetrics:
    """Aggregated metrics for a specific provider."""

    provider: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    total_duration_ms: float = 0.0
    avg_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0
    circuit_breaker_trips: int = 0
    rate_limit_hits: int = 0
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class ModelMetrics:
    """Aggregated metrics for a specific model."""

    provider: str
    model: str
    model_type: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_cost: float = 0.0
    total_tokens: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    quality_score: float = 0.0
    last_updated: datetime = field(default_factory=datetime.now)


class LLMMetricsCollector:
    """Comprehensive metrics collector for LLM operations."""

    def __init__(self, retention_hours: int = 24):
        """Initialize the LLM metrics collector."""
        self.retention_hours = retention_hours
        self.retention_duration = timedelta(hours=retention_hours)

        # Storage for metrics
        self._metrics: deque = deque()
        self._provider_metrics: Dict[str, ProviderMetrics] = {}
        self._model_metrics: Dict[str, ModelMetrics] = {}

        # Performance tracking
        self._latency_samples: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=1000)
        )
        self._cost_samples: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))

        # Rate limiting tracking
        self._request_counts: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=3600)
        )  # 1 hour of seconds

        logger.info(
            f"LLMMetricsCollector initialized with {retention_hours}h retention"
        )

    def _get_metric_key(self, provider: str, model: str) -> str:
        """Get a unique key for provider-model combination."""
        return f"{provider}:{model}"

    def _cleanup_old_metrics(self):
        """Remove metrics older than retention period."""
        cutoff_time = datetime.now() - self.retention_duration

        # Remove old metrics
        while self._metrics and self._metrics[0].timestamp < cutoff_time:
            self._metrics.popleft()

        # Clean up old latency samples
        for key in list(self._latency_samples.keys()):
            samples = self._latency_samples[key]
            while samples and samples[0][0] < cutoff_time:
                samples.popleft()
            if not samples:
                del self._latency_samples[key]

        # Clean up old cost samples
        for key in list(self._cost_samples.keys()):
            samples = self._cost_samples[key]
            while samples and samples[0][0] < cutoff_time:
                samples.popleft()
            if not samples:
                del self._cost_samples[key]

        # Clean up old request counts
        for key in list(self._request_counts.keys()):
            counts = self._request_counts[key]
            while counts and counts[0][0] < cutoff_time:
                counts.popleft()
            if not counts:
                del self._request_counts[key]

    def record_request(
        self,
        provider: str,
        model: str,
        model_type: str,
        request: LLMRequest,
        response: Optional[LLMResponse] = None,
        error: Optional[Exception] = None,
        duration_ms: float = 0.0,
        cost: float = 0.0,
    ):
        """Record a complete LLM request with metrics."""
        timestamp = datetime.now()
        success = response is not None and error is None

        # Create metric value
        metric = LLMMetricValue(
            name="llm_request",
            value=1 if success else 0,
            metric_type=LLMMetricType.REQUEST_COUNT,
            provider=provider,
            model=model,
            model_type=model_type,
            timestamp=timestamp,
            labels={
                "success": str(success),
                "error_type": type(error).__name__ if error else "none",
            },
        )

        self._metrics.append(metric)

        # Update provider metrics
        if provider not in self._provider_metrics:
            self._provider_metrics[provider] = ProviderMetrics(provider=provider)

        provider_metric = self._provider_metrics[provider]
        provider_metric.total_requests += 1
        provider_metric.total_duration_ms += duration_ms
        provider_metric.total_cost += cost
        provider_metric.last_updated = timestamp

        if success:
            provider_metric.successful_requests += 1
            if response and response.usage:
                provider_metric.total_tokens += response.usage.get("total_tokens", 0)
        else:
            provider_metric.failed_requests += 1

        # Update success/error rates
        provider_metric.success_rate = (
            provider_metric.successful_requests / provider_metric.total_requests
        )
        provider_metric.error_rate = (
            provider_metric.failed_requests / provider_metric.total_requests
        )
        provider_metric.avg_latency_ms = (
            provider_metric.total_duration_ms / provider_metric.total_requests
        )

        # Update model metrics
        model_key = self._get_metric_key(provider, model)
        if model_key not in self._model_metrics:
            self._model_metrics[model_key] = ModelMetrics(
                provider=provider, model=model, model_type=model_type
            )

        model_metric = self._model_metrics[model_key]
        model_metric.total_requests += 1
        model_metric.total_cost += cost
        model_metric.last_updated = timestamp

        if success:
            model_metric.successful_requests += 1
            if response and response.usage:
                model_metric.total_tokens += response.usage.get("total_tokens", 0)
        else:
            model_metric.failed_requests += 1

        model_metric.success_rate = (
            model_metric.successful_requests / model_metric.total_requests
        )

        # Record latency sample
        self._latency_samples[model_key].append((timestamp, duration_ms))

        # Record cost sample
        if cost > 0:
            self._cost_samples[model_key].append((timestamp, cost))

        # Record request count for rate limiting
        current_second = int(timestamp.timestamp())
        self._request_counts[provider].append((timestamp, current_second))

        # Calculate percentiles
        self._update_percentiles(provider, model_key)

        # Cleanup old metrics periodically
        if len(self._metrics) % 100 == 0:
            self._cleanup_old_metrics()

    def _update_percentiles(self, provider: str, model_key: str):
        """Update latency percentiles for provider and model."""
        # Update provider percentiles
        if provider in self._provider_metrics:
            provider_samples = []
            for key, samples in self._latency_samples.items():
                if key.startswith(f"{provider}:"):
                    provider_samples.extend([sample[1] for sample in samples])

            if provider_samples:
                provider_samples.sort()
                provider_metric = self._provider_metrics[provider]
                provider_metric.p95_latency_ms = self._percentile(provider_samples, 95)
                provider_metric.p99_latency_ms = self._percentile(provider_samples, 99)

        # Update model percentiles
        if model_key in self._model_metrics and model_key in self._latency_samples:
            model_samples = [sample[1] for sample in self._latency_samples[model_key]]
            if model_samples:
                model_samples.sort()
                model_metric = self._model_metrics[model_key]
                model_metric.avg_latency_ms = sum(model_samples) / len(model_samples)

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0
        index = int((percentile / 100) * len(data))
        return data[min(index, len(data) - 1)]

    def record_circuit_breaker_trip(self, provider: str):
        """Record a circuit breaker trip."""
        if provider in self._provider_metrics:
            self._provider_metrics[provider].circuit_breaker_trips += 1
            self._provider_metrics[provider].last_updated = datetime.now()

    def record_rate_limit_hit(self, provider: str):
        """Record a rate limit hit."""
        if provider in self._provider_metrics:
            self._provider_metrics[provider].rate_limit_hits += 1
            self._provider_metrics[provider].last_updated = datetime.now()

    def get_provider_metrics(self, provider: str) -> Optional[ProviderMetrics]:
        """Get metrics for a specific provider."""
        return self._provider_metrics.get(provider)

    def get_model_metrics(self, provider: str, model: str) -> Optional[ModelMetrics]:
        """Get metrics for a specific model."""
        model_key = self._get_metric_key(provider, model)
        return self._model_metrics.get(model_key)

    def get_all_provider_metrics(self) -> Dict[str, ProviderMetrics]:
        """Get metrics for all providers."""
        return self._provider_metrics.copy()

    def get_all_model_metrics(self) -> Dict[str, ModelMetrics]:
        """Get metrics for all models."""
        return self._model_metrics.copy()

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        total_requests = sum(
            pm.total_requests for pm in self._provider_metrics.values()
        )
        total_cost = sum(pm.total_cost for pm in self._provider_metrics.values())
        total_tokens = sum(pm.total_tokens for pm in self._provider_metrics.values())

        # Calculate overall success rate
        total_successful = sum(
            pm.successful_requests for pm in self._provider_metrics.values()
        )
        overall_success_rate = (
            total_successful / total_requests if total_requests > 0 else 0.0
        )

        # Calculate average latency
        total_duration = sum(
            pm.total_duration_ms for pm in self._provider_metrics.values()
        )
        avg_latency = total_duration / total_requests if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "total_cost": total_cost,
            "total_tokens": total_tokens,
            "overall_success_rate": overall_success_rate,
            "average_latency_ms": avg_latency,
            "provider_count": len(self._provider_metrics),
            "model_count": len(self._model_metrics),
            "retention_hours": self.retention_hours,
            "last_updated": datetime.now().isoformat(),
        }

    def get_throughput_metrics(
        self, provider: str, window_minutes: int = 5
    ) -> Dict[str, float]:
        """Get throughput metrics for a provider."""
        if provider not in self._request_counts:
            return {"requests_per_minute": 0.0, "requests_per_second": 0.0}

        cutoff_time = datetime.now() - timedelta(minutes=window_minutes)
        recent_requests = [
            req for req in self._request_counts[provider] if req[0] >= cutoff_time
        ]

        requests_per_minute = len(recent_requests) / window_minutes
        requests_per_second = requests_per_minute / 60

        return {
            "requests_per_minute": requests_per_minute,
            "requests_per_second": requests_per_second,
            "window_minutes": window_minutes,
        }

    def export_metrics(self, format: str = "json") -> Dict[str, Any]:
        """Export metrics in specified format."""
        if format == "json":
            return {
                "summary": self.get_metrics_summary(),
                "providers": {
                    provider: {
                        "total_requests": pm.total_requests,
                        "success_rate": pm.success_rate,
                        "total_cost": pm.total_cost,
                        "avg_latency_ms": pm.avg_latency_ms,
                        "p95_latency_ms": pm.p95_latency_ms,
                        "p99_latency_ms": pm.p99_latency_ms,
                        "circuit_breaker_trips": pm.circuit_breaker_trips,
                        "rate_limit_hits": pm.rate_limit_hits,
                        "last_updated": pm.last_updated.isoformat(),
                    }
                    for provider, pm in self._provider_metrics.items()
                },
                "models": {
                    model_key: {
                        "provider": mm.provider,
                        "model": mm.model,
                        "model_type": mm.model_type,
                        "total_requests": mm.total_requests,
                        "success_rate": mm.success_rate,
                        "total_cost": mm.total_cost,
                        "avg_latency_ms": mm.avg_latency_ms,
                        "quality_score": mm.quality_score,
                        "last_updated": mm.last_updated.isoformat(),
                    }
                    for model_key, mm in self._model_metrics.items()
                },
            }
        else:
            raise ValueError(f"Unsupported export format: {format}")


# Global metrics collector instance
llm_metrics_collector = LLMMetricsCollector()


def get_llm_metrics_collector() -> LLMMetricsCollector:
    """Get the global LLM metrics collector instance."""
    return llm_metrics_collector
