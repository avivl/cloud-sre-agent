"""
Tests for CodeContextExtractor and related models.

This module tests code context analysis including git analysis,
static analysis integration, and code quality metrics extraction.
"""

import asyncio
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.ml.code_analysis_models import (
    CodeAnalysisConfig,
    CodeChange,
    ComplexityMetrics,
    DependencyVulnerability,
    StaticAnalysisResult,
)
from gemini_sre_agent.ml.code_context_extractor import CodeContextExtractor
from gemini_sre_agent.pattern_detector.models import LogEntry, TimeWindow


class TestCodeAnalysisConfig:
    """Test CodeAnalysisConfig data model."""

    def test_valid_config_creation(self, tmp_path: Path) -> None:
        """Test creating valid configuration."""
        config = CodeAnalysisConfig(
            repository_path=str(tmp_path),
            enable_static_analysis=True,
            enable_complexity_analysis=True,
            enable_dependency_scan=True,
            analysis_timeout_seconds=60,
            max_recent_commits=20,
        )

        assert config.repository_path == str(tmp_path)
        assert config.enable_static_analysis is True
        assert config.enable_complexity_analysis is True
        assert config.enable_dependency_scan is True
        assert config.analysis_timeout_seconds == 60
        assert config.max_recent_commits == 20

    def test_config_with_defaults(self, tmp_path: Path) -> None:
        """Test configuration with default values."""
        config = CodeAnalysisConfig(repository_path=str(tmp_path))

        assert config.enable_static_analysis is False
        assert config.enable_complexity_analysis is False
        assert config.enable_dependency_scan is False
        assert config.analysis_timeout_seconds == 30
        assert config.max_recent_commits == 10

    def test_invalid_timeout(self, tmp_path: Path) -> None:
        """Test configuration with invalid timeout."""
        with pytest.raises(
            ValueError, match="analysis_timeout_seconds must be positive"
        ):
            CodeAnalysisConfig(
                repository_path=str(tmp_path), analysis_timeout_seconds=0
            )

    def test_invalid_commit_count(self, tmp_path: Path) -> None:
        """Test configuration with invalid commit count."""
        with pytest.raises(ValueError, match="max_recent_commits must be positive"):
            CodeAnalysisConfig(repository_path=str(tmp_path), max_recent_commits=-1)

    def test_nonexistent_repository(self) -> None:
        """Test configuration with nonexistent repository path."""
        with pytest.raises(ValueError, match="Repository path does not exist"):
            CodeAnalysisConfig(repository_path="/nonexistent/path")


class TestCodeChange:
    """Test CodeChange data model."""

    def test_valid_code_change_creation(self) -> None:
        """Test creating valid code change."""
        timestamp = datetime.now()
        change = CodeChange(
            commit_hash="abcd1234567890",
            timestamp=timestamp,
            author="test-author",
            message="Test commit message",
            files_changed=["file1.py", "file2.py"],
            lines_added=10,
            lines_deleted=5,
            is_rollback=False,
        )

        assert change.commit_hash == "abcd1234567890"
        assert change.timestamp == timestamp
        assert change.author == "test-author"
        assert change.message == "Test commit message"
        assert change.files_changed == ["file1.py", "file2.py"]
        assert change.lines_added == 10
        assert change.lines_deleted == 5
        assert change.is_rollback is False

    def test_code_change_properties(self) -> None:
        """Test CodeChange computed properties."""
        change = CodeChange(
            commit_hash="abcd1234567890abcdef",
            timestamp=datetime.now(),
            author="test-author",
            message="Test commit",
            files_changed=["file.py"],
            lines_added=15,
            lines_deleted=5,
        )

        assert change.short_hash == "abcd1234"
        assert change.net_lines_changed == 10
        assert change.total_lines_changed == 20

    def test_empty_commit_hash(self) -> None:
        """Test code change with empty commit hash."""
        with pytest.raises(ValueError, match="commit_hash cannot be empty"):
            CodeChange(
                commit_hash="",
                timestamp=datetime.now(),
                author="test-author",
                message="Test commit",
                files_changed=[],
                lines_added=0,
                lines_deleted=0,
            )

    def test_empty_author(self) -> None:
        """Test code change with empty author."""
        with pytest.raises(ValueError, match="author cannot be empty"):
            CodeChange(
                commit_hash="abcd1234",
                timestamp=datetime.now(),
                author="",
                message="Test commit",
                files_changed=[],
                lines_added=0,
                lines_deleted=0,
            )

    def test_negative_lines(self) -> None:
        """Test code change with negative line counts."""
        with pytest.raises(ValueError, match="lines_added cannot be negative"):
            CodeChange(
                commit_hash="abcd1234",
                timestamp=datetime.now(),
                author="test-author",
                message="Test commit",
                files_changed=[],
                lines_added=-1,
                lines_deleted=0,
            )

        with pytest.raises(ValueError, match="lines_deleted cannot be negative"):
            CodeChange(
                commit_hash="abcd1234",
                timestamp=datetime.now(),
                author="test-author",
                message="Test commit",
                files_changed=[],
                lines_added=0,
                lines_deleted=-1,
            )


