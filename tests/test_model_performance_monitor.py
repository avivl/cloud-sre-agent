"""
Unit tests for model performance monitoring and drift detection.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.ml.drift_detector import DriftDetector, MetricsCalculator
from gemini_sre_agent.ml.model_performance_monitor import ModelPerformanceMonitor
from gemini_sre_agent.ml.performance_config import (
    DriftAlert,
    PerformanceConfig,
    PerformanceMetrics,
)


class TestModelPerformanceMonitor:
    """Test cases for ModelPerformanceMonitor class."""

    @pytest.fixture
    def config(self) -> PerformanceConfig:
        """Create a test performance configuration."""
        return PerformanceConfig(
            window_size=10,
            recent_window_size=5,
            pattern_accuracy_window=3,
            max_pattern_history=20,
            baseline_establishment_size=5,
            accuracy_drift_threshold=0.20,
            confidence_drift_threshold=0.25,
            high_drift_threshold=0.35,
            drift_check_interval_seconds=60,
            min_samples_for_drift_check=8,
        )

    @pytest.fixture
    def monitor(self, config: PerformanceConfig) -> ModelPerformanceMonitor:
        """Create a ModelPerformanceMonitor instance with test configuration."""
        return ModelPerformanceMonitor(config)

    def test_initialization(self, monitor: ModelPerformanceMonitor):
        """Test ModelPerformanceMonitor initialization."""
        assert len(monitor.accuracy_history) == 0
        assert len(monitor.confidence_history) == 0
        assert len(monitor.latency_history) == 0
        assert len(monitor.pattern_type_accuracy) == 0
        assert monitor.baseline_accuracy is None
        assert monitor.baseline_confidence is None
        assert monitor.baseline_latency is None
        assert len(monitor.drift_alerts) == 0
        assert isinstance(monitor.drift_detector, DriftDetector)

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        monitor = ModelPerformanceMonitor()
        assert monitor.config.window_size == 100
        assert monitor.config.accuracy_drift_threshold == 0.15
        assert monitor.config.baseline_establishment_size == 20

    @pytest.mark.asyncio
    async def test_track_prediction_accuracy_correct(
        self, monitor: ModelPerformanceMonitor
    ):
        """Test tracking correct prediction."""
        await monitor.track_prediction_accuracy(
            prediction="memory_leak",
            actual_outcome="memory_leak",
            confidence_score=0.85,
            latency_ms=120.5,
        )

        assert len(monitor.accuracy_history) == 1
        assert monitor.accuracy_history[0] == 1.0
        assert monitor.confidence_history[0] == 0.85
        assert monitor.latency_history[0] == 120.5
        assert len(monitor.pattern_type_accuracy["memory_leak"]) == 1
        assert monitor.pattern_type_accuracy["memory_leak"][0] == 1.0

    @pytest.mark.asyncio
    async def test_track_prediction_accuracy_incorrect(
        self, monitor: ModelPerformanceMonitor
    ):
        """Test tracking incorrect prediction."""
        await monitor.track_prediction_accuracy(
            prediction="memory_leak",
            actual_outcome="cpu_spike",
            confidence_score=0.60,
            latency_ms=95.0,
        )

        assert len(monitor.accuracy_history) == 1
        assert monitor.accuracy_history[0] == 0.0
        assert monitor.confidence_history[0] == 0.60
        assert monitor.latency_history[0] == 95.0

    @pytest.mark.asyncio
    async def test_baseline_establishment(self, monitor: ModelPerformanceMonitor):
        """Test baseline metrics establishment."""
        # Add enough samples to establish baseline
        for i in range(5):
            await monitor.track_prediction_accuracy(
                prediction="memory_leak",
                actual_outcome="memory_leak" if i < 4 else "cpu_spike",
                confidence_score=0.8 + i * 0.02,
                latency_ms=100.0 + i * 10,
            )

        # Baseline should be established after 5 samples
        assert monitor.baseline_accuracy is not None
        assert monitor.baseline_confidence is not None
        assert monitor.baseline_latency is not None
        assert monitor.baseline_accuracy == 0.8  # 4/5 correct
        assert (
            abs(monitor.baseline_confidence - 0.84) < 1e-10
        )  # Mean of 0.8, 0.82, 0.84, 0.86, 0.88
        assert monitor.baseline_latency == 120.0  # Mean of 100, 110, 120, 130, 140

    def test_get_performance_metrics_empty(self, monitor: ModelPerformanceMonitor):
        """Test getting metrics when no data is available."""
        metrics = monitor.get_performance_metrics()
        expected = PerformanceMetrics.empty_metrics()
        assert metrics == expected

    @pytest.mark.asyncio
    async def test_get_performance_metrics_with_data(
        self, monitor: ModelPerformanceMonitor
    ):
        """Test getting metrics with data."""
        # Add test data
        for i in range(8):
            await monitor.track_prediction_accuracy(
                prediction="memory_leak",
                actual_outcome="memory_leak" if i < 6 else "cpu_spike",
                confidence_score=0.75 + i * 0.02,
                latency_ms=80.0 + i * 5,
            )

        metrics = monitor.get_performance_metrics()

        assert metrics["total_predictions"] == 8
        assert metrics["overall_accuracy"] == 0.75  # 6/8 correct
        assert metrics["baseline_established"] is True
        assert metrics["drift_check_enabled"] is True
        assert "pattern_accuracy" in metrics
        assert "memory_leak" in metrics["pattern_accuracy"]

    def test_get_drift_summary_no_alerts(self, monitor: ModelPerformanceMonitor):
        """Test drift summary with no alerts."""
        summary = monitor.get_drift_summary()
        assert summary["has_drift"] is False
        assert summary["total_alerts"] == 0
        assert summary["recent_alerts"] == []
        assert summary["severity_counts"] == {"HIGH": 0, "MEDIUM": 0, "LOW": 0}

    def test_get_drift_summary_with_alerts(self, monitor: ModelPerformanceMonitor):
        """Test drift summary with alerts."""
        # Add test alerts
        alert1 = DriftAlert(
            drift_type="accuracy_drift",
            severity="HIGH",
            baseline_value=0.8,
            current_value=0.4,
            drift_amount=0.4,
            timestamp=datetime.now(),
        )
        alert2 = DriftAlert(
            drift_type="confidence_drift",
            severity="MEDIUM",
            baseline_value=0.85,
            current_value=0.6,
            drift_amount=0.25,
            timestamp=datetime.now(),
        )
        monitor.drift_alerts = [alert1, alert2]

        summary = monitor.get_drift_summary()
        assert summary["has_drift"] is True
        assert summary["total_alerts"] == 2
        assert len(summary["recent_alerts"]) == 2
        assert summary["severity_counts"]["HIGH"] == 1
        assert summary["severity_counts"]["MEDIUM"] == 1
        assert summary["high_severity_recent"] == 2

    def test_reset_drift_alerts(self, monitor: ModelPerformanceMonitor):
        """Test resetting drift alerts."""
        # Add test alerts
        monitor.drift_alerts = [
            DriftAlert(
                drift_type="accuracy_drift",
                severity="HIGH",
                baseline_value=0.8,
                current_value=0.4,
                drift_amount=0.4,
                timestamp=datetime.now(),
            )
        ]

        cleared_count = monitor.reset_drift_alerts()
        assert cleared_count == 1
        assert len(monitor.drift_alerts) == 0

    @pytest.mark.asyncio
    async def test_drift_check_conditions(self, monitor: ModelPerformanceMonitor):
        """Test drift check timing conditions."""
        # Add enough samples but don't wait for interval
        for i in range(8):
            await monitor.track_prediction_accuracy(
                prediction="memory_leak",
                actual_outcome="memory_leak",
                confidence_score=0.8,
                latency_ms=100.0,
            )

        # Should not trigger drift check immediately
        assert monitor._should_check_drift() is False

        # Simulate time passage
        monitor.last_drift_check = datetime.now() - timedelta(seconds=70)
        assert monitor._should_check_drift() is True

    def test_can_check_drift(self, monitor: ModelPerformanceMonitor):
        """Test drift check capability conditions."""
        # Initially cannot check drift
        assert monitor._can_check_drift() is False

        # Add samples but no baseline
        for _ in range(8):
            monitor.accuracy_history.append(1.0)

        assert monitor._can_check_drift() is False

        # Set baseline
        monitor.baseline_accuracy = 0.8
        assert monitor._can_check_drift() is True

    @pytest.mark.asyncio
    async def test_drift_detection_integration(self, monitor: ModelPerformanceMonitor):
        """Test drift detection integration with DriftDetector."""
        # Establish baseline with good accuracy
        for _ in range(5):
            await monitor.track_prediction_accuracy(
                prediction="memory_leak",
                actual_outcome="memory_leak",
                confidence_score=0.85,
                latency_ms=100.0,
            )

        # Simulate time passage for drift check
        monitor.last_drift_check = datetime.now() - timedelta(seconds=70)

        # Add samples with poor accuracy to trigger drift
        for _ in range(5):
            await monitor.track_prediction_accuracy(
                prediction="memory_leak",
                actual_outcome="cpu_spike",  # All incorrect
                confidence_score=0.9,  # High confidence but wrong
                latency_ms=200.0,  # Higher latency
            )

        # Should have detected drift
        assert len(monitor.drift_alerts) > 0
        drift_types = {alert.drift_type for alert in monitor.drift_alerts}
        assert "accuracy_drift" in drift_types

    def test_pattern_accuracy_tracking(self, monitor: ModelPerformanceMonitor):
        """Test pattern-specific accuracy tracking."""
        # Add mixed pattern predictions
        patterns_data = [
            ("memory_leak", "memory_leak", True),
            ("memory_leak", "cpu_spike", False),
            ("cpu_spike", "cpu_spike", True),
            ("network_issue", "network_issue", True),
            ("network_issue", "memory_leak", False),
        ]

        for pattern, actual, _ in patterns_data:
            monitor.accuracy_history.append(1.0)
            monitor.confidence_history.append(0.8)
            monitor.latency_history.append(100.0)
            monitor.pattern_type_accuracy[pattern].append(
                1.0 if pattern == actual else 0.0
            )

        pattern_accuracy = monitor._calculate_pattern_accuracy()

        assert "memory_leak" in pattern_accuracy
        assert "cpu_spike" in pattern_accuracy
        assert "network_issue" in pattern_accuracy
        assert pattern_accuracy["memory_leak"]["accuracy"] == 0.5  # 1/2 correct
        assert pattern_accuracy["cpu_spike"]["accuracy"] == 1.0  # 1/1 correct
        assert pattern_accuracy["network_issue"]["accuracy"] == 0.5  # 1/2 correct

    def test_pattern_history_trimming(self, monitor: ModelPerformanceMonitor):
        """Test pattern history trimming."""
        pattern = "memory_leak"

        # Add more samples than max_pattern_history
        for i in range(25):  # Config has max_pattern_history=20
            monitor.pattern_type_accuracy[pattern].append(float(i % 2))

        monitor._trim_pattern_history(pattern)

        # Should be trimmed to max size
        assert len(monitor.pattern_type_accuracy[pattern]) == 20
        # Should keep the most recent samples
        assert monitor.pattern_type_accuracy[pattern][-1] == 0.0  # 24 % 2 = 0
        assert monitor.pattern_type_accuracy[pattern][-2] == 1.0  # 23 % 2 = 1


class TestMetricsCalculator:
    """Test cases for MetricsCalculator helper class."""

    def test_calculate_recent_metrics_empty(self):
        """Test calculating recent metrics with empty history."""
        result = MetricsCalculator.calculate_recent_metrics([], 5)
        assert result == 0.0

    def test_calculate_recent_metrics_partial(self):
        """Test calculating recent metrics with partial data."""
        history = [1.0, 0.8, 0.6, 0.9, 0.7, 0.5]
        result = MetricsCalculator.calculate_recent_metrics(history, 3)
        # Should use last 3: 0.9, 0.7, 0.5 -> mean = 0.7
        assert result == 0.7

    def test_calculate_recent_metrics_full_window(self):
        """Test calculating recent metrics with full window."""
        history = [1.0, 0.8]
        result = MetricsCalculator.calculate_recent_metrics(history, 5)
        # Should use all available: 1.0, 0.8 -> mean = 0.9
        assert result == 0.9

    def test_calculate_pattern_accuracy_empty(self):
        """Test calculating pattern accuracy with empty data."""
        result = MetricsCalculator.calculate_pattern_accuracy([], 5)
        expected = {"accuracy": 0.0, "sample_count": 0, "recent_samples": 0}
        assert result == expected

    def test_calculate_pattern_accuracy_with_data(self):
        """Test calculating pattern accuracy with data."""
        accuracies = [1.0, 1.0, 0.0, 1.0, 0.0, 1.0]
        result = MetricsCalculator.calculate_pattern_accuracy(accuracies, 4)

        assert result["sample_count"] == 6
        assert result["recent_samples"] == 4
        # Recent 4: 0.0, 1.0, 0.0, 1.0 -> mean = 0.5
        assert result["accuracy"] == 0.5

    def test_trim_history_no_trimming(self):
        """Test trimming history when no trimming needed."""
        history = [1.0, 2.0, 3.0]
        result = MetricsCalculator.trim_history(history, 5)
        assert result == history

    def test_trim_history_with_trimming(self):
        """Test trimming history when trimming needed."""
        history = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = MetricsCalculator.trim_history(history, 3)
        assert result == [3.0, 4.0, 5.0]

    def test_analyze_drift_alerts_empty(self):
        """Test analyzing drift alerts with no alerts."""
        result = MetricsCalculator.analyze_drift_alerts([])
        expected = {
            "has_drift": False,
            "total_alerts": 0,
            "recent_alerts": [],
            "severity_counts": {"HIGH": 0, "MEDIUM": 0, "LOW": 0},
        }
        assert result == expected

    def test_analyze_drift_alerts_with_data(self):
        """Test analyzing drift alerts with data."""
        alerts = [
            DriftAlert(
                drift_type="accuracy_drift",
                severity="HIGH",
                baseline_value=0.8,
                current_value=0.4,
                drift_amount=0.4,
                timestamp=datetime.now(),
            ),
            DriftAlert(
                drift_type="confidence_drift",
                severity="MEDIUM",
                baseline_value=0.85,
                current_value=0.6,
                drift_amount=0.25,
                timestamp=datetime.now(),
            ),
            DriftAlert(
                drift_type="latency_drift",
                severity="LOW",
                baseline_value=100.0,
                current_value=120.0,
                drift_amount=20.0,
                timestamp=datetime.now(),
            ),
        ]

        result = MetricsCalculator.analyze_drift_alerts(alerts)

        assert result["has_drift"] is True
        assert result["total_alerts"] == 3
        assert len(result["recent_alerts"]) == 3
        assert result["severity_counts"]["HIGH"] == 1
        assert result["severity_counts"]["MEDIUM"] == 1
        assert result["severity_counts"]["LOW"] == 1
        assert result["high_severity_recent"] == 2  # HIGH and MEDIUM


class TestDriftDetector:
    """Test cases for DriftDetector class."""

    @pytest.fixture
    def config(self) -> PerformanceConfig:
        """Create a test performance configuration."""
        return PerformanceConfig(
            accuracy_drift_threshold=0.15,
            confidence_drift_threshold=0.20,
            high_drift_threshold=0.25,
            latency_drift_multiplier=1.5,
        )

    @pytest.fixture
    def detector(self, config: PerformanceConfig) -> DriftDetector:
        """Create a DriftDetector instance."""
        return DriftDetector(config)

    @pytest.mark.asyncio
    async def test_accuracy_drift_detection_no_baseline(self, detector: DriftDetector):
        """Test accuracy drift detection with no baseline."""
        alerts = []
        await detector.check_accuracy_drift(0.7, None, alerts)
        assert len(alerts) == 0

    @pytest.mark.asyncio
    async def test_accuracy_drift_detection_no_drift(self, detector: DriftDetector):
        """Test accuracy drift detection with no drift."""
        alerts = []
        await detector.check_accuracy_drift(0.82, 0.8, alerts)
        assert len(alerts) == 0  # 0.02 drift < 0.15 threshold

    @pytest.mark.asyncio
    async def test_accuracy_drift_detection_medium_drift(self, detector: DriftDetector):
        """Test accuracy drift detection with medium drift."""
        alerts = []
        await detector.check_accuracy_drift(0.6, 0.8, alerts)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.drift_type == "accuracy_drift"
        assert alert.severity == "MEDIUM"  # 0.2 drift < 0.25 high threshold
        assert alert.baseline_value == 0.8
        assert alert.current_value == 0.6
        assert abs(alert.drift_amount - 0.2) < 1e-10

    @pytest.mark.asyncio
    async def test_accuracy_drift_detection_high_drift(self, detector: DriftDetector):
        """Test accuracy drift detection with high drift."""
        alerts = []
        await detector.check_accuracy_drift(0.5, 0.8, alerts)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == "HIGH"  # 0.3 drift > 0.25 high threshold
        assert abs(alert.drift_amount - 0.3) < 1e-10

    @pytest.mark.asyncio
    async def test_confidence_drift_detection(self, detector: DriftDetector):
        """Test confidence drift detection."""
        alerts = []
        await detector.check_confidence_drift(0.6, 0.85, alerts)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.drift_type == "confidence_drift"
        assert alert.severity == "MEDIUM"
        assert alert.drift_amount == 0.25

    @pytest.mark.asyncio
    async def test_latency_drift_detection(self, detector: DriftDetector):
        """Test latency drift detection."""
        alerts = []
        await detector.check_latency_drift(200.0, 100.0, alerts)

        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.drift_type == "latency_drift"
        assert alert.severity == "MEDIUM"
        assert alert.drift_amount == 100.0  # (2.0 - 1.0) * 100

    def test_determine_drift_severity(self, detector: DriftDetector):
        """Test drift severity determination."""
        assert detector._determine_drift_severity(0.30, 0.25) == "HIGH"
        assert detector._determine_drift_severity(0.20, 0.25) == "MEDIUM"  # > 0.125
        assert detector._determine_drift_severity(0.10, 0.25) == "LOW"


class TestPerformanceConfig:
    """Test cases for PerformanceConfig dataclass."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = PerformanceConfig()
        assert config.window_size == 100
        assert config.recent_window_size == 25
        assert config.baseline_establishment_size == 20
        assert config.accuracy_drift_threshold == 0.15
        assert config.confidence_drift_threshold == 0.20
        assert config.latency_drift_multiplier == 2.0

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = PerformanceConfig(
            window_size=50,
            accuracy_drift_threshold=0.10,
            drift_check_interval_seconds=1800,
        )
        assert config.window_size == 50
        assert config.accuracy_drift_threshold == 0.10
        assert config.drift_check_interval_seconds == 1800


