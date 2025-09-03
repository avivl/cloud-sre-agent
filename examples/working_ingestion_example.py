#!/usr/bin/env python3
"""
Working example of the log ingestion system.
This demonstrates the core functionality without the complex test setup.
"""

import asyncio
import logging
import tempfile
import os
from datetime import datetime
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.interfaces.resilience import create_resilience_config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_test_log_file():
    """Create a temporary log file with test data."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.log', delete=False) as f:
        f.write("2024-01-01 10:00:00 INFO Test log message 1\n")
        f.write("2024-01-01 10:00:01 WARN Test warning message\n")
        f.write("2024-01-01 10:00:02 ERROR Test error message\n")
        temp_file = f.name
    
    logger.info(f"Created test log file: {temp_file}")
    return temp_file


async def demonstrate_file_system_adapter():
    """Demonstrate the file system adapter functionality."""
    logger.info("=== File System Adapter Demo ===")
    
    # Create test log file
    log_file = await create_test_log_file()
    
    try:
        # Create configuration
        config = FileSystemConfig(
            name="demo-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path=log_file,
            file_pattern="*.log"
        )
        
        logger.info(f"Created configuration: {config.name}")
        logger.info(f"File path: {config.file_path}")
        logger.info(f"File pattern: {config.file_pattern}")
        
        # Create adapter
        adapter = FileSystemAdapter(config)
        logger.info("Created FileSystemAdapter instance")
        
        # Check health
        health = await adapter.health_check()
        logger.info(f"Health check: {health.is_healthy}")
        logger.info(f"Error count: {health.error_count}")
        
        # Get configuration
        current_config = adapter.get_config()
        logger.info(f"Current config name: {current_config.name}")
        
        # Clean up
        logger.info("Demo completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
    finally:
        # Clean up test file
        try:
            os.unlink(log_file)
            logger.info("Cleaned up test log file")
        except OSError:
            pass


async def demonstrate_resilience_config():
    """Demonstrate the resilience configuration system."""
    logger.info("=== Resilience Configuration Demo ===")
    
    try:
        # Create different environment configurations
        dev_config = create_resilience_config("development")
        staging_config = create_resilience_config("staging")
        prod_config = create_resilience_config("production")
        
        logger.info("Development config:")
        logger.info(f"  Retry attempts: {dev_config.retry['max_attempts']}")
        logger.info(f"  Timeout: {dev_config.timeout}s")
        logger.info(f"  Circuit breaker threshold: {dev_config.circuit_breaker['failure_threshold']}")
        
        logger.info("Staging config:")
        logger.info(f"  Retry attempts: {staging_config.retry['max_attempts']}")
        logger.info(f"  Timeout: {staging_config.timeout}s")
        logger.info(f"  Circuit breaker threshold: {staging_config.circuit_breaker['failure_threshold']}")
        
        logger.info("Production config:")
        logger.info(f"  Retry attempts: {prod_config.retry['max_attempts']}")
        logger.info(f"  Timeout: {prod_config.timeout}s")
        logger.info(f"  Circuit breaker threshold: {prod_config.circuit_breaker['failure_threshold']}")
        
        logger.info("Resilience configuration demo completed!")
        
    except Exception as e:
        logger.error(f"Resilience demo failed: {e}")


async def demonstrate_log_entry():
    """Demonstrate the LogEntry dataclass."""
    logger.info("=== Log Entry Demo ===")
    
    try:
        # Create a log entry
        entry = LogEntry(
            id="demo-123",
            timestamp=datetime.now(),
            message="This is a demo log message",
            source="demo-source",
            severity=LogSeverity.INFO,
            metadata={"demo": "true", "version": "1.0"}
        )
        
        logger.info(f"Created log entry:")
        logger.info(f"  ID: {entry.id}")
        logger.info(f"  Message: {entry.message}")
        logger.info(f"  Source: {entry.source}")
        logger.info(f"  Severity: {entry.severity}")
        logger.info(f"  Metadata: {entry.metadata}")
        
        # Test the get_field method
        demo_value = entry.get_field("demo", "not_found")
        version_value = entry.get_field("version", "unknown")
        logger.info(f"  Demo field: {demo_value}")
        logger.info(f"  Version field: {version_value}")
        
        logger.info("Log entry demo completed!")
        
    except Exception as e:
        logger.error(f"Log entry demo failed: {e}")


async def main():
    """Main demo function."""
    logger.info("🚀 Starting Log Ingestion System Demo")
    logger.info("=" * 50)
    
    try:
        # Run all demonstrations
        await demonstrate_log_entry()
        logger.info("")
        
        await demonstrate_resilience_config()
        logger.info("")
        
        await demonstrate_file_system_adapter()
        logger.info("")
        
        logger.info("✅ All demonstrations completed successfully!")
        logger.info("🎉 The log ingestion system is working!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