class TestStaticAnalysisResult:
    """Test StaticAnalysisResult data model."""

    def test_valid_static_analysis_result(self) -> None:
        """Test creating valid static analysis result."""
        findings = [
            {"severity": "error", "message": "Syntax error"},
            {"severity": "warning", "message": "Unused variable"},
        ]

        result = StaticAnalysisResult(
            tool_name="pylint",
            findings=findings,
            scan_duration_seconds=2.5,
            files_analyzed=["file1.py", "file2.py"],
            error_count=1,
            warning_count=1,
            info_count=0,
        )

        assert result.tool_name == "pylint"
        assert result.findings == findings
        assert result.scan_duration_seconds == 2.5
        assert result.files_analyzed == ["file1.py", "file2.py"]
        assert result.error_count == 1
        assert result.warning_count == 1
        assert result.info_count == 0

    def test_static_analysis_properties(self) -> None:
        """Test StaticAnalysisResult computed properties."""
        result = StaticAnalysisResult(
            tool_name="test-tool",
            findings=[],
            scan_duration_seconds=1.0,
            files_analyzed=[],
            error_count=2,
            warning_count=3,
            info_count=1,
        )

        assert result.total_findings == 6
        assert result.has_errors is True

        result_no_errors = StaticAnalysisResult(
            tool_name="test-tool",
            findings=[],
            scan_duration_seconds=1.0,
            files_analyzed=[],
            error_count=0,
            warning_count=1,
            info_count=0,
        )

        assert result_no_errors.has_errors is False

    def test_get_findings_by_severity(self) -> None:
        """Test filtering findings by severity."""
        findings = [
            {"severity": "ERROR", "message": "Error 1"},
            {"severity": "warning", "message": "Warning 1"},
            {"severity": "ERROR", "message": "Error 2"},
        ]

        result = StaticAnalysisResult(
            tool_name="test-tool",
            findings=findings,
            scan_duration_seconds=1.0,
            files_analyzed=[],
        )

        errors = result.get_findings_by_severity("error")
        warnings = result.get_findings_by_severity("warning")

        assert len(errors) == 2
        assert len(warnings) == 1


