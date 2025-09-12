"""
Tests for baseline tracking logic.
"""

from datetime import datetime, timedelta

import pytest

from gemini_sre_agent.pattern_detector.baseline_tracker import BaselineTracker
from gemini_sre_agent.pattern_detector.models import LogEntry, TimeWindow


class TestBaselineTracker:
    """Test BaselineTracker functionality."""

    @pytest.fixture
    def sample_windows(self) -> None:
        """Create sample time windows for testing."""
        base_time = datetime(2025, 1, 27, 10, 0, 0)
        windows = []
        for i in range(5):
            window = TimeWindow(
                start_time=base_time + timedelta(minutes=i * 5), duration_minutes=5
            )
            for j in range(10):
                severity = "ERROR" if j < i + 1 else "INFO"
                log = LogEntry(
                    insert_id=f"log-{i}-{j}",
                    timestamp=window.start_time + timedelta(seconds=j * 30),
                    severity=severity,
                    service_name=f"service-{j % 3}",
                    raw_data={"severity": severity},
                )
                window.add_log(log)
            windows.append(window)
        return windows

    def test_baseline_tracker_initialization(self) -> None:
        """Test BaselineTracker initialization."""
        tracker = BaselineTracker(max_history=50)
        assert tracker.max_history == 50
        assert len(tracker.global_baseline) == 0
        assert len(tracker.service_baselines) == 0

    def test_baseline_tracker_update(self, sample_windows: str) -> None:
        """Test updating baseline with window data."""
        tracker = BaselineTracker()
        tracker.update_baseline(sample_windows[0])
        assert len(tracker.global_baseline) == 1
        assert tracker.global_baseline[0] == 10.0
        assert len(tracker.service_baselines) == 3

    def test_baseline_tracker_history_limit(self, sample_windows: str) -> None:
        """Test baseline history limit enforcement."""
        tracker = BaselineTracker(max_history=3)
        for window in sample_windows:
            tracker.update_baseline(window)
        assert len(tracker.global_baseline) == 3
        expected_rates = [30.0, 40.0, 50.0]
        assert tracker.global_baseline == expected_rates

    def test_baseline_tracker_get_global_baseline(self, sample_windows: str) -> None:
        """Test getting global baseline average."""
        tracker = BaselineTracker()
        for window in sample_windows[:3]:
            tracker.update_baseline(window)
        baseline = tracker.get_global_baseline(2)
        expected = (20.0 + 30.0) / 2
        assert baseline == expected

    def test_baseline_tracker_get_service_baseline(self, sample_windows: str) -> None:
        """Test getting service-specific baseline."""
        tracker = BaselineTracker()
        for window in sample_windows[:3]:
            tracker.update_baseline(window)
        service_baseline = tracker.get_service_baseline("service-0", 2)
        assert service_baseline >= 0.0
