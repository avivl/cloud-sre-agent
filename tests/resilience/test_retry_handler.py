"""Tests for RetryHandler."""

import asyncio

import pytest

from gemini_sre_agent.resilience.retry_handler import RetryHandler


@pytest.fixture
def retry_handler():
    """Create a RetryHandler instance."""
    return RetryHandler(
        max_attempts=3,
        base_delay=0.1,  # Fast for testing
        max_delay=1.0,
        jitter=False,  # Disable jitter for predictable testing
    )


class TestRetryHandlerInitialization:
    """Test cases for RetryHandler initialization."""

    def test_default_config(self):
        """Test default RetryHandler values."""
        handler = RetryHandler()

        assert handler.max_attempts == 3
        assert handler.base_delay == 1.0
        assert handler.max_delay == 60.0
        assert handler.jitter is True
        # The retry handler uses an error classifier internally
        assert hasattr(handler, "error_classifier")

    def test_custom_config(self, retry_handler):
        """Test custom RetryHandler values."""
        assert retry_handler.max_attempts == 3
        assert retry_handler.base_delay == 0.1
        assert retry_handler.max_delay == 1.0
        assert retry_handler.jitter is False
        assert retry_handler.error_classifier is not None
        assert ConnectionError in retry_handler.error_classifier._exception_mappings


