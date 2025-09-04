# tests/llm/test_performance_cache.py

"""
Unit tests for the Performance Cache system.
"""

from gemini_sre_agent.llm.performance_cache import (
    PerformanceCache,
    PerformanceMonitor,
    PerformanceMetric,
    ModelPerformanceStats,
    MetricType
)
from gemini_sre_agent.llm.base import ProviderType


class TestPerformanceMetric:
    """Test the PerformanceMetric dataclass."""
    
    def test_metric_creation(self):
        """Test creating a performance metric."""
        metric = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=150.5,
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        assert metric.metric_type == MetricType.LATENCY
        assert metric.value == 150.5
        assert metric.model_name == "test-model"
        assert metric.provider == ProviderType.OPENAI
        assert isinstance(metric.timestamp, float)
        assert metric.timestamp > 0
    
    def test_metric_with_context(self):
        """Test creating a metric with context and metadata."""
        context = {"task_type": "classification", "input_length": 100}
        metadata = {"source": "test", "version": "1.0"}
        
        metric = PerformanceMetric(
            metric_type=MetricType.THROUGHPUT,
            value=25.0,
            model_name="test-model",
            context=context,
            metadata=metadata
        )
        
        assert metric.context == context
        assert metric.metadata == metadata


class TestModelPerformanceStats:
    """Test the ModelPerformanceStats class."""
    
    def test_stats_creation(self):
        """Test creating performance stats."""
        stats = ModelPerformanceStats(
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        assert stats.model_name == "test-model"
        assert stats.provider == ProviderType.OPENAI
        assert stats.sample_count == 0
        assert len(stats.metric_counts) == 0
    
    def test_add_metric(self):
        """Test adding metrics to stats."""
        stats = ModelPerformanceStats(
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        metric1 = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=100.0,
            model_name="test-model"
        )
        
        metric2 = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=200.0,
            model_name="test-model"
        )
        
        stats.add_metric(metric1)
        stats.add_metric(metric2)
        
        assert stats.sample_count == 2
        assert stats.metric_counts[MetricType.LATENCY] == 2
        assert stats.metric_sums[MetricType.LATENCY] == 300.0
        assert stats.metric_mins[MetricType.LATENCY] == 100.0
        assert stats.metric_maxs[MetricType.LATENCY] == 200.0
    
    def test_get_average(self):
        """Test getting average metric values."""
        stats = ModelPerformanceStats(
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        # Add some metrics
        for value in [100.0, 200.0, 300.0]:
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=value,
                model_name="test-model"
            )
            stats.add_metric(metric)
        
        avg = stats.get_average(MetricType.LATENCY)
        assert avg == 200.0
        
        # Test non-existent metric
        avg_none = stats.get_average(MetricType.THROUGHPUT)
        assert avg_none is None
    
    def test_get_percentile(self):
        """Test getting percentile values."""
        stats = ModelPerformanceStats(
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        # Add metrics with known values
        for value in [100.0, 200.0, 300.0]:
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=value,
                model_name="test-model"
            )
            stats.add_metric(metric)
        
        p50 = stats.get_percentile(MetricType.LATENCY, 0.5)
        assert p50 is not None
        assert 100.0 <= p50 <= 300.0


