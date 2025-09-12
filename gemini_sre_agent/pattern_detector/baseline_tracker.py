# gemini_sre_agent/pattern_detector/baseline_tracker.py

"""
Baseline tracking for rate-based threshold evaluation.
"""

import logging
from collections import defaultdict
from typing import Dict, List

from .models import TimeWindow

logger = logging.getLogger(__name__)


class BaselineTracker:
    """Tracks historical baselines for rate-based threshold evaluation."""

    def __init__(self, max_history: int = 100):
        self.max_history = max_history
        self.service_baselines: Dict[str, List[float]] = defaultdict(list)
        self.global_baseline: List[float] = []
        logger.info(
            f"[PATTERN_DETECTION] BaselineTracker initialized: max_history={max_history}"
        )

    def update_baseline(self, window: TimeWindow) -> None:
        """
        Update Baseline.

        Args:
            window: TimeWindow: Description of window: TimeWindow.

        """
        total_logs = len(window.logs)
        error_logs = len(window.get_error_logs())
        error_rate = (error_logs / total_logs * 100) if total_logs > 0 else 0.0

        self.global_baseline.append(error_rate)
        if len(self.global_baseline) > self.max_history:
            self.global_baseline.pop(0)

        service_groups = window.get_service_groups()
        for service_name, service_logs in service_groups.items():
            service_total = len(service_logs)
            service_errors = len(
                [
                    log
                    for log in service_logs
                    if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
                ]
            )
            service_rate = (
                (service_errors / service_total * 100) if service_total > 0 else 0.0
            )

            self.service_baselines[service_name].append(service_rate)
            if len(self.service_baselines[service_name]) > self.max_history:
                self.service_baselines[service_name].pop(0)

        logger.debug(
            f"[PATTERN_DETECTION] Updated baselines: global_rate={error_rate:.2f}%, "
            f"services={len(service_groups)}, window={window.start_time}"
        )

    def get_global_baseline(self, window_count: int) -> float:
        """
        Get Global Baseline.

        Args:
            window_count: int: Description of window_count: int.

        Returns:
            float: Description of return value.

        """
        if not self.global_baseline:
            return 0.0
        recent_windows = self.global_baseline[-window_count:]
        return sum(recent_windows) / len(recent_windows)

    def get_service_baseline(self, service_name: str, window_count: int) -> float:
        """
        Get Service Baseline.

        Args:
            service_name: str: Description of service_name: str.
            window_count: int: Description of window_count: int.

        Returns:
            float: Description of return value.

        """
        service_history = self.service_baselines.get(service_name, [])
        if not service_history:
            return 0.0
        recent_windows = service_history[-window_count:]
        return sum(recent_windows) / len(recent_windows)
