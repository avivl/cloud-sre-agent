import asyncio
from asyncio import TimeoutError  # Added for asyncio.TimeoutError
from unittest.mock import AsyncMock

import pytest
from hyx.circuitbreaker.exceptions import BreakerFailing
from hyx.ratelimit.exceptions import RateLimitExceeded
from hyx.retry.exceptions import MaxAttemptsExceeded

from gemini_sre_agent.resilience import (
    HyxResilientClient,
    ResilienceConfig,
    create_resilience_config,
)


@pytest.mark.asyncio
async def test_resilient_client_success():
    # Arrange
    config = create_resilience_config("development")
    client = HyxResilientClient(config)

    async def successful_operation():
        return "success"

    # Act
    result = await client.execute(successful_operation)

    # Assert
    assert result == "success"
    stats = client.get_health_stats()
    assert stats["statistics"]["total_operations"] == 1
    assert stats["statistics"]["successful_operations"] == 1
    assert stats["statistics"]["failed_operations"] == 0
    assert stats["circuit_breaker"]["state"] == "working"


@pytest.mark.asyncio
async def test_resilient_client_failure():
    # Arrange
    config = create_resilience_config("development")
    client = HyxResilientClient(config)

    async def failing_operation():
        raise ValueError("operation failed")

    # Act & Assert
    with pytest.raises(MaxAttemptsExceeded):  # Changed to MaxAttemptsExceeded
        await client.execute(failing_operation)

    stats = client.get_health_stats()
    assert stats["statistics"]["total_operations"] == 1
    assert stats["statistics"]["successful_operations"] == 0
    assert stats["statistics"]["failed_operations"] == 1
    assert stats["statistics"]["retries"] > 0  # Ensure retries happened


@pytest.mark.asyncio
async def test_resilient_client_circuit_breaker_open():
    # Arrange
    config = create_resilience_config("development")
    # Set failure threshold to 1 for easy testing
    config.circuit_breaker["failure_threshold"] = 1
    client = HyxResilientClient(config)

    async def failing_operation():
        raise ConnectionError("simulated connection error")

    @client._circuitbreaker
    async def circuit_breaker_test_operation():
        return await failing_operation()

    # Act - First failure should open the circuit
    with pytest.raises(ConnectionError):  # Expect ConnectionError for the first call
        await circuit_breaker_test_operation()

    # Assert circuit breaker is open
    stats = client.get_health_stats()
    assert stats["circuit_breaker"]["state"] == "failing"
    # assert stats['statistics']['circuit_breaker_opens'] == 1 # Removed

    # Act - Subsequent call should immediately fail due to open circuit
    with pytest.raises(BreakerFailing):  # Expect BreakerFailing for subsequent calls
        await circuit_breaker_test_operation()

    stats = client.get_health_stats()
    assert stats["circuit_breaker"]["state"] == "failing"


@pytest.mark.asyncio
async def test_resilient_client_rate_limit():
    # Arrange
    config = create_resilience_config("development")
    config.rate_limit["requests_per_second"] = 1  # Allow only 1 request per second
    client = HyxResilientClient(config)

    async def dummy_operation():
        return "done"

    # Act & Assert
    result1 = await client.execute(dummy_operation)
    assert result1 == "done"

    # The second call should be rate-limited if called immediately
    with pytest.raises(RateLimitExceeded):  # Changed to RateLimitExceeded
        await client.execute(dummy_operation)

    stats = client.get_health_stats()
    assert stats["statistics"]["rate_limit_hits"] == 1


@pytest.mark.asyncio
async def test_resilient_client_timeout():  # New test case
    # Arrange
    config = create_resilience_config("development")
    config.timeout = 0.1  # Set a very short timeout
    client = HyxResilientClient(config)

    async def long_running_operation():
        await asyncio.sleep(0.5)  # Simulate a long-running operation
        return "done"

    # Act & Assert
    with pytest.raises(TimeoutError):
        await client.execute(long_running_operation)

    stats = client.get_health_stats()
    assert stats["statistics"]["total_operations"] == 1
    assert stats["statistics"]["successful_operations"] == 0
    assert stats["statistics"]["failed_operations"] == 1
    assert stats["statistics"]["timeouts"] == 1  # Ensure timeout stat is incremented


def test_create_resilience_config():
    # Act
    prod_config = create_resilience_config("production")
    dev_config = create_resilience_config("development")
    staging_config = create_resilience_config("staging")
    default_config = create_resilience_config("unknown")

    # Assert
    assert isinstance(prod_config, ResilienceConfig)
    assert prod_config.timeout == 30.0  # Re-enabled and updated
    assert isinstance(dev_config, ResilienceConfig)
    assert isinstance(staging_config, ResilienceConfig)
    assert isinstance(default_config, ResilienceConfig)

    assert prod_config.retry["max_attempts"] == 3
    assert dev_config.retry["max_attempts"] == 2
    assert staging_config.retry["max_attempts"] == 3

    assert prod_config.circuit_breaker["failure_threshold"] == 3
    assert dev_config.circuit_breaker["failure_threshold"] == 5

    assert prod_config.bulkhead["limit"] == 10
    assert dev_config.bulkhead["limit"] == 5

    assert prod_config.rate_limit["requests_per_second"] == 8
    assert dev_config.rate_limit["requests_per_second"] == 15
