"""
Service pattern analysis for incident detection.

This module provides service interaction analysis including primary service
identification, interaction pattern classification, and cross-service timing.
"""

from typing import Any, Dict, Set

from ..pattern_detector.models import TimeWindow
from .temporal_analyzer import TemporalAnalyzer


class ServiceAnalyzer:
    """Analyze service interaction patterns."""

    def __init__(self) -> None:
        """Initialize the service analyzer."""
        self.temporal_analyzer = TemporalAnalyzer()

    async def analyze_service_patterns(self, window: TimeWindow) -> Dict[str, Any]:
        """Analyze service interaction patterns."""
        service_counts = {}
        affected_services: Set[str] = set()

        for log in window.logs:
            service = log.service_name or "unknown"
            affected_services.add(service)
            service_counts[service] = service_counts.get(service, 0) + 1

        # Determine primary service (most errors)
        primary_service = (
            max(service_counts.items(), key=lambda x: x[1])[0]
            if service_counts
            else "unknown"
        )

        # Analyze interaction pattern
        if len(affected_services) == 1:
            interaction_pattern = "Isolated service issue"
        elif len(affected_services) <= 3:
            interaction_pattern = "Limited service interaction"
        else:
            interaction_pattern = "Wide service interaction"

        return {
            "primary_service": primary_service,
            "affected_services": list(affected_services),
            "interaction_pattern": interaction_pattern,
            "service_counts": service_counts,
            "cross_service_timing": self.temporal_analyzer.analyze_cross_service_timing(
                window
            ),
        }