class TestRetryHandler:
    """Test cases for RetryHandler."""

    def test_initialization_default(self):
        """Test RetryHandler initialization with default config."""
        handler = RetryHandler()

        assert handler.max_attempts == 3
        assert handler.base_delay == 1.0
        assert handler.max_delay == 60.0
        assert handler.jitter is True
        # The retry handler uses an error classifier internally
        assert hasattr(handler, "error_classifier")
        assert ConnectionError in handler.error_classifier._exception_mappings

    def test_initialization_custom(self, retry_handler):
        """Test RetryHandler initialization with custom config."""
        assert retry_handler.max_attempts == 3
        assert retry_handler.base_delay == 0.1
        assert retry_handler.max_delay == 1.0
        assert retry_handler.jitter is False
        assert retry_handler.error_classifier is not None
        assert ConnectionError in retry_handler.error_classifier._exception_mappings

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_first_attempt(self, retry_handler):
        """Test successful execution on first attempt."""

        async def success_func():
            return "success"

        result = await retry_handler.execute_with_retry(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_execute_with_retry_success_after_retries(self, retry_handler):
        """Test successful execution after retries."""
        call_count = 0

        async def retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("retry error")
            return "success"

        result = await retry_handler.execute_with_retry(retry_func)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_with_retry_max_attempts_exceeded(self, retry_handler):
        """Test failure after max attempts exceeded."""
        call_count = 0

        async def always_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fail")

        with pytest.raises(ValueError, match="always fail"):
            await retry_handler.execute_with_retry(always_fail_func)

        assert call_count == 3  # max_attempts

    @pytest.mark.asyncio
    async def test_execute_with_retry_non_retryable_exception(self, retry_handler):
        """Test that non-retryable exceptions are not retried."""
        call_count = 0

        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("non-retryable error")

        with pytest.raises(RuntimeError, match="non-retryable error"):
            await retry_handler.execute_with_retry(
                non_retryable_func, retryable_exceptions=(ValueError,)
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_execute_with_retry_sync_function(self, retry_handler):
        """Test retry with synchronous function."""
        call_count = 0

        def sync_retry_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("sync retry error")
            return "sync success"

        result = await retry_handler.execute_with_retry(sync_retry_func)
        assert result == "sync success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_with_retry_sync_function_failure(self, retry_handler):
        """Test retry with synchronous function that always fails."""
        call_count = 0

        def sync_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("sync always fail")

        with pytest.raises(ValueError, match="sync always fail"):
            await retry_handler.execute_with_retry(sync_fail_func)

        assert call_count == 3  # max_attempts

    @pytest.mark.asyncio
    async def test_async_retry_delay_calculation(self, retry_handler):
        """Test that async retry delays are calculated correctly."""
        call_times = []

        async def delayed_fail_func():
            call_times.append(asyncio.get_event_loop().time())
            raise ValueError("delayed fail")

        with pytest.raises(ValueError):
            await retry_handler.execute_with_retry(delayed_fail_func)

        # Check that delays were applied (allowing for some timing variance)
        assert len(call_times) == 3

        # First call should be immediate
        # Second call should be after base_delay (0.1s)
        # Third call should be after 2 * base_delay (0.2s)
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert delay1 >= 0.19  # Allow for timing variance (0.2s expected)
            assert delay1 <= 0.25

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert delay2 >= 0.39  # Allow for timing variance (0.4s expected)
            assert delay2 <= 0.45

    @pytest.mark.asyncio
    async def test_async_retry_max_delay_respected(self, retry_handler):
        """Test that max_delay is respected in async retry."""
        # Create a handler with very high base_delay but low max_delay
        handler = RetryHandler(
            max_attempts=3,
            base_delay=10.0,  # High base delay
            max_delay=0.2,  # Low max delay
            jitter=False,
        )

        call_times = []

        async def delayed_fail_func():
            call_times.append(asyncio.get_event_loop().time())
            raise ValueError("delayed fail")

        with pytest.raises(ValueError):
            await handler.execute_with_retry(delayed_fail_func)

        # Check that delays were capped at max_delay
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert delay1 <= 0.25  # Should be capped at max_delay

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert delay2 <= 0.25  # Should be capped at max_delay

    @pytest.mark.asyncio
    async def test_async_retry_jitter_enabled(self):
        """Test that jitter is applied when enabled."""
        handler = RetryHandler(
            max_attempts=3,
            base_delay=0.1,
            max_delay=1.0,
            jitter=True,  # Enable jitter
        )

        call_times = []

        async def jittered_fail_func():
            call_times.append(asyncio.get_event_loop().time())
            raise ValueError("jittered fail")

        with pytest.raises(ValueError):
            await handler.execute_with_retry(jittered_fail_func)

        # With jitter, delays should vary slightly
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            # Should be around 0.2s but with some jitter (base delay * 2^1 = 0.2s)
            assert delay1 >= 0.18
            assert delay1 <= 0.22

    @pytest.mark.asyncio
    async def test_async_retry_jitter_disabled(self, retry_handler):
        """Test that jitter is not applied when disabled."""
        call_times = []

        async def no_jitter_fail_func():
            call_times.append(asyncio.get_event_loop().time())
            raise ValueError("no jitter fail")

        with pytest.raises(ValueError):
            await retry_handler.execute_with_retry(no_jitter_fail_func)

        # Without jitter, delays should be more predictable
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            # Should be exactly base_delay * 2^1 (0.2s) with minimal variance
            assert delay1 >= 0.19
            assert delay1 <= 0.21

    @pytest.mark.asyncio
    async def test_async_retry_single_attempt_success(self, retry_handler):
        """Test async retry with single attempt success."""
        call_count = 0

        async def single_success_func():
            nonlocal call_count
            call_count += 1
            return "single success"

        result = await retry_handler.execute_with_retry(single_success_func)
        assert result == "single success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_single_attempt_failure(self, retry_handler):
        """Test async retry with single attempt failure."""
        call_count = 0

        async def single_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("single fail")

        with pytest.raises(ValueError, match="single fail"):
            await retry_handler.execute_with_retry(
                single_fail_func, retryable_exceptions=(RuntimeError,)
            )

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_async_retry_non_retryable_exception(self, retry_handler):
        """Test async retry with non-retryable exception."""
        call_count = 0

        async def non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("non-retryable")

        with pytest.raises(RuntimeError, match="non-retryable"):
            await retry_handler.execute_with_retry(
                non_retryable_func, retryable_exceptions=(ValueError,)
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_async_retry_mixed_exceptions(self, retry_handler):
        """Test async retry with mixed retryable and non-retryable exceptions."""
        call_count = 0

        async def mixed_exception_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("retryable")  # Should retry
            elif call_count == 2:
                raise RuntimeError("non-retryable")  # Should not retry
            else:
                return "success"

        with pytest.raises(RuntimeError, match="non-retryable"):
            await retry_handler.execute_with_retry(
                mixed_exception_func, retryable_exceptions=(ValueError,)
            )

        assert call_count == 2  # Should stop at non-retryable exception

    @pytest.mark.asyncio
    async def test_tenacity_integration_sync_function(self, retry_handler):
        """Test tenacity integration with synchronous functions."""
        call_count = 0

        def tenacity_sync_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("tenacity sync error")
            return "tenacity sync success"

        result = await retry_handler.execute_with_retry(tenacity_sync_func)
        assert result == "tenacity sync success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_tenacity_integration_sync_function_failure(self, retry_handler):
        """Test tenacity integration with synchronous function failure."""
        call_count = 0

        def tenacity_sync_fail_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("tenacity sync fail")

        with pytest.raises(ValueError, match="tenacity sync fail"):
            await retry_handler.execute_with_retry(tenacity_sync_fail_func)

        assert call_count == 3  # max_attempts

    @pytest.mark.asyncio
    async def test_tenacity_integration_non_retryable_exception(self, retry_handler):
        """Test tenacity integration with non-retryable exception."""
        call_count = 0

        def tenacity_non_retryable_func():
            nonlocal call_count
            call_count += 1
            raise RuntimeError("tenacity non-retryable")

        with pytest.raises(RuntimeError, match="tenacity non-retryable"):
            await retry_handler.execute_with_retry(
                tenacity_non_retryable_func, retryable_exceptions=(ValueError,)
            )

        assert call_count == 1  # Should not retry

    @pytest.mark.asyncio
    async def test_function_with_arguments(self, retry_handler):
        """Test retry with function that takes arguments."""

        async def func_with_args(arg1, arg2, kwarg1=None):
            if arg1 == "fail":
                raise ValueError("arg fail")
            return f"{arg1}_{arg2}_{kwarg1}"

        # Test success case
        result = await retry_handler.execute_with_retry(
            func_with_args, "test", "value", kwarg1="keyword"
        )
        assert result == "test_value_keyword"

        # Test failure case
        with pytest.raises(ValueError, match="arg fail"):
            await retry_handler.execute_with_retry(
                func_with_args, "fail", "value", kwarg1="keyword"
            )

    @pytest.mark.asyncio
    async def test_sync_function_with_arguments(self, retry_handler):
        """Test retry with synchronous function that takes arguments."""

        def sync_func_with_args(arg1, arg2, kwarg1=None):
            if arg1 == "fail":
                raise ValueError("sync arg fail")
            return f"sync_{arg1}_{arg2}_{kwarg1}"

        # Test success case
        result = await retry_handler.execute_with_retry(
            sync_func_with_args, "test", "value", kwarg1="keyword"
        )
        assert result == "sync_test_value_keyword"

        # Test failure case
        with pytest.raises(ValueError, match="sync arg fail"):
            await retry_handler.execute_with_retry(
                sync_func_with_args, "fail", "value", kwarg1="keyword"
            )

    @pytest.mark.asyncio
    async def test_concurrent_retries(self, retry_handler):
        """Test concurrent retry executions."""
        call_counts = [0, 0]

        async def concurrent_func_1():
            call_counts[0] += 1
            if call_counts[0] < 2:
                raise ValueError("concurrent 1 fail")
            return "concurrent 1 success"

        async def concurrent_func_2():
            call_counts[1] += 1
            if call_counts[1] < 2:
                raise ValueError("concurrent 2 fail")
            return "concurrent 2 success"

        # Execute both functions concurrently
        results = await asyncio.gather(
            retry_handler.execute_with_retry(concurrent_func_1),
            retry_handler.execute_with_retry(concurrent_func_2),
        )

        assert results == ["concurrent 1 success", "concurrent 2 success"]
        assert call_counts[0] == 2
        assert call_counts[1] == 2
