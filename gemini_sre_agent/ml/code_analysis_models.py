"""
Data models for code context analysis.

This module defines the data structures used by CodeContextExtractor
for git analysis, static analysis, and code quality metrics.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class CodeAnalysisConfig:
    """Configuration for code context analysis."""

    repository_path: str
    enable_static_analysis: bool = False
    enable_complexity_analysis: bool = False
    enable_dependency_scan: bool = False
    analysis_timeout_seconds: int = 30
    max_recent_commits: int = 10

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.analysis_timeout_seconds <= 0:
            raise ValueError("analysis_timeout_seconds must be positive")
        if self.max_recent_commits <= 0:
            raise ValueError("max_recent_commits must be positive")

        # Convert to Path for validation
        repo_path = Path(self.repository_path)
        if not repo_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repository_path}")


@dataclass
class CodeChange:
    """Represents a git commit with associated metadata."""

    commit_hash: str
    timestamp: datetime
    author: str
    message: str
    files_changed: List[str]
    lines_added: int
    lines_deleted: int
    is_rollback: bool = False

    def __post_init__(self) -> None:
        """Validate code change data after initialization."""
        if not self.commit_hash:
            raise ValueError("commit_hash cannot be empty")
        if not self.author:
            raise ValueError("author cannot be empty")
        if self.lines_added < 0:
            raise ValueError("lines_added cannot be negative")
        if self.lines_deleted < 0:
            raise ValueError("lines_deleted cannot be negative")

    @property
    def short_hash(self) -> str:
        """Return shortened commit hash."""
        return self.commit_hash[:8]

    @property
    def net_lines_changed(self) -> int:
        """Return net change in lines (added - deleted)."""
        return self.lines_added - self.lines_deleted

    @property
    def total_lines_changed(self) -> int:
        """Return total lines affected (added + deleted)."""
        return self.lines_added + self.lines_deleted


@dataclass
class StaticAnalysisResult:
    """Results from static code analysis tools."""

    tool_name: str
    findings: List[Dict[str, Any]]
    scan_duration_seconds: float
    files_analyzed: List[str]
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0

    def __post_init__(self) -> None:
        """Validate static analysis result after initialization."""
        if not self.tool_name:
            raise ValueError("tool_name cannot be empty")
        if self.scan_duration_seconds < 0:
            raise ValueError("scan_duration_seconds cannot be negative")
        if self.error_count < 0:
            raise ValueError("error_count cannot be negative")
        if self.warning_count < 0:
            raise ValueError("warning_count cannot be negative")
        if self.info_count < 0:
            raise ValueError("info_count cannot be negative")

    @property
    def total_findings(self) -> int:
        """Return total number of findings."""
        return self.error_count + self.warning_count + self.info_count

    @property
    def has_errors(self) -> bool:
        """Return True if any errors were found."""
        return self.error_count > 0

    def get_findings_by_severity(self, severity: str) -> List[Dict[str, Any]]:
        """Get findings filtered by severity level."""
        return [
            finding
            for finding in self.findings
            if finding.get("severity", "").lower() == severity.lower()
        ]


@dataclass
class ComplexityMetrics:
    """Code complexity and quality metrics."""

    cyclomatic_complexity: float
    cognitive_complexity: float
    maintainability_index: float
    lines_of_code: int
    technical_debt_ratio: float
    code_coverage: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate complexity metrics after initialization."""
        if self.cyclomatic_complexity < 0:
            raise ValueError("cyclomatic_complexity cannot be negative")
        if self.cognitive_complexity < 0:
            raise ValueError("cognitive_complexity cannot be negative")
        if not (0 <= self.maintainability_index <= 100):
            raise ValueError("maintainability_index must be between 0 and 100")
        if self.lines_of_code < 0:
            raise ValueError("lines_of_code cannot be negative")
        if not (0 <= self.technical_debt_ratio <= 1):
            raise ValueError("technical_debt_ratio must be between 0 and 1")
        if self.code_coverage is not None and not (0 <= self.code_coverage <= 100):
            raise ValueError("code_coverage must be between 0 and 100")

    @property
    def complexity_rating(self) -> str:
        """Return human-readable complexity rating."""
        if self.cyclomatic_complexity <= 10:
            return "Low"
        elif self.cyclomatic_complexity <= 20:
            return "Moderate"
        elif self.cyclomatic_complexity <= 50:
            return "High"
        else:
            return "Very High"

    @property
    def maintainability_rating(self) -> str:
        """Return human-readable maintainability rating."""
        if self.maintainability_index >= 85:
            return "Excellent"
        elif self.maintainability_index >= 70:
            return "Good"
        elif self.maintainability_index >= 50:
            return "Moderate"
        elif self.maintainability_index >= 25:
            return "Poor"
        else:
            return "Very Poor"


@dataclass
class DependencyVulnerability:
    """Security vulnerability in project dependency."""

    package_name: str
    current_version: str
    vulnerability_id: str
    severity: str
    description: str
    fixed_version: Optional[str] = None
    cve_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate dependency vulnerability after initialization."""
        if not self.package_name:
            raise ValueError("package_name cannot be empty")
        if not self.current_version:
            raise ValueError("current_version cannot be empty")
        if not self.vulnerability_id:
            raise ValueError("vulnerability_id cannot be empty")
        if self.severity.upper() not in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            raise ValueError("severity must be CRITICAL, HIGH, MEDIUM, or LOW")

    @property
    def is_fixable(self) -> bool:
        """Return True if a fix is available."""
        return self.fixed_version is not None

    @property
    def severity_score(self) -> int:
        """Return numeric severity score for sorting."""
        severity_map = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}
        return severity_map.get(self.severity.upper(), 0)
