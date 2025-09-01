"""
Test suite for Pattern Detection System - Layer 1: Time-Window Accumulation

This test suite validates the time-window accumulation functionality including:
- LogEntry creation and parsing
- TimeWindow management and log acceptance
- LogAccumulator with sliding windows
- WindowManager dual-window coordination
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List, Dict, Any

from gemini_sre_agent.pattern_detector import (
    LogEntry,
    TimeWindow,
    LogAccumulator,
    WindowManager
)


class TestLogEntry:
    """Test LogEntry creation and parsing functionality."""
    
    def test_log_entry_basic_creation(self):
        """Test basic LogEntry creation with all fields provided."""
        timestamp = datetime.now(timezone.utc)
        raw_data = {"severity": "ERROR", "textPayload": "Test error"}
        
        log_entry = LogEntry(
            insert_id="test-123",
            timestamp=timestamp,
            severity="ERROR",
            service_name="test-service",
            error_message="Test error",
            raw_data=raw_data
        )
        
        assert log_entry.insert_id == "test-123"
        assert log_entry.timestamp == timestamp
        assert log_entry.severity == "ERROR"
        assert log_entry.service_name == "test-service"
        assert log_entry.error_message == "Test error"
        assert log_entry.raw_data == raw_data
    
    def test_log_entry_timestamp_extraction(self):
        """Test automatic timestamp extraction from raw data."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "severity": "ERROR",
            "textPayload": "Test error"
        }
        
        log_entry = LogEntry(
            insert_id="test-123",
            raw_data=raw_data
        )
        
        assert log_entry.timestamp.year == 2025
        assert log_entry.timestamp.month == 1
        assert log_entry.timestamp.day == 27
        assert log_entry.timestamp.hour == 10
    
    def test_log_entry_service_name_extraction(self):
        """Test automatic service name extraction from resource labels."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "billing-service",
                    "revision_name": "billing-service-001"
                }
            },
            "severity": "ERROR"
        }
        
        log_entry = LogEntry(
            insert_id="test-123",
            raw_data=raw_data
        )
        
        assert log_entry.service_name == "billing-service"
    
    def test_log_entry_function_name_extraction(self):
        """Test service name extraction from function_name label."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "resource": {
                "type": "cloud_function",
                "labels": {
                    "function_name": "payment-processor"
                }
            },
            "severity": "ERROR"
        }
        
        log_entry = LogEntry(
            insert_id="test-123",
            raw_data=raw_data
        )
        
        assert log_entry.service_name == "payment-processor"
    
    def test_log_entry_error_message_extraction(self):
        """Test automatic error message extraction from textPayload."""
        raw_data = {
            "timestamp": "2025-01-27T10:00:00Z",
            "textPayload": "Database connection failed: timeout after 30s",
            "severity": "ERROR"
        }
        
        log_entry = LogEntry(
            insert_id="test-123",
            raw_data=raw_data
        )
        
        assert log_entry.error_message == "Database connection failed: timeout after 30s"
    
    def test_log_entry_invalid_timestamp_fallback(self):
        """Test fallback to current time for invalid timestamps."""
        raw_data = {
            "timestamp": "invalid-timestamp",
            "severity": "ERROR"
        }
        
        before_creation = datetime.now(timezone.utc)
        log_entry = LogEntry(
            insert_id="test-123",
            raw_data=raw_data
        )
        after_creation = datetime.now(timezone.utc)
        
        # Should fallback to current time
        assert before_creation <= log_entry.timestamp <= after_creation


