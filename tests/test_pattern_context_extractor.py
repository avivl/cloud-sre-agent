"""
Comprehensive unit tests for PatternContextExtractor.

Tests temporal analysis, service pattern detection, error classification,
and historical context extraction for Gemini ML pattern detection.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from gemini_sre_agent.ml.gemini_prompt_engine import PatternContext
from gemini_sre_agent.ml.pattern_context_extractor import PatternContextExtractor
from gemini_sre_agent.pattern_detector.models import LogEntry, TimeWindow


class TestPatternContextExtractor:
    """Test PatternContextExtractor functionality."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        """Create extractor instance."""
        return PatternContextExtractor()

    @pytest.fixture
    def sample_window(self) -> TimeWindow:
        """Create sample time window with logs."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=10)

        # Add diverse logs for testing
        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Database connection timeout",
                raw_data={},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=start_time + timedelta(seconds=30),
                severity="CRITICAL",
                service_name="db-service",
                error_message="Connection pool exhausted",
                raw_data={},
            ),
            LogEntry(
                insert_id="log3",
                timestamp=start_time + timedelta(seconds=45),
                severity="ERROR",
                service_name="auth-service",
                error_message="Token validation failed",
                raw_data={},
            ),
            LogEntry(
                insert_id="log4",
                timestamp=start_time + timedelta(minutes=2),
                severity="WARNING",
                service_name="api-service",
                error_message="High memory usage detected",
                raw_data={},
            ),
        ]
        return window

    @pytest.mark.asyncio
    async def test_extract_context_basic(self, extractor, sample_window):
        """Test basic context extraction."""
        context = await extractor.extract_context(sample_window)

        assert isinstance(context, PatternContext)
        assert context.error_frequency == 4
        assert "10min window" in context.time_window
        assert "api-service" in context.affected_services
        assert "db-service" in context.affected_services
        assert context.primary_service == "api-service"
        assert "database_error" in context.error_types
        assert context.severity_distribution["ERROR"] == 2

    @pytest.mark.asyncio
    async def test_extract_context_with_historical_data(self, extractor, sample_window):
        """Test context extraction with historical data."""
        historical_data = {
            "baseline_comparison": "200% above normal",
            "trend_analysis": "Sharp increase from 10:00",
            "similar_incidents": ["INC-001", "INC-002"],
            "recent_changes": ["API v2.1.0 deployment"],
        }

        context = await extractor.extract_context(sample_window, historical_data)

        assert context.baseline_comparison == "200% above normal"
        assert context.trend_analysis == "Sharp increase from 10:00"
        assert "INC-001" in context.similar_incidents
        assert "API v2.1.0 deployment" in context.recent_changes

    @pytest.mark.asyncio
    async def test_extract_context_with_code_extractor(self, extractor, sample_window):
        """Test context extraction with code context extractor."""
        mock_code_extractor = AsyncMock()
        mock_code_extractor.extract_code_context.return_value = {
            "git_context": {
                "code_changes_summary": "Recent auth service updates",
                "recent_commits": ["abc123: Fix auth timeout"],
            },
            "static_analysis": {"complexity_warnings": 2},
            "complexity_metrics": {"coverage": 0.85},
            "dependency_vulnerabilities": ["CVE-2024-1234"],
            "error_related_files": ["auth.py", "middleware.py"],
        }

        context = await extractor.extract_context(
            sample_window, code_context_extractor=mock_code_extractor
        )

        assert context.code_changes_context == "Recent auth service updates"
        assert "abc123: Fix auth timeout" in context.recent_commits
        assert "CVE-2024-1234" in context.dependency_vulnerabilities
        assert "auth.py" in context.error_related_files

    @pytest.mark.asyncio
    async def test_extract_context_code_extractor_failure(
        self, extractor, sample_window
    ):
        """Test handling of code extractor failures."""
        mock_code_extractor = AsyncMock()
        mock_code_extractor.extract_code_context.side_effect = Exception("Git error")

        context = await extractor.extract_context(
            sample_window, code_context_extractor=mock_code_extractor
        )

        # Should have empty code context on failure
        assert context.code_changes_context is None
        assert context.static_analysis_findings is None


