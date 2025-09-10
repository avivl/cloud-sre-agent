"""
Performance tests for metrics collection to ensure minimal impact on operations.
"""

import asyncio
import time
from typing import Any, Dict, List

import pytest

from gemini_sre_agent.source_control.error_handling.core import CircuitState, ErrorType
from gemini_sre_agent.source_control.error_handling.metrics_integration import (
    ErrorHandlingMetrics,
)
from gemini_sre_agent.source_control.metrics.core import MetricType


class MockMetricsCollector:
    """Mock metrics collector that simulates real collection behavior."""

    def __init__(self):
        self.metrics: List[Dict[str, Any]] = []
        self.record_calls = 0
        self.total_time = 0.0

    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: MetricType,
        tags: Dict[str, str],
        unit: str = None,
    ):
        """Simulate metrics recording with realistic timing."""
        start_time = time.time()

        # Simulate some processing time (realistic for metrics collection)
        await asyncio.sleep(0.001)  # 1ms processing time

        self.metrics.append(
            {
                "name": name,
                "value": value,
                "metric_type": metric_type,
                "tags": tags,
                "unit": unit,
                "timestamp": time.time(),
            }
        )

        self.record_calls += 1
        self.total_time += time.time() - start_time

    def get_average_record_time(self) -> float:
        """Get average time per record_metric call."""
        return self.total_time / max(self.record_calls, 1)


