"""
Tests for time window accumulation logic.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.pattern_detector.time_window_accumulator import (
    LogAccumulator,
    WindowManager,
)


class TestLogAccumulator:
    """Test LogAccumulator functionality."""

    @pytest.fixture
    def mock_callback(self) -> None:
        """Create mock callback for testing."""
        return MagicMock()

    def test_log_accumulator_initialization(self, mock_callback: str) -> None:
        """Test LogAccumulator initialization."""
        accumulator = LogAccumulator(
            window_duration_minutes=5, max_windows=10, on_window_ready=mock_callback
        )

        assert accumulator.window_duration_minutes == 5
        assert accumulator.max_windows == 10
        assert accumulator.on_window_ready == mock_callback
        assert len(accumulator.windows) == 0

    def test_log_accumulator_round_to_window_start(self, mock_callback: str) -> None:
        """Test timestamp rounding to window boundaries."""
        accumulator = LogAccumulator(
            window_duration_minutes=5, on_window_ready=mock_callback
        )

        test_cases = [
            (datetime(2025, 1, 27, 10, 3, 30), datetime(2025, 1, 27, 10, 0, 0)),
            (datetime(2025, 1, 27, 10, 7, 15), datetime(2025, 1, 27, 10, 5, 0)),
            (datetime(2025, 1, 27, 10, 12, 45), datetime(2025, 1, 27, 10, 10, 0)),
        ]

        for input_time, expected_start in test_cases:
            result = accumulator._round_to_window_start(input_time)
            assert result == expected_start

    def test_log_accumulator_add_log(self, mock_callback: str) -> None:
        """Test adding logs to accumulator."""
        accumulator = LogAccumulator(
            window_duration_minutes=5, on_window_ready=mock_callback
        )

        log_data = {
            "insertId": "test-123",
            "timestamp": "2025-01-27T10:03:00Z",
            "severity": "ERROR",
            "textPayload": "Test error",
        }

        accumulator.add_log(log_data)

        assert len(accumulator.windows) == 1
        window = list(accumulator.windows.values())[0]
        assert len(window.logs) == 1
        assert window.logs[0].insert_id == "test-123"

    def test_log_accumulator_multiple_windows(self, mock_callback: str) -> None:
        """Test creation of multiple windows for different time ranges."""
        accumulator = LogAccumulator(
            window_duration_minutes=5, on_window_ready=mock_callback
        )

        log_data_1 = {
            "insertId": "test-1",
            "timestamp": "2025-01-27T10:03:00Z",
            "severity": "ERROR",
        }
        log_data_2 = {
            "insertId": "test-2",
            "timestamp": "2025-01-27T10:07:00Z",
            "severity": "ERROR",
        }

        accumulator.add_log(log_data_1)
        accumulator.add_log(log_data_2)

        assert len(accumulator.windows) == 2

    def test_log_accumulator_window_eviction(self, mock_callback: str) -> None:
        """Test window eviction when max_windows is exceeded."""
        accumulator = LogAccumulator(
            window_duration_minutes=5, max_windows=2, on_window_ready=mock_callback
        )

        timestamps = [
            "2025-01-27T10:03:00Z",
            "2025-01-27T10:07:00Z",
            "2025-01-27T10:13:00Z",
        ]

        for i, timestamp in enumerate(timestamps):
            log_data = {
                "insertId": f"test-{i}",
                "timestamp": timestamp,
                "severity": "ERROR",
            }
            accumulator.add_log(log_data)

        assert len(accumulator.windows) == 2
        mock_callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_accumulator_start_stop(self, mock_callback):
        """Test starting and stopping the accumulator."""
        accumulator = LogAccumulator(on_window_ready=mock_callback)

        accumulator.start()
        assert accumulator._cleanup_task is not None
        assert not accumulator._cleanup_task.done()

        await accumulator.stop()
        assert accumulator._shutdown is True


class TestWindowManager:
    """Test WindowManager functionality."""

    @pytest.fixture
    def mock_pattern_callback(self) -> None:
        """Create mock pattern callback for testing."""
        return MagicMock()

    def test_window_manager_initialization(self, mock_pattern_callback: str) -> None:
        """Test WindowManager initialization."""
        manager = WindowManager(
            fast_window_minutes=5,
            trend_window_minutes=15,
            max_windows=20,
            pattern_callback=mock_pattern_callback,
        )

        assert manager.fast_window_minutes == 5
        assert manager.trend_window_minutes == 15
        assert manager.pattern_callback == mock_pattern_callback
        assert manager.fast_accumulator is not None
        assert manager.trend_accumulator is not None

    @pytest.mark.asyncio
    async def test_window_manager_start_stop(self, mock_pattern_callback):
        """Test starting and stopping the window manager."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)

        manager.fast_accumulator.start = MagicMock()
        manager.trend_accumulator.start = MagicMock()
        manager.fast_accumulator.stop = AsyncMock()
        manager.trend_accumulator.stop = AsyncMock()

        manager.start()
        manager.fast_accumulator.start.assert_called_once()
        manager.trend_accumulator.start.assert_called_once()

        await manager.stop()
        manager.fast_accumulator.stop.assert_called_once()
        manager.trend_accumulator.stop.assert_called_once()

    def test_window_manager_add_log(self, mock_pattern_callback: str) -> None:
        """Test adding logs to both accumulators."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)

        manager.fast_accumulator.add_log = MagicMock()
        manager.trend_accumulator.add_log = MagicMock()

        log_data = {
            "insertId": "test-123",
            "timestamp": "2025-01-27T10:03:00Z",
            "severity": "ERROR",
        }

        manager.add_log(log_data)

        manager.fast_accumulator.add_log.assert_called_once_with(log_data)
        manager.trend_accumulator.add_log.assert_called_once_with(log_data)

    def test_window_manager_fast_window_callback(
        self, mock_pattern_callback: str
    ) -> None:
        """Test fast window completion callback."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)

        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = ["log1", "log2"]
        mock_window.get_error_logs.return_value = ["error1"]

        manager._on_fast_window_ready(mock_window)

        mock_pattern_callback.assert_called_once_with(mock_window)

    def test_window_manager_trend_window_callback(
        self, mock_pattern_callback: str
    ) -> None:
        """Test trend window completion callback."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)

        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = ["log1", "log2", "log3"]
        mock_window.get_error_logs.return_value = ["error1", "error2"]

        manager._on_trend_window_ready(mock_window)

        mock_pattern_callback.assert_called_once_with(mock_window)

    def test_window_manager_callback_error_handling(
        self, mock_pattern_callback: str
    ) -> None:
        """Test error handling in window callbacks."""
        mock_pattern_callback.side_effect = RuntimeError("Test error")
        manager = WindowManager(pattern_callback=mock_pattern_callback)
        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = []
        mock_window.get_error_logs.return_value = []

        with patch(
            "gemini_sre_agent.pattern_detector.time_window_accumulator.logger"
        ) as mock_logger:
            manager._on_fast_window_ready(mock_window)
            manager._on_trend_window_ready(mock_window)
            assert mock_logger.error.call_count == 2
