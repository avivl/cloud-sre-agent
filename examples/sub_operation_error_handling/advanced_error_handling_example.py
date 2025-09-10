#!/usr/bin/env python3
"""
Advanced Sub-Operation Error Handling Example

This example demonstrates advanced error handling scenarios including:
- Circuit breaker patterns
- Retry strategies with exponential backoff
- Error classification and handling
- Metrics collection and monitoring
- Health checks and recovery
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any

# Import the error handling components
from gemini_sre_agent.source_control.error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingFactory,
    RetryConfig,
)
from gemini_sre_agent.source_control.metrics.collectors import MetricsCollector
from gemini_sre_agent.source_control.providers.local.local_file_operations import (
    LocalFileOperations,
)
from gemini_sre_agent.source_control.providers.sub_operation_config import (
    SubOperationConfig,
)


class FailingFileOperations(LocalFileOperations):
    """A test implementation that can simulate various failure scenarios."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.failure_count = 0
        self.max_failures = 3
        self.should_fail = True

    async def _simulate_failure(self, operation_name: str):
        """Simulate various types of failures."""
        if not self.should_fail:
            return

        self.failure_count += 1

        if self.failure_count <= self.max_failures:
            if operation_name == "timeout_operation":
                await asyncio.sleep(5)  # Simulate timeout
            elif operation_name == "network_error":
                raise ConnectionError("Simulated network error")
            elif operation_name == "permission_error":
                raise PermissionError("Simulated permission error")
            elif operation_name == "temporary_error":
                raise RuntimeError("Simulated temporary error")
            else:
                raise Exception(f"Simulated error for {operation_name}")

    async def get_file_content(self, path: str) -> str:
        """Override to add failure simulation."""
        await self._simulate_failure("get_file_content")
        return await super().get_file_content(path)

    async def apply_remediation(
        self, file_path: str, remediation: str, commit_message: str
    ) -> Any:
        """Override to add failure simulation."""
        await self._simulate_failure("apply_remediation")
        return await super().apply_remediation(file_path, remediation, commit_message)