class TestMetricsPerformance:
    """Performance tests for metrics collection."""

    @pytest.fixture
    def mock_collector(self):
        """Create a mock metrics collector."""
        return MockMetricsCollector()

    @pytest.fixture
    def metrics(self, mock_collector):
        """Create ErrorHandlingMetrics instance."""
        return ErrorHandlingMetrics(mock_collector)

    @pytest.mark.asyncio
    async def test_single_metric_record_performance(self, metrics, mock_collector):
        """Test performance of recording a single metric."""
        start_time = time.time()

        await metrics.record_error(
            error_type=ErrorType.NETWORK_ERROR,
            operation_name="test_operation",
            provider="github",
            is_retryable=True,
        )

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in under 10ms (including 1ms mock processing)
        assert (
            total_time < 0.01
        ), f"Single metric recording took {total_time:.4f}s, expected < 0.01s"

        # Verify metrics were recorded
        assert mock_collector.record_calls == 1
        assert len(mock_collector.metrics) == 1

    @pytest.mark.asyncio
    async def test_batch_metrics_performance(self, metrics, mock_collector):
        """Test performance of recording multiple metrics in batch."""
        num_metrics = 100
        start_time = time.time()

        # Record multiple metrics concurrently
        tasks = []
        for i in range(num_metrics):
            task = metrics.record_error(
                error_type=ErrorType.NETWORK_ERROR,
                operation_name=f"test_operation_{i}",
                provider="github",
                is_retryable=True,
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in under 1 second for 100 metrics
        assert (
            total_time < 1.0
        ), f"Batch metrics recording took {total_time:.4f}s, expected < 1.0s"

        # Verify all metrics were recorded
        assert mock_collector.record_calls == num_metrics
        assert len(mock_collector.metrics) == num_metrics

        # Calculate average time per metric
        avg_time_per_metric = total_time / num_metrics
        print(f"Average time per metric: {avg_time_per_metric:.6f}s")

        # Should be under 5ms per metric on average
        assert (
            avg_time_per_metric < 0.005
        ), f"Average time per metric {avg_time_per_metric:.6f}s, expected < 0.005s"

    @pytest.mark.asyncio
    async def test_high_frequency_metrics_performance(self, metrics, mock_collector):
        """Test performance under high frequency metric recording."""
        num_metrics = 1000
        start_time = time.time()

        # Record metrics in rapid succession
        for i in range(num_metrics):
            await metrics.record_error(
                error_type=ErrorType.NETWORK_ERROR,
                operation_name=f"test_operation_{i}",
                provider="github",
                is_retryable=True,
            )

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in under 5 seconds for 1000 metrics
        assert (
            total_time < 5.0
        ), f"High frequency metrics took {total_time:.4f}s, expected < 5.0s"

        # Verify all metrics were recorded
        assert mock_collector.record_calls == num_metrics
        assert len(mock_collector.metrics) == num_metrics

        # Calculate metrics per second
        metrics_per_second = num_metrics / total_time
        print(f"Metrics per second: {metrics_per_second:.2f}")

        # Should handle at least 200 metrics per second
        assert (
            metrics_per_second > 200
        ), f"Metrics per second {metrics_per_second:.2f}, expected > 200"

    @pytest.mark.asyncio
    async def test_complex_metrics_performance(self, metrics, mock_collector):
        """Test performance of complex metrics with multiple data points."""
        num_operations = 100
        start_time = time.time()

        # Record complex metrics (each operation records multiple metrics)
        for i in range(num_operations):
            # Record error
            await metrics.record_error(
                error_type=ErrorType.NETWORK_ERROR,
                operation_name=f"test_operation_{i}",
                provider="github",
                is_retryable=True,
                retry_count=2,
                error_details={"status_code": 500, "message": "Internal server error"},
            )

            # Record operation success
            await metrics.record_operation_success(
                operation_name=f"test_operation_{i}",
                provider="github",
                duration_seconds=1.5,
                retry_count=2,
            )

            # Record circuit breaker state change
            await metrics.record_circuit_breaker_state_change(
                circuit_name=f"test_circuit_{i}",
                old_state=CircuitState.CLOSED,
                new_state=CircuitState.OPEN,
                operation_type="file_operations",
            )

            # Record retry attempt
            await metrics.record_retry_attempt(
                operation_name=f"test_operation_{i}",
                provider="github",
                attempt_number=1,
                delay_seconds=1.0,
                error_type=ErrorType.RATE_LIMIT_ERROR,
            )

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in under 10 seconds for 100 complex operations
        assert (
            total_time < 10.0
        ), f"Complex metrics took {total_time:.4f}s, expected < 10.0s"

        # Each operation records 10 metrics:
        # - record_error: 3 metrics (error count + retry count + error details)
        # - record_operation_success: 3 metrics (operation count + duration + retry count)
        # - record_circuit_breaker_state_change: 2 metrics (state change + current state)
        # - record_retry_attempt: 2 metrics (retry count + delay histogram)
        expected_metrics = num_operations * 10
        assert mock_collector.record_calls == expected_metrics
        assert len(mock_collector.metrics) == expected_metrics

        # Calculate average time per operation
        avg_time_per_operation = total_time / num_operations
        print(f"Average time per complex operation: {avg_time_per_operation:.6f}s")

        # Should be under 50ms per operation on average
        assert (
            avg_time_per_operation < 0.05
        ), f"Average time per operation {avg_time_per_operation:.6f}s, expected < 0.05s"

    @pytest.mark.asyncio
    async def test_metrics_memory_usage(self, metrics, mock_collector):
        """Test memory usage of metrics collection."""
        import os

        import psutil

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Record many metrics
        num_metrics = 10000
        for i in range(num_metrics):
            await metrics.record_error(
                error_type=ErrorType.NETWORK_ERROR,
                operation_name=f"test_operation_{i}",
                provider="github",
                is_retryable=True,
            )

        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        print(f"Memory increase for {num_metrics} metrics: {memory_increase:.2f} MB")

        # Memory increase should be reasonable (less than 100MB for 10k metrics)
        assert (
            memory_increase < 100
        ), f"Memory increase {memory_increase:.2f} MB, expected < 100 MB"

        # Calculate memory per metric
        memory_per_metric = memory_increase / num_metrics * 1024  # KB
        print(f"Memory per metric: {memory_per_metric:.2f} KB")

        # Should be under 10KB per metric
        assert (
            memory_per_metric < 10
        ), f"Memory per metric {memory_per_metric:.2f} KB, expected < 10 KB"

    @pytest.mark.asyncio
    async def test_concurrent_metrics_performance(self, metrics, mock_collector):
        """Test performance under concurrent metric recording."""
        num_concurrent_operations = 50
        metrics_per_operation = 10

        start_time = time.time()

        async def record_metrics_batch(operation_id: int):
            """Record a batch of metrics for one operation."""
            for i in range(metrics_per_operation):
                await metrics.record_error(
                    error_type=ErrorType.NETWORK_ERROR,
                    operation_name=f"concurrent_operation_{operation_id}_{i}",
                    provider="github",
                    is_retryable=True,
                )

        # Run concurrent operations
        tasks = [record_metrics_batch(i) for i in range(num_concurrent_operations)]
        await asyncio.gather(*tasks)

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in under 5 seconds
        assert (
            total_time < 5.0
        ), f"Concurrent metrics took {total_time:.4f}s, expected < 5.0s"

        # Verify all metrics were recorded
        expected_metrics = num_concurrent_operations * metrics_per_operation
        assert mock_collector.record_calls == expected_metrics
        assert len(mock_collector.metrics) == expected_metrics

        # Calculate throughput
        throughput = expected_metrics / total_time
        print(f"Concurrent metrics throughput: {throughput:.2f} metrics/second")

        # Should handle at least 100 metrics per second under concurrency
        assert (
            throughput > 100
        ), f"Throughput {throughput:.2f} metrics/second, expected > 100"

    @pytest.mark.asyncio
    async def test_metrics_error_handling_performance(self, mock_collector):
        """Test performance when metrics collection encounters errors."""

        # Create a metrics collector that sometimes fails
        class FailingMetricsCollector:
            def __init__(self):
                self.call_count = 0
                self.success_count = 0

            async def record_metric(
                self,
                name: str,
                value: float,
                metric_type: MetricType,
                tags: Dict[str, str],
                unit: str = None,
            ):
                self.call_count += 1
                # Fail every 10th call
                if self.call_count % 10 == 0:
                    raise Exception("Metrics collection error")
                self.success_count += 1
                # Simulate processing time
                await asyncio.sleep(0.001)

        failing_collector = FailingMetricsCollector()
        metrics = ErrorHandlingMetrics(failing_collector)

        num_metrics = 100
        start_time = time.time()

        # Record metrics (some will fail)
        for i in range(num_metrics):
            await metrics.record_error(
                error_type=ErrorType.NETWORK_ERROR,
                operation_name=f"test_operation_{i}",
                provider="github",
                is_retryable=True,
            )

        end_time = time.time()
        total_time = end_time - start_time

        # Should complete in reasonable time even with errors
        assert (
            total_time < 2.0
        ), f"Metrics with errors took {total_time:.4f}s, expected < 2.0s"

        # Should have some successful recordings
        assert (
            failing_collector.success_count > 0
        ), "No metrics were successfully recorded"

        # Should have some failed recordings
        assert (
            failing_collector.call_count > failing_collector.success_count
        ), "No metrics failed as expected"

        print(
            f"Successful metrics: {failing_collector.success_count}/{failing_collector.call_count}"
        )

    def test_metrics_collector_overhead(self, mock_collector):
        """Test the overhead of the mock metrics collector itself."""

        # Test direct calls to mock collector
        async def test_direct_calls():
            start_time = time.time()

            for _i in range(1000):
                await mock_collector.record_metric(
                    name="test_metric",
                    value=1.0,
                    metric_type=MetricType.COUNTER,
                    tags={"test": "value"},
                )

            end_time = time.time()
            return end_time - start_time

        # Run the test
        total_time = asyncio.run(test_direct_calls())

        # Calculate overhead
        avg_time_per_call = total_time / 1000
        print(f"Mock collector overhead per call: {avg_time_per_call:.6f}s")

        # Should be under 2ms per call
        assert (
            avg_time_per_call < 0.002
        ), f"Mock collector overhead {avg_time_per_call:.6f}s, expected < 0.002s"

        # Verify calls were recorded
        assert mock_collector.record_calls == 1000
        assert len(mock_collector.metrics) == 1000


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])
