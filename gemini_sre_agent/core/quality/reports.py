# gemini_sre_agent/core/quality/reports.py
"""
Quality gate reporting and formatting.

This module provides comprehensive reporting capabilities for quality gate results,
including HTML, JSON, and console output formats.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from ..logging import get_logger
from .gates import QualityGateResult, QualityGateStatus

logger = get_logger(__name__)


class ReportFormat(Enum):
    """Supported report formats."""
    JSON = "json"
    HTML = "html"
    CONSOLE = "console"
    MARKDOWN = "markdown"


@dataclass
class QualityReport:
    """Comprehensive quality report."""
    timestamp: datetime
    total_gates: int
    passed_gates: int
    failed_gates: int
    skipped_gates: int
    error_gates: int
    results: list[QualityGateResult] = field(default_factory=list)
    duration: float = 0.0
    success: bool = True

    @property
    def pass_rate(self) -> float:
        """Calculate pass rate percentage."""
        if self.total_gates == 0:
            return 0.0
        return (self.passed_gates / self.total_gates) * 100

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate percentage."""
        if self.total_gates == 0:
            return 0.0
        return ((self.failed_gates + self.error_gates) / self.total_gates) * 100


class QualityReportGenerator:
    """Generates quality reports from gate results."""

    def __init__(self):
        """Initialize the report generator."""
        self.logger = get_logger(__name__)

    def generate_report(
        self, 
        results: list[QualityGateResult], 
        duration: float = 0.0
    ) -> QualityReport:
        """Generate a comprehensive quality report.
        
        Args:
            results: List of quality gate results.
            duration: Total execution duration in seconds.
            
        Returns:
            Generated quality report.
        """
        total_gates = len(results)
        passed_gates = len([r for r in results if r.status == QualityGateStatus.PASSED])
        failed_gates = len([r for r in results if r.status == QualityGateStatus.FAILED])
        skipped_gates = len([r for r in results if r.status == QualityGateStatus.SKIPPED])
        error_gates = len([r for r in results if r.status == QualityGateStatus.ERROR])

        success = failed_gates == 0 and error_gates == 0

        return QualityReport(
            timestamp=datetime.now(),
            total_gates=total_gates,
            passed_gates=passed_gates,
            failed_gates=failed_gates,
            skipped_gates=skipped_gates,
            error_gates=error_gates,
            results=results,
            duration=duration,
            success=success
        )


