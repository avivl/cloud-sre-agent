# examples/comprehensive_ingestion_example.py

"""
Comprehensive example demonstrating the enhanced log ingestion system with:
- Multiple log source adapters (File System, AWS CloudWatch, Kubernetes)
- Memory queue system for file system consumption
- Resilience patterns and error handling
- Configuration management
- Health monitoring and metrics
"""

import asyncio
import logging
import os
import tempfile
from datetime import datetime, timezone

from gemini_sre_agent.config.ingestion_config import (
    AWSCloudWatchConfig,
    FileSystemConfig,
    KubernetesConfig,
    SourceType,
)
from gemini_sre_agent.ingestion import (
    AWSCloudWatchAdapter,
    KubernetesAdapter,
    LogEntry,
    LogManager,
    LogSeverity,
    MemoryQueue,
    QueueConfig,
    QueuedFileSystemAdapter,
    create_resilience_config,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LogProcessor:
    """Example log processor that handles incoming log entries."""

    def __init__(self):
        self.processed_count = 0
        self.error_count = 0

    async def process_log(self, log_entry: LogEntry) -> None:
        """Process a single log entry."""
        try:
            self.processed_count += 1

            # Example processing logic
            if log_entry.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL]:
                logger.warning(f"High severity log detected: {log_entry.message}")

            # Simulate some processing time
            await asyncio.sleep(0.001)

            if self.processed_count % 100 == 0:
                logger.info(f"Processed {self.processed_count} log entries")

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error processing log entry {log_entry.id}: {e}")


