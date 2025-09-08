# gemini_sre_agent/llm/performance_cache.py

"""
Performance Metrics Caching System for LLM Model Selection.

This module provides a comprehensive caching system for performance metrics,
enabling real-time monitoring, optimization, and intelligent model selection
based on historical performance data.
"""

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .common.enums import ProviderType

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Types of performance metrics."""

    LATENCY = "latency"  # Response time in milliseconds
    THROUGHPUT = "throughput"  # Tokens per second
    SUCCESS_RATE = "success_rate"  # Percentage of successful requests
    ERROR_RATE = "error_rate"  # Percentage of failed requests
    COST_EFFICIENCY = "cost_efficiency"  # Cost per successful token
    QUALITY_SCORE = "quality_score"  # Quality assessment score
    AVAILABILITY = "availability"  # Model availability percentage


@dataclass
class PerformanceMetric:
    """Individual performance metric measurement."""

    metric_type: MetricType
    value: float
    timestamp: float = field(default_factory=time.time)
    model_name: str = ""
    provider: Optional[ProviderType] = None
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelPerformanceStats:
    """Aggregated performance statistics for a model."""

    model_name: str
    provider: ProviderType
    metric_counts: Dict[MetricType, int] = field(default_factory=dict)
    metric_sums: Dict[MetricType, float] = field(default_factory=dict)
    metric_mins: Dict[MetricType, float] = field(default_factory=dict)
    metric_maxs: Dict[MetricType, float] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)
    sample_count: int = 0

    def add_metric(self, metric: PerformanceMetric) -> None:
        """Add a metric to the statistics."""
        metric_type = metric.metric_type

        # Update counts and sums
        self.metric_counts[metric_type] = self.metric_counts.get(metric_type, 0) + 1
        self.metric_sums[metric_type] = (
            self.metric_sums.get(metric_type, 0.0) + metric.value
        )

        # Update min/max
        if metric_type not in self.metric_mins:
            self.metric_mins[metric_type] = metric.value
            self.metric_maxs[metric_type] = metric.value
        else:
            self.metric_mins[metric_type] = min(
                self.metric_mins[metric_type], metric.value
            )
            self.metric_maxs[metric_type] = max(
                self.metric_maxs[metric_type], metric.value
            )

        self.last_updated = time.time()
        self.sample_count += 1

    def get_average(self, metric_type: MetricType) -> Optional[float]:
        """Get average value for a metric type."""
        if (
            metric_type not in self.metric_counts
            or self.metric_counts[metric_type] == 0
        ):
            return None
        return self.metric_sums[metric_type] / self.metric_counts[metric_type]

    def get_percentile(
        self, metric_type: MetricType, percentile: float
    ) -> Optional[float]:
        """Get percentile value for a metric type (simplified implementation)."""
        # This is a simplified implementation - in production, you'd want to store
        # individual values and calculate proper percentiles
        avg = self.get_average(metric_type)
        if avg is None:
            return None

        # Simple approximation based on min/max and average
        min_val = self.metric_mins.get(metric_type, avg)
        max_val = self.metric_maxs.get(metric_type, avg)

        if percentile <= 0.5:
            return min_val + (avg - min_val) * (percentile * 2)
        else:
            return avg + (max_val - avg) * ((percentile - 0.5) * 2)


class PerformanceCache:
    """
    Performance metrics caching system with TTL and size limits.

    Provides efficient storage and retrieval of performance metrics
    with automatic cleanup and aggregation capabilities.
    """

    def __init__(
        self,
        max_cache_size: int = 10000,
        default_ttl: int = 3600,  # 1 hour
        aggregation_window: int = 300,  # 5 minutes
        cleanup_interval: int = 600,  # 10 minutes
    ):
        """Initialize the performance cache."""
        self.max_cache_size = max_cache_size
        self.default_ttl = default_ttl
        self.aggregation_window = aggregation_window
        self.cleanup_interval = cleanup_interval

        # Storage for individual metrics
        self._metrics: deque = deque(maxlen=max_cache_size)

        # Aggregated statistics by model
        self._model_stats: Dict[str, ModelPerformanceStats] = {}

        # Indexes for efficient querying
        self._model_index: Dict[str, List[int]] = defaultdict(list)
        self._provider_index: Dict[ProviderType, List[int]] = defaultdict(list)
        self._metric_type_index: Dict[MetricType, List[int]] = defaultdict(list)
        self._time_index: List[Tuple[float, int]] = []  # (timestamp, metric_index)

        self._last_cleanup = time.time()
        self.logger = logging.getLogger(f"{__name__}.PerformanceCache")

        self.logger.info(
            f"PerformanceCache initialized with max_size={max_cache_size}, ttl={default_ttl}s"
        )

    def add_metric(self, metric: PerformanceMetric) -> None:
        """Add a performance metric to the cache."""
        current_time = time.time()

        # Clean up old metrics if needed
        if current_time - self._last_cleanup > self.cleanup_interval:
            self._cleanup_expired_metrics()

        # Add metric to storage
        metric_index = len(self._metrics)
        self._metrics.append(metric)

        # Update indexes
        self._model_index[metric.model_name].append(metric_index)
        if metric.provider:
            self._provider_index[metric.provider].append(metric_index)
        self._metric_type_index[metric.metric_type].append(metric_index)
        self._time_index.append((metric.timestamp, metric_index))

        # Update aggregated statistics
        if metric.model_name not in self._model_stats:
            self._model_stats[metric.model_name] = ModelPerformanceStats(
                model_name=metric.model_name,
                provider=metric.provider or ProviderType.OPENAI,
            )

        self._model_stats[metric.model_name].add_metric(metric)

        self.logger.debug(
            f"Added metric: {metric.metric_type.value}={metric.value} for {metric.model_name}"
        )

    def get_model_stats(self, model_name: str) -> Optional[ModelPerformanceStats]:
        """Get aggregated statistics for a specific model."""
        return self._model_stats.get(model_name)

    def get_metrics(
        self,
        model_name: Optional[str] = None,
        provider: Optional[ProviderType] = None,
        metric_type: Optional[MetricType] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[PerformanceMetric]:
        """Get metrics matching the specified criteria."""
        # Start with all metrics
        candidate_indices = set(range(len(self._metrics)))

        # Filter by model name
        if model_name:
            model_indices = set(self._model_index.get(model_name, []))
            candidate_indices &= model_indices

        # Filter by provider
        if provider:
            provider_indices = set(self._provider_index.get(provider, []))
            candidate_indices &= provider_indices

        # Filter by metric type
        if metric_type:
            type_indices = set(self._metric_type_index.get(metric_type, []))
            candidate_indices &= type_indices

        # Filter by time range
        if start_time or end_time:
            time_filtered_indices = set()
            for timestamp, metric_index in self._time_index:
                if start_time and timestamp < start_time:
                    continue
                if end_time and timestamp > end_time:
                    continue
                time_filtered_indices.add(metric_index)
            candidate_indices &= time_filtered_indices

        # Get metrics and apply limit
        metrics = [self._metrics[i] for i in sorted(candidate_indices)]
        if limit:
            metrics = metrics[-limit:]  # Get most recent metrics

        return metrics

    def get_performance_summary(
        self, model_name: str, metric_types: Optional[List[MetricType]] = None
    ) -> Dict[str, Any]:
        """Get a performance summary for a model."""
        stats = self._model_stats.get(model_name)
        if not stats:
            return {}

        if metric_types is None:
            metric_types = list(MetricType)

        summary = {
            "model_name": model_name,
            "provider": stats.provider.value,
            "last_updated": stats.last_updated,
            "sample_count": stats.sample_count,
            "metrics": {},
        }

        for metric_type in metric_types:
            if metric_type in stats.metric_counts:
                summary["metrics"][metric_type.value] = {
                    "count": stats.metric_counts[metric_type],
                    "average": stats.get_average(metric_type),
                    "min": stats.metric_mins.get(metric_type),
                    "max": stats.metric_maxs.get(metric_type),
                    "p50": stats.get_percentile(metric_type, 0.5),
                    "p95": stats.get_percentile(metric_type, 0.95),
                    "p99": stats.get_percentile(metric_type, 0.99),
                }

        return summary

    def get_top_models(
        self, metric_type: MetricType, limit: int = 10, ascending: bool = True
    ) -> List[Tuple[str, float]]:
        """Get top performing models for a specific metric."""
        model_scores = []

        for model_name, stats in self._model_stats.items():
            avg_score = stats.get_average(metric_type)
            if avg_score is not None:
                model_scores.append((model_name, avg_score))

        # Sort by score
        model_scores.sort(key=lambda x: x[1], reverse=not ascending)

        return model_scores[:limit]

    def get_model_rankings(
        self,
        metric_types: List[MetricType],
        weights: Optional[Dict[MetricType, float]] = None,
    ) -> List[Tuple[str, float]]:
        """Get model rankings based on weighted combination of metrics."""
        if weights is None:
            # Equal weights
            weights = {
                metric_type: 1.0 / len(metric_types) for metric_type in metric_types
            }

        model_scores = {}

        for model_name, stats in self._model_stats.items():
            total_score = 0.0
            total_weight = 0.0

            for metric_type, weight in weights.items():
                avg_score = stats.get_average(metric_type)
                if avg_score is not None:
                    # Normalize score to 0-1 range (simplified)
                    normalized_score = min(
                        1.0, max(0.0, avg_score / 1000.0)
                    )  # Adjust based on expected range
                    total_score += normalized_score * weight
                    total_weight += weight

            if total_weight > 0:
                model_scores[model_name] = total_score / total_weight

        # Sort by combined score
        ranked_models = sorted(model_scores.items(), key=lambda x: x[1], reverse=True)
        return ranked_models

    def _cleanup_expired_metrics(self) -> None:
        """Remove expired metrics and update indexes."""
        current_time = time.time()
        expired_indices = set()

        # Find expired metrics
        for i, metric in enumerate(self._metrics):
            if current_time - metric.timestamp > self.default_ttl:
                expired_indices.add(i)

        if not expired_indices:
            self._last_cleanup = current_time
            return

        # Remove expired metrics (simplified - in production, you'd want more efficient cleanup)
        self.logger.info(f"Cleaning up {len(expired_indices)} expired metrics")

        # Update time index
        self._time_index = [
            (timestamp, idx)
            for timestamp, idx in self._time_index
            if idx not in expired_indices
        ]

        self._last_cleanup = current_time

    def clear_cache(self) -> None:
        """Clear all cached metrics and statistics."""
        self._metrics.clear()
        self._model_stats.clear()
        self._model_index.clear()
        self._provider_index.clear()
        self._metric_type_index.clear()
        self._time_index.clear()
        self._last_cleanup = time.time()

        self.logger.info("Performance cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        current_time = time.time()
        valid_metrics = sum(
            1
            for metric in self._metrics
            if current_time - metric.timestamp <= self.default_ttl
        )

        return {
            "total_metrics": len(self._metrics),
            "valid_metrics": valid_metrics,
            "expired_metrics": len(self._metrics) - valid_metrics,
            "model_count": len(self._model_stats),
            "cache_size_limit": self.max_cache_size,
            "cache_utilization": len(self._metrics) / self.max_cache_size,
            "last_cleanup": self._last_cleanup,
            "time_since_cleanup": current_time - self._last_cleanup,
        }


class PerformanceMonitor:
    """
    High-level performance monitoring interface.

    Provides convenient methods for recording and querying performance metrics
    with automatic aggregation and analysis capabilities.
    """

    def __init__(self, cache: Optional[PerformanceCache] = None):
        """Initialize the performance monitor."""
        self.cache = cache or PerformanceCache()
        self.logger = logging.getLogger(f"{__name__}.PerformanceMonitor")

    def record_latency(
        self,
        model_name: str,
        latency_ms: float,
        provider: Optional[ProviderType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record latency metric for a model."""
        metric = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=latency_ms,
            model_name=model_name,
            provider=provider,
            context=context or {},
        )
        self.cache.add_metric(metric)

    def record_throughput(
        self,
        model_name: str,
        tokens_per_second: float,
        provider: Optional[ProviderType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record throughput metric for a model."""
        metric = PerformanceMetric(
            metric_type=MetricType.THROUGHPUT,
            value=tokens_per_second,
            model_name=model_name,
            provider=provider,
            context=context or {},
        )
        self.cache.add_metric(metric)

    def record_success(
        self,
        model_name: str,
        success: bool,
        provider: Optional[ProviderType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record success/failure metric for a model."""
        metric_type = MetricType.SUCCESS_RATE if success else MetricType.ERROR_RATE
        metric = PerformanceMetric(
            metric_type=metric_type,
            value=1.0 if success else 0.0,
            model_name=model_name,
            provider=provider,
            context=context or {},
        )
        self.cache.add_metric(metric)

    def record_cost_efficiency(
        self,
        model_name: str,
        cost_per_token: float,
        provider: Optional[ProviderType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record cost efficiency metric for a model."""
        metric = PerformanceMetric(
            metric_type=MetricType.COST_EFFICIENCY,
            value=cost_per_token,
            model_name=model_name,
            provider=provider,
            context=context or {},
        )
        self.cache.add_metric(metric)

    def record_quality_score(
        self,
        model_name: str,
        quality_score: float,
        provider: Optional[ProviderType] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record quality score metric for a model."""
        metric = PerformanceMetric(
            metric_type=MetricType.QUALITY_SCORE,
            value=quality_score,
            model_name=model_name,
            provider=provider,
            context=context or {},
        )
        self.cache.add_metric(metric)

    def get_model_performance(
        self, model_name: str, metric_types: Optional[List[MetricType]] = None
    ) -> Dict[str, Any]:
        """Get performance summary for a model."""
        return self.cache.get_performance_summary(model_name, metric_types)

    def get_best_models(
        self, metric_type: MetricType, limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Get best performing models for a metric."""
        return self.cache.get_top_models(metric_type, limit, ascending=True)

    def get_worst_models(
        self, metric_type: MetricType, limit: int = 5
    ) -> List[Tuple[str, float]]:
        """Get worst performing models for a metric."""
        return self.cache.get_top_models(metric_type, limit, ascending=False)

    def get_model_rankings(
        self,
        metric_types: List[MetricType],
        weights: Optional[Dict[MetricType, float]] = None,
    ) -> List[Tuple[str, float]]:
        """Get model rankings based on multiple metrics."""
        return self.cache.get_model_rankings(metric_types, weights)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return self.cache.get_cache_stats()