class TestTimeWindow:
    """Test TimeWindow functionality."""
    
    def test_time_window_creation(self):
        """Test basic TimeWindow creation."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        assert window.start_time == start_time
        assert window.duration_minutes == 5
        assert window.end_time == datetime(2025, 1, 27, 10, 5, 0)
        assert len(window.logs) == 0
    
    def test_time_window_is_active(self):
        """Test window active status checking."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Should be active before end time
        assert window.is_active(datetime(2025, 1, 27, 10, 3, 0)) is True
        
        # Should not be active at end time
        assert window.is_active(datetime(2025, 1, 27, 10, 5, 0)) is False
        
        # Should not be active after end time
        assert window.is_active(datetime(2025, 1, 27, 10, 6, 0)) is False
    
    def test_time_window_is_expired(self):
        """Test window expiration checking."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Should not be expired before end time
        assert window.is_expired(datetime(2025, 1, 27, 10, 3, 0)) is False
        
        # Should be expired at end time
        assert window.is_expired(datetime(2025, 1, 27, 10, 5, 0)) is True
        
        # Should be expired after end time
        assert window.is_expired(datetime(2025, 1, 27, 10, 6, 0)) is True
    
    def test_time_window_accepts_log(self):
        """Test log acceptance logic."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Create test log entries
        log_before = LogEntry(
            insert_id="before",
            timestamp=datetime(2025, 1, 27, 9, 59, 0),
            severity="ERROR",
            raw_data={}
        )
        
        log_within = LogEntry(
            insert_id="within",
            timestamp=datetime(2025, 1, 27, 10, 3, 0),
            severity="ERROR",
            raw_data={}
        )
        
        log_after = LogEntry(
            insert_id="after",
            timestamp=datetime(2025, 1, 27, 10, 6, 0),
            severity="ERROR",
            raw_data={}
        )
        
        assert window.accepts_log(log_before) is False
        assert window.accepts_log(log_within) is True
        assert window.accepts_log(log_after) is False
    
    def test_time_window_add_log(self):
        """Test adding logs to window."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Create test logs
        valid_log = LogEntry(
            insert_id="valid",
            timestamp=datetime(2025, 1, 27, 10, 3, 0),
            severity="ERROR",
            raw_data={}
        )
        
        invalid_log = LogEntry(
            insert_id="invalid",
            timestamp=datetime(2025, 1, 27, 10, 6, 0),
            severity="ERROR",
            raw_data={}
        )
        
        # Valid log should be added
        assert window.add_log(valid_log) is True
        assert len(window.logs) == 1
        assert window.logs[0] == valid_log
        
        # Invalid log should be rejected
        assert window.add_log(invalid_log) is False
        assert len(window.logs) == 1
    
    def test_time_window_get_error_logs(self):
        """Test filtering for error-level logs."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Add logs of different severities
        logs = [
            LogEntry(insert_id="info", timestamp=start_time, severity="INFO", raw_data={}),
            LogEntry(insert_id="error", timestamp=start_time, severity="ERROR", raw_data={}),
            LogEntry(insert_id="critical", timestamp=start_time, severity="CRITICAL", raw_data={}),
            LogEntry(insert_id="warning", timestamp=start_time, severity="WARNING", raw_data={})
        ]
        
        for log in logs:
            window.add_log(log)
        
        error_logs = window.get_error_logs()
        assert len(error_logs) == 2
        assert error_logs[0].severity == "ERROR"
        assert error_logs[1].severity == "CRITICAL"
    
    def test_time_window_get_service_groups(self):
        """Test grouping logs by service."""
        start_time = datetime(2025, 1, 27, 10, 0, 0)
        window = TimeWindow(start_time=start_time, duration_minutes=5)
        
        # Add logs from different services
        logs = [
            LogEntry(insert_id="1", timestamp=start_time, service_name="service-a", severity="ERROR", raw_data={}),
            LogEntry(insert_id="2", timestamp=start_time, service_name="service-a", severity="INFO", raw_data={}),
            LogEntry(insert_id="3", timestamp=start_time, service_name="service-b", severity="ERROR", raw_data={}),
            LogEntry(insert_id="4", timestamp=start_time, service_name=None, severity="WARN", raw_data={})
        ]
        
        for log in logs:
            window.add_log(log)
        
        groups = window.get_service_groups()
        assert len(groups) == 3
        assert len(groups["service-a"]) == 2
        assert len(groups["service-b"]) == 1
        assert len(groups["unknown"]) == 1