class QualityReportFormatter:
    """Formats quality reports for different output formats."""

    def __init__(self):
        """Initialize the report formatter."""
        self.logger = get_logger(__name__)

    def format_report(self, report: QualityReport, format_type: ReportFormat) -> str:
        """Format a quality report.
        
        Args:
            report: Quality report to format.
            format_type: Output format type.
            
        Returns:
            Formatted report string.
        """
        if format_type == ReportFormat.JSON:
            return self._format_json(report)
        elif format_type == ReportFormat.HTML:
            return self._format_html(report)
        elif format_type == ReportFormat.MARKDOWN:
            return self._format_markdown(report)
        else:
            return self._format_console(report)

    def _format_json(self, report: QualityReport) -> str:
        """Format report as JSON.
        
        Args:
            report: Quality report to format.
            
        Returns:
            JSON formatted report.
        """
        data = {
            "timestamp": report.timestamp.isoformat(),
            "summary": {
                "total_gates": report.total_gates,
                "passed_gates": report.passed_gates,
                "failed_gates": report.failed_gates,
                "skipped_gates": report.skipped_gates,
                "error_gates": report.error_gates,
                "pass_rate": report.pass_rate,
                "failure_rate": report.failure_rate,
                "success": report.success,
                "duration": report.duration
            },
            "results": [
                {
                    "gate_name": result.gate_name,
                    "status": result.status.value,
                    "message": result.message,
                    "duration": result.duration,
                    "timestamp": result.timestamp.isoformat(),
                    "details": result.details
                }
                for result in report.results
            ]
        }

        return json.dumps(data, indent=2, default=str)

    def _format_html(self, report: QualityReport) -> str:
        """Format report as HTML.
        
        Args:
            report: Quality report to format.
            
        Returns:
            HTML formatted report.
        """
        status_icons = {
            QualityGateStatus.PASSED: "✅",
            QualityGateStatus.FAILED: "❌",
            QualityGateStatus.WARNING: "⚠️",
            QualityGateStatus.SKIPPED: "⏭️",
            QualityGateStatus.ERROR: "💥"
        }

        status_colors = {
            QualityGateStatus.PASSED: "#28a745",
            QualityGateStatus.FAILED: "#dc3545",
            QualityGateStatus.WARNING: "#ffc107",
            QualityGateStatus.SKIPPED: "#6c757d",
            QualityGateStatus.ERROR: "#dc3545"
        }

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Quality Gate Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ 
                    background-color: #f8f9fa; 
                    padding: 20px; 
                    border-radius: 5px; 
                    margin-bottom: 20px; 
                }}
                .summary {{ 
                    display: grid; 
                    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); 
                    gap: 15px; 
                    margin-bottom: 20px; 
                }}
                .summary-card {{ 
                    background-color: white; 
                    padding: 15px; 
                    border-radius: 5px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                }}
                .summary-card h3 {{ margin: 0 0 10px 0; color: #333; }}
                .summary-card .value {{ font-size: 24px; font-weight: bold; }}
                .results {{ 
                    background-color: white; 
                    border-radius: 5px; 
                    box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
                }}
                .result-item {{ padding: 15px; border-bottom: 1px solid #eee; }}
                .result-item:last-child {{ border-bottom: none; }}
                .result-header {{ display: flex; align-items: center; gap: 10px; }}
                .result-status {{ font-size: 20px; }}
                .result-name {{ font-weight: bold; font-size: 16px; }}
                .result-message {{ color: #666; margin-top: 5px; }}
                .result-details {{ margin-top: 10px; font-size: 12px; color: #888; }}
                .success {{ color: #28a745; }}
                .failure {{ color: #dc3545; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Quality Gate Report</h1>
                <p>Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>Duration: {report.duration:.2f} seconds</p>
            </div>
            
            <div class="summary">
                <div class="summary-card">
                    <h3>Total Gates</h3>
                    <div class="value">{report.total_gates}</div>
                </div>
                <div class="summary-card">
                    <h3>Passed</h3>
                    <div class="value success">{report.passed_gates}</div>
                </div>
                <div class="summary-card">
                    <h3>Failed</h3>
                    <div class="value failure">{report.failed_gates + report.error_gates}</div>
                </div>
                <div class="summary-card">
                    <h3>Pass Rate</h3>
                    <div class="value">{report.pass_rate:.1f}%</div>
                </div>
            </div>
            
            <div class="results">
                <h2>Gate Results</h2>
        """

        for result in report.results:
            status_icon = status_icons.get(result.status, "❓")
            status_color = status_colors.get(result.status, "#6c757d")

            html += f"""
                <div class="result-item">
                    <div class="result-header">
                        <span class="result-status">{status_icon}</span>
                        <span class="result-name">{result.gate_name}</span>
                        <span style="color: {status_color}; font-weight: bold;">
                            {result.status.value.upper()}
                        </span>
                    </div>
                    <div class="result-message">{result.message}</div>
                    <div class="result-details">
                        Duration: {result.duration:.2f}s | 
                        Timestamp: {result.timestamp.strftime('%H:%M:%S')}
                    </div>
                </div>
            """

        html += """
            </div>
        </body>
        </html>
        """

        return html

    def _format_markdown(self, report: QualityReport) -> str:
        """Format report as Markdown.
        
        Args:
            report: Quality report to format.
            
        Returns:
            Markdown formatted report.
        """
        status_icons = {
            QualityGateStatus.PASSED: "✅",
            QualityGateStatus.FAILED: "❌",
            QualityGateStatus.WARNING: "⚠️",
            QualityGateStatus.SKIPPED: "⏭️",
            QualityGateStatus.ERROR: "💥"
        }

        md = f"""# Quality Gate Report

**Generated:** {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}  
**Duration:** {report.duration:.2f} seconds  
**Overall Status:** {'✅ PASSED' if report.success else '❌ FAILED'}

## Summary

| Metric | Value |
|--------|-------|
| Total Gates | {report.total_gates} |
| Passed | {report.passed_gates} |
| Failed | {report.failed_gates + report.error_gates} |
| Skipped | {report.skipped_gates} |
| Pass Rate | {report.pass_rate:.1f}% |
| Failure Rate | {report.failure_rate:.1f}% |

## Gate Results

"""

        for result in report.results:
            status_icon = status_icons.get(result.status, "❓")
            md += f"""### {status_icon} {result.gate_name}

- **Status:** {result.status.value.upper()}
- **Message:** {result.message}
- **Duration:** {result.duration:.2f}s
- **Timestamp:** {result.timestamp.strftime('%H:%M:%S')}

"""

        return md

    def _format_console(self, report: QualityReport) -> str:
        """Format report for console output.
        
        Args:
            report: Quality report to format.
            
        Returns:
            Console formatted report.
        """
        status_icons = {
            QualityGateStatus.PASSED: "✅",
            QualityGateStatus.FAILED: "❌",
            QualityGateStatus.WARNING: "⚠️",
            QualityGateStatus.SKIPPED: "⏭️",
            QualityGateStatus.ERROR: "💥"
        }

        output = []
        output.append("=" * 60)
        output.append("QUALITY GATE REPORT")
        output.append("=" * 60)
        output.append(f"Generated: {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        output.append(f"Duration: {report.duration:.2f} seconds")
        output.append(f"Overall Status: {'✅ PASSED' if report.success else '❌ FAILED'}")
        output.append("")

        output.append("SUMMARY:")
        output.append(f"  Total Gates: {report.total_gates}")
        output.append(f"  Passed: {report.passed_gates}")
        output.append(f"  Failed: {report.failed_gates + report.error_gates}")
        output.append(f"  Skipped: {report.skipped_gates}")
        output.append(f"  Pass Rate: {report.pass_rate:.1f}%")
        output.append("")

        output.append("GATE RESULTS:")
        for result in report.results:
            status_icon = status_icons.get(result.status, "❓")
            output.append(f"  {status_icon} {result.gate_name}: {result.status.value.upper()}")
            output.append(f"    Message: {result.message}")
            output.append(f"    Duration: {result.duration:.2f}s")
            output.append("")

        output.append("=" * 60)

        return "\n".join(output)

    def save_report(
        self, 
        report: QualityReport, 
        file_path: Path, 
        format_type: ReportFormat
    ) -> None:
        """Save a quality report to a file.
        
        Args:
            report: Quality report to save.
            file_path: Path to save the report.
            format_type: Format type for the report.
        """
        try:
            content = self.format_report(report, format_type)

            # Ensure directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            self.logger.info(f"Quality report saved to {file_path}")

        except Exception as e:
            self.logger.error(f"Failed to save quality report: {e!s}")
            raise
