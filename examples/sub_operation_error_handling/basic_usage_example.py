#!/usr/bin/env python3
"""
Basic Sub-Operation Error Handling Example

This example demonstrates the basic usage of sub-operation error handling
with different providers (GitHub, GitLab, Local) and various error scenarios.
"""

import asyncio
import logging
from pathlib import Path

# Import the error handling components
from gemini_sre_agent.source_control.error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingFactory,
    RetryConfig,
)
from gemini_sre_agent.source_control.providers.local.local_file_operations import (
    LocalFileOperations,
)
from gemini_sre_agent.source_control.providers.sub_operation_config import (
    SubOperationConfig,
    SubOperationConfigManager,
)

# Note: GitHub and GitLab providers would require actual API credentials
# from gemini_sre_agent.source_control.providers.github.github_file_operations import (
#     GitHubFileOperations,
# )
# from gemini_sre_agent.source_control.providers.gitlab.gitlab_file_operations import (
#     GitLabFileOperations,
# )


async def basic_local_file_operations_example():
    """Demonstrate basic local file operations with error handling."""
    print("=== Basic Local File Operations Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_example")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create error handling components
        error_handling_factory = ErrorHandlingFactory()
        error_handling_components = error_handling_factory.create_error_handling_system(
            provider_name="local",
            config={
                "circuit_breaker": {
                    "failure_threshold": 3,
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

        # Create sub-operation configuration
        config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=3,
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
        )

        # Initialize file operations with error handling
        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=True,
            backup_directory=str(temp_dir / "backups"),
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
        )

        # Test basic operations
        print("1. Testing file content retrieval...")
        content = await file_ops.get_file_content("test.txt")
        print(f"   File content: '{content}'")

        print("2. Testing file existence check...")
        exists = await file_ops.file_exists("test.txt")
        print(f"   File exists: {exists}")

        print("3. Testing file creation...")
        result = await file_ops.apply_remediation(
            "test.txt", "Hello, World!", "Initial commit"
        )
        print(f"   Remediation result: {result.success} - {result.message}")

        print("4. Testing file content after creation...")
        content = await file_ops.get_file_content("test.txt")
        print(f"   File content: '{content}'")

        print("5. Testing health check...")
        health = await file_ops.health_check()
        print(f"   Health check: {health}")

        print("6. Testing performance stats...")
        stats = file_ops.get_performance_stats()
        print(f"   Performance stats: {stats}")

    except Exception as e:
        print(f"Error in basic example: {e}")
        logger.error(f"Basic example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def error_scenarios_example():
    """Demonstrate various error scenarios and how they're handled."""
    print("\n=== Error Scenarios Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_error_example")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Create error handling components with aggressive settings for testing
        error_handling_factory = ErrorHandlingFactory()
        error_handling_components = error_handling_factory.create_error_handling_system(
            provider_name="local",
            config={
                "circuit_breaker": {
                    "failure_threshold": 2,  # Low threshold for testing
                    "recovery_timeout": 5.0,  # Short recovery time
                    "timeout": 2.0,  # Short timeout
                },
                "retry": {
                    "max_retries": 2,  # Few retries for testing
                    "base_delay": 0.5,  # Short delays
                    "max_delay": 2.0,
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
                failure_threshold=2,
                recovery_timeout=5.0,
                timeout=2.0,
            ),
            retry_config=RetryConfig(
                max_retries=2,
                base_delay=0.5,
                max_delay=2.0,
                backoff_factor=1.5,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
        )

        # Initialize file operations
        file_ops = LocalFileOperations(
            root_path=temp_dir,
            default_encoding="utf-8",
            backup_files=False,  # Disable backups for this test
            backup_directory=None,
            logger=logger,
            error_handling_components=error_handling_components,
            config=config,
        )

        print("1. Testing normal operation...")
        result = await file_ops.apply_remediation(
            "normal.txt", "Normal content", "Normal commit"
        )
        print(f"   Normal operation: {result.success}")

        print("2. Testing file operations on non-existent directory...")
        # This should work fine - the operation will create the directory
        result = await file_ops.apply_remediation(
            "subdir/test.txt", "Subdirectory content", "Subdirectory commit"
        )
        print(f"   Subdirectory operation: {result.success}")

        print("3. Testing error handling with disabled error handling...")
        # Temporarily disable error handling
        file_ops.update_config(
            SubOperationConfig(
                operation_name="file_operations",
                provider_type="local",
                error_handling_enabled=False,  # Disable error handling
            )
        )

        result = await file_ops.apply_remediation(
            "no_error_handling.txt",
            "No error handling content",
            "No error handling commit",
        )
        print(f"   Disabled error handling: {result.success}")

        # Re-enable error handling
        file_ops.update_config(config)

        print("4. Testing performance tracking...")
        # Perform several operations to generate performance data
        for i in range(5):
            await file_ops.apply_remediation(
                f"perf_test_{i}.txt",
                f"Performance test content {i}",
                f"Performance test commit {i}",
            )

        stats = file_ops.get_performance_stats()
        print(f"   Performance stats after 5 operations: {stats}")

    except Exception as e:
        print(f"Error in error scenarios example: {e}")
        logger.error(f"Error scenarios example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def configuration_management_example():
    """Demonstrate configuration management for sub-operations."""
    print("\n=== Configuration Management Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Create configuration manager
        config_manager = SubOperationConfigManager()

        # Register different configurations for different providers
        github_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="github",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=5,
                recovery_timeout=60.0,
                timeout=30.0,
            ),
            retry_config=RetryConfig(
                max_retries=5,
                base_delay=2.0,
                max_delay=30.0,
                backoff_factor=2.0,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
            enable_metrics=True,
        )

        gitlab_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="gitlab",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=3,
                recovery_timeout=45.0,
                timeout=20.0,
            ),
            retry_config=RetryConfig(
                max_retries=3,
                base_delay=1.5,
                max_delay=20.0,
                backoff_factor=1.8,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=False,  # Disable performance logging for GitLab
            enable_metrics=True,
        )

        local_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=10,  # Higher threshold for local operations
                recovery_timeout=10.0,
                timeout=5.0,
            ),
            retry_config=RetryConfig(
                max_retries=2,  # Fewer retries for local operations
                base_delay=0.5,
                max_delay=5.0,
                backoff_factor=1.5,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
            enable_metrics=False,  # Disable metrics for local operations
        )

        # Register configurations
        config_manager.register_config(github_config)
        config_manager.register_config(gitlab_config)
        config_manager.register_config(local_config)

        print("1. Registered configurations for GitHub, GitLab, and Local providers")

        # List all configurations
        config_keys = config_manager.list_configs()
        print(f"2. Total configurations: {len(config_keys)}")
        for key in config_keys:
            print(f"   - {key}")

        # Get specific configuration
        retrieved_config = config_manager.get_config("github", "file_operations")
        if retrieved_config:
            print(f"3. Retrieved GitHub config: {retrieved_config.operation_name}")
            print(
                f"   - Error handling enabled: {retrieved_config.error_handling_enabled}"
            )
            print(f"   - Max retries: {retrieved_config.get_operation_retries('file')}")
            print(f"   - Timeout: {retrieved_config.get_operation_timeout('file')}")

        # Test configuration serialization
        config_dict = github_config.to_dict()
        print(f"4. Serialized GitHub config: {len(config_dict)} fields")

        # Test configuration deserialization
        restored_config = SubOperationConfig.from_dict(config_dict)
        print(
            f"5. Restored config matches: {restored_config.operation_name == github_config.operation_name}"
        )

    except Exception as e:
        print(f"Error in configuration management example: {e}")
        logger.error(f"Configuration management example failed: {e}")


async def main():
    """Run all examples."""
    print("Sub-Operation Error Handling Examples")
    print("=" * 50)

    try:
        await basic_local_file_operations_example()
        await error_scenarios_example()
        await configuration_management_example()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"Error running examples: {e}")


if __name__ == "__main__":
    asyncio.run(main())