class TestLogAccumulator:
    """Test LogAccumulator functionality."""
    
    @pytest.fixture
    def mock_callback(self):
        """Create mock callback for testing."""
        return MagicMock()
    
    def test_log_accumulator_initialization(self, mock_callback):
        """Test LogAccumulator initialization."""
        accumulator = LogAccumulator(
            window_duration_minutes=5,
            max_windows=10,
            on_window_ready=mock_callback
        )
        
        assert accumulator.window_duration_minutes == 5
        assert accumulator.max_windows == 10
        assert accumulator.on_window_ready == mock_callback
        assert len(accumulator.windows) == 0
    
    def test_log_accumulator_round_to_window_start(self, mock_callback):
        """Test timestamp rounding to window boundaries."""
        accumulator = LogAccumulator(
            window_duration_minutes=5,
            on_window_ready=mock_callback
        )
        
        # Test various timestamps
        test_cases = [
            (datetime(2025, 1, 27, 10, 3, 30), datetime(2025, 1, 27, 10, 0, 0)),
            (datetime(2025, 1, 27, 10, 7, 15), datetime(2025, 1, 27, 10, 5, 0)),
            (datetime(2025, 1, 27, 10, 12, 45), datetime(2025, 1, 27, 10, 10, 0)),
        ]
        
        for input_time, expected_start in test_cases:
            result = accumulator._round_to_window_start(input_time)
            assert result == expected_start
    
    def test_log_accumulator_add_log(self, mock_callback):
        """Test adding logs to accumulator."""
        accumulator = LogAccumulator(
            window_duration_minutes=5,
            on_window_ready=mock_callback
        )
        
        # Add a log
        log_data = {
            "insertId": "test-123",
            "timestamp": "2025-01-27T10:03:00Z",
            "severity": "ERROR",
            "textPayload": "Test error"
        }
        
        accumulator.add_log(log_data)
        
        # Should create one window
        assert len(accumulator.windows) == 1
        
        # Window should contain the log
        window = list(accumulator.windows.values())[0]
        assert len(window.logs) == 1
        assert window.logs[0].insert_id == "test-123"
    
    def test_log_accumulator_multiple_windows(self, mock_callback):
        """Test creation of multiple windows for different time ranges."""
        accumulator = LogAccumulator(
            window_duration_minutes=5,
            on_window_ready=mock_callback
        )
        
        # Add logs in different 5-minute windows
        log_data_1 = {
            "insertId": "test-1",
            "timestamp": "2025-01-27T10:03:00Z",  # 10:00-10:05 window
            "severity": "ERROR"
        }
        
        log_data_2 = {
            "insertId": "test-2",
            "timestamp": "2025-01-27T10:07:00Z",  # 10:05-10:10 window
            "severity": "ERROR"
        }
        
        accumulator.add_log(log_data_1)
        accumulator.add_log(log_data_2)
        
        # Should create two windows
        assert len(accumulator.windows) == 2
    
    def test_log_accumulator_window_eviction(self, mock_callback):
        """Test window eviction when max_windows is exceeded."""
        accumulator = LogAccumulator(
            window_duration_minutes=5,
            max_windows=2,
            on_window_ready=mock_callback
        )
        
        # Add logs to create 3 windows (should trigger eviction)
        timestamps = [
            "2025-01-27T10:03:00Z",  # Window 1: 10:00-10:05
            "2025-01-27T10:07:00Z",  # Window 2: 10:05-10:10  
            "2025-01-27T10:13:00Z"   # Window 3: 10:10-10:15 (should evict window 1)
        ]
        
        for i, timestamp in enumerate(timestamps):
            log_data = {
                "insertId": f"test-{i}",
                "timestamp": timestamp,
                "severity": "ERROR"
            }
            accumulator.add_log(log_data)
        
        # Should only have max_windows (2) windows
        assert len(accumulator.windows) == 2
        
        # Callback should have been called for evicted window
        mock_callback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_log_accumulator_start_stop(self, mock_callback):
        """Test starting and stopping the accumulator."""
        accumulator = LogAccumulator(on_window_ready=mock_callback)
        
        # Start should create cleanup task
        accumulator.start()
        assert accumulator._cleanup_task is not None
        assert not accumulator._cleanup_task.done()
        
        # Stop should cancel task and process remaining windows
        await accumulator.stop()
        assert accumulator._shutdown is True