class TestComplexityMetrics:
    """Test ComplexityMetrics data model."""

    def test_valid_complexity_metrics(self) -> None:
        """Test creating valid complexity metrics."""
        metrics = ComplexityMetrics(
            cyclomatic_complexity=15.0,
            cognitive_complexity=12.0,
            maintainability_index=75.0,
            lines_of_code=500,
            technical_debt_ratio=0.15,
            code_coverage=85.0,
        )

        assert metrics.cyclomatic_complexity == 15.0
        assert metrics.cognitive_complexity == 12.0
        assert metrics.maintainability_index == 75.0
        assert metrics.lines_of_code == 500
        assert metrics.technical_debt_ratio == 0.15
        assert metrics.code_coverage == 85.0

    def test_complexity_ratings(self) -> None:
        """Test complexity rating calculations."""
        # Low complexity
        low_metrics = ComplexityMetrics(
            cyclomatic_complexity=5.0,
            cognitive_complexity=3.0,
            maintainability_index=90.0,
            lines_of_code=100,
            technical_debt_ratio=0.05,
        )
        assert low_metrics.complexity_rating == "Low"
        assert low_metrics.maintainability_rating == "Excellent"

        # High complexity
        high_metrics = ComplexityMetrics(
            cyclomatic_complexity=25.0,
            cognitive_complexity=20.0,
            maintainability_index=30.0,
            lines_of_code=1000,
            technical_debt_ratio=0.8,
        )
        assert high_metrics.complexity_rating == "High"
        assert high_metrics.maintainability_rating == "Poor"

    def test_invalid_complexity_values(self) -> None:
        """Test complexity metrics with invalid values."""
        with pytest.raises(
            ValueError, match="cyclomatic_complexity cannot be negative"
        ):
            ComplexityMetrics(
                cyclomatic_complexity=-1.0,
                cognitive_complexity=5.0,
                maintainability_index=50.0,
                lines_of_code=100,
                technical_debt_ratio=0.1,
            )

        with pytest.raises(
            ValueError, match="maintainability_index must be between 0 and 100"
        ):
            ComplexityMetrics(
                cyclomatic_complexity=5.0,
                cognitive_complexity=5.0,
                maintainability_index=150.0,
                lines_of_code=100,
                technical_debt_ratio=0.1,
            )

        with pytest.raises(ValueError, match="code_coverage must be between 0 and 100"):
            ComplexityMetrics(
                cyclomatic_complexity=5.0,
                cognitive_complexity=5.0,
                maintainability_index=50.0,
                lines_of_code=100,
                technical_debt_ratio=0.1,
                code_coverage=150.0,
            )


class TestDependencyVulnerability:
    """Test DependencyVulnerability data model."""

    def test_valid_dependency_vulnerability(self) -> None:
        """Test creating valid dependency vulnerability."""
        vuln = DependencyVulnerability(
            package_name="requests",
            current_version="2.25.0",
            vulnerability_id="VULN-001",
            severity="HIGH",
            description="Security vulnerability in HTTP handling",
            fixed_version="2.25.1",
            cve_id="CVE-2021-1234",
        )

        assert vuln.package_name == "requests"
        assert vuln.current_version == "2.25.0"
        assert vuln.vulnerability_id == "VULN-001"
        assert vuln.severity == "HIGH"
        assert vuln.description == "Security vulnerability in HTTP handling"
        assert vuln.fixed_version == "2.25.1"
        assert vuln.cve_id == "CVE-2021-1234"

    def test_vulnerability_properties(self) -> None:
        """Test DependencyVulnerability computed properties."""
        fixable_vuln = DependencyVulnerability(
            package_name="package1",
            current_version="1.0.0",
            vulnerability_id="VULN-001",
            severity="CRITICAL",
            description="Critical vulnerability",
            fixed_version="1.0.1",
        )

        unfixable_vuln = DependencyVulnerability(
            package_name="package2",
            current_version="1.0.0",
            vulnerability_id="VULN-002",
            severity="LOW",
            description="Low severity issue",
        )

        assert fixable_vuln.is_fixable is True
        assert fixable_vuln.severity_score == 4
        assert unfixable_vuln.is_fixable is False
        assert unfixable_vuln.severity_score == 1

    def test_invalid_severity(self) -> None:
        """Test vulnerability with invalid severity."""
        with pytest.raises(
            ValueError, match="severity must be CRITICAL, HIGH, MEDIUM, or LOW"
        ):
            DependencyVulnerability(
                package_name="package",
                current_version="1.0.0",
                vulnerability_id="VULN-001",
                severity="INVALID",
                description="Test vulnerability",
            )