class TestDriftAlert:
    """Test cases for DriftAlert dataclass."""

    def test_drift_alert_creation(self):
        """Test creating drift alert."""
        timestamp = datetime.now()
        alert = DriftAlert(
            drift_type="accuracy_drift",
            severity="HIGH",
            baseline_value=0.8,
            current_value=0.4,
            drift_amount=0.4,
            timestamp=timestamp,
        )

        assert alert.drift_type == "accuracy_drift"
        assert alert.severity == "HIGH"
        assert alert.baseline_value == 0.8
        assert alert.current_value == 0.4
        assert alert.drift_amount == 0.4
        assert alert.timestamp == timestamp

    def test_drift_alert_string_representation(self):
        """Test drift alert string representation."""
        alert = DriftAlert(
            drift_type="accuracy_drift",
            severity="HIGH",
            baseline_value=0.800,
            current_value=0.400,
            drift_amount=0.400,
            timestamp=datetime.now(),
        )

        expected = "ACCURACY_DRIFT(HIGH): baseline=0.800, current=0.400, drift=0.400"
        assert str(alert) == expected


class TestPerformanceMetrics:
    """Test cases for PerformanceMetrics helper class."""

    def test_empty_metrics(self):
        """Test empty metrics structure."""
        metrics = PerformanceMetrics.empty_metrics()
        assert metrics["overall_accuracy"] == 0.0
        assert metrics["baseline_accuracy"] is None
        assert metrics["total_predictions"] == 0
        assert metrics["baseline_established"] is False

    def test_calculate_drift_percentage(self):
        """Test drift percentage calculation."""
        assert (
            abs(PerformanceMetrics.calculate_drift_percentage(0.8, 0.9) - 12.5) < 1e-10
        )
        assert (
            abs(PerformanceMetrics.calculate_drift_percentage(0.8, 0.7) - (-12.5))
            < 1e-10
        )
        assert PerformanceMetrics.calculate_drift_percentage(0.0, 0.5) == 0.0

    def test_is_significant_drift(self):
        """Test significant drift detection."""
        assert PerformanceMetrics.is_significant_drift(0.8, 0.6, 0.15) is True
        assert PerformanceMetrics.is_significant_drift(0.8, 0.75, 0.15) is False
        assert PerformanceMetrics.is_significant_drift(0.8, 0.95, 0.10) is True

    def test_categorize_drift_severity(self):
        """Test drift severity categorization."""
        assert PerformanceMetrics.categorize_drift_severity(0.30, 0.25) == "HIGH"
        assert PerformanceMetrics.categorize_drift_severity(0.20, 0.25) == "MEDIUM"
        assert PerformanceMetrics.categorize_drift_severity(0.10, 0.25) == "LOW"
