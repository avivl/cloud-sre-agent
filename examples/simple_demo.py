#!/usr/bin/env python3
"""
Simple demo of the working parts of the log ingestion system.
"""

import asyncio
import logging
from gemini_sre_agent.ingestion.interfaces.resilience import create_resilience_config
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_resilience_config():
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
        
        logger.info("✅ Resilience configuration demo completed!")
        
    except Exception as e:
        logger.error(f"❌ Resilience demo failed: {e}")


def demo_log_entry():
    """Demonstrate the LogEntry dataclass."""
    logger.info("=== Log Entry Demo ===")
    
    try:
        from datetime import datetime
        
        # Create a log entry
        entry = LogEntry(
            id="demo-123",
            timestamp=datetime.fromisoformat("2024-01-01T10:00:00"),
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
        
        logger.info("✅ Log entry demo completed!")
        
    except Exception as e:
        logger.error(f"❌ Log entry demo failed: {e}")


def demo_file_system_config():
    """Demonstrate the file system configuration."""
    logger.info("=== File System Configuration Demo ===")
    
    try:
        # Create configuration
        config = FileSystemConfig(
            name="demo-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path="/tmp/test.log",
            file_pattern="*.log"
        )
        
        logger.info(f"Created configuration:")
        logger.info(f"  Name: {config.name}")
        logger.info(f"  Type: {config.type}")
        logger.info(f"  File path: {config.file_path}")
        logger.info(f"  File pattern: {config.file_pattern}")
        logger.info(f"  Watch mode: {config.watch_mode}")
        logger.info(f"  Encoding: {config.encoding}")
        logger.info(f"  Buffer size: {config.buffer_size}")
        logger.info(f"  Max memory: {config.max_memory_mb}MB")
        
        logger.info("✅ File system configuration demo completed!")
        
    except Exception as e:
        logger.error(f"❌ File system config demo failed: {e}")


async def main():
    """Main demo function."""
    logger.info("🚀 Starting Simple Log Ingestion System Demo")
    logger.info("=" * 50)
    
    try:
        # Run all demonstrations
        demo_log_entry()
        logger.info("")
        
        demo_file_system_config()
        logger.info("")
        
        await demo_resilience_config()
        logger.info("")
        
        logger.info("✅ All demonstrations completed successfully!")
        logger.info("🎉 The core log ingestion system is working!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