class TestPerformanceCache:
    """Test the PerformanceCache class."""
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = PerformanceCache(max_cache_size=1000, default_ttl=1800)
        
        assert cache.max_cache_size == 1000
        assert cache.default_ttl == 1800
        assert len(cache._metrics) == 0
        assert len(cache._model_stats) == 0
    
    def test_add_metric(self):
        """Test adding metrics to cache."""
        cache = PerformanceCache()
        
        metric = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=150.0,
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        
        cache.add_metric(metric)
        
        assert len(cache._metrics) == 1
        assert "test-model" in cache._model_stats
        assert len(cache._model_index["test-model"]) == 1
    
    def test_get_model_stats(self):
        """Test getting model statistics."""
        cache = PerformanceCache()
        
        # Add some metrics
        for i in range(5):
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=100.0 + i * 10,
                model_name="test-model",
                provider=ProviderType.OPENAI
            )
            cache.add_metric(metric)
        
        stats = cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.model_name == "test-model"
        assert stats.sample_count == 5
        assert stats.get_average(MetricType.LATENCY) == 120.0
    
    def test_get_metrics_filtering(self):
        """Test filtering metrics by various criteria."""
        cache = PerformanceCache()
        
        # Add metrics for different models and types
        metrics_data = [
            (MetricType.LATENCY, 100.0, "model1", ProviderType.OPENAI),
            (MetricType.THROUGHPUT, 25.0, "model1", ProviderType.OPENAI),
            (MetricType.LATENCY, 150.0, "model2", ProviderType.CLAUDE),
            (MetricType.THROUGHPUT, 30.0, "model2", ProviderType.CLAUDE),
        ]
        
        for metric_type, value, model_name, provider in metrics_data:
            metric = PerformanceMetric(
                metric_type=metric_type,
                value=value,
                model_name=model_name,
                provider=provider
            )
            cache.add_metric(metric)
        
        # Filter by model
        model1_metrics = cache.get_metrics(model_name="model1")
        assert len(model1_metrics) == 2
        
        # Filter by metric type
        latency_metrics = cache.get_metrics(metric_type=MetricType.LATENCY)
        assert len(latency_metrics) == 2
        
        # Filter by provider
        openai_metrics = cache.get_metrics(provider=ProviderType.OPENAI)
        assert len(openai_metrics) == 2
        
        # Combined filter
        model1_latency = cache.get_metrics(
            model_name="model1",
            metric_type=MetricType.LATENCY
        )
        assert len(model1_latency) == 1
        assert model1_latency[0].value == 100.0
    
    def test_get_performance_summary(self):
        """Test getting performance summary."""
        cache = PerformanceCache()
        
        # Add metrics
        for value in [100.0, 150.0, 200.0]:
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=value,
                model_name="test-model",
                provider=ProviderType.OPENAI
            )
            cache.add_metric(metric)
        
        summary = cache.get_performance_summary("test-model")
        
        assert summary['model_name'] == "test-model"
        assert summary['provider'] == ProviderType.OPENAI.value
        assert summary['sample_count'] == 3
        assert 'metrics' in summary
        assert MetricType.LATENCY.value in summary['metrics']
        
        latency_metrics = summary['metrics'][MetricType.LATENCY.value]
        assert latency_metrics['count'] == 3
        assert latency_metrics['average'] == 150.0
        assert latency_metrics['min'] == 100.0
        assert latency_metrics['max'] == 200.0
    
    def test_get_top_models(self):
        """Test getting top performing models."""
        cache = PerformanceCache()
        
        # Add metrics for different models
        models_data = [
            ("fast-model", 50.0),
            ("medium-model", 100.0),
            ("slow-model", 200.0),
        ]
        
        for model_name, latency in models_data:
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=latency,
                model_name=model_name,
                provider=ProviderType.OPENAI
            )
            cache.add_metric(metric)
        
        # Get fastest models (lowest latency)
        fastest = cache.get_top_models(MetricType.LATENCY, limit=2, ascending=True)
        assert len(fastest) == 2
        assert fastest[0][0] == "fast-model"
        assert fastest[0][1] == 50.0
        
        # Get slowest models (highest latency)
        slowest = cache.get_top_models(MetricType.LATENCY, limit=2, ascending=False)
        assert len(slowest) == 2
        assert slowest[0][0] == "slow-model"
        assert slowest[0][1] == 200.0
    
    def test_get_model_rankings(self):
        """Test getting model rankings based on multiple metrics."""
        cache = PerformanceCache()
        
        # Add metrics for different models
        models_data = [
            ("model1", 100.0, 25.0),  # latency, throughput
            ("model2", 150.0, 30.0),
            ("model3", 200.0, 20.0),
        ]
        
        for model_name, latency, throughput in models_data:
            # Add latency metric
            latency_metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=latency,
                model_name=model_name,
                provider=ProviderType.OPENAI
            )
            cache.add_metric(latency_metric)
            
            # Add throughput metric
            throughput_metric = PerformanceMetric(
                metric_type=MetricType.THROUGHPUT,
                value=throughput,
                model_name=model_name,
                provider=ProviderType.OPENAI
            )
            cache.add_metric(throughput_metric)
        
        # Get rankings based on latency and throughput
        rankings = cache.get_model_rankings([MetricType.LATENCY, MetricType.THROUGHPUT])
        
        assert len(rankings) == 3
        # Rankings should be sorted by combined score
        assert rankings[0][0] in ["model1", "model2", "model3"]
    
    def test_clear_cache(self):
        """Test clearing the cache."""
        cache = PerformanceCache()
        
        # Add some metrics
        metric = PerformanceMetric(
            metric_type=MetricType.LATENCY,
            value=150.0,
            model_name="test-model",
            provider=ProviderType.OPENAI
        )
        cache.add_metric(metric)
        
        assert len(cache._metrics) > 0
        assert len(cache._model_stats) > 0
        
        cache.clear_cache()
        
        assert len(cache._metrics) == 0
        assert len(cache._model_stats) == 0
        assert len(cache._model_index) == 0
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        cache = PerformanceCache()
        
        # Add some metrics
        for i in range(3):
            metric = PerformanceMetric(
                metric_type=MetricType.LATENCY,
                value=100.0 + i * 10,
                model_name="test-model",
                provider=ProviderType.OPENAI
            )
            cache.add_metric(metric)
        
        stats = cache.get_cache_stats()
        
        assert stats['total_metrics'] == 3
        assert stats['valid_metrics'] == 3
        assert stats['expired_metrics'] == 0
        assert stats['model_count'] == 1
        assert stats['cache_utilization'] > 0