async def create_test_log_file() -> str:
    """Create a temporary log file with sample data."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        # Write sample log entries
        for i in range(50):
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
            severity = ["INFO", "WARN", "ERROR", "DEBUG"][i % 4]
            message = f"Test log message {i} with severity {severity}"
            f.write(f"{timestamp} {severity} {message}\n")

        return f.name


async def demo_memory_queue():
    """Demonstrate the memory queue system."""
    logger.info("=== Memory Queue Demo ===")

    # Create queue configuration
    queue_config = QueueConfig(
        max_size=1000,
        max_memory_mb=10,
        batch_size=50,
        flush_interval_seconds=1.0,
        enable_metrics=True,
    )

    # Create and start memory queue
    async with MemoryQueue(queue_config) as queue:
        # Enqueue some sample log entries
        for i in range(25):
            log_entry = LogEntry(
                id=f"test-{i}",
                timestamp=datetime.now(timezone.utc),
                message=f"Sample log message {i}",
                source="memory-queue-demo",
                severity=LogSeverity.INFO,
                metadata={"batch": "demo"},
            )

            success = await queue.enqueue(log_entry)
            if not success:
                logger.warning(f"Failed to enqueue log entry {i}")

        # Dequeue and process entries
        processed = 0
        while processed < 25:
            entries = await queue.dequeue(max_items=10)
            if not entries:
                break

            for entry in entries:
                logger.info(f"Processed: {entry.message}")
                processed += 1

        # Show queue statistics
        stats = queue.get_stats()
        logger.info(f"Queue Stats: {stats}")


async def demo_queued_file_system():
    """Demonstrate the queued file system adapter."""
    logger.info("=== Queued File System Demo ===")

    # Create test log file
    log_file = await create_test_log_file()

    try:
        # Create file system configuration
        config = FileSystemConfig(
            name="demo-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path=log_file,
            file_pattern="*.log",
            watch_mode=True,
            encoding="utf-8",
            buffer_size=8192,
            max_memory_mb=5,
        )

        # Create and start adapter
        adapter = QueuedFileSystemAdapter(config)
        await adapter.start()

        # Process logs for a short time
        processed_count = 0
        start_time = datetime.now(timezone.utc)

        async for log_entry in adapter.get_logs():
            logger.info(f"File System Log: {log_entry.message}")
            processed_count += 1

            # Stop after processing 10 entries or 5 seconds
            if (
                processed_count >= 10
                or (datetime.now(timezone.utc) - start_time).seconds >= 5
            ):
                break

        # Show health metrics
        health = await adapter.health_check()
        metrics = await adapter.get_health_metrics()

        logger.info(f"File System Health: {health.is_healthy}")
        logger.info(f"File System Metrics: {metrics}")

        await adapter.stop()

    finally:
        # Cleanup
        try:
            os.unlink(log_file)
        except OSError:
            pass


async def demo_aws_cloudwatch():
    """Demonstrate AWS CloudWatch adapter (mock)."""
    logger.info("=== AWS CloudWatch Demo ===")

    # Create AWS CloudWatch configuration
    config = AWSCloudWatchConfig(
        name="demo-aws-source",
        type=SourceType.AWS_CLOUDWATCH,
        log_group_name="demo-log-group",
        log_stream_name="demo-stream",
        region="us-east-1",
        credentials_profile=None,
        poll_interval=30,
        max_events=100,
    )

    try:
        # Create adapter (this will fail if boto3 is not available)
        adapter = AWSCloudWatchAdapter(config)
        logger.info("AWS CloudWatch adapter created successfully")

        # Show configuration
        logger.info(f"AWS Config: {adapter.get_config()}")

    except ImportError:
        logger.info("AWS CloudWatch adapter requires boto3 (not installed)")


async def demo_kubernetes():
    """Demonstrate Kubernetes adapter (mock)."""
    logger.info("=== Kubernetes Demo ===")

    # Create Kubernetes configuration
    config = KubernetesConfig(
        name="demo-k8s-source",
        type=SourceType.KUBERNETES,
        namespace="default",
        label_selector="app=demo",
        kubeconfig_path=None,
        max_pods=10,
        tail_lines=100,
    )

    try:
        # Create adapter (this will fail if kubernetes client is not available)
        adapter = KubernetesAdapter(config)
        logger.info("Kubernetes adapter created successfully")

        # Show configuration
        logger.info(f"Kubernetes Config: {adapter.get_config()}")

    except ImportError:
        logger.info("Kubernetes adapter requires kubernetes client (not installed)")


async def demo_log_manager():
    """Demonstrate the LogManager with multiple sources."""
    logger.info("=== Log Manager Demo ===")

    # Create log processor
    processor = LogProcessor()

    # Create log manager with callback
    manager = LogManager(callback=processor.process_log)

    # Create test log file
    log_file = await create_test_log_file()

    try:
        # Create file system adapter
        fs_config = FileSystemConfig(
            name="manager-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path=log_file,
            file_pattern="*.log",
            watch_mode=True,
            encoding="utf-8",
            buffer_size=8192,
            max_memory_mb=5,
        )

        fs_adapter = QueuedFileSystemAdapter(fs_config)

        # Add source to manager
        await manager.add_source(fs_adapter)

        # Start manager
        await manager.start()

        # Let it run for a few seconds
        await asyncio.sleep(3)

        # Get health status
        health_status = await manager.get_health_status()
        logger.info(f"Manager Health Status: {health_status}")

        # Get metrics
        metrics = await manager.get_metrics()
        logger.info(f"Manager Metrics: {metrics}")

        # Stop manager
        await manager.stop()

        logger.info(
            f"Processed {processor.processed_count} logs with {processor.error_count} errors"
        )

    finally:
        # Cleanup
        try:
            os.unlink(log_file)
        except OSError:
            pass


async def demo_resilience_config():
    """Demonstrate resilience configuration."""
    logger.info("=== Resilience Configuration Demo ===")

    # Create resilience configurations for different environments
    dev_config = create_resilience_config(environment="development")
    staging_config = create_resilience_config(environment="staging")
    prod_config = create_resilience_config(environment="production")

    logger.info(f"Development Config: {dev_config}")
    logger.info(f"Staging Config: {staging_config}")
    logger.info(f"Production Config: {prod_config}")


async def main():
    """Run all demonstrations."""
    logger.info("Starting comprehensive log ingestion system demo...")

    try:
        # Run individual demos
        await demo_memory_queue()
        await asyncio.sleep(1)

        await demo_queued_file_system()
        await asyncio.sleep(1)

        await demo_aws_cloudwatch()
        await asyncio.sleep(1)

        await demo_kubernetes()
        await asyncio.sleep(1)

        await demo_resilience_config()
        await asyncio.sleep(1)

        await demo_log_manager()

        logger.info("Demo completed successfully!")

    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