class TestWindowManager:
    """Test WindowManager functionality."""
    
    @pytest.fixture
    def mock_pattern_callback(self):
        """Create mock pattern callback for testing."""
        return MagicMock()
    
    def test_window_manager_initialization(self, mock_pattern_callback):
        """Test WindowManager initialization."""
        manager = WindowManager(
            fast_window_minutes=5,
            trend_window_minutes=15,
            max_windows=20,
            pattern_callback=mock_pattern_callback
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
        
        # Mock the accumulator methods
        manager.fast_accumulator.start = MagicMock()
        manager.trend_accumulator.start = MagicMock()
        manager.fast_accumulator.stop = AsyncMock()
        manager.trend_accumulator.stop = AsyncMock()
        
        # Start should call start on both accumulators
        manager.start()
        manager.fast_accumulator.start.assert_called_once()
        manager.trend_accumulator.start.assert_called_once()
        
        # Stop should call stop on both accumulators
        await manager.stop()
        manager.fast_accumulator.stop.assert_called_once()
        manager.trend_accumulator.stop.assert_called_once()
    
    def test_window_manager_add_log(self, mock_pattern_callback):
        """Test adding logs to both accumulators."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)
        
        # Mock the add_log methods
        manager.fast_accumulator.add_log = MagicMock()
        manager.trend_accumulator.add_log = MagicMock()
        
        log_data = {
            "insertId": "test-123",
            "timestamp": "2025-01-27T10:03:00Z",
            "severity": "ERROR"
        }
        
        manager.add_log(log_data)
        
        # Should call add_log on both accumulators
        manager.fast_accumulator.add_log.assert_called_once_with(log_data)
        manager.trend_accumulator.add_log.assert_called_once_with(log_data)
    
    def test_window_manager_fast_window_callback(self, mock_pattern_callback):
        """Test fast window completion callback."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)
        
        # Create mock window
        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = ["log1", "log2"]
        mock_window.get_error_logs.return_value = ["error1"]
        
        # Call the fast window callback
        manager._on_fast_window_ready(mock_window)
        
        # Should call the pattern callback
        mock_pattern_callback.assert_called_once_with(mock_window)
    
    def test_window_manager_trend_window_callback(self, mock_pattern_callback):
        """Test trend window completion callback."""
        manager = WindowManager(pattern_callback=mock_pattern_callback)
        
        # Create mock window
        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = ["log1", "log2", "log3"]
        mock_window.get_error_logs.return_value = ["error1", "error2"]
        
        # Call the trend window callback
        manager._on_trend_window_ready(mock_window)
        
        # Should call the pattern callback
        mock_pattern_callback.assert_called_once_with(mock_window)
    
    def test_window_manager_callback_error_handling(self, mock_pattern_callback):
        """Test error handling in window callbacks."""
        # Make callback raise an exception
        mock_pattern_callback.side_effect = RuntimeError("Test error")
        
        manager = WindowManager(pattern_callback=mock_pattern_callback)
        
        mock_window = MagicMock()
        mock_window.start_time = datetime(2025, 1, 27, 10, 0, 0)
        mock_window.logs = []
        mock_window.get_error_logs.return_value = []
        
        # Should not raise exception (error should be logged)
        with patch('gemini_sre_agent.pattern_detector.logger') as mock_logger:
            manager._on_fast_window_ready(mock_window)
            manager._on_trend_window_ready(mock_window)
            
            # Should log errors
            assert mock_logger.error.call_count == 2


@pytest.mark.integration
class TestPatternDetectorIntegration:
    """Integration tests for the complete pattern detection system."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_pattern_detection(self):
        """Test complete flow from log ingestion to pattern detection."""
        received_windows = []
        
        def pattern_callback(window):
            received_windows.append(window)
        
        # Create manager with short windows for testing
        manager = WindowManager(
            fast_window_minutes=1,  # Very short for testing
            trend_window_minutes=2,
            pattern_callback=pattern_callback
        )
        
        manager.start()
        
        try:
            # Add logs over time
            base_time = datetime.now(timezone.utc)
            logs = [
                {
                    "insertId": f"test-{i}",
                    "timestamp": (base_time + timedelta(seconds=i*10)).isoformat() + "Z",
                    "severity": "ERROR" if i % 2 == 0 else "INFO",
                    "textPayload": f"Test message {i}",
                    "resource": {
                        "labels": {"service_name": f"service-{i % 2}"}
                    }
                }
                for i in range(6)
            ]
            
            for log_data in logs:
                manager.add_log(log_data)
            
            # Wait a bit for window processing
            await asyncio.sleep(0.1)
            
            # Verify logs were distributed correctly
            assert len(manager.fast_accumulator.windows) > 0
            assert len(manager.trend_accumulator.windows) > 0
            
        finally:
            await manager.stop()
    
    def test_realistic_log_data_processing(self):
        """Test with realistic GCP log data structure."""
        received_windows = []
        
        def pattern_callback(window):
            received_windows.append(window)
        
        manager = WindowManager(
            fast_window_minutes=5,
            pattern_callback=pattern_callback
        )
        
        # Realistic GCP Cloud Run log
        realistic_log = {
            "insertId": "1234567890abcdef",
            "logName": "projects/my-project/logs/run.googleapis.com%2Frequest",
            "receiveTimestamp": "2025-01-27T10:03:45.123456Z",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {
                    "service_name": "billing-service",
                    "revision_name": "billing-service-00001-abc",
                    "location": "us-central1"
                }
            },
            "severity": "ERROR",
            "textPayload": "Database connection failed: java.sql.SQLException: Connection refused",
            "timestamp": "2025-01-27T10:03:44.987654Z",
            "trace": "projects/my-project/traces/abc123def456"
        }
        
        manager.add_log(realistic_log)
        
        # Verify log was processed correctly
        assert len(manager.fast_accumulator.windows) == 1
        window = list(manager.fast_accumulator.windows.values())[0]
        assert len(window.logs) == 1
        
        log_entry = window.logs[0]
        assert log_entry.service_name == "billing-service"
        assert log_entry.severity == "ERROR"
        assert log_entry.error_message is not None
        assert "Database connection failed" in log_entry.error_message