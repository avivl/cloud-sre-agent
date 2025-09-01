"""
Pattern Detection System - Multi-Layer Architecture

This module implements a multi-layered pattern detection system for SRE automation.
Each layer builds upon the previous to create intelligent pattern recognition:

Layer 1 - Time-Window Accumulation:
- TimeWindow: Manages log accumulation within time boundaries
- LogAccumulator: Coordinates multiple time windows with sliding window behavior
- WindowManager: High-level interface for log accumulation and pattern detection

Layer 2 - Smart Thresholds:
- ThresholdConfig: Configuration for various threshold types
- ThresholdEvaluator: Evaluates windows against configured thresholds
- BaselineTracker: Tracks historical baselines for rate-based thresholds
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Callable, Any
from collections import defaultdict
from dataclasses import dataclass, field
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class LogEntry(BaseModel):
    """Structured representation of a log entry for pattern analysis."""
    
    insert_id: str
    timestamp: datetime
    severity: str
    service_name: Optional[str] = None
    error_message: Optional[str] = None
    raw_data: Dict[str, Any]
    
    def __init__(self, **data):
        # Extract timestamp from raw data if not provided
        if 'timestamp' not in data and 'raw_data' in data:
            raw_timestamp = data['raw_data'].get('timestamp')
            if raw_timestamp:
                try:
                    data['timestamp'] = datetime.fromisoformat(
                        raw_timestamp.replace('Z', '+00:00')
                    )
                except (ValueError, TypeError):
                    data['timestamp'] = datetime.now(timezone.utc)
            else:
                data['timestamp'] = datetime.now(timezone.utc)
        
        # Extract severity from raw data if not provided
        if 'severity' not in data and 'raw_data' in data:
            data['severity'] = data['raw_data'].get('severity', 'INFO')
        
        # Extract service name from resource labels
        if 'service_name' not in data and 'raw_data' in data:
            resource = data['raw_data'].get('resource', {})
            labels = resource.get('labels', {})
            data['service_name'] = labels.get('service_name') or labels.get('function_name')
        
        # Extract error message
        if 'error_message' not in data and 'raw_data' in data:
            data['error_message'] = data['raw_data'].get('textPayload') or data['raw_data'].get('message')
        
        super().__init__(**data)


@dataclass
class TimeWindow:
    """Represents a time window for log accumulation."""
    
    start_time: datetime
    duration_minutes: int
    logs: List[LogEntry] = field(default_factory=list)
    
    @property
    def end_time(self) -> datetime:
        """Calculate the end time of this window."""
        return self.start_time + timedelta(minutes=self.duration_minutes)
    
    def is_active(self, current_time: datetime) -> bool:
        """Check if this window is still active for log collection."""
        return current_time < self.end_time
    
    def is_expired(self, current_time: datetime) -> bool:
        """Check if this window has expired and should be processed."""
        return current_time >= self.end_time
    
    def accepts_log(self, log_entry: LogEntry) -> bool:
        """Check if this window should accept the given log entry."""
        return (
            self.start_time <= log_entry.timestamp < self.end_time
        )
    
    def add_log(self, log_entry: LogEntry) -> bool:
        """Add a log entry to this window if it belongs here."""
        if self.accepts_log(log_entry):
            self.logs.append(log_entry)
            logger.debug(
                f"[PATTERN_DETECTION] Added log to window {self.start_time}: "
                f"total_logs={len(self.logs)}, log_id={log_entry.insert_id}"
            )
            return True
        return False
    
    def get_error_logs(self) -> List[LogEntry]:
        """Get only error-level logs from this window."""
        return [
            log for log in self.logs 
            if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]
        ]
    
    def get_service_groups(self) -> Dict[str, List[LogEntry]]:
        """Group logs by service name."""
        groups: Dict[str, List[LogEntry]] = defaultdict(list)
        for log in self.logs:
            service = log.service_name or "unknown"
            groups[service].append(log)
        return dict(groups)


class LogAccumulator:
    """Manages multiple time windows with sliding window behavior."""
    
    def __init__(
        self,
        window_duration_minutes: int = 5,
        max_windows: int = 10,
        on_window_ready: Optional[Callable[[TimeWindow], None]] = None
    ):
        """
        Initialize the log accumulator.
        
        Args:
            window_duration_minutes: Duration of each time window in minutes
            max_windows: Maximum number of windows to keep in memory
            on_window_ready: Callback function called when a window is ready for processing
        """
        self.window_duration_minutes = window_duration_minutes
        self.max_windows = max_windows
        self.on_window_ready = on_window_ready
        
        # Active windows indexed by start time
        self.windows: Dict[datetime, TimeWindow] = {}
        
        # Background task for window management
        self._cleanup_task: Optional[asyncio.Task] = None
        self._shutdown = False
        
        logger.info(
            f"[PATTERN_DETECTION] LogAccumulator initialized: "
            f"window_duration={window_duration_minutes}min, max_windows={max_windows}"
        )
    
    def start(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None:
            self._cleanup_task = asyncio.create_task(self._cleanup_expired_windows())
            logger.info("[PATTERN_DETECTION] LogAccumulator background task started")
    
    async def stop(self) -> None:
        """Stop the background cleanup task and process remaining windows."""
        self._shutdown = True
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Process any remaining windows
        await self._process_expired_windows()
        logger.info("[PATTERN_DETECTION] LogAccumulator stopped")
    
    def add_log(self, raw_log_data: Dict[str, Any]) -> None:
        """
        Add a log entry to the appropriate time window.
        
        Args:
            raw_log_data: Raw log data from Pub/Sub message
        """
        try:
            # Convert raw log data to LogEntry
            log_entry = LogEntry(
                insert_id=raw_log_data.get('insertId', 'unknown'),
                raw_data=raw_log_data
            )
            
            # Find or create appropriate window
            window = self._get_or_create_window(log_entry.timestamp)
            window.add_log(log_entry)
            
            logger.debug(
                f"[PATTERN_DETECTION] Log added: window={window.start_time}, "
                f"service={log_entry.service_name}, severity={log_entry.severity}"
            )
            
        except Exception as e:
            logger.error(
                f"[ERROR_HANDLING] Failed to add log to accumulator: {e}, "
                f"log_data={raw_log_data}"
            )
    
    def _get_or_create_window(self, log_timestamp: datetime) -> TimeWindow:
        """Get existing window or create new one for the given timestamp."""
        # Round down to window boundary
        window_start = self._round_to_window_start(log_timestamp)
        
        if window_start not in self.windows:
            # Create new window
            window = TimeWindow(
                start_time=window_start,
                duration_minutes=self.window_duration_minutes
            )
            self.windows[window_start] = window
            
            # Enforce max windows limit
            if len(self.windows) > self.max_windows:
                self._evict_oldest_window()
            
            logger.debug(
                f"[PATTERN_DETECTION] Created new window: {window_start}, "
                f"total_windows={len(self.windows)}"
            )
        
        return self.windows[window_start]
    
    def _round_to_window_start(self, timestamp: datetime) -> datetime:
        """Round timestamp down to the nearest window boundary."""
        # Round down to nearest window_duration_minutes boundary
        minutes_since_hour = timestamp.minute
        window_boundary = (minutes_since_hour // self.window_duration_minutes) * self.window_duration_minutes
        
        return timestamp.replace(
            minute=window_boundary,
            second=0,
            microsecond=0
        )
    
    def _evict_oldest_window(self) -> None:
        """Remove the oldest window to stay within memory limits."""
        if not self.windows:
            return
        
        oldest_start = min(self.windows.keys())
        oldest_window = self.windows.pop(oldest_start)
        
        # Process the evicted window if it has logs
        if oldest_window.logs and self.on_window_ready:
            try:
                self.on_window_ready(oldest_window)
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error processing evicted window: {e}"
                )
        
        logger.debug(
            f"[PATTERN_DETECTION] Evicted oldest window: {oldest_start}, "
            f"logs_count={len(oldest_window.logs)}"
        )
    
    async def _cleanup_expired_windows(self) -> None:
        """Background task to clean up expired windows."""
        while not self._shutdown:
            try:
                await self._process_expired_windows()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error in window cleanup task: {e}"
                )
                await asyncio.sleep(30)
    
    async def _process_expired_windows(self) -> None:
        """Process and remove expired windows."""
        current_time = datetime.now(timezone.utc)
        expired_windows = [
            (start_time, window)
            for start_time, window in self.windows.items()
            if window.is_expired(current_time)
        ]
        
        for start_time, window in expired_windows:
            # Remove from active windows
            self.windows.pop(start_time, None)
            
            # Process if has logs and callback is set
            if window.logs and self.on_window_ready:
                try:
                    self.on_window_ready(window)
                    logger.info(
                        f"[PATTERN_DETECTION] Processed expired window: {start_time}, "
                        f"logs_count={len(window.logs)}, error_count={len(window.get_error_logs())}"
                    )
                except Exception as e:
                    logger.error(
                        f"[ERROR_HANDLING] Error processing expired window: {e}"
                    )


class WindowManager:
    """High-level interface for time-window log accumulation and pattern detection."""
    
    def __init__(
        self,
        fast_window_minutes: int = 5,
        trend_window_minutes: int = 15,
        max_windows: int = 20,
        pattern_callback: Optional[Callable[[TimeWindow], None]] = None
    ):
        """
        Initialize the window manager with dual time windows.
        
        Args:
            fast_window_minutes: Duration for fast-moving issue detection
            trend_window_minutes: Duration for trend analysis
            max_windows: Maximum windows to keep in memory per accumulator
            pattern_callback: Callback for processing ready windows
        """
        self.fast_window_minutes = fast_window_minutes
        self.trend_window_minutes = trend_window_minutes
        self.pattern_callback = pattern_callback
        
        # Create dual accumulators
        self.fast_accumulator = LogAccumulator(
            window_duration_minutes=fast_window_minutes,
            max_windows=max_windows,
            on_window_ready=self._on_fast_window_ready
        )
        
        self.trend_accumulator = LogAccumulator(
            window_duration_minutes=trend_window_minutes,
            max_windows=max_windows // 2,  # Fewer trend windows since they're longer
            on_window_ready=self._on_trend_window_ready
        )
        
        logger.info(
            f"[PATTERN_DETECTION] WindowManager initialized: "
            f"fast_window={fast_window_minutes}min, trend_window={trend_window_minutes}min"
        )
    
    def start(self) -> None:
        """Start both accumulators."""
        self.fast_accumulator.start()
        self.trend_accumulator.start()
        logger.info("[PATTERN_DETECTION] WindowManager started")
    
    async def stop(self) -> None:
        """Stop both accumulators."""
        await asyncio.gather(
            self.fast_accumulator.stop(),
            self.trend_accumulator.stop(),
            return_exceptions=True
        )
        logger.info("[PATTERN_DETECTION] WindowManager stopped")
    
    def add_log(self, raw_log_data: Dict[str, Any]) -> None:
        """Add log to both fast and trend accumulators."""
        self.fast_accumulator.add_log(raw_log_data)
        self.trend_accumulator.add_log(raw_log_data)
    
    def _on_fast_window_ready(self, window: TimeWindow) -> None:
        """Handle fast window completion."""
        logger.info(
            f"[PATTERN_DETECTION] Fast window ready: {window.start_time}, "
            f"duration={self.fast_window_minutes}min, logs={len(window.logs)}, "
            f"errors={len(window.get_error_logs())}"
        )
        
        if self.pattern_callback:
            try:
                self.pattern_callback(window)
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error in fast window callback: {e}"
                )
    
    def _on_trend_window_ready(self, window: TimeWindow) -> None:
        """Handle trend window completion."""
        logger.info(
            f"[PATTERN_DETECTION] Trend window ready: {window.start_time}, "
            f"duration={self.trend_window_minutes}min, logs={len(window.logs)}, "
            f"errors={len(window.get_error_logs())}"
        )
        
        if self.pattern_callback:
            try:
                self.pattern_callback(window)
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error in trend window callback: {e}"
                )


# ==========================================
# Layer 2: Smart Thresholds
# ==========================================


class ThresholdType:
    """Enumeration of threshold types for pattern detection."""
    
    ERROR_FREQUENCY = "error_frequency"      # Count of errors in window
    ERROR_RATE = "error_rate"               # Percentage increase from baseline
    SERVICE_IMPACT = "service_impact"        # Number of affected services
    SEVERITY_WEIGHTED = "severity_weighted"  # Weighted score by severity
    CASCADE_FAILURE = "cascade_failure"      # Multi-service correlation


@dataclass
class ThresholdConfig:
    """Configuration for smart thresholds."""
    
    threshold_type: str
    min_value: float
    max_value: Optional[float] = None
    
    # Error frequency thresholds
    min_error_count: int = 3
    
    # Error rate thresholds (percentage)
    min_rate_increase: float = 10.0  # 10% increase from baseline
    baseline_window_count: int = 12   # Windows to use for baseline
    
    # Service impact thresholds
    min_affected_services: int = 2
    
    # Severity weights for scoring
    severity_weights: Dict[str, float] = field(default_factory=lambda: {
        "CRITICAL": 10.0,
        "ERROR": 5.0,
        "WARNING": 2.0,
        "INFO": 1.0
    })
    
    # Cascade failure detection
    cascade_time_window_minutes: int = 10
    cascade_min_services: int = 2


@dataclass
class ThresholdResult:
    """Result of threshold evaluation."""
    
    threshold_type: str
    triggered: bool
    score: float
    details: Dict[str, Any]
    triggering_logs: List[LogEntry]
    affected_services: List[str]


class BaselineTracker:
    """Tracks historical baselines for rate-based threshold evaluation."""
    
    def __init__(self, max_history: int = 100):
        """
        Initialize baseline tracker.
        
        Args:
            max_history: Maximum number of historical windows to keep
        """
        self.max_history = max_history
        
        # Historical data per service
        self.service_baselines: Dict[str, List[float]] = defaultdict(list)
        
        # Global baseline
        self.global_baseline: List[float] = []
        
        logger.info(
            f"[PATTERN_DETECTION] BaselineTracker initialized: max_history={max_history}"
        )
    
    def update_baseline(self, window: TimeWindow) -> None:
        """
        Update baseline with data from a completed window.
        
        Args:
            window: Completed time window to extract baseline data from
        """
        # Calculate global error rate for this window
        total_logs = len(window.logs)
        error_logs = len(window.get_error_logs())
        error_rate = (error_logs / total_logs * 100) if total_logs > 0 else 0.0
        
        # Update global baseline
        self.global_baseline.append(error_rate)
        if len(self.global_baseline) > self.max_history:
            self.global_baseline.pop(0)
        
        # Update per-service baselines
        service_groups = window.get_service_groups()
        for service_name, service_logs in service_groups.items():
            service_total = len(service_logs)
            service_errors = len([log for log in service_logs if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]])
            service_rate = (service_errors / service_total * 100) if service_total > 0 else 0.0
            
            self.service_baselines[service_name].append(service_rate)
            if len(self.service_baselines[service_name]) > self.max_history:
                self.service_baselines[service_name].pop(0)
        
        logger.debug(
            f"[PATTERN_DETECTION] Updated baselines: global_rate={error_rate:.2f}%, "
            f"services={len(service_groups)}, window={window.start_time}"
        )
    
    def get_global_baseline(self, window_count: int) -> float:
        """
        Get average global error rate over recent windows.
        
        Args:
            window_count: Number of recent windows to average
            
        Returns:
            Average error rate percentage
        """
        if not self.global_baseline:
            return 0.0
        
        recent_windows = self.global_baseline[-window_count:]
        return sum(recent_windows) / len(recent_windows)
    
    def get_service_baseline(self, service_name: str, window_count: int) -> float:
        """
        Get average service error rate over recent windows.
        
        Args:
            service_name: Service to get baseline for
            window_count: Number of recent windows to average
            
        Returns:
            Average service error rate percentage
        """
        service_history = self.service_baselines.get(service_name, [])
        if not service_history:
            return 0.0
        
        recent_windows = service_history[-window_count:]
        return sum(recent_windows) / len(recent_windows)


class ThresholdEvaluator:
    """Evaluates time windows against configured smart thresholds."""
    
    def __init__(
        self,
        threshold_configs: List[ThresholdConfig],
        baseline_tracker: Optional[BaselineTracker] = None
    ):
        """
        Initialize threshold evaluator.
        
        Args:
            threshold_configs: List of threshold configurations to evaluate
            baseline_tracker: Optional baseline tracker for rate-based thresholds
        """
        self.threshold_configs = threshold_configs
        self.baseline_tracker = baseline_tracker or BaselineTracker()
        
        logger.info(
            f"[PATTERN_DETECTION] ThresholdEvaluator initialized with {len(threshold_configs)} thresholds"
        )
    
    def evaluate_window(self, window: TimeWindow) -> List[ThresholdResult]:
        """
        Evaluate a time window against all configured thresholds.
        
        Args:
            window: Time window to evaluate
            
        Returns:
            List of threshold evaluation results
        """
        results = []
        
        for config in self.threshold_configs:
            try:
                result = self._evaluate_single_threshold(window, config)
                results.append(result)
                
                if result.triggered:
                    logger.info(
                        f"[PATTERN_DETECTION] Threshold triggered: type={result.threshold_type}, "
                        f"score={result.score:.2f}, services={len(result.affected_services)}, "
                        f"window={window.start_time}"
                    )
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error evaluating threshold {config.threshold_type}: {e}"
                )
        
        # Update baseline tracker with this window
        if self.baseline_tracker:
            self.baseline_tracker.update_baseline(window)
        
        return results
    
    def _evaluate_single_threshold(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate a single threshold configuration."""
        
        if config.threshold_type == ThresholdType.ERROR_FREQUENCY:
            return self._evaluate_error_frequency(window, config)
        elif config.threshold_type == ThresholdType.ERROR_RATE:
            return self._evaluate_error_rate(window, config)
        elif config.threshold_type == ThresholdType.SERVICE_IMPACT:
            return self._evaluate_service_impact(window, config)
        elif config.threshold_type == ThresholdType.SEVERITY_WEIGHTED:
            return self._evaluate_severity_weighted(window, config)
        elif config.threshold_type == ThresholdType.CASCADE_FAILURE:
            return self._evaluate_cascade_failure(window, config)
        else:
            raise ValueError(f"Unknown threshold type: {config.threshold_type}")
    
    def _evaluate_error_frequency(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate error frequency threshold."""
        error_logs = window.get_error_logs()
        error_count = len(error_logs)
        triggered = error_count >= config.min_error_count
        
        service_groups = window.get_service_groups()
        affected_services = [
            service for service, logs in service_groups.items()
            if len([log for log in logs if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]]) > 0
        ]
        
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(error_count),
            details={
                "error_count": error_count,
                "total_logs": len(window.logs),
                "threshold": config.min_error_count
            },
            triggering_logs=error_logs,
            affected_services=affected_services
        )
    
    def _evaluate_error_rate(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate error rate threshold against baseline."""
        error_logs = window.get_error_logs()
        total_logs = len(window.logs)
        current_rate = (len(error_logs) / total_logs * 100) if total_logs > 0 else 0.0
        
        # Get baseline rate
        baseline_rate = self.baseline_tracker.get_global_baseline(config.baseline_window_count)
        
        # Calculate rate increase
        rate_increase = current_rate - baseline_rate if baseline_rate > 0 else current_rate
        rate_increase_percentage = (rate_increase / baseline_rate * 100) if baseline_rate > 0 else float('inf') if current_rate > 0 else 0.0
        
        triggered = rate_increase_percentage >= config.min_rate_increase and current_rate > 0
        
        service_groups = window.get_service_groups()
        affected_services = [
            service for service, logs in service_groups.items()
            if len([log for log in logs if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]]) > 0
        ]
        
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=rate_increase_percentage,
            details={
                "current_rate": current_rate,
                "baseline_rate": baseline_rate,
                "rate_increase": rate_increase,
                "rate_increase_percentage": rate_increase_percentage,
                "threshold": config.min_rate_increase
            },
            triggering_logs=error_logs,
            affected_services=affected_services
        )
    
    def _evaluate_service_impact(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate service impact threshold."""
        service_groups = window.get_service_groups()
        
        # Count services with errors
        affected_services = []
        all_error_logs = []
        
        for service, logs in service_groups.items():
            service_errors = [log for log in logs if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]]
            if service_errors:
                affected_services.append(service)
                all_error_logs.extend(service_errors)
        
        triggered = len(affected_services) >= config.min_affected_services
        
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(len(affected_services)),
            details={
                "affected_services": len(affected_services),
                "total_services": len(service_groups),
                "threshold": config.min_affected_services
            },
            triggering_logs=all_error_logs,
            affected_services=affected_services
        )
    
    def _evaluate_severity_weighted(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate severity-weighted threshold."""
        weighted_score = 0.0
        triggering_logs = []
        
        for log in window.logs:
            weight = config.severity_weights.get(log.severity, 1.0)
            weighted_score += weight
            
            # Include high-severity logs as triggering logs
            if weight >= 5.0:  # ERROR and above
                triggering_logs.append(log)
        
        triggered = weighted_score >= config.min_value
        
        service_groups = window.get_service_groups()
        affected_services = [
            service for service, logs in service_groups.items()
            if any(config.severity_weights.get(log.severity, 1.0) >= 5.0 for log in logs)
        ]
        
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=weighted_score,
            details={
                "weighted_score": weighted_score,
                "threshold": config.min_value,
                "severity_breakdown": self._get_severity_breakdown(window.logs, config.severity_weights)
            },
            triggering_logs=triggering_logs,
            affected_services=affected_services
        )
    
    def _evaluate_cascade_failure(
        self,
        window: TimeWindow,
        config: ThresholdConfig
    ) -> ThresholdResult:
        """Evaluate cascade failure threshold (simplified for single window)."""
        service_groups = window.get_service_groups()
        
        # Look for temporal correlation of errors across services
        services_with_errors = []
        all_error_logs = []
        
        for service, logs in service_groups.items():
            service_errors = [log for log in logs if log.severity in ["ERROR", "CRITICAL", "ALERT", "EMERGENCY"]]
            if service_errors:
                services_with_errors.append(service)
                all_error_logs.extend(service_errors)
        
        # Simple cascade detection: multiple services with errors in short timespan
        triggered = len(services_with_errors) >= config.cascade_min_services
        
        return ThresholdResult(
            threshold_type=config.threshold_type,
            triggered=triggered,
            score=float(len(services_with_errors)),
            details={
                "services_with_errors": len(services_with_errors),
                "total_services": len(service_groups),
                "threshold": config.cascade_min_services,
                "time_window_minutes": config.cascade_time_window_minutes
            },
            triggering_logs=all_error_logs,
            affected_services=services_with_errors
        )
    
    def _get_severity_breakdown(
        self,
        logs: List[LogEntry],
        severity_weights: Dict[str, float]
    ) -> Dict[str, int]:
        """Get breakdown of logs by severity level."""
        breakdown: Dict[str, int] = defaultdict(int)
        for log in logs:
            breakdown[log.severity] += 1
        return dict(breakdown)