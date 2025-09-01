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

from .logger import setup_logging

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


# ==========================================
# Layer 3: Pattern Classification
# ==========================================


class PatternType:
    """Enumeration of detectable issue patterns."""
    
    SPORADIC_ERRORS = "sporadic_errors"          # Random errors across services
    SERVICE_DEGRADATION = "service_degradation"  # Single service having issues
    CASCADE_FAILURE = "cascade_failure"          # Multi-service failure chain
    TRAFFIC_SPIKE = "traffic_spike"              # High volume causing errors
    CONFIGURATION_ISSUE = "configuration_issue"  # Config-related problems
    DEPENDENCY_FAILURE = "dependency_failure"    # External dependency issues
    RESOURCE_EXHAUSTION = "resource_exhaustion"  # Memory/CPU/disk issues


@dataclass
class PatternMatch:
    """Result of pattern classification."""
    
    pattern_type: str
    confidence_score: float  # 0.0 to 1.0
    primary_service: Optional[str]
    affected_services: List[str]
    severity_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    
    # Evidence supporting the pattern classification
    evidence: Dict[str, Any]
    
    # Recommended remediation approach
    remediation_priority: str  # IMMEDIATE, HIGH, MEDIUM, LOW
    suggested_actions: List[str]


class PatternClassifier:
    """Classifies threshold evaluation results into actionable patterns."""
    
    def __init__(self):
        """Initialize the pattern classifier."""
        self.logger = setup_logging()
        
        # Pattern detection rules and thresholds
        self.classification_rules = self._load_classification_rules()
        
        self.logger.info("[PATTERN_DETECTION] PatternClassifier initialized")
    
    def classify_patterns(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """
        Classify threshold evaluation results into actionable patterns.
        
        Args:
            window: Time window containing log data
            threshold_results: Results from threshold evaluation
            
        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []
        
        # Only classify if we have triggered thresholds
        triggered_results = [r for r in threshold_results if r.triggered]
        if not triggered_results:
            self.logger.debug(
                f"[PATTERN_DETECTION] No triggered thresholds to classify: window={window.start_time}"
            )
            return patterns
        
        self.logger.info(
            f"[PATTERN_DETECTION] Classifying patterns: window={window.start_time}, "
            f"triggered_thresholds={len(triggered_results)}"
        )
        
        # Analyze each pattern type
        patterns.extend(self._detect_cascade_failure(window, triggered_results))
        patterns.extend(self._detect_service_degradation(window, triggered_results))
        patterns.extend(self._detect_traffic_spike(window, triggered_results))
        patterns.extend(self._detect_configuration_issue(window, triggered_results))
        patterns.extend(self._detect_dependency_failure(window, triggered_results))
        patterns.extend(self._detect_resource_exhaustion(window, triggered_results))
        patterns.extend(self._detect_sporadic_errors(window, triggered_results))
        
        # Sort by confidence score (highest first)
        patterns.sort(key=lambda p: p.confidence_score, reverse=True)
        
        self.logger.info(
            f"[PATTERN_DETECTION] Pattern classification complete: "
            f"patterns_detected={len(patterns)}, window={window.start_time}"
        )
        
        return patterns
    
    def _load_classification_rules(self) -> Dict[str, Dict[str, Any]]:
        """Load pattern classification rules and thresholds."""
        return {
            "cascade_failure": {
                "min_services": 2,
                "min_confidence": 0.7,
                "error_correlation_window_seconds": 300,  # 5 minutes
                "severity_threshold": ["ERROR", "CRITICAL"]
            },
            "service_degradation": {
                "min_error_rate": 0.05,  # 5% error rate
                "min_confidence": 0.6,
                "single_service_threshold": 0.8  # 80% of errors from one service
            },
            "traffic_spike": {
                "volume_increase_threshold": 2.0,  # 2x normal volume
                "min_confidence": 0.5,
                "concurrent_error_threshold": 10
            },
            "configuration_issue": {
                "config_keywords": ["config", "configuration", "settings", "invalid", "missing"],
                "min_confidence": 0.6,
                "rapid_onset_threshold_seconds": 60  # Errors start quickly
            },
            "dependency_failure": {
                "dependency_keywords": ["timeout", "connection", "unavailable", "refused", "dns", "network"],
                "min_confidence": 0.7,
                "external_service_indicators": ["api", "external", "third-party"]
            },
            "resource_exhaustion": {
                "resource_keywords": ["memory", "cpu", "disk", "space", "limit", "quota", "throttle"],
                "min_confidence": 0.6,
                "gradual_onset_indicators": ["slow", "degraded", "performance"]
            }
        }
    
    def _detect_cascade_failure(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect cascade failure patterns across multiple services."""
        patterns = []
        rules = self.classification_rules["cascade_failure"]
        
        # Look for CASCADE_FAILURE threshold triggers or multiple service impact
        cascade_triggers = [
            r for r in threshold_results 
            if r.threshold_type == ThresholdType.CASCADE_FAILURE and r.triggered
        ]
        
        service_impact_triggers = [
            r for r in threshold_results
            if r.threshold_type == ThresholdType.SERVICE_IMPACT and r.triggered
        ]
        
        if cascade_triggers or (service_impact_triggers and 
                               any(len(r.affected_services) >= rules["min_services"] for r in service_impact_triggers)):
            
            all_affected_services = set()
            all_triggering_logs = []
            
            for result in threshold_results:
                if result.triggered:
                    all_affected_services.update(result.affected_services)
                    all_triggering_logs.extend(result.triggering_logs)
            
            # Calculate confidence based on service correlation and timing
            confidence = self._calculate_cascade_confidence(
                list(all_affected_services),
                all_triggering_logs,
                rules
            )
            
            if confidence >= rules["min_confidence"]:
                severity = self._determine_severity_level(all_triggering_logs)
                primary_service = self._identify_primary_service(all_triggering_logs)
                
                patterns.append(PatternMatch(
                    pattern_type=PatternType.CASCADE_FAILURE,
                    confidence_score=confidence,
                    primary_service=primary_service,
                    affected_services=list(all_affected_services),
                    severity_level=severity,
                    evidence={
                        "service_count": len(all_affected_services),
                        "error_correlation": "high",
                        "failure_chain": list(all_affected_services)
                    },
                    remediation_priority="IMMEDIATE",
                    suggested_actions=[
                        "Investigate primary failure service",
                        "Check service dependencies",
                        "Implement circuit breakers",
                        "Scale up affected services"
                    ]
                ))
        
        return patterns
    
    def _detect_service_degradation(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect single service degradation patterns."""
        patterns = []
        rules = self.classification_rules["service_degradation"]
        
        # Group errors by service
        service_errors: Dict[str, List[LogEntry]] = defaultdict(list)
        for result in threshold_results:
            if result.triggered:
                for log in result.triggering_logs:
                    if log.service_name:
                        service_errors[log.service_name].append(log)
        
        total_errors = sum(len(logs) for logs in service_errors.values())
        
        for service_name, error_logs in service_errors.items():
            service_error_ratio = len(error_logs) / total_errors if total_errors > 0 else 0
            
            if service_error_ratio >= rules["single_service_threshold"]:
                confidence = min(0.9, service_error_ratio + 0.1)
                
                if confidence >= rules["min_confidence"]:
                    severity = self._determine_severity_level(error_logs)
                    
                    patterns.append(PatternMatch(
                        pattern_type=PatternType.SERVICE_DEGRADATION,
                        confidence_score=confidence,
                        primary_service=service_name,
                        affected_services=[service_name],
                        severity_level=severity,
                        evidence={
                            "error_concentration": service_error_ratio,
                            "error_count": len(error_logs),
                            "service_dominance": "high"
                        },
                        remediation_priority="HIGH" if severity in ["HIGH", "CRITICAL"] else "MEDIUM",
                        suggested_actions=[
                            f"Investigate {service_name} service health",
                            "Check service logs and metrics",
                            "Verify service dependencies",
                            "Consider service restart or rollback"
                        ]
                    ))
        
        return patterns
    
    def _detect_traffic_spike(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect traffic spike patterns causing errors."""
        patterns = []
        rules = self.classification_rules["traffic_spike"]
        
        # Look for high error frequency with concurrent timing
        frequency_triggers = [
            r for r in threshold_results
            if (r.threshold_type == ThresholdType.ERROR_FREQUENCY and 
                r.triggered and r.score >= rules["concurrent_error_threshold"])
        ]
        
        if frequency_triggers:
            all_logs = []
            affected_services = set()
            
            for result in frequency_triggers:
                all_logs.extend(result.triggering_logs)
                affected_services.update(result.affected_services)
            
            # Check if errors are concentrated in time (indicating traffic spike)
            time_concentration = self._calculate_time_concentration(all_logs, window)
            
            confidence = min(0.8, time_concentration * rules["min_confidence"] * 2)
            
            if confidence >= rules["min_confidence"]:
                severity = self._determine_severity_level(all_logs)
                primary_service = self._identify_primary_service(all_logs)
                
                patterns.append(PatternMatch(
                    pattern_type=PatternType.TRAFFIC_SPIKE,
                    confidence_score=confidence,
                    primary_service=primary_service,
                    affected_services=list(affected_services),
                    severity_level=severity,
                    evidence={
                        "concurrent_errors": len(all_logs),
                        "time_concentration": time_concentration,
                        "spike_intensity": "high"
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Scale up affected services",
                        "Implement rate limiting",
                        "Check load balancer configuration",
                        "Monitor traffic patterns"
                    ]
                ))
        
        return patterns
    
    def _detect_configuration_issue(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect configuration-related issue patterns."""
        patterns = []
        rules = self.classification_rules["configuration_issue"]
        
        config_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                for log in result.triggering_logs:
                    if log.error_message and any(
                        keyword in log.error_message.lower() 
                        for keyword in rules["config_keywords"]
                    ):
                        config_logs.append(log)
                        if log.service_name:
                            affected_services.add(log.service_name)
        
        if config_logs:
            # Configuration issues often have rapid onset
            rapid_onset = self._check_rapid_onset(
                config_logs, 
                rules["rapid_onset_threshold_seconds"]
            )
            
            keyword_density = len(config_logs) / len(window.logs) if window.logs else 0
            base_confidence = min(0.8, keyword_density * 3)
            
            confidence = base_confidence + (0.2 if rapid_onset else 0)
            
            if confidence >= rules["min_confidence"]:
                severity = self._determine_severity_level(config_logs)
                primary_service = self._identify_primary_service(config_logs)
                
                patterns.append(PatternMatch(
                    pattern_type=PatternType.CONFIGURATION_ISSUE,
                    confidence_score=confidence,
                    primary_service=primary_service,
                    affected_services=list(affected_services),
                    severity_level=severity,
                    evidence={
                        "config_error_count": len(config_logs),
                        "rapid_onset": rapid_onset,
                        "keyword_matches": rules["config_keywords"]
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Review recent configuration changes",
                        "Validate configuration files",
                        "Check environment variables",
                        "Rollback recent config deployments"
                    ]
                ))
        
        return patterns
    
    def _detect_dependency_failure(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect dependency failure patterns."""
        patterns = []
        rules = self.classification_rules["dependency_failure"]
        
        dependency_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                for log in result.triggering_logs:
                    if log.error_message and any(
                        keyword in log.error_message.lower()
                        for keyword in rules["dependency_keywords"]
                    ):
                        dependency_logs.append(log)
                        if log.service_name:
                            affected_services.add(log.service_name)
        
        if dependency_logs:
            # Check for external service indicators
            external_indicators = any(
                indicator in log.error_message.lower()
                for log in dependency_logs
                for indicator in rules["external_service_indicators"]
                if log.error_message
            )
            
            keyword_density = len(dependency_logs) / len(window.logs) if window.logs else 0
            base_confidence = min(0.8, keyword_density * 2.5)
            
            confidence = base_confidence + (0.2 if external_indicators else 0)
            
            if confidence >= rules["min_confidence"]:
                severity = self._determine_severity_level(dependency_logs)
                primary_service = self._identify_primary_service(dependency_logs)
                
                patterns.append(PatternMatch(
                    pattern_type=PatternType.DEPENDENCY_FAILURE,
                    confidence_score=confidence,
                    primary_service=primary_service,
                    affected_services=list(affected_services),
                    severity_level=severity,
                    evidence={
                        "dependency_error_count": len(dependency_logs),
                        "external_service": external_indicators,
                        "keyword_matches": rules["dependency_keywords"]
                    },
                    remediation_priority="HIGH",
                    suggested_actions=[
                        "Check external service status",
                        "Verify network connectivity",
                        "Implement fallback mechanisms",
                        "Review timeout configurations"
                    ]
                ))
        
        return patterns
    
    def _detect_resource_exhaustion(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect resource exhaustion patterns."""
        patterns = []
        rules = self.classification_rules["resource_exhaustion"]
        
        resource_logs = []
        affected_services = set()
        
        for result in threshold_results:
            if result.triggered:
                for log in result.triggering_logs:
                    if log.error_message and any(
                        keyword in log.error_message.lower()
                        for keyword in rules["resource_keywords"]
                    ):
                        resource_logs.append(log)
                        if log.service_name:
                            affected_services.add(log.service_name)
        
        if resource_logs:
            # Resource exhaustion often has gradual onset
            gradual_onset = self._check_gradual_onset(resource_logs)
            
            keyword_density = len(resource_logs) / len(window.logs) if window.logs else 0
            base_confidence = min(0.8, keyword_density * 2)
            
            confidence = base_confidence + (0.1 if gradual_onset else 0)
            
            if confidence >= rules["min_confidence"]:
                severity = self._determine_severity_level(resource_logs)
                primary_service = self._identify_primary_service(resource_logs)
                
                patterns.append(PatternMatch(
                    pattern_type=PatternType.RESOURCE_EXHAUSTION,
                    confidence_score=confidence,
                    primary_service=primary_service,
                    affected_services=list(affected_services),
                    severity_level=severity,
                    evidence={
                        "resource_error_count": len(resource_logs),
                        "gradual_onset": gradual_onset,
                        "resource_types": rules["resource_keywords"]
                    },
                    remediation_priority="MEDIUM",
                    suggested_actions=[
                        "Check resource utilization",
                        "Scale up affected services",
                        "Optimize resource usage",
                        "Review resource limits"
                    ]
                ))
        
        return patterns
    
    def _detect_sporadic_errors(
        self,
        window: TimeWindow,
        threshold_results: List[ThresholdResult]
    ) -> List[PatternMatch]:
        """Detect sporadic error patterns (fallback for unclassified errors)."""
        patterns = []
        
        # Only create sporadic pattern if no other patterns were detected
        # This serves as a fallback classification
        
        triggered_results = [r for r in threshold_results if r.triggered]
        if not triggered_results:
            return patterns
        
        all_logs = []
        affected_services = set()
        
        for result in triggered_results:
            all_logs.extend(result.triggering_logs)
            affected_services.update(result.affected_services)
        
        # Check if errors are distributed across services and time
        service_distribution = len(affected_services) / max(1, len(all_logs))
        time_distribution = self._calculate_time_distribution(all_logs, window)
        
        # Sporadic errors have high distribution (not concentrated)
        if service_distribution > 0.3 and time_distribution > 0.4:
            confidence = min(0.6, (service_distribution + time_distribution) / 2)
            severity = self._determine_severity_level(all_logs)
            primary_service = self._identify_primary_service(all_logs)
            
            patterns.append(PatternMatch(
                pattern_type=PatternType.SPORADIC_ERRORS,
                confidence_score=confidence,
                primary_service=primary_service,
                affected_services=list(affected_services),
                severity_level=severity,
                evidence={
                    "error_distribution": "dispersed",
                    "service_spread": len(affected_services),
                    "time_spread": time_distribution
                },
                remediation_priority="LOW" if severity in ["LOW", "MEDIUM"] else "MEDIUM",
                suggested_actions=[
                    "Monitor error trends",
                    "Investigate common root causes",
                    "Improve error handling",
                    "Check system stability"
                ]
            ))
        
        return patterns
    
    # Helper methods for confidence calculation
    
    def _calculate_cascade_confidence(
        self,
        affected_services: List[str],
        triggering_logs: List[LogEntry],
        rules: Dict[str, Any]
    ) -> float:
        """Calculate confidence for cascade failure detection."""
        base_confidence = min(0.8, len(affected_services) / 5.0)
        
        # Bonus for temporal correlation
        time_correlation = self._calculate_time_correlation(triggering_logs)
        
        # Bonus for severity correlation
        severity_bonus = 0.1 if any(
            log.severity in rules["severity_threshold"] 
            for log in triggering_logs
        ) else 0
        
        return min(1.0, base_confidence + time_correlation * 0.2 + severity_bonus)
    
    def _calculate_time_concentration(self, logs: List[LogEntry], window: TimeWindow) -> float:
        """Calculate how concentrated errors are in time within the window."""
        if not logs or len(logs) < 2:
            return 0.0
        
        timestamps = sorted([log.timestamp for log in logs])
        first_error = timestamps[0]
        last_error = timestamps[-1]
        
        error_span = (last_error - first_error).total_seconds()
        window_span = window.duration_minutes * 60
        
        # Higher concentration = errors happen in smaller time span
        return 1.0 - (error_span / window_span) if window_span > 0 else 1.0
    
    def _calculate_time_distribution(self, logs: List[LogEntry], window: TimeWindow) -> float:
        """Calculate how distributed errors are across time within the window."""
        # Opposite of concentration - higher value means more spread out
        return 1.0 - self._calculate_time_concentration(logs, window)
    
    def _calculate_time_correlation(self, logs: List[LogEntry]) -> float:
        """Calculate temporal correlation between error logs."""
        if len(logs) < 2:
            return 0.0
        
        # Simple correlation: if errors happen close together, correlation is high
        timestamps = sorted([log.timestamp for log in logs])
        total_span = (timestamps[-1] - timestamps[0]).total_seconds()
        
        if total_span == 0:
            return 1.0  # All errors at same time
        
        # High correlation if errors happen within 1 minute
        return max(0.0, 1.0 - (total_span / 60.0))
    
    def _check_rapid_onset(self, logs: List[LogEntry], threshold_seconds: int) -> bool:
        """Check if errors have rapid onset (all within threshold seconds)."""
        if not logs:
            return False
        
        timestamps = [log.timestamp for log in logs]
        time_span = (max(timestamps) - min(timestamps)).total_seconds()
        
        return time_span <= threshold_seconds
    
    def _check_gradual_onset(self, logs: List[LogEntry]) -> bool:
        """Check if errors have gradual onset pattern."""
        if len(logs) < 3:
            return False
        
        timestamps = sorted([log.timestamp for log in logs])
        
        # Check if timestamps are somewhat evenly distributed
        intervals = []
        for i in range(1, len(timestamps)):
            interval = (timestamps[i] - timestamps[i-1]).total_seconds()
            intervals.append(interval)
        
        if not intervals:
            return False
        
        avg_interval = sum(intervals) / len(intervals)
        
        # Gradual onset: intervals are relatively consistent and not too small
        variance = sum((interval - avg_interval) ** 2 for interval in intervals) / len(intervals)
        
        return avg_interval > 30 and variance < (avg_interval ** 2)  # Low variance, reasonable spacing
    
    def _determine_severity_level(self, logs: List[LogEntry]) -> str:
        """Determine overall severity level from log entries."""
        if not logs:
            return "LOW"
        
        severity_counts = {"CRITICAL": 0, "ERROR": 0, "WARNING": 0, "INFO": 0}
        
        for log in logs:
            if log.severity in severity_counts:
                severity_counts[log.severity] += 1
        
        total_logs = len(logs)
        critical_ratio = severity_counts["CRITICAL"] / total_logs
        error_ratio = severity_counts["ERROR"] / total_logs
        
        if critical_ratio > 0.1:  # 10% critical
            return "CRITICAL"
        elif error_ratio > 0.5:  # 50% errors
            return "HIGH"
        elif error_ratio > 0.2:  # 20% errors
            return "MEDIUM"
        else:
            return "LOW"
    
    def _identify_primary_service(self, logs: List[LogEntry]) -> Optional[str]:
        """Identify the service with the most errors as primary service."""
        if not logs:
            return None
        
        service_counts: Dict[str, int] = defaultdict(int)
        
        for log in logs:
            if log.service_name:
                service_counts[log.service_name] += 1
        
        if not service_counts:
            return None
        
        return max(service_counts.items(), key=lambda x: x[1])[0]