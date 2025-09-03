#!/usr/bin/env python3
"""
Example of using Hyx-based resilience patterns in the log ingestion system.
Following the Jimini Resilience Guide for Python implementation.
"""

import asyncio
import os
from typing import Any, Dict

from gemini_sre_agent.config.ingestion_config import IngestionConfigManager
from gemini_sre_agent.ingestion.interfaces.resilience import (
    HyxResilientClient,
    ResilienceConfig,
    create_resilience_config,
)


async def simulate_external_api_call(
    api_name: str, should_fail: bool = False
) -> Dict[str, Any]:
    """Simulate an external API call that might fail."""
    await asyncio.sleep(0.1)  # Simulate network delay

    if should_fail:
        raise ConnectionError(f"API {api_name} is temporarily unavailable")

    return {
        "api": api_name,
        "status": "success",
        "data": f"Response from {api_name}",
        "timestamp": asyncio.get_event_loop().time(),
    }


async def simulate_database_operation(
    operation: str, should_fail: bool = False
) -> Dict[str, Any]:
    """Simulate a database operation that might fail."""
    await asyncio.sleep(0.05)  # Simulate database delay

    if should_fail:
        raise TimeoutError(f"Database operation {operation} timed out")

    return {
        "operation": operation,
        "status": "success",
        "affected_rows": 1,
        "timestamp": asyncio.get_event_loop().time(),
    }


async def demonstrate_basic_resilience():
    """Demonstrate basic resilience patterns with Hyx."""
    print("🔧 Basic Resilience Patterns Demo")
    print("=" * 50)

    # Create resilience configuration for development
    config = create_resilience_config("development")
    client = HyxResilientClient(config)

    print(f"📊 Configuration: {config}")
    print()

    # Test successful operation
    print("✅ Testing successful operation...")
    try:
        result = await client.execute(
            lambda: simulate_external_api_call("health-check")
        )
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test retry on transient failure
    print("\n🔄 Testing retry on transient failure...")
    try:
        result = await client.execute(
            lambda: simulate_external_api_call("flaky-api", should_fail=True)
        )
        print(f"   Result: {result}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test circuit breaker after multiple failures
    print("\n⚡ Testing circuit breaker...")
    for i in range(6):  # More than failure threshold
        try:
            result = await client.execute(
                lambda: simulate_external_api_call("failing-api", should_fail=True)
            )
            print(f"   Attempt {i+1}: Success - {result}")
        except Exception as e:
            print(f"   Attempt {i+1}: Failed - {e}")

    # Show health stats
    print("\n📈 Health Statistics:")
    stats = client.get_health_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")


async def demonstrate_batch_operations():
    """Demonstrate batch operations with resilience."""
    print("\n\n📦 Batch Operations Demo")
    print("=" * 50)

    config = create_resilience_config("development")
    client = HyxResilientClient(config)

    # Simulate batch of API calls
    operations = [lambda: simulate_external_api_call(f"api-{i}") for i in range(10)]

    print("🚀 Executing batch of 10 operations...")
    results = []

    for i, operation in enumerate(operations):
        try:
            result = await client.execute(operation)
            results.append(result)
            print(f"   Operation {i+1}: ✅ Success")
        except Exception as e:
            print(f"   Operation {i+1}: ❌ Failed - {e}")
            results.append(None)

    successful = sum(1 for r in results if r is not None)
    print(f"\n📊 Batch Results: {successful}/10 successful")

    # Show final health stats
    stats = client.get_health_stats()
    print(f"📈 Final Statistics: {stats['statistics']}")


async def demonstrate_environment_configs():
    """Demonstrate different environment configurations."""
    print("\n\n🌍 Environment Configurations Demo")
    print("=" * 50)

    environments = ["development", "staging", "production"]

    for env in environments:
        print(f"\n🔧 {env.upper()} Configuration:")
        config = create_resilience_config(env)
        print(f"   Retry attempts: {config.retry['max_attempts']}")
        print(
            f"   Circuit breaker threshold: {config.circuit_breaker['failure_threshold']}"
        )
        print(f"   Timeout: {config.timeout}s")
        print(f"   Bulkhead limit: {config.bulkhead['limit']}")
        print(f"   Rate limit: {config.rate_limit['requests_per_second']} req/s")


async def demonstrate_with_ingestion_config():
    """Demonstrate resilience with actual ingestion configuration."""
    print("\n\n📋 Integration with Ingestion Config Demo")
    print("=" * 50)

    # Load a sample configuration
    config_manager = IngestionConfigManager()

    try:
        # Try to load the basic config we created earlier
        config_path = "examples/ingestion_configs/basic_config.json"
        if os.path.exists(config_path):
            config = config_manager.load_config(config_path)
            print(f"✅ Loaded configuration from {config_path}")
            print(f"   Schema version: {config.schema_version}")
            print(f"   Sources: {len(config.sources)}")
            print(f"   Global config: {config.global_config}")

            # Create resilience config based on global settings
            global_cfg = config.global_config
            ResilienceConfig(
                retry={
                    "max_attempts": global_cfg.retry_attempts,
                    "initial_delay": global_cfg.retry_delay,
                    "max_delay": global_cfg.retry_delay * 10,
                    "randomize": True,
                },
                circuit_breaker={
                    "failure_threshold": global_cfg.circuit_breaker_threshold,
                    "recovery_timeout": global_cfg.circuit_breaker_timeout,
                },
                timeout=30,
                bulkhead={"limit": 10, "queue": 5},
                rate_limit={
                    "requests_per_second": global_cfg.max_throughput,
                    "burst_limit": global_cfg.max_throughput * 2,
                },
            )

            print("\n🔧 Derived Resilience Config:"g:")
            print(f"   Max throughput: {global_cfg.max_throughput} logs/sec")
            print(f"   Buffer strategy: {global_cfg.buffer_strategy}")
            print(f"   Error threshold: {global_cfg.error_threshold}")
            print(f"   Retry attempts: {global_cfg.retry_attempts}")
            print(
                f"   Circuit breaker threshold: {global_cfg.circuit_breaker_threshold}"
            )

        else:
            print(f"❌ Configuration file not found: {config_path}")
            print("   Please ensure the basic_config.json file exists")

    except Exception as e:
        print(f"❌ Error loading configuration: {e}")


async def main():
    """Main demonstration function."""
    print("🎯 Hyx Resilience Patterns for Log Ingestion System")
    print("Following the Jimini Resilience Guide")
    print("=" * 60)

    try:
        await demonstrate_basic_resilience()
        await demonstrate_batch_operations()
        await demonstrate_environment_configs()
        await demonstrate_with_ingestion_config()

        print("\n\n🎉 Demo completed successfully!")
        print("\n💡 Key Takeaways:")
        print("   - Hyx provides comprehensive resilience patterns")
        print(
            "   - Environment-specific configurations for different deployment stages"
        )
        print("   - Integration with existing ingestion configuration system")
        print("   - Built-in health monitoring and statistics")
        print("   - Legacy compatibility with deprecation warnings")

    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        print("   Make sure to install required dependencies:")
        print("   pip install -r requirements-resilience.txt")


if __name__ == "__main__":
    asyncio.run(main())
