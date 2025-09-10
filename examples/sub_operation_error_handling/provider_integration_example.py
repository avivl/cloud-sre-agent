#!/usr/bin/env python3
"""
Provider Integration Example

This example demonstrates how to integrate sub-operation error handling
with different source control providers (GitHub, GitLab, Local) and
shows real-world usage patterns.
"""

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict

# Import the error handling components
from gemini_sre_agent.source_control.error_handling import (
    CircuitBreakerConfig,
    ErrorHandlingFactory,
    RetryConfig,
)
from gemini_sre_agent.source_control.providers.github.github_file_operations import (
    GitHubFileOperations,
)
from gemini_sre_agent.source_control.providers.gitlab.gitlab_file_operations import (
    GitLabFileOperations,
)
from gemini_sre_agent.source_control.providers.local.local_file_operations import (
    LocalFileOperations,
)
from gemini_sre_agent.source_control.providers.sub_operation_config import (
    SubOperationConfig,
    SubOperationConfigManager,
)


class ProviderManager:
    """Manages multiple source control providers with error handling."""

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.providers: Dict[str, Any] = {}
        self.config_manager = SubOperationConfigManager()
        self.error_handling_factory = ErrorHandlingFactory()
        self._setup_default_configurations()

    def _setup_default_configurations(self):
        """Setup default configurations for different providers."""
        # GitHub configuration - more aggressive retry for API rate limits
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

        # GitLab configuration - moderate retry for API stability
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

        # Local configuration - minimal retry for local operations
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
        self.config_manager.register_config(github_config)
        self.config_manager.register_config(gitlab_config)
        self.config_manager.register_config(local_config)

    async def initialize_local_provider(self, root_path: Path) -> bool:
        """Initialize local provider with error handling."""
        try:
            # Get configuration
            config = self.config_manager.get_config("local", "file_operations")
            if not config:
                self.logger.error("No configuration found for local provider")
                return False

            # Create error handling components
            error_handling_components = (
                self.error_handling_factory.create_error_handling_system(
                    provider_name="local",
                    config={
                        "circuit_breaker": {
                            "failure_threshold": (
                                config.circuit_breaker_config.failure_threshold
                                if config.circuit_breaker_config
                                else 5
                            ),
                            "recovery_timeout": (
                                config.circuit_breaker_config.recovery_timeout
                                if config.circuit_breaker_config
                                else 30.0
                            ),
                            "timeout": (
                                config.circuit_breaker_config.timeout
                                if config.circuit_breaker_config
                                else 10.0
                            ),
                        },
                        "retry": {
                            "max_retries": (
                                config.retry_config.max_retries
                                if config.retry_config
                                else 3
                            ),
                            "base_delay": (
                                config.retry_config.base_delay
                                if config.retry_config
                                else 1.0
                            ),
                            "max_delay": (
                                config.retry_config.max_delay
                                if config.retry_config
                                else 10.0
                            ),
                            "backoff_factor": (
                                config.retry_config.backoff_factor
                                if config.retry_config
                                else 2.0
                            ),
                        },
                    },
                )
            )

            # Initialize local file operations
            self.providers["local"] = LocalFileOperations(
                root_path=root_path,
                default_encoding="utf-8",
                backup_files=True,
                backup_directory=str(root_path / "backups"),
                logger=self.logger,
                error_handling_components=error_handling_components,
                config=config,
            )

            self.logger.info("Local provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize local provider: {e}")
            return False

    async def initialize_github_provider(self, client, repo) -> bool:
        """Initialize GitHub provider with error handling."""
        try:
            # Get configuration
            config = self.config_manager.get_config("github", "file_operations")
            if not config:
                self.logger.error("No configuration found for GitHub provider")
                return False

            # Create error handling components
            error_handling_components = (
                self.error_handling_factory.create_error_handling_system(
                    provider_name="github",
                    config={
                        "circuit_breaker": {
                            "failure_threshold": (
                                config.circuit_breaker_config.failure_threshold
                                if config.circuit_breaker_config
                                else 5
                            ),
                            "recovery_timeout": (
                                config.circuit_breaker_config.recovery_timeout
                                if config.circuit_breaker_config
                                else 30.0
                            ),
                            "timeout": (
                                config.circuit_breaker_config.timeout
                                if config.circuit_breaker_config
                                else 10.0
                            ),
                        },
                        "retry": {
                            "max_retries": (
                                config.retry_config.max_retries
                                if config.retry_config
                                else 3
                            ),
                            "base_delay": (
                                config.retry_config.base_delay
                                if config.retry_config
                                else 1.0
                            ),
                            "max_delay": (
                                config.retry_config.max_delay
                                if config.retry_config
                                else 10.0
                            ),
                            "backoff_factor": (
                                config.retry_config.backoff_factor
                                if config.retry_config
                                else 2.0
                            ),
                        },
                    },
                )
            )

            # Initialize GitHub file operations
            self.providers["github"] = GitHubFileOperations(
                client=client,
                repo=repo,
                logger=self.logger,
                error_handling_components=error_handling_components,
            )

            self.logger.info("GitHub provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize GitHub provider: {e}")
            return False

    async def initialize_gitlab_provider(self, gl, project) -> bool:
        """Initialize GitLab provider with error handling."""
        try:
            # Get configuration
            config = self.config_manager.get_config("gitlab", "file_operations")
            if not config:
                self.logger.error("No configuration found for GitLab provider")
                return False

            # Create error handling components
            error_handling_components = (
                self.error_handling_factory.create_error_handling_system(
                    provider_name="gitlab",
                    config={
                        "circuit_breaker": {
                            "failure_threshold": (
                                config.circuit_breaker_config.failure_threshold
                                if config.circuit_breaker_config
                                else 5
                            ),
                            "recovery_timeout": (
                                config.circuit_breaker_config.recovery_timeout
                                if config.circuit_breaker_config
                                else 30.0
                            ),
                            "timeout": (
                                config.circuit_breaker_config.timeout
                                if config.circuit_breaker_config
                                else 10.0
                            ),
                        },
                        "retry": {
                            "max_retries": (
                                config.retry_config.max_retries
                                if config.retry_config
                                else 3
                            ),
                            "base_delay": (
                                config.retry_config.base_delay
                                if config.retry_config
                                else 1.0
                            ),
                            "max_delay": (
                                config.retry_config.max_delay
                                if config.retry_config
                                else 10.0
                            ),
                            "backoff_factor": (
                                config.retry_config.backoff_factor
                                if config.retry_config
                                else 2.0
                            ),
                        },
                    },
                )
            )

            # Initialize GitLab file operations
            self.providers["gitlab"] = GitLabFileOperations(
                gl=gl,
                project=project,
                logger=self.logger,
                error_handling_components=error_handling_components,
            )

            self.logger.info("GitLab provider initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize GitLab provider: {e}")
            return False

    async def perform_operation(
        self, provider_name: str, operation: str, *args, **kwargs
    ) -> Any:
        """Perform an operation on a specific provider."""
        if provider_name not in self.providers:
            raise ValueError(f"Provider {provider_name} not initialized")

        provider = self.providers[provider_name]

        if operation == "get_file_content":
            return await provider.get_file_content(*args, **kwargs)
        elif operation == "apply_remediation":
            return await provider.apply_remediation(*args, **kwargs)
        elif operation == "file_exists":
            return await provider.file_exists(*args, **kwargs)
        elif operation == "get_file_info":
            return await provider.get_file_info(*args, **kwargs)
        elif operation == "list_files":
            return await provider.list_files(*args, **kwargs)
        elif operation == "health_check":
            return await provider.health_check()
        else:
            raise ValueError(f"Unknown operation: {operation}")

    async def get_provider_health(self, provider_name: str) -> bool:
        """Get health status of a provider."""
        if provider_name not in self.providers:
            return False

        try:
            return await self.perform_operation(provider_name, "health_check")
        except Exception as e:
            self.logger.error(f"Health check failed for {provider_name}: {e}")
            return False

    async def get_all_provider_health(self) -> Dict[str, bool]:
        """Get health status of all providers."""
        health_status = {}
        for provider_name in self.providers:
            health_status[provider_name] = await self.get_provider_health(provider_name)
        return health_status

    def get_provider_stats(self, provider_name: str) -> Dict[str, Any]:
        """Get performance statistics for a provider."""
        if provider_name not in self.providers:
            return {}

        provider = self.providers[provider_name]
        if hasattr(provider, "get_performance_stats"):
            return provider.get_performance_stats()
        return {}

    def get_all_provider_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get performance statistics for all providers."""
        stats = {}
        for provider_name in self.providers:
            stats[provider_name] = self.get_provider_stats(provider_name)
        return stats


async def local_provider_example():
    """Demonstrate local provider integration."""
    print("=== Local Provider Integration Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_local_provider")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Initialize provider manager
        manager = ProviderManager(logger)

        # Initialize local provider
        success = await manager.initialize_local_provider(temp_dir)
        if not success:
            print("Failed to initialize local provider")
            return

        print("1. Testing local provider operations...")

        # Test file operations
        operations = [
            ("apply_remediation", "test.txt", "Hello, World!", "Initial commit"),
            ("get_file_content", "test.txt"),
            ("file_exists", "test.txt"),
            ("get_file_info", "test.txt"),
            ("list_files", ""),
        ]

        for op_name, *args in operations:
            try:
                print(f"   Executing {op_name}...")
                result = await manager.perform_operation("local", op_name, *args)
                print(f"   {op_name}: SUCCESS")
                if hasattr(result, "success"):
                    print(f"     - Success: {result.success}")
                    print(f"     - Message: {result.message}")
                elif isinstance(result, str):
                    print(
                        f"     - Content: '{result[:50]}{'...' if len(result) > 50 else ''}'"
                    )
                elif isinstance(result, bool):
                    print(f"     - Result: {result}")
                elif hasattr(result, "__dict__"):
                    print(f"     - Result: {result}")
            except Exception as e:
                print(f"   {op_name}: FAILED - {type(e).__name__}: {e}")

        print("\n2. Testing health checks...")

        # Test health check
        health = await manager.get_provider_health("local")
        print(f"   Local provider health: {health}")

        # Test all provider health
        all_health = await manager.get_all_provider_health()
        print(f"   All providers health: {all_health}")

        print("\n3. Testing performance statistics...")

        # Get performance stats
        stats = manager.get_provider_stats("local")
        print(f"   Local provider stats: {stats}")

        # Get all provider stats
        all_stats = manager.get_all_provider_stats()
        print(f"   All providers stats: {all_stats}")

    except Exception as e:
        print(f"Error in local provider example: {e}")
        logger.error(f"Local provider example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def multi_provider_example():
    """Demonstrate multiple provider integration."""
    print("\n=== Multi-Provider Integration Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Create a temporary directory for testing
    temp_dir = Path("/tmp/gemini_sre_multi_provider")
    temp_dir.mkdir(exist_ok=True)

    try:
        # Initialize provider manager
        manager = ProviderManager(logger)

        # Initialize local provider
        local_success = await manager.initialize_local_provider(temp_dir)
        print(
            f"Local provider initialization: {'SUCCESS' if local_success else 'FAILED'}"
        )

        # Note: GitHub and GitLab providers would require actual API credentials
        # For this example, we'll just show the configuration setup

        print("\n1. Provider configurations:")
        config_keys = manager.config_manager.list_configs()
        for key in config_keys:
            print(f"   - {key}")
            # Get the actual config to display details
            provider_type, operation_name = key.split(":", 1)
            config = manager.config_manager.get_config(provider_type, operation_name)
            if config:
                print(f"     - Error handling: {config.error_handling_enabled}")
                print(f"     - Max retries: {config.get_operation_retries('file')}")
                print(f"     - Timeout: {config.get_operation_timeout('file')}")
                print(f"     - Metrics enabled: {config.enable_metrics}")

        print("\n2. Testing local provider operations...")

        if local_success:
            # Test various operations
            test_operations = [
                (
                    "apply_remediation",
                    "multi_test.txt",
                    "Multi-provider test content",
                    "Multi-provider commit",
                ),
                ("get_file_content", "multi_test.txt"),
                ("file_exists", "multi_test.txt"),
                ("health_check",),
            ]

            for op_name, *args in test_operations:
                try:
                    print(f"   Executing {op_name}...")
                    await manager.perform_operation("local", op_name, *args)
                    print(f"   {op_name}: SUCCESS")
                except Exception as e:
                    print(f"   {op_name}: FAILED - {type(e).__name__}: {e}")

        print("\n3. Provider health status:")
        health_status = await manager.get_all_provider_health()
        for provider, health in health_status.items():
            print(f"   - {provider}: {'HEALTHY' if health else 'UNHEALTHY'}")

        print("\n4. Provider performance statistics:")
        all_stats = manager.get_all_provider_stats()
        for provider, stats in all_stats.items():
            print(f"   - {provider}: {len(stats)} metrics")

    except Exception as e:
        print(f"Error in multi-provider example: {e}")
        logger.error(f"Multi-provider example failed: {e}")

    finally:
        # Cleanup
        import shutil

        if temp_dir.exists():
            shutil.rmtree(temp_dir)


async def configuration_management_example():
    """Demonstrate configuration management across providers."""
    print("\n=== Configuration Management Example ===")

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    try:
        # Initialize provider manager
        manager = ProviderManager(logger)

        print("1. Default configurations:")
        config_keys = manager.config_manager.list_configs()
        for key in config_keys:
            print(f"   - {key}")
            # Get the actual config to display details
            provider_type, operation_name = key.split(":", 1)
            config = manager.config_manager.get_config(provider_type, operation_name)
            if config:
                print(f"     - Operation: {config.operation_name}")
                print(f"     - Error handling: {config.error_handling_enabled}")
                print(f"     - Max retries: {config.get_operation_retries('file')}")
                print(f"     - Timeout: {config.get_operation_timeout('file')}")
                print(f"     - Log operations: {config.log_operations}")
                print(f"     - Log errors: {config.log_errors}")
                print(f"     - Log performance: {config.log_performance}")
                print(f"     - Enable metrics: {config.enable_metrics}")

        print("\n2. Creating custom configuration...")

        # Create a custom configuration
        custom_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="custom",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=7,
                recovery_timeout=45.0,
                timeout=15.0,
            ),
            retry_config=RetryConfig(
                max_retries=4,
                base_delay=1.2,
                max_delay=15.0,
                backoff_factor=1.7,
            ),
            log_operations=True,
            log_errors=True,
            log_performance=True,
            enable_metrics=True,
            custom_settings={
                "custom_timeout": 30.0,
                "custom_retry_delay": 2.0,
            },
        )

        # Register custom configuration
        manager.config_manager.register_config(custom_config)
        print("   Custom configuration registered")

        # List all configurations
        all_configs = manager.config_manager.list_configs()
        print(f"   Total configurations: {len(all_configs)}")

        print("\n3. Testing configuration serialization...")

        # Test serialization
        config_dict = custom_config.to_dict()
        print(f"   Serialized config fields: {len(config_dict)}")

        # Test deserialization
        restored_config = SubOperationConfig.from_dict(config_dict)
        print(
            f"   Restored config matches: {restored_config.operation_name == custom_config.operation_name}"
        )

        print("\n4. Testing configuration retrieval...")

        # Test getting specific configuration
        retrieved_config = manager.config_manager.get_config(
            "custom", "file_operations"
        )
        if retrieved_config:
            print(f"   Retrieved custom config: {retrieved_config.operation_name}")
            print(f"   - Custom settings: {retrieved_config.custom_settings}")
        else:
            print("   Failed to retrieve custom config")

        print("\n5. Testing configuration updates...")

        # Update an existing configuration
        updated_config = SubOperationConfig(
            operation_name="file_operations",
            provider_type="local",
            error_handling_enabled=True,
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=15,  # Increased threshold
                recovery_timeout=5.0,  # Decreased recovery time
                timeout=3.0,  # Decreased timeout
            ),
            retry_config=RetryConfig(
                max_retries=1,  # Decreased retries
                base_delay=0.2,  # Decreased base delay
                max_delay=2.0,  # Decreased max delay
                backoff_factor=1.2,  # Decreased backoff factor
            ),
            log_operations=True,
            log_errors=True,
            log_performance=False,  # Disabled performance logging
            enable_metrics=False,  # Disabled metrics
        )

        manager.config_manager.register_config(updated_config)
        print("   Local configuration updated")

        # Verify update
        updated_retrieved = manager.config_manager.get_config(
            "local", "file_operations"
        )
        if updated_retrieved:
            print(
                f"   Updated config - Max retries: {updated_retrieved.get_operation_retries('file')}"
            )
            print(
                f"   Updated config - Timeout: {updated_retrieved.get_operation_timeout('file')}"
            )
            print(
                f"   Updated config - Performance logging: {updated_retrieved.log_performance}"
            )

    except Exception as e:
        print(f"Error in configuration management example: {e}")
        logger.error(f"Configuration management example failed: {e}")


async def main():
    """Run all provider integration examples."""
    print("Provider Integration Examples")
    print("=" * 50)

    try:
        await local_provider_example()
        await multi_provider_example()
        await configuration_management_example()

        print("\n" + "=" * 50)
        print("All provider integration examples completed successfully!")

    except Exception as e:
        print(f"Error running provider integration examples: {e}")


if __name__ == "__main__":
    asyncio.run(main())