class TestCodeContextExtractor:
    """Test CodeContextExtractor main functionality."""

    @pytest.fixture
    def mock_repo(self, tmp_path: Path) -> Path:
        """Create a mock git repository."""
        repo_path = tmp_path / "test_repo"
        repo_path.mkdir()
        # Create .git directory to simulate git repo
        (repo_path / ".git").mkdir()
        return repo_path

    @pytest.fixture
    def config(self, mock_repo: Path) -> CodeAnalysisConfig:
        """Create test configuration."""
        return CodeAnalysisConfig(
            repository_path=str(mock_repo),
            enable_static_analysis=True,
            enable_complexity_analysis=True,
            enable_dependency_scan=True,
            analysis_timeout_seconds=10,
            max_recent_commits=5,
        )

    @pytest.fixture
    def time_window(self) -> TimeWindow:
        """Create test time window with logs."""
        start_time = datetime.now() - timedelta(hours=1)

        logs = [
            LogEntry(
                insert_id="log1",
                timestamp=start_time + timedelta(minutes=10),
                service_name="auth-service",
                severity="ERROR",
                error_message="Authentication failed in user_auth.py:45",
                raw_data={"textPayload": "Authentication failed"},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=start_time + timedelta(minutes=20),
                service_name="api-service",
                severity="ERROR",
                error_message="Database connection error in db_client.py:123",
                raw_data={"textPayload": "Database error"},
            ),
        ]

        return TimeWindow(
            start_time=start_time,
            duration_minutes=60,
            logs=logs,
        )

    def test_extractor_initialization(self, config: CodeAnalysisConfig) -> None:
        """Test CodeContextExtractor initialization."""
        extractor = CodeContextExtractor(config)
        assert extractor.config == config
        assert extractor.repo_path == Path(config.repository_path)

    def test_initialization_invalid_repo(self) -> None:
        """Test initialization with invalid repository path."""
        with pytest.raises(ValueError, match="Repository path does not exist"):
            config = CodeAnalysisConfig(repository_path="/nonexistent/path")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_extract_git_context_success(
        self,
        mock_subprocess: AsyncMock,
        config: CodeAnalysisConfig,
        time_window: TimeWindow,
    ) -> None:
        """Test successful git context extraction."""
        # Mock git log output
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (
            b"abc123|1234567890|John Doe|Initial commit\ndef456|1234567891|Jane Smith|Bug fix\n",
            b"",
        )
        mock_subprocess.return_value = mock_process

        extractor = CodeContextExtractor(config)
        result = await extractor._extract_git_context(time_window)

        assert "recent_commits" in result
        assert "code_changes_summary" in result
        assert len(result["recent_commits"]) == 2
        assert result["recent_commits"][0]["hash"] == "abc123"
        assert result["recent_commits"][0]["author"] == "John Doe"

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_extract_git_context_failure(
        self,
        mock_subprocess: AsyncMock,
        config: CodeAnalysisConfig,
        time_window: TimeWindow,
    ) -> None:
        """Test git context extraction failure."""
        # Mock git command failure
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"fatal: not a git repository")
        mock_subprocess.return_value = mock_process

        extractor = CodeContextExtractor(config)
        result = await extractor._extract_git_context(time_window)

        assert result["recent_commits"] == []
        assert "Git analysis failed" in result["code_changes_summary"]

    def test_parse_git_log_output(self, config: CodeAnalysisConfig) -> None:
        """Test parsing git log output."""
        extractor = CodeContextExtractor(config)
        output = "abc123|1234567890|John Doe|Initial commit\ndef456|1234567891|Jane Smith|Revert previous changes"

        commits = extractor._parse_git_log_output(output)

        assert len(commits) == 2
        assert commits[0].commit_hash == "abc123"
        assert commits[0].author == "John Doe"
        assert commits[0].message == "Initial commit"
        assert commits[0].is_rollback is False

        assert commits[1].commit_hash == "def456"
        assert commits[1].author == "Jane Smith"
        assert commits[1].message == "Revert previous changes"
        assert commits[1].is_rollback is True

    def test_generate_code_changes_summary(
        self, config: CodeAnalysisConfig, time_window: TimeWindow
    ) -> None:
        """Test generating code changes summary."""
        extractor = CodeContextExtractor(config)

        # Test with commits in window
        commits = [
            CodeChange(
                commit_hash="abc123",
                timestamp=time_window.start_time + timedelta(minutes=30),
                author="John Doe",
                message="Fix bug",
                files_changed=["file1.py"],
                lines_added=5,
                lines_deleted=2,
            ),
            CodeChange(
                commit_hash="def456",
                timestamp=time_window.start_time + timedelta(minutes=45),
                author="Jane Smith",
                message="Revert changes",
                files_changed=["file1.py"],
                lines_added=2,
                lines_deleted=5,
                is_rollback=True,
            ),
        ]

        summary = extractor._generate_code_changes_summary(commits, time_window)
        assert "2 commits during incident window" in summary
        assert "1 rollback/revert commits detected" in summary

    @pytest.mark.asyncio
    async def test_extract_error_related_files(
        self, config: CodeAnalysisConfig, time_window: TimeWindow
    ) -> None:
        """Test extracting error-related files from logs."""
        extractor = CodeContextExtractor(config)

        result = await extractor._extract_error_related_files(time_window)

        assert "user_auth.py:45" in result
        assert "db_client.py:123" in result

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ml.code_context_extractor.asyncio.wait_for")
    async def test_extract_code_context_success(
        self,
        mock_wait_for: AsyncMock,
        config: CodeAnalysisConfig,
        time_window: TimeWindow,
    ) -> None:
        """Test successful code context extraction."""
        # Mock all analysis results
        git_context = {
            "code_changes_summary": "2 commits during window",
            "recent_commits": [{"hash": "abc123", "message": "Test commit"}],
        }

        mock_wait_for.return_value = [
            git_context,  # git context
            {"enabled": True, "findings": []},  # static analysis
            {"complexity_score": 5},  # complexity metrics
            [],  # dependency scan
            ["error.py"],  # error files
        ]

        extractor = CodeContextExtractor(config)
        result = await extractor.extract_code_context(time_window, ["auth-service"])

        assert result["changes_summary"] == "2 commits during window"
        assert result["static_findings"] == {"enabled": True, "findings": []}
        assert result["quality_metrics"] == {"complexity_score": 5}
        assert result["vulnerabilities"] == []
        assert result["related_files"] == ["error.py"]

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ml.code_context_extractor.asyncio.wait_for")
    async def test_extract_code_context_with_exceptions(
        self,
        mock_wait_for: AsyncMock,
        config: CodeAnalysisConfig,
        time_window: TimeWindow,
    ) -> None:
        """Test code context extraction with task exceptions."""
        # Mock some tasks failing
        mock_wait_for.return_value = [
            Exception("Git failed"),  # git context
            {"enabled": True},  # static analysis
            Exception("Complexity failed"),  # complexity metrics
            [],  # dependency scan
            ["error.py"],  # error files
        ]

        extractor = CodeContextExtractor(config)
        result = await extractor.extract_code_context(time_window, ["auth-service"])

        assert result["changes_summary"] == ""
        assert result["static_findings"] == {"enabled": True}
        assert result["quality_metrics"] == {}
        assert result["vulnerabilities"] == []
        assert result["related_files"] == ["error.py"]

    @pytest.mark.asyncio
    async def test_extract_code_context_timeout(
        self, config: CodeAnalysisConfig, time_window: TimeWindow
    ) -> None:
        """Test code context extraction timeout."""
        config_short_timeout = CodeAnalysisConfig(
            repository_path=config.repository_path, analysis_timeout_seconds=0.001
        )

        extractor = CodeContextExtractor(config_short_timeout)

        with patch(
            "gemini_sre_agent.ml.code_context_extractor.asyncio.create_subprocess_exec"
        ) as mock_subprocess:
            # Mock a slow subprocess
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(
                side_effect=asyncio.sleep(1)
            )  # Slow operation
            mock_subprocess.return_value = mock_process

            result = await extractor.extract_code_context(time_window, [])

            assert result["changes_summary"] == "Code context extraction failed"
            assert result["static_findings"] == {}

    @pytest.mark.asyncio
    async def test_empty_analysis_methods(self, config: CodeAnalysisConfig) -> None:
        """Test empty analysis methods."""
        extractor = CodeContextExtractor(config)

        static_result = await extractor._empty_static_analysis()
        assert static_result == {"enabled": False}

        complexity_result = await extractor._empty_complexity_analysis()
        assert complexity_result == {"enabled": False}

        dependency_result = await extractor._empty_dependency_scan()
        assert dependency_result == []

    def test_empty_context(self, config: CodeAnalysisConfig) -> None:
        """Test empty context generation."""
        extractor = CodeContextExtractor(config)
        empty_context = extractor._empty_context()

        expected_keys = [
            "changes_summary",
            "static_findings",
            "quality_metrics",
            "vulnerabilities",
            "related_files",
            "recent_commits",
        ]

        for key in expected_keys:
            assert key in empty_context

        assert empty_context["changes_summary"] == "Code context extraction failed"