async def circuit_breaker_example():
    """Demonstrate circuit breaker functionality."""
    print("=== Circuit Breaker Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_circuit_breaker")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create error handling components with circuit breaker
        error_handling_factory = ErrorHandlingFactory()
        error_handling_components = error_handling_factory.create_error_handling_system(
            provider_name="local",
            config={
                "circuit_breaker": {
                    "failure_threshold": 3,  # Open after 3 failures
                    "recovery_timeout": 10.0,  # Try to close after 10 seconds
                    "timeout": 2.0,  # 2 second timeout per operation
                },
                "retry": {
                    "max_retries": 1,  # Minimal retries to see circuit breaker effect
                    "base_delay": 0.5,
                    "max_delay": 1.0,
                    "backoff_factor": 1.5,
                },
            },
        )

        # Create sub-operation configuration
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=10.0,
                timeout=2.0,
            ),
            retry_config=RetryConfig(
                max_retries=1,
                base_delay=0.5,
                max_delay=1.0,
                backoff_factor=1.5,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
        )

        # Initialize failing file operations
        file_ops = FailingFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=False,
            backup_directory=None,
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
        )

        print("1. Testing circuit breaker with consecutive failures...")

        # Try to perform operations that will fail
        for i in range(5):
            try:
                print(f"   Attempt {i+1}: ", end="")
                result = await file_ops.get_file_content("test.txt")
                print(f"SUCCESS - Content: '{result}'")
            except Exception as e:
                print(f"FAILED - Error: {type(e).__name__}: {e}")

            # Small delay between attempts
            await asyncio.sleep(0.1)

        print("\n2. Waiting for circuit breaker recovery...")
        await asyncio.sleep(12)  # Wait for recovery timeout

        print("3. Testing circuit breaker after recovery...")
        file_ops.should_fail = False  # Stop failing

        for i in range(3):
            try:
                print(f"   Recovery attempt {i+1}: ", end="")
                result = await file_ops.get_file_content("test.txt")
                print(f"SUCCESS - Content: '{result}'")
            except Exception as e:
                print(f"FAILED - Error: {type(e).__name__}: {e}")

            await asyncio.sleep(0.1)

    except Exception as e:
        print(f"Error in circuit breaker example: {e}")
        logger.error(f"Circuit breaker example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def retry_strategies_example():
    """Demonstrate different retry strategies."""
    print("\n=== Retry Strategies Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_retry_strategies")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Test different retry configurations
        retry_configs = [
            {
                "name": "Aggressive Retry",
                "config": {
                    "max_retries": 5,
                    "base_delay": 0.1,
                    "max_delay": 2.0,
                    "backoff_factor": 1.2,
                },
            },
            {
                "name": "Conservative Retry",
                "config": {
                    "max_retries": 2,
                    "base_delay": 1.0,
                    "max_delay": 5.0,
                    "backoff_factor": 2.0,
                },
            },
            {
                "name": "No Retry",
                "config": {
                    "max_retries": 0,
                    "base_delay": 0.1,
                    "max_delay": 1.0,
                    "backoff_factor": 1.0,
                },
            },
        ]

        for retry_test in retry_configs:
            print(f"\n1. Testing {retry_test['name']}...")

            # Create error handling components
            error_handling_factory = ErrorHandlingFactory()
            error_handling_components = error_handling_factory.create_error_handling_system(
                provider_name="local",
                config={
                    "circuit_breaker": {
                        "failure_threshold": 10,  # High threshold to avoid circuit breaker
                        "recovery_timeout": 30.0,
                        "timeout": 5.0,
                    },
                    "retry": retry_test["config"],
                },
            )

            # Create sub-operation configuration
            config = SubOperationConfig(
                operation_name="file_operations",
                provider_type="local",
                error_handling_enabled=True,
                circuit_breaker_config=CircuitBreakerConfig(
                    failure_threshold=10,
                    recovery_timeout=30.0,
                    timeout=5.0,
                ),
                retry_config=RetryConfig(**retry_test["config"]),
                log_operations=True,
                log_errors=True,
                log_performance=True,
            )

            # Initialize failing file operations
            file_ops = FailingFileOperations(
                root_path=temp_dir,
                default_encoding="utf-8",
                backup_files=False,
                backup_directory=None,
                logger=logger,
                error_handling_components=error_handling_components,
                config=config,
            )

            # Reset failure count
            file_ops.failure_count = 0
            file_ops.max_failures = 3  # Will fail 3 times then succeed

            start_time = time.time()

            try:
                result = await file_ops.apply_remediation(
                    f"retry_test_{retry_test['name'].lower().replace(' ', '_')}.txt",
                    "Retry test content",
                    "Retry test commit",
                )
                elapsed = time.time() - start_time
                print(f"   Result: SUCCESS after {elapsed:.2f}s - {result.success}")
            except Exception as e:
                elapsed = time.time() - start_time
                print(
                    f"   Result: FAILED after {elapsed:.2f}s - {type(e).__name__}: {e}"
                )

            # Show performance stats
            stats = file_ops.get_performance_stats()
            print(f"   Performance stats: {stats}")

    except Exception as e:
        print(f"Error in retry strategies example: {e}")
        logger.error(f"Retry strategies example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def metrics_collection_example():
    """Demonstrate metrics collection and monitoring."""
    print("\n=== Metrics Collection Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_metrics")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create metrics collector
        metrics_collector = MetricsCollector(
            max_series=1000,
            max_points_per_series=1000,
            retention_hours=24,
            cleanup_interval_minutes=60,
        )

        # Start background processing
        await metrics_collector.start_background_processing()

        # Create error handling components with metrics
        error_handling_factory = ErrorHandlingFactory()
        error_handling_components = error_handling_factory.create_error_handling_system(
            provider_name="local",
            config={
                "circuit_breaker": {
                    "failure_threshold": 5,
                    "recovery_timeout": 30.0,
                    "timeout": 10.0,
                },
                "retry": {
                    "max_retries": 3,
                    "base_delay": 1.0,
                    "max_delay": 10.0,
                    "backoff_factor": 2.0,
                },
            },
        )

        # Create sub-operation configuration with metrics enabled
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=30.0,
                timeout=10.0,
            ),
            retry_config=RetryConfig(
                max_retries=3,
                base_delay=1.0,
                max_delay=10.0,
                backoff_factor=2.0,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
            enable_metrics=True,
        )

        # Initialize file operations
        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=False,
            backup_directory=None,
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
        )

        print("1. Performing operations with metrics collection...")

        # Perform various operations
        operations = [
            (
                "create_file",
                lambda: file_ops.apply_remediation(
                    "metrics_test.txt", "Test content", "Test commit"
                ),
            ),
            ("read_file", lambda: file_ops.get_file_content("metrics_test.txt")),
            ("check_exists", lambda: file_ops.file_exists("metrics_test.txt")),
            ("get_info", lambda: file_ops.get_file_info("metrics_test.txt")),
            ("list_files", lambda: file_ops.list_files()),
        ]

        for op_name, op_func in operations:
            try:
                print(f"   Executing {op_name}...")
                await op_func()
                print(f"   {op_name}: SUCCESS")
            except Exception as e:
                print(f"   {op_name}: FAILED - {type(e).__name__}: {e}")

            # Small delay between operations
            await asyncio.sleep(0.1)

        print("\n2. Collecting metrics...")

        # Wait a bit for metrics to be processed
        await asyncio.sleep(2)

        # Get metrics summary
        metrics_summary = await metrics_collector.get_metrics_summary()
        print(f"   Total series: {metrics_summary['total_series']}")
        print(f"   Total points: {metrics_summary['total_points']}")

        # Stop background processing
        await metrics_collector.stop_background_processing()

    except Exception as e:
        print(f"Error in metrics collection example: {e}")
        logger.error(f"Metrics collection example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def health_check_example():
    """Demonstrate health checks and recovery."""
    print("\n=== Health Check Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_health_check")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create error handling components
        error_handling_factory = ErrorHandlingFactory()
        error_handling_components = error_handling_factory.create_error_handling_system(
            provider_name="local",
            config={
                "circuit_breaker": {
                    "failure_threshold": 3,
                    "recovery_timeout": 10.0,
                    "timeout": 5.0,
                },
                "retry": {
                    "max_retries": 2,
                    "base_delay": 1.0,
                    "max_delay": 5.0,
                    "backoff_factor": 2.0,
                },
            },
        )

        # Create sub-operation configuration
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=10.0,
                timeout=5.0,
            ),
            retry_config=RetryConfig(
                max_retries=2,
                base_delay=1.0,
                max_delay=5.0,
                backoff_factor=2.0,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
        )

        # Initialize file operations
        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=False,
            backup_directory=None,
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
        )

        print("1. Testing health check...")

        # Perform health check
        health = await file_ops.health_check()
        print(f"   Health check result: {health}")

        print("2. Testing health check after operations...")

        # Perform some operations
        await file_ops.apply_remediation(
            "health_test.txt", "Health test content", "Health test commit"
        )
        await file_ops.get_file_content("health_test.txt")

        # Check health again
        health = await file_ops.health_check()
        print(f"   Health check after operations: {health}")

        print("3. Testing configuration updates...")

        # Update configuration
        new_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=5,  # Increased threshold
                recovery_timeout=15.0,  # Increased recovery time
                timeout=8.0,  # Increased timeout
            ),
            retry_config=RetryConfig(
                max_retries=5,  # Increased retries
                base_delay=0.5,  # Decreased base delay
                max_delay=15.0,  # Increased max delay
                backoff_factor=1.8,  # Different backoff factor
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
        )

        file_ops.update_config(new_config)
        print("   Configuration updated successfully")

        # Test with new configuration
        health = await file_ops.health_check()
        print(f"   Health check with new config: {health}")

        print("4. Testing performance statistics...")

        # Get performance stats
        stats = file_ops.get_performance_stats()
        print(f"   Performance stats: {stats}")

        # Reset stats
        file_ops.reset_stats()
        print("   Performance stats reset")

        # Get stats after reset
        stats = file_ops.get_performance_stats()
        print(f"   Performance stats after reset: {stats}")

    except Exception as e:
        print(f"Error in health check example: {e}")
        logger.error(f"Health check example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def main():
    """Run all advanced examples."""
    print("Advanced Sub-Operation Error Handling Examples")
    print("=" * 60)

    try:
        await circuit_breaker_example()
        await retry_strategies_example()
        await metrics_collection_example()
        await health_check_example()

        print("\n" + "=" * 60)
        print("All advanced examples completed successfully!")

    except Exception as e:
        print(f"Error running advanced examples: {e}")


if __name__ == "__main__":
    asyncio.run(main())