class TestTemporalAnalysis:
    """Test temporal pattern analysis."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        return PatternContextExtractor()

    @pytest.mark.asyncio
    async def test_rapid_burst_pattern(self, extractor):
        """Test rapid burst pattern detection."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        # Create rapid burst: 10 errors in 30 seconds
        window.logs = []
        for i in range(10):
            window.logs.append(
                LogEntry(
                    insert_id=f"log{i}",
                    timestamp=start_time + timedelta(seconds=i * 3),
                    severity="ERROR",
                    service_name="api-service",
                    error_message=f"Error {i}",
                    raw_data={},
                )
            )

        temporal_features = await extractor._analyze_temporal_patterns(window)

        assert "Rapid burst" in temporal_features["burst_pattern"]

    @pytest.mark.asyncio
    async def test_periodic_pattern(self, extractor):
        """Test periodic pattern detection."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=10)

        # Create periodic pattern: errors every 60 seconds
        window.logs = []
        for i in range(5):
            window.logs.append(
                LogEntry(
                    insert_id=f"log{i}",
                    timestamp=start_time + timedelta(seconds=i * 60),
                    severity="ERROR",
                    service_name="api-service",
                    error_message=f"Periodic error {i}",
                    raw_data={},
                )
            )

        temporal_features = await extractor._analyze_temporal_patterns(window)

        assert "Periodic pattern" in temporal_features["burst_pattern"]

    @pytest.mark.asyncio
    async def test_accelerating_pattern(self, extractor):
        """Test accelerating error pattern detection."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=10)

        # Create accelerating pattern: decreasing intervals
        intervals = [120, 60, 30, 15, 8]  # Accelerating
        window.logs = []
        current_time = start_time
        for i, interval in enumerate(intervals):
            window.logs.append(
                LogEntry(
                    insert_id=f"log{i}",
                    timestamp=current_time,
                    severity="ERROR",
                    service_name="api-service",
                    error_message=f"Error {i}",
                    raw_data={},
                )
            )
            current_time += timedelta(seconds=interval)

        temporal_features = await extractor._analyze_temporal_patterns(window)

        assert "Accelerating pattern" in temporal_features["burst_pattern"]

    def test_check_acceleration(self, extractor):
        """Test acceleration detection algorithm."""
        # Accelerating intervals (decreasing)
        accelerating = [120, 60, 40, 20, 10]
        assert extractor._check_acceleration(accelerating)

        # Stable intervals
        stable = [60, 60, 60, 60, 60]
        assert not extractor._check_acceleration(stable)

        # Insufficient data
        short = [60, 30]
        assert not extractor._check_acceleration(short)

    @pytest.mark.asyncio
    async def test_time_distribution_analysis(self, extractor):
        """Test time distribution analysis."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=8)

        # Concentrate errors in first quarter
        window.logs = []
        for i in range(10):
            window.logs.append(
                LogEntry(
                    insert_id=f"log{i}",
                    timestamp=start_time + timedelta(seconds=i * 10),
                    severity="ERROR",
                    service_name="api-service",
                    error_message=f"Error {i}",
                    raw_data={},
                )
            )

        temporal_features = await extractor._analyze_temporal_patterns(window)

        assert "Heavily concentrated in quarter 1" in temporal_features["distribution"]


class TestServicePatternAnalysis:
    """Test service pattern analysis."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        return PatternContextExtractor()

    @pytest.mark.asyncio
    async def test_single_service_impact(self, extractor):
        """Test single service impact analysis."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Service error",
                raw_data={},
            )
        ]

        service_features = await extractor._analyze_service_patterns(window)

        assert service_features["primary_service"] == "api-service"
        assert len(service_features["affected_services"]) == 1
        assert "Single service affected" in service_features["interaction_pattern"]

    @pytest.mark.asyncio
    async def test_cascade_failure_detection(self, extractor):
        """Test cascade failure pattern detection."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        # Primary service has most errors
        window.logs = []
        for i in range(8):  # 8 errors from primary
            window.logs.append(
                LogEntry(
                    insert_id=f"primary{i}",
                    timestamp=start_time + timedelta(seconds=i * 10),
                    severity="ERROR",
                    service_name="primary-service",
                    error_message=f"Primary error {i}",
                    raw_data={},
                )
            )

        # Secondary services have fewer errors
        for service in ["secondary1", "secondary2"]:
            window.logs.append(
                LogEntry(
                    insert_id=f"{service}_error",
                    timestamp=start_time + timedelta(minutes=1),
                    severity="ERROR",
                    service_name=f"{service}-service",
                    error_message=f"{service} error",
                    raw_data={},
                )
            )

        service_features = await extractor._analyze_service_patterns(window)

        assert "dominant" in service_features["interaction_pattern"]
        assert service_features["primary_service"] == "primary-service"

    @pytest.mark.asyncio
    async def test_cross_service_timing_analysis(self, extractor):
        """Test cross-service timing correlation analysis."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        # Simultaneous failures (within 30 seconds)
        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time,
                severity="ERROR",
                service_name="service-a",
                error_message="Error A",
                raw_data={},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=start_time + timedelta(seconds=15),
                severity="ERROR",
                service_name="service-b",
                error_message="Error B",
                raw_data={},
            ),
        ]

        service_features = await extractor._analyze_service_patterns(window)

        assert "Simultaneous failure" in service_features["cross_service_timing"]


class TestErrorPatternAnalysis:
    """Test error pattern analysis."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        return PatternContextExtractor()

    def test_error_type_classification(self, extractor):
        """Test error message classification."""
        # Database errors
        assert (
            extractor._classify_error_type("Database connection failed")
            == "database_error"
        )
        assert extractor._classify_error_type("SQL query timeout") == "database_error"

        # Network errors
        assert (
            extractor._classify_error_type("Connection timeout") == "connectivity_error"
        )
        assert (
            extractor._classify_error_type("Network unreachable")
            == "connectivity_error"
        )

        # Auth errors
        assert extractor._classify_error_type("Unauthorized access") == "auth_error"
        assert extractor._classify_error_type("Token validation failed") == "auth_error"

        # Resource errors
        assert extractor._classify_error_type("Out of memory") == "resource_error"
        assert extractor._classify_error_type("CPU usage high") == "resource_error"

        # Generic errors
        assert extractor._classify_error_type("Something went wrong") == "generic_error"

    def test_message_similarity_calculation(self, extractor):
        """Test error message similarity scoring."""
        # Identical messages
        identical = ["Database timeout", "Database timeout"]
        assert extractor._calculate_message_similarity(identical) == 1.0

        # Similar messages
        similar = ["Database connection timeout", "Database query timeout"]
        similarity = extractor._calculate_message_similarity(similar)
        assert 0.0 < similarity < 1.0

        # Different messages
        different = ["Database error", "Network failure"]
        similarity = extractor._calculate_message_similarity(different)
        assert 0.0 <= similarity < 0.5

        # Single message
        single = ["Single error message"]
        assert extractor._calculate_message_similarity(single) == 1.0

        # Empty messages
        empty = []
        assert extractor._calculate_message_similarity(empty) == 0.0

    @pytest.mark.asyncio
    async def test_error_pattern_analysis_comprehensive(self, extractor):
        """Test comprehensive error pattern analysis."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        window.logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time,
                severity="ERROR",
                service_name="api-service",
                error_message="Database connection timeout",
                raw_data={},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=start_time,
                severity="CRITICAL",
                service_name="api-service",
                error_message="Database query timeout",
                raw_data={},
            ),
        ]

        error_features = await extractor._analyze_error_patterns(window)

        assert "database_error" in error_features["error_types"]
        assert error_features["severity_distribution"]["ERROR"] == 1
        assert error_features["severity_distribution"]["CRITICAL"] == 1
        assert len(error_features["message_samples"]) == 2
        assert error_features["similarity_score"] >= 0.5  # Similar database messages


class TestHistoricalContextAnalysis:
    """Test historical context analysis."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        return PatternContextExtractor()

    @pytest.mark.asyncio
    async def test_historical_context_extraction(self, extractor):
        """Test historical context data extraction."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        historical_data = {
            "baseline_comparison": "150% above baseline",
            "trend_analysis": "Gradual increase over 2 hours",
            "similar_incidents": ["INC-001", "INC-002", "INC-003", "INC-004"],
            "recent_changes": [
                "DB migration",
                "API update",
                "Config change",
                "Extra change",
            ],
        }

        context = await extractor._analyze_historical_context(window, historical_data)

        assert context["baseline_comparison"] == "150% above baseline"
        assert context["trend_analysis"] == "Gradual increase over 2 hours"
        assert len(context["similar_incidents"]) == 3  # Limited to top 3
        assert len(context["recent_changes"]) == 3  # Limited to top 3

    @pytest.mark.asyncio
    async def test_empty_historical_data(self, extractor):
        """Test handling of empty historical data."""
        start_time = datetime.now(timezone.utc)
        window = TimeWindow(start_time=start_time, duration_minutes=5)

        context = await extractor._analyze_historical_context(window, {})

        assert "No baseline data available" in context["baseline_comparison"]
        assert "No trend data available" in context["trend_analysis"]
        assert context["similar_incidents"] == []
        assert "No recent change information available" in context["recent_changes"]


class TestCodeContextFormatting:
    """Test code context formatting methods."""

    @pytest.fixture
    def extractor(self) -> PatternContextExtractor:
        return PatternContextExtractor()

    def test_format_code_context(self, extractor):
        """Test code context formatting."""
        code_analysis = {
            "git_context": {
                "code_changes_summary": "Auth service refactor",
                "recent_commits": ["abc123: Fix auth bug"],
            },
            "static_analysis": {
                "pylint": Mock(
                    success=True,
                    severity_counts={"error": 2, "warning": 5},
                    files_analyzed=10,
                    findings=["finding1", "finding2"],
                    analysis_time_ms=150,
                )
            },
            "complexity_metrics": {"coverage": 0.85, "complexity": 7.2},
            "dependency_vulnerabilities": ["CVE-2024-1234"],
            "error_related_files": ["auth.py"],
        }

        formatted = extractor._format_code_context(code_analysis)

        assert formatted["code_changes_context"] == "Auth service refactor"
        assert "abc123: Fix auth bug" in formatted["recent_commits"]
        assert "pylint" in formatted["static_analysis_findings"]
        assert formatted["code_quality_metrics"]["coverage"] == 0.85
        assert "CVE-2024-1234" in formatted["dependency_vulnerabilities"]

    def test_format_static_analysis_findings(self, extractor):
        """Test static analysis findings formatting."""
        static_analysis = {
            "pylint": Mock(
                success=True,
                severity_counts={"error": 2},
                files_analyzed=5,
                findings=["f1", "f2"],
                analysis_time_ms=100,
            ),
            "failed_tool": Mock(success=False, error_message="Tool failed"),
        }

        formatted = extractor._format_static_analysis_findings(static_analysis)

        assert "pylint" in formatted
        assert formatted["pylint"]["severity_counts"] == {"error": 2}
        assert formatted["pylint"]["files_analyzed"] == 5
        assert formatted["failed_tool"]["error"] == "Tool failed"

    def test_empty_code_context(self, extractor):
        """Test empty code context generation."""
        empty_context = extractor._empty_code_context()

        assert empty_context["code_changes_context"] is None
        assert empty_context["static_analysis_findings"] is None
        assert empty_context["code_quality_metrics"] is None
        assert empty_context["dependency_vulnerabilities"] is None
        assert empty_context["error_related_files"] is None
        assert empty_context["recent_commits"] is None
