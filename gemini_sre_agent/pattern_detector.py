"""
Pattern Detection System - Layer 1: Time-Window Accumulation

This module implements the first layer of the multi-layered pattern detection system.
It accumulates log entries within configurable time windows to enable pattern analysis
before triggering triage decisions.

Architecture:
- TimeWindow: Manages log accumulation within time boundaries
- LogAccumulator: Coordinates multiple time windows with sliding window behavior
- WindowManager: High-level interface for log accumulation and pattern detection
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