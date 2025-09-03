#!/usr/bin/env python3
"""
Example script demonstrating the new log ingestion system.

This script shows how to:
1. Load configuration from files
2. Create and configure log sources
3. Set up the LogManager with callbacks
4. Handle different log sources (GCP, File System, etc.)
5. Monitor health and metrics
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_sre_agent.config.ingestion_config import (
    FileSystemConfig,
    IngestionConfigManager,
    SourceType,
)
from gemini_sre_agent.ingestion import LogManager
from gemini_sre_agent.ingestion.adapters import (
    FileSystemAdapter,
    GCPPubSubAdapter,
)
from gemini_sre_agent.ingestion.interfaces.resilience import (
    HyxResilientClient,
    create_resilience_config,
)
from gemini_sre_agent.ingestion.models import LogEntry

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class LogProcessor:
    """Example log processor that handles incoming log entries with Hyx resilience."""

    def __init__(self):
        self.processed_count = 0
        # Initialize Hyx resilience client
        self.resilience_config = create_resilience_config("development")
        self.resilient_client = HyxResilientClient(self.resilience_config)
        self.error_count = 0
        self.pii_detected_count = 0

    async def process_log(self, log_entry: LogEntry) -> None:
        """Process a single log entry with Hyx resilience patterns."""
        try:
            # Use Hyx resilience for processing operations
            await self.resilient_client.execute(
                lambda: self._process_log_with_resilience(log_entry)
            )

        except Exception as e:
            self.error_count += 1
            logger.error(f"Error processing log with resilience: {e}")

    async def _process_log_with_resilience(self, log_entry: LogEntry) -> None:
        """Internal method that performs the actual log processing."""
        self.processed_count += 1

        # Example processing logic
        logger.info(
            f"Processing log from {log_entry.source}: {log_entry.message[:100]}..."
        )

        # Check for PII (example)
        if log_entry.pii_detected:
            self.pii_detected_count += 1
            logger.warning(f"PII detected in log from {log_entry.source}")

        # Example: Extract billing information
        if "billing" in log_entry.message.lower():
            logger.info(f"Billing-related log detected: {log_entry.flow_id}")

        # Example: Check for errors
        if log_entry.level in ["ERROR", "CRITICAL"]:
            logger.error(f"Error log from {log_entry.source}: {log_entry.message}")

        # Simulate some processing time
        await asyncio.sleep(0.001)

    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return {
            "processed": self.processed_count,
            "errors": self.error_count,
            "pii_detected": self.pii_detected_count,
        }

    def get_resilience_stats(self) -> Dict[str, Any]:
        """Get resilience statistics from Hyx client."""
        return self.resilient_client.get_health_stats()


async def example_basic_usage():
    """Example 1: Basic usage with manual configuration."""
    logger.info("=== Example 1: Basic Usage ===")

    # Create a log processor
    processor = LogProcessor()

    # Create a simple callback function
    async def log_callback(log_entry: LogEntry):
        await processor.process_log(log_entry)

    # Create the log manager
    manager = LogManager(callback=log_callback)

    # Create a file system source manually
    fs_config = FileSystemConfig(
        name="example-logs",
        file_path="/tmp/example-logs",
        file_pattern="*.log",
        watch_mode=False,  # Don't watch for changes in this example
        encoding="utf-8",
        buffer_size=100,
        max_memory_mb=10,
    )

    # Create the adapter
    fs_adapter = FileSystemAdapter(fs_config)

    # Add source to manager
    await manager.add_source(fs_adapter)

    # Start the manager
    await manager.start()

    # Create some test log files
    test_log_dir = Path("/tmp/example-logs")
    test_log_dir.mkdir(exist_ok=True)

    # Write some test logs
    test_log_file = test_log_dir / "test.log"
    with open(test_log_file, "w") as f:
        f.write("2024-01-01 10:00:00 INFO Application started\n")
        f.write("2024-01-01 10:01:00 ERROR Failed to connect to database\n")
        f.write("2024-01-01 10:02:00 INFO User john.doe@example.com logged in\n")
        f.write("2024-01-01 10:03:00 WARNING High memory usage detected\n")

    # Process logs for a short time
    await asyncio.sleep(2)

    # Get stats
    stats = processor.get_stats()
    logger.info(f"Processing stats: {stats}")

    # Stop the manager
    await manager.stop()

    # Clean up
    test_log_file.unlink()
    test_log_dir.rmdir()


async def example_config_based():
    """Example 2: Configuration-based setup."""
    logger.info("=== Example 2: Configuration-Based Setup ===")

    # Create a log processor
    processor = LogProcessor()

    # Create a callback function
    async def log_callback(log_entry: LogEntry):
        await processor.process_log(log_entry)

    # Load configuration
    config_path = Path(__file__).parent / "ingestion_configs" / "basic_config.json"

    if not config_path.exists():
        logger.warning(f"Config file not found: {config_path}")
        logger.info("Skipping configuration-based example")
        return

    try:
        # Load configuration
        config_manager = IngestionConfigManager()
        config = config_manager.load_config(config_path)

        # Validate configuration
        errors = config_manager.validate_config()
        if errors:
            logger.error(f"Configuration errors: {errors}")
            return

        logger.info(f"Loaded configuration with {len(config.sources)} sources")

        # Create the log manager
        manager = LogManager(callback=log_callback)

        # Add sources based on configuration
        for source_config in config.get_enabled_sources():
            logger.info(
                f"Adding source: {source_config.name} (type: {source_config.type})"
            )

            if source_config.type == SourceType.FILE_SYSTEM:
                # Create file system adapter
                adapter = FileSystemAdapter(source_config)
                await manager.add_source(adapter)

            elif source_config.type == SourceType.GCP_PUBSUB:
                # Create GCP Pub/Sub adapter (if credentials are available)
                try:
                    adapter = GCPPubSubAdapter(source_config)
                    await manager.add_source(adapter)
                except Exception as e:
                    logger.warning(f"Could not create GCP Pub/Sub adapter: {e}")

        # Start the manager
        await manager.start()

        # Monitor for a short time
        await asyncio.sleep(3)

        # Get health status
        health = await manager.get_health_status()
        logger.info(f"Health status: {health}")

        # Get metrics
        metrics = await manager.get_metrics()
        logger.info(f"Metrics: {json.dumps(metrics, indent=2)}")

        # Get processing stats
        stats = processor.get_stats()
        logger.info(f"Processing stats: {stats}")

        # Stop the manager
        await manager.stop()

    except Exception as e:
        logger.error(f"Error in configuration-based example: {e}")


async def example_health_monitoring():
    """Example 3: Health monitoring and metrics."""
    logger.info("=== Example 3: Health Monitoring ===")

    # Create a log processor
    processor = LogProcessor()

    # Create a callback function
    async def log_callback(log_entry: LogEntry):
        await processor.process_log(log_entry)

    # Create the log manager
    manager = LogManager(callback=log_callback)

    # Create a file system source
    fs_config = FileSystemConfig(
        name="health-test-logs",
        file_path="/tmp/health-test-logs",
        file_pattern="*.log",
        watch_mode=False,
        encoding="utf-8",
        buffer_size=50,
        max_memory_mb=5,
    )

    fs_adapter = FileSystemAdapter(fs_config)
    await manager.add_source(fs_adapter)

    # Start the manager
    await manager.start()

    # Monitor health and metrics for a period
    for _i in range(5):
        await asyncio.sleep(1)

        # Get health status
        health = await manager.get_health_status()
        for source_name, health_status in health.items():
            status = "healthy" if health_status.is_healthy else "unhealthy"
            message = health_status.last_error or "No errors"
            logger.info(f"Source {source_name}: {status} - {message}")

        # Get metrics
        metrics = await manager.get_metrics()
        logger.info(
            f"Total processed: {metrics.get('manager', {}).get('total_processed', 0)}"
        )

        # Get processing stats
        stats = processor.get_stats()
        logger.info(f"Processor stats: {stats}")

    # Stop the manager
    await manager.stop()


async def example_error_handling():
    """Example 4: Error handling and resilience."""
    logger.info("=== Example 4: Error Handling ===")

    # Create a callback that sometimes fails
    error_count = 0

    async def error_prone_callback(log_entry: LogEntry):
        nonlocal error_count
        error_count += 1

        # Simulate errors for every 3rd log entry
        if error_count % 3 == 0:
            raise Exception(f"Simulated error processing log {error_count}")

        logger.info(f"Successfully processed log {error_count}")

    # Create the log manager
    manager = LogManager(callback=error_prone_callback)

    # Create a file system source
    fs_config = FileSystemConfig(
        name="error-test-logs",
        file_path="/tmp/error-test-logs",
        file_pattern="*.log",
        watch_mode=False,
        encoding="utf-8",
        buffer_size=10,
        max_memory_mb=5,
        max_retries=2,  # Allow some retries
        retry_delay=0.1,  # Quick retry for demo
    )

    fs_adapter = FileSystemAdapter(fs_config)
    await manager.add_source(fs_adapter)

    # Start the manager
    await manager.start()

    # Create test logs
    test_log_dir = Path("/tmp/error-test-logs")
    test_log_dir.mkdir(exist_ok=True)

    test_log_file = test_log_dir / "error-test.log"
    with open(test_log_file, "w") as f:
        for i in range(10):
            f.write(f"2024-01-01 10:00:{i:02d} INFO Test log message {i}\n")

    # Process logs
    await asyncio.sleep(3)

    # Get metrics to see error handling in action
    metrics = await manager.get_metrics()
    logger.info(f"Error handling metrics: {json.dumps(metrics, indent=2)}")

    # Stop the manager
    await manager.stop()

    # Clean up
    test_log_file.unlink()
    test_log_dir.rmdir()


async def example_hyx_resilience():
    """Example 5: Demonstrate Hyx resilience patterns."""
    logger.info("=== Example 5: Hyx Resilience Patterns ===")

    # Create a processor with Hyx resilience
    processor = LogProcessor()

    # Show initial resilience stats
    logger.info("Initial resilience configuration:")
    resilience_stats = processor.get_resilience_stats()
    logger.info(f"Resilience stats: {json.dumps(resilience_stats, indent=2)}")

    # Create some test log entries
    test_logs = [
        LogEntry(
            message="User login successful",
            level="INFO",
            source="auth-service",
            timestamp=1234567890.0,
            flow_id="flow-1",
        ),
        LogEntry(
            "Database connection failed", "ERROR", "db-service", 1234567891.0, "flow-2"
        ),
        LogEntry(
            "Billing transaction processed",
            "INFO",
            "billing-service",
            1234567892.0,
            "flow-3",
        ),
    ]

    # Process logs with resilience
    logger.info("Processing logs with Hyx resilience patterns...")
    for i, log_entry in enumerate(test_logs):
        try:
            await processor.process_log(log_entry)
            logger.info(f"Successfully processed log {i+1}")
        except Exception as e:
            logger.error(f"Failed to process log {i+1}: {e}")

    # Show final stats
    logger.info("Final processing stats:")
    stats = processor.get_stats()
    logger.info(f"Processing stats: {json.dumps(stats, indent=2)}")

    logger.info("Final resilience stats:")
    final_resilience_stats = processor.get_resilience_stats()
    logger.info(f"Resilience stats: {json.dumps(final_resilience_stats, indent=2)}")

    logger.info("Hyx resilience patterns demonstrated successfully!")


async def main():
    """Run all examples."""
    logger.info("Starting Log Ingestion System Examples")
    logger.info("=" * 50)

    try:
        # Run examples
        await example_basic_usage()
        await asyncio.sleep(1)

        await example_config_based()
        await asyncio.sleep(1)

        await example_health_monitoring()
        await asyncio.sleep(1)

        await example_error_handling()
        await asyncio.sleep(1)

        await example_hyx_resilience()

        logger.info("=" * 50)
        logger.info("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Error running examples: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
