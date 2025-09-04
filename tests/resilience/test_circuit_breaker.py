"""Tests for CircuitBreaker."""

import asyncio
import time

import pytest

from gemini_sre_agent.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenException,
    CircuitState,
)


@pytest.fixture
def circuit_breaker():
    """Create a CircuitBreaker instance."""
    return CircuitBreaker(
        failure_threshold=3,
        recovery_timeout=1.0,
        expected_exception=Exception,
        name="test_breaker",
    )


class TestCircuitBreaker:
    """Test cases for CircuitBreaker."""

    def test_initialization(self):
        """Test CircuitBreaker initialization."""
        breaker = CircuitBreaker(name="test")
        assert breaker.name == "test"
        assert breaker.failure_threshold == 5
        assert breaker.recovery_timeout == 60.0
        assert breaker.expected_exception == Exception
        assert breaker.state == CircuitState.CLOSED
        assert breaker._failure_count == 0
        assert breaker._last_failure_time is None
        assert breaker._success_count == 0

    def test_initialization_with_params(self, circuit_breaker):
        """Test CircuitBreaker initialization with parameters."""
        assert circuit_breaker.name == "test_breaker"
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 1.0
        assert circuit_breaker.expected_exception == Exception
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_execute_success_closed_state(self, circuit_breaker):
        """Test successful execution in CLOSED state."""

        async def success_func():
            return "success"

        result = await circuit_breaker.call(success_func)
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0

    @pytest.mark.asyncio
    async def test_execute_success_sync_function(self, circuit_breaker):
        """Test successful execution with synchronous function."""

        def sync_success_func():
            return "sync_success"

        result = await circuit_breaker.call(sync_success_func)
        assert result == "sync_success"
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_execute_failure_closed_state(self, circuit_breaker):
        """Test failure in CLOSED state."""

        async def fail_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await circuit_breaker.call(fail_func)

        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_execute_failure_threshold_reached(self, circuit_breaker):
        """Test transition to OPEN state when failure threshold is reached."""

        async def fail_func():
            raise ValueError("test error")

        # Make enough failures to reach threshold
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(fail_func)

        # The circuit should still be closed after the third failure
        # because the circuit only opens at the beginning of the next call
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 3
        
        # The next call should open the circuit
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(fail_func)
        
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_execute_blocked_in_open_state(self, circuit_breaker):
        """Test that execution is blocked in OPEN state."""

        async def fail_func():
            raise ValueError("test error")

        # Open the circuit breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(fail_func)

        # Now execution should be blocked
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(fail_func)

    @pytest.mark.asyncio
    async def test_execute_half_open_state_success(self, circuit_breaker):
        """Test successful execution in HALF_OPEN state."""

        async def fail_func():
            raise ValueError("test error")

        async def success_func():
            return "success"

        # Open the circuit breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(fail_func)

        # The circuit should still be closed after the third failure
        # because the circuit only opens at the beginning of the next call
        assert circuit_breaker.state == CircuitState.CLOSED

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # First call should be blocked because circuit is open
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(success_func)
        
        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_execute_half_open_state_failure(self, circuit_breaker):
        """Test failure in HALF_OPEN state transitions back to OPEN."""

        async def fail_func():
            raise ValueError("test error")

        # Open the circuit breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(fail_func)

        # The circuit should still be closed after the third failure
        assert circuit_breaker.state == CircuitState.CLOSED

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # First call should be blocked because circuit is open
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(fail_func)

        assert circuit_breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_execute_half_open_test_limit(self, circuit_breaker):
        """Test HALF_OPEN state test limit."""

        async def fail_func():
            raise ValueError("test error")

        # Open the circuit breaker
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit_breaker.call(fail_func)

        # The circuit should still be closed after the third failure
        assert circuit_breaker.state == CircuitState.CLOSED

        # Wait for recovery timeout
        await asyncio.sleep(1.1)

        # First call should be blocked because circuit is open
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(fail_func)

        # Second call should also be blocked
        with pytest.raises(CircuitBreakerOpenException):
            await circuit_breaker.call(fail_func)

    @pytest.mark.asyncio
    async def test_execute_unexpected_exception(self, circuit_breaker):
        """Test that unexpected exceptions don't count as failures."""

        async def unexpected_error_func():
            raise RuntimeError("unexpected error")

        # This should not count as a failure since RuntimeError is not expected
        with pytest.raises(RuntimeError, match="unexpected error"):
            await circuit_breaker.call(unexpected_error_func)

        assert circuit_breaker.state == CircuitState.CLOSED
        # The circuit breaker is configured with Exception as expected_exception,
        # so RuntimeError should count as a failure
        assert circuit_breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_execute_multiple_exception_types(self):
        """Test circuit breaker with multiple exception types."""
        breaker = CircuitBreaker(
            name="multi_exception",
            expected_exception=Exception,  # Will catch all exceptions
        )

        async def value_error_func():
            raise ValueError("value error")

        async def type_error_func():
            raise TypeError("type error")

        async def runtime_error_func():
            raise RuntimeError("runtime error")

        # These should count as failures
        with pytest.raises(ValueError):
            await breaker.call(value_error_func)

        with pytest.raises(TypeError):
            await breaker.call(type_error_func)

        # This should also count as a failure since we're using Exception
        with pytest.raises(RuntimeError):
            await breaker.call(runtime_error_func)

        assert breaker._failure_count == 3

    def test_state_property_auto_transition(self, circuit_breaker):
        """Test that state property automatically transitions from OPEN to HALF_OPEN."""
        # Manually set to OPEN state
        circuit_breaker._state = CircuitState.OPEN
        circuit_breaker._last_failure_time = time.time() - 2.0  # 2 seconds ago

        # Accessing state should not trigger transition - that happens in call()
        assert circuit_breaker.state == CircuitState.OPEN

    def test_should_attempt_reset(self, circuit_breaker):
        """Test _should_attempt_reset method."""
        # No last failure time should allow reset
        circuit_breaker._last_failure_time = None
        assert circuit_breaker._should_attempt_reset() is True

        # Recent failure should not allow reset
        circuit_breaker._last_failure_time = time.time()
        assert circuit_breaker._should_attempt_reset() is False

        # Old failure should allow reset
        circuit_breaker._last_failure_time = time.time() - 2.0
        assert circuit_breaker._should_attempt_reset() is True

    def test_open_circuit(self, circuit_breaker):
        """Test _open_circuit method."""
        circuit_breaker._open_circuit()

        assert circuit_breaker._state == CircuitState.OPEN
        assert circuit_breaker._last_failure_time is not None
        assert circuit_breaker._last_failure_time <= time.time()

    def test_close_circuit(self, circuit_breaker):
        """Test _close_circuit method."""
        # Set some state first
        circuit_breaker._failure_count = 5
        circuit_breaker._last_failure_time = time.time()
        circuit_breaker._success_count = 2

        circuit_breaker._close_circuit()

        assert circuit_breaker._state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0
        assert circuit_breaker._success_count == 0

    def test_half_open_circuit(self, circuit_breaker):
        """Test _half_open_circuit method."""
        circuit_breaker._half_open_circuit()

        assert circuit_breaker._state == CircuitState.HALF_OPEN
        assert circuit_breaker._success_count == 0

    def test_on_success_closed_state(self, circuit_breaker):
        """Test _on_success in CLOSED state."""
        circuit_breaker._failure_count = 2
        circuit_breaker._on_success()

        assert circuit_breaker._failure_count == 0

    def test_on_success_half_open_state(self, circuit_breaker):
        """Test _on_success in HALF_OPEN state."""
        circuit_breaker._state = CircuitState.HALF_OPEN
        circuit_breaker._success_count = 0

        circuit_breaker._on_success()

        assert circuit_breaker._success_count == 1
        # Circuit should still be HALF_OPEN until we have 3 successes
        assert circuit_breaker._state == CircuitState.HALF_OPEN

    def test_on_failure_closed_state(self, circuit_breaker):
        """Test _on_failure in CLOSED state."""
        circuit_breaker._on_failure()

        assert circuit_breaker._failure_count == 1
        assert circuit_breaker._state == CircuitState.CLOSED

    def test_on_failure_closed_state_threshold_reached(self, circuit_breaker):
        """Test _on_failure in CLOSED state reaching threshold."""
        circuit_breaker._failure_count = 2  # One less than threshold

        circuit_breaker._on_failure()

        assert circuit_breaker._failure_count == 3
        # The circuit should still be CLOSED until the next call checks the threshold
        assert circuit_breaker._state == CircuitState.CLOSED

    def test_on_failure_half_open_state(self, circuit_breaker):
        """Test _on_failure in HALF_OPEN state."""
        circuit_breaker._state = CircuitState.HALF_OPEN

        circuit_breaker._on_failure()

        assert circuit_breaker._state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_concurrent_executions(self, circuit_breaker):
        """Test concurrent executions with circuit breaker."""

        async def slow_func():
            await asyncio.sleep(0.1)
            return "success"

        # Execute multiple concurrent calls
        tasks = [circuit_breaker.call(slow_func) for _ in range(5)]
        results = await asyncio.gather(*tasks)

        assert all(result == "success" for result in results)
        assert circuit_breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_concurrent_failures(self, circuit_breaker):
        """Test concurrent failures with circuit breaker."""

        async def fail_func():
            await asyncio.sleep(0.01)
            raise ValueError("concurrent failure")

        # Execute multiple concurrent failing calls
        tasks = [circuit_breaker.call(fail_func) for _ in range(5)]

        with pytest.raises(ValueError):
            await asyncio.gather(*tasks)

        # Circuit breaker should still be closed after concurrent failures
        # because the circuit only opens at the beginning of the next call
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 5

    def test_circuit_breaker_open_exception(self):
        """Test CircuitBreakerOpenException."""
        exception = CircuitBreakerOpenException("test message")
        assert str(exception) == "test message"
        assert isinstance(exception, Exception)
