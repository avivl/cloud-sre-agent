# gemini_sre_agent/pattern_detector/time_window_accumulator.py

"""
Time window accumulation logic.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from .models import LogEntry, TimeWindow

logger = logging.getLogger(__name__)


class LogAccumulator:
    """Manages multiple time windows with sliding window behavior."""

    def __init__(
        self,
        window_duration_minutes: int = 5,
        max_windows: int = 10,
        on_window_ready: Optional[Callable[[TimeWindow], None]] = None,
    ):
        self.window_duration_minutes = window_duration_minutes
        self.max_windows = max_windows
        self.on_window_ready = on_window_ready
        self.windows: Dict[datetime, TimeWindow] = {}
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
        await self._process_expired_windows()
        logger.info("[PATTERN_DETECTION] LogAccumulator stopped")

    def add_log(self, raw_log_data: Dict[str, Any]) -> None:
        """
        Add Log.

        Args:
            raw_log_data: Dict[str, Any]: Description of raw_log_data: Dict[str, Any].

        """
        try:
            log_entry = LogEntry(
                insert_id=raw_log_data.get("insertId", "unknown"), raw_data=raw_log_data
            )
            window = self._get_or_create_window(log_entry.timestamp)
            if window.add_log(log_entry):
                logger.debug(
                    f"[PATTERN_DETECTION] Added log to window {window.start_time}: "
                    f"total_logs={len(window.logs)}, log_id={log_entry.insert_id}"
                )

        except Exception as e:
            logger.error(
                f"[ERROR_HANDLING] Failed to add log to accumulator: {e}, "
                f"log_data={raw_log_data}"
            )

    def _get_or_create_window(self, log_timestamp: datetime) -> TimeWindow:
        window_start = self._round_to_window_start(log_timestamp)
        if window_start not in self.windows:
            window = TimeWindow(
                start_time=window_start, duration_minutes=self.window_duration_minutes
            )
            self.windows[window_start] = window
            if len(self.windows) > self.max_windows:
                self._evict_oldest_window()
            logger.debug(
                f"[PATTERN_DETECTION] Created new window: {window_start}, "
                f"total_windows={len(self.windows)}"
            )
        return self.windows[window_start]

    def _round_to_window_start(self, timestamp: datetime) -> datetime:
        minutes_since_hour = timestamp.minute
        window_boundary = (
            minutes_since_hour // self.window_duration_minutes
        ) * self.window_duration_minutes
        return timestamp.replace(minute=window_boundary, second=0, microsecond=0)

    def _evict_oldest_window(self) -> None:
        if not self.windows:
            return
        oldest_start = min(self.windows.keys())
        oldest_window = self.windows.pop(oldest_start)
        if oldest_window.logs and self.on_window_ready:
            try:
                self.on_window_ready(oldest_window)
            except Exception as e:
                logger.error(f"[ERROR_HANDLING] Error processing evicted window: {e}")
        logger.debug(
            f"[PATTERN_DETECTION] Evicted oldest window: {oldest_start}, "
            f"logs_count={len(oldest_window.logs)}"
        )

    async def _cleanup_expired_windows(self) -> None:
        while not self._shutdown:
            try:
                await self._process_expired_windows()
                await asyncio.sleep(30)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[ERROR_HANDLING] Error in window cleanup task: {e}")
                await asyncio.sleep(30)

    async def _process_expired_windows(self) -> None:
        current_time = datetime.now(timezone.utc)
        expired_windows = [
            (start_time, window)
            for start_time, window in self.windows.items()
            if window.is_expired(current_time)
        ]
        for start_time, window in expired_windows:
            self.windows.pop(start_time, None)
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
        pattern_callback: Optional[Callable[[TimeWindow], None]] = None,
    ):
        self.fast_window_minutes = fast_window_minutes
        self.trend_window_minutes = trend_window_minutes
        self.pattern_callback = pattern_callback
        self.fast_accumulator = LogAccumulator(
            window_duration_minutes=fast_window_minutes,
            max_windows=max_windows,
            on_window_ready=self._on_fast_window_ready,
        )
        self.trend_accumulator = LogAccumulator(
            window_duration_minutes=trend_window_minutes,
            max_windows=max_windows // 2,
            on_window_ready=self._on_trend_window_ready,
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
            return_exceptions=True,
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
                logger.error(f"[ERROR_HANDLING] Error in fast window callback: {e}")

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
                logger.error(f"[ERROR_HANDLING] Error in trend window callback: {e}")
