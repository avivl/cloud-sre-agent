"""
Pattern context extraction system for Gemini ML pattern detection.

Extracts comprehensive structured context from time windows including temporal,
service interaction, error characteristics, and historical patterns.
"""

import logging
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import numpy as np

from ..pattern_detector.models import LogEntry, TimeWindow
from .gemini_prompt_engine import PatternContext


class PatternContextExtractor:
    """Extract structured context from time windows for Gemini analysis."""

    def __init__(self):
        """Initialize the context extractor."""
        self.logger = logging.getLogger(__name__)

    async def extract_context(
        self,
        window: TimeWindow,
        historical_data: Optional[Dict] = None,
        code_context_extractor: Optional[Any] = None,
    ) -> PatternContext:
        """Extract comprehensive context from time window.

        Args:
            window: Time window containing logs to analyze
            historical_data: Optional historical context data
            code_context_extractor: Optional code context extractor

        Returns:
            PatternContext with extracted features
        """
        # Temporal analysis
        temporal_features = await self._analyze_temporal_patterns(window)

        # Service analysis
        service_features = await self._analyze_service_patterns(window)

        # Error analysis
        error_features = await self._analyze_error_patterns(window)

        # Historical context
        historical_features = await self._analyze_historical_context(
            window, historical_data or {}
        )

        # Optional source code context
        code_context = None
        if code_context_extractor:
            try:
                code_analysis = await code_context_extractor.extract_code_context(
                    window, service_features["affected_services"]
                )
                code_context = self._format_code_context(code_analysis)
            except Exception as e:
                self.logger.warning(f"Code context extraction failed: {e}")
                code_context = self._empty_code_context()
        else:
            code_context = self._empty_code_context()

        return PatternContext(
            time_window=f"{window.duration_minutes}min window ({window.start_time.strftime('%H:%M:%S')} - {(window.start_time + timedelta(minutes=window.duration_minutes)).strftime('%H:%M:%S')})",
            error_frequency=len(window.logs),
            error_burst_pattern=temporal_features["burst_pattern"],
            temporal_distribution=temporal_features["distribution"],
            affected_services=service_features["affected_services"],
            primary_service=service_features["primary_service"],
            service_interaction_pattern=service_features["interaction_pattern"],
            cross_service_timing=service_features["cross_service_timing"],
            error_types=error_features["error_types"],
            severity_distribution=error_features["severity_distribution"],
            error_messages_sample=error_features["message_samples"],
            error_similarity_score=error_features["similarity_score"],
            baseline_comparison=historical_features["baseline_comparison"],
            trend_analysis=historical_features["trend_analysis"],
            similar_incidents=historical_features["similar_incidents"],
            recent_changes=historical_features["recent_changes"],
            # Source code context
            code_changes_context=code_context["code_changes_context"],
            static_analysis_findings=code_context["static_analysis_findings"],
            code_quality_metrics=code_context["code_quality_metrics"],
            dependency_vulnerabilities=code_context["dependency_vulnerabilities"],
            error_related_files=code_context["error_related_files"],
            recent_commits=code_context["recent_commits"],
        )

    async def _analyze_temporal_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze temporal characteristics of errors."""
        if not window.logs:
            return {"burst_pattern": "No errors", "distribution": "Empty window"}

        timestamps = sorted([log.timestamp for log in window.logs])

        # Calculate time differences
        if len(timestamps) > 1:
            intervals = [
                (timestamps[i + 1] - timestamps[i]).total_seconds()
                for i in range(len(timestamps) - 1)
            ]

            # Analyze burst pattern
            burst_pattern = self._classify_burst_pattern(intervals, timestamps, window)

            # Analyze distribution
            distribution = self._analyze_time_distribution(timestamps, window)
        else:
            burst_pattern = "Single error event"
            distribution = "Point occurrence"

        return {"burst_pattern": burst_pattern, "distribution": distribution}

    def _classify_burst_pattern(
        self, intervals: List[float], timestamps: List[datetime], window: TimeWindow
    ) -> str:
        """Classify the burst pattern of errors."""
        if len(intervals) == 0:
            return "Single event"

        avg_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        total_span = (timestamps[-1] - timestamps[0]).total_seconds()
        window_span = window.duration_minutes * 60

        # High frequency, short intervals
        if avg_interval < 10 and len(intervals) > 5:
            return "Rapid burst (high-frequency errors in tight clusters)"

        # Errors concentrated in small portion of window
        elif total_span < (window_span * 0.3):
            return "Concentrated burst (errors clustered in time)"

        # Regular intervals
        elif std_interval < (avg_interval * 0.3):
            return "Periodic pattern (regular interval errors)"

        # Increasing frequency over time
        elif self._check_acceleration(intervals):
            return "Accelerating pattern (increasing error frequency)"

        # Scattered throughout window
        else:
            return "Distributed pattern (errors spread across time window)"

    def _check_acceleration(self, intervals: List[float]) -> bool:
        """Check if error intervals are decreasing (acceleration)."""
        if len(intervals) < 4:
            return False

        # Split into first half and second half
        mid = len(intervals) // 2
        first_half_avg = np.mean(intervals[:mid])
        second_half_avg = np.mean(intervals[mid:])

        # If second half has shorter intervals, it's accelerating
        return bool(second_half_avg < (first_half_avg * 0.7))

    def _analyze_time_distribution(
        self, timestamps: List[datetime], window: TimeWindow
    ) -> str:
        """Analyze how errors are distributed across the time window."""
        if len(timestamps) <= 1:
            return "Single occurrence"

        # Divide window into quarters
        window_start = window.start_time
        quarter_duration = timedelta(minutes=window.duration_minutes / 4)

        quarters = [0, 0, 0, 0]
        for ts in timestamps:
            elapsed = ts - window_start
            quarter_idx = min(
                3, int(elapsed.total_seconds() / quarter_duration.total_seconds())
            )
            quarters[quarter_idx] += 1

        # Analyze distribution
        total_errors = sum(quarters)
        if total_errors == 0:
            return "No errors"

        # Calculate distribution pattern
        max_quarter = max(quarters)
        max_percentage = (max_quarter / total_errors) * 100

        if max_percentage > 70:
            dominant_quarter = quarters.index(max_quarter) + 1
            return f"Heavily concentrated in quarter {dominant_quarter} ({max_percentage:.0f}% of errors)"

        elif max_percentage > 50:
            return f"Moderately concentrated ({max_percentage:.0f}% in peak quarter)"

        else:
            non_zero_quarters = sum(1 for q in quarters if q > 0)
            return f"Well distributed across {non_zero_quarters} quarters"

    async def _analyze_service_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze service interaction patterns."""
        # Group logs by service
        service_logs = defaultdict(list)
        for log in window.logs:
            service = log.service_name or "unknown"
            service_logs[service].append(log)

        affected_services = list(service_logs.keys())

        if not affected_services:
            return {
                "affected_services": [],
                "primary_service": None,
                "interaction_pattern": "No service information",
                "cross_service_timing": "Unknown",
            }

        # Find primary service (most errors)
        primary_service = max(service_logs.keys(), key=lambda s: len(service_logs[s]))

        # Analyze interaction pattern
        interaction_pattern = self._analyze_service_interactions(service_logs)

        # Analyze cross-service timing
        cross_service_timing = self._analyze_cross_service_timing(service_logs)

        return {
            "affected_services": affected_services,
            "primary_service": primary_service,
            "interaction_pattern": interaction_pattern,
            "cross_service_timing": cross_service_timing,
        }

    def _analyze_service_interactions(
        self, service_logs: Dict[str, List[LogEntry]]
    ) -> str:
        """Analyze how services are interacting during the incident."""
        if len(service_logs) == 1:
            return "Single service affected (isolated incident)"

        elif len(service_logs) == 2:
            return "Two services affected (potential dependency issue)"

        elif len(service_logs) <= 5:
            # Check if there's a dominant service
            error_counts = {service: len(logs) for service, logs in service_logs.items()}
            max_errors = max(error_counts.values())
            total_errors = sum(error_counts.values())

            if max_errors > (total_errors * 0.7):
                return "Multiple services with one dominant (likely cascade from primary service)"
            else:
                return "Multiple services equally affected (potential shared dependency issue)"

        else:
            return f"Wide-scale impact ({len(service_logs)} services affected - potential infrastructure issue)"

    def _analyze_cross_service_timing(
        self, service_logs: Dict[str, List[LogEntry]]
    ) -> str:
        """Analyze timing relationships between service errors."""
        if len(service_logs) <= 1:
            return "Single service - no cross-service timing analysis"

        # Get first error timestamp for each service
        service_first_errors = {}
        for service, logs in service_logs.items():
            if logs:
                service_first_errors[service] = min(log.timestamp for log in logs)

        # Sort services by first error time
        services_by_time = sorted(service_first_errors.items(), key=lambda x: x[1])

        if len(services_by_time) < 2:
            return "Insufficient timing data"

        # Calculate time differences between first errors
        time_diffs = []
        for i in range(1, len(services_by_time)):
            diff = (services_by_time[i][1] - services_by_time[i - 1][1]).total_seconds()
            time_diffs.append(diff)

        # Analyze timing pattern
        if all(diff < 30 for diff in time_diffs):
            return "Simultaneous failure across services (likely shared root cause)"

        elif max(time_diffs) > 300:  # 5 minutes
            return f"Staggered failure over {max(time_diffs):.0f}s (potential cascade pattern)"

        else:
            return f"Sequential failure pattern (services failed {time_diffs[0]:.0f}s apart on average)"

    async def _analyze_error_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze error characteristics and patterns."""
        if not window.logs:
            return {
                "error_types": [],
                "severity_distribution": {},
                "message_samples": [],
                "similarity_score": 0.0,
            }

        # Extract error types from messages
        error_types = []
        for log in window.logs:
            if log.error_message:
                error_type = self._classify_error_type(log.error_message)
                error_types.append(error_type)

        # Count severities
        severity_counts = Counter(log.severity for log in window.logs if log.severity)

        # Get sample error messages
        error_messages = [log.error_message for log in window.logs if log.error_message]
        message_samples = error_messages[:5]  # First 5 messages

        # Calculate message similarity
        similarity_score = self._calculate_message_similarity(error_messages)

        return {
            "error_types": list(set(error_types)) if error_types else ["unknown"],
            "severity_distribution": dict(severity_counts),
            "message_samples": message_samples,
            "similarity_score": similarity_score,
        }

    def _classify_error_type(self, error_message: str) -> str:
        """Classify error type from message content."""
        message_lower = error_message.lower()

        # Database errors
        if any(
            keyword in message_lower
            for keyword in ["database", "sql", "connection pool", "db"]
        ):
            return "database_error"

        # Network/connectivity errors
        elif any(
            keyword in message_lower
            for keyword in ["timeout", "connection refused", "network", "unreachable"]
        ):
            return "connectivity_error"

        # Authentication/authorization errors
        elif any(
            keyword in message_lower
            for keyword in ["unauthorized", "forbidden", "authentication", "token"]
        ):
            return "auth_error"

        # Resource errors
        elif any(
            keyword in message_lower
            for keyword in ["memory", "disk", "cpu", "resource", "out of"]
        ):
            return "resource_error"

        # Configuration errors
        elif any(
            keyword in message_lower
            for keyword in ["config", "property", "setting", "parameter"]
        ):
            return "configuration_error"

        # Service dependency errors
        elif any(
            keyword in message_lower
            for keyword in [
                "service unavailable",
                "upstream",
                "downstream",
                "dependency",
            ]
        ):
            return "dependency_error"

        else:
            return "generic_error"

    def _calculate_message_similarity(self, messages: List[str]) -> float:
        """Calculate similarity score between error messages."""
        if len(messages) < 2:
            return 1.0 if messages else 0.0

        # Simple word-based similarity
        similarities = []
        for i in range(len(messages)):
            for j in range(i + 1, len(messages)):
                words_i = set(messages[i].lower().split())
                words_j = set(messages[j].lower().split())

                if not words_i and not words_j:
                    similarity = 1.0
                elif not words_i or not words_j:
                    similarity = 0.0
                else:
                    intersection = len(words_i & words_j)
                    union = len(words_i | words_j)
                    similarity = intersection / union if union > 0 else 0.0

                similarities.append(similarity)

        return float(np.mean(similarities)) if similarities else 0.0

    async def _analyze_historical_context(
        self, window: TimeWindow, historical_data: Dict
    ) -> Dict[str, Any]:
        """Analyze historical context and trends."""
        # Extract historical insights
        baseline_comparison = historical_data.get(
            "baseline_comparison", "No baseline data available"
        )

        trend_analysis = historical_data.get("trend_analysis", "No trend data available")

        similar_incidents = historical_data.get("similar_incidents", [])

        recent_changes = historical_data.get(
            "recent_changes", ["No recent change information available"]
        )

        return {
            "baseline_comparison": baseline_comparison,
            "trend_analysis": trend_analysis,
            "similar_incidents": similar_incidents[:3],  # Top 3 similar incidents
            "recent_changes": recent_changes[:3],  # Top 3 recent changes
        }

    def _format_code_context(self, code_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Format code analysis results for PatternContext."""
        git_context = code_analysis.get("git_context", {})
        static_analysis = code_analysis.get("static_analysis", {})
        complexity_metrics = code_analysis.get("complexity_metrics", {})
        dependency_vulns = code_analysis.get("dependency_vulnerabilities", [])
        error_files = code_analysis.get("error_related_files", [])

        return {
            "code_changes_context": git_context.get(
                "code_changes_summary", "No code changes detected"
            ),
            "static_analysis_findings": self._format_static_analysis_findings(
                static_analysis
            ),
            "code_quality_metrics": (
                complexity_metrics if isinstance(complexity_metrics, dict) else None
            ),
            "dependency_vulnerabilities": (
                dependency_vulns if isinstance(dependency_vulns, list) else []
            ),
            "error_related_files": (
                error_files if isinstance(error_files, list) else []
            ),
            "recent_commits": git_context.get("recent_commits", []),
        }

    def _format_static_analysis_findings(
        self, static_analysis: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Format static analysis results for readability."""
        if not static_analysis:
            return None

        formatted = {}
        for tool_name, result in static_analysis.items():
            if hasattr(result, "success") and result.success:
                formatted[tool_name] = {
                    "severity_counts": getattr(result, "severity_counts", {}),
                    "files_analyzed": getattr(result, "files_analyzed", 0),
                    "findings_count": len(getattr(result, "findings", [])),
                    "analysis_time_ms": getattr(result, "analysis_time_ms", 0),
                }
            else:
                formatted[tool_name] = {
                    "error": getattr(result, "error_message", "Analysis failed")
                }

        return formatted if formatted else None

    def _empty_code_context(self) -> Dict[str, Any]:
        """Return empty code context when not available."""
        return {
            "code_changes_context": None,
            "static_analysis_findings": None,
            "code_quality_metrics": None,
            "dependency_vulnerabilities": None,
            "error_related_files": None,
            "recent_commits": None,
        }