class TestPerformanceMonitor:
    """Test the PerformanceMonitor class."""
    
    def test_monitor_initialization(self):
        """Test monitor initialization."""
        monitor = PerformanceMonitor()
        assert isinstance(monitor.cache, PerformanceCache)
        
        # Test with custom cache
        custom_cache = PerformanceCache(max_cache_size=500)
        monitor = PerformanceMonitor(custom_cache)
        assert monitor.cache == custom_cache
    
    def test_record_latency(self):
        """Test recording latency metrics."""
        monitor = PerformanceMonitor()
        
        monitor.record_latency("test-model", 150.0, ProviderType.OPENAI)
        
        stats = monitor.cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.get_average(MetricType.LATENCY) == 150.0
    
    def test_record_throughput(self):
        """Test recording throughput metrics."""
        monitor = PerformanceMonitor()
        
        monitor.record_throughput("test-model", 25.0, ProviderType.OPENAI)
        
        stats = monitor.cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.get_average(MetricType.THROUGHPUT) == 25.0
    
    def test_record_success(self):
        """Test recording success/failure metrics."""
        monitor = PerformanceMonitor()
        
        # Record success
        monitor.record_success("test-model", True, ProviderType.OPENAI)
        
        # Record failure
        monitor.record_success("test-model", False, ProviderType.OPENAI)
        
        stats = monitor.cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.metric_counts[MetricType.SUCCESS_RATE] == 1
        assert stats.metric_counts[MetricType.ERROR_RATE] == 1
    
    def test_record_cost_efficiency(self):
        """Test recording cost efficiency metrics."""
        monitor = PerformanceMonitor()
        
        monitor.record_cost_efficiency("test-model", 0.001, ProviderType.OPENAI)
        
        stats = monitor.cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.get_average(MetricType.COST_EFFICIENCY) == 0.001
    
    def test_record_quality_score(self):
        """Test recording quality score metrics."""
        monitor = PerformanceMonitor()
        
        monitor.record_quality_score("test-model", 0.85, ProviderType.OPENAI)
        
        stats = monitor.cache.get_model_stats("test-model")
        assert stats is not None
        assert stats.get_average(MetricType.QUALITY_SCORE) == 0.85
    
    def test_get_model_performance(self):
        """Test getting model performance summary."""
        monitor = PerformanceMonitor()
        
        # Add some metrics
        monitor.record_latency("test-model", 150.0, ProviderType.OPENAI)
        monitor.record_throughput("test-model", 25.0, ProviderType.OPENAI)
        
        performance = monitor.get_model_performance("test-model")
        
        assert performance['model_name'] == "test-model"
        assert performance['provider'] == ProviderType.OPENAI.value
        assert 'metrics' in performance
        assert MetricType.LATENCY.value in performance['metrics']
        assert MetricType.THROUGHPUT.value in performance['metrics']
    
    def test_get_best_models(self):
        """Test getting best performing models."""
        monitor = PerformanceMonitor()
        
        # Add metrics for different models
        models_data = [
            ("fast-model", 50.0),
            ("medium-model", 100.0),
            ("slow-model", 200.0),
        ]
        
        for model_name, latency in models_data:
            monitor.record_latency(model_name, latency, ProviderType.OPENAI)
        
        best_models = monitor.get_best_models(MetricType.LATENCY, limit=2)
        
        assert len(best_models) == 2
        assert best_models[0][0] == "fast-model"  # Lowest latency is best
        assert best_models[0][1] == 50.0
    
    def test_get_worst_models(self):
        """Test getting worst performing models."""
        monitor = PerformanceMonitor()
        
        # Add metrics for different models
        models_data = [
            ("fast-model", 50.0),
            ("medium-model", 100.0),
            ("slow-model", 200.0),
        ]
        
        for model_name, latency in models_data:
            monitor.record_latency(model_name, latency, ProviderType.OPENAI)
        
        worst_models = monitor.get_worst_models(MetricType.LATENCY, limit=2)
        
        assert len(worst_models) == 2
        assert worst_models[0][0] == "slow-model"  # Highest latency is worst
        assert worst_models[0][1] == 200.0
    
    def test_get_model_rankings(self):
        """Test getting model rankings."""
        monitor = PerformanceMonitor()
        
        # Add metrics for different models
        models_data = [
            ("model1", 100.0, 25.0),  # latency, throughput
            ("model2", 150.0, 30.0),
        ]
        
        for model_name, latency, throughput in models_data:
            monitor.record_latency(model_name, latency, ProviderType.OPENAI)
            monitor.record_throughput(model_name, throughput, ProviderType.OPENAI)
        
        rankings = monitor.get_model_rankings([MetricType.LATENCY, MetricType.THROUGHPUT])
        
        assert len(rankings) == 2
        # Should be sorted by combined score
        assert isinstance(rankings[0][1], float)
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        monitor = PerformanceMonitor()
        
        # Add some metrics
        monitor.record_latency("test-model", 150.0, ProviderType.OPENAI)
        
        stats = monitor.get_cache_stats()
        
        assert stats['total_metrics'] == 1
        assert stats['model_count'] == 1
        assert 'cache_utilization' in stats
