# gemini_sre_agent/llm/testing/benchmark_monitors.py

"""
System monitoring components for performance benchmarks.

This module provides monitoring capabilities for system resources
including memory usage, CPU utilization, and other performance metrics.
"""

import statistics
from typing import List, Optional

try:
    import psutil

    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False


class BaseMonitor:
    """Base class for system monitors."""

    def __init__(self):
        """Initialize the monitor."""
        self.monitoring = False

    def start(self) -> None:
        """Start monitoring."""
        self.monitoring = True

    def stop(self) -> float:
        """Stop monitoring and return the measured value."""
        self.monitoring = False
        return 0.0

    def update(self) -> None:
        """Update monitoring data (call periodically)."""
        pass


class MemoryMonitor(BaseMonitor):
    """Monitor memory usage during benchmarks."""

    def __init__(self):
        """Initialize memory monitor."""
        super().__init__()
        if not PSUTIL_AVAILABLE:
            raise ImportError("psutil is required for memory monitoring")

        self.process = psutil.Process()  # type: ignore
        self.initial_memory = 0.0
        self.max_memory = 0.0

    def start(self) -> None:
        """Start memory monitoring."""
        super().start()
        self.initial_memory = self.process.memory_info().rss / 1024 / 1024  # MB
        self.max_memory = self.initial_memory

    def stop(self) -> float:
        """Stop memory monitoring and return peak memory usage."""
        super().stop()
        return self.max_memory - self.initial_memory

    def update(self) -> None:
        """Update memory usage (call periodically during monitoring)."""
        if self.monitoring:
            current_memory = self.process.memory_info().rss / 1024 / 1024  # MB
            self.max_memory = max(self.max_memory, current_memory)


class CPUMonitor(BaseMonitor):
    """Monitor CPU usage during benchmarks."""

    def __init__(self):
        """Initialize CPU monitor."""
        super().__init__()
        if not PSUTIL_AVAILABLE:
            raise ImportError("psutil is required for CPU monitoring")

        self.process = psutil.Process()  # type: ignore
        self.cpu_samples: List[float] = []

    def start(self) -> None:
        """Start CPU monitoring."""
        super().start()
        self.cpu_samples = []

    def stop(self) -> float:
        """Stop CPU monitoring and return average CPU usage."""
        super().stop()
        return statistics.mean(self.cpu_samples) if self.cpu_samples else 0.0

    def update(self) -> None:
        """Update CPU usage (call periodically during monitoring)."""
        if self.monitoring:
            cpu_percent = self.process.cpu_percent()
            self.cpu_samples.append(cpu_percent)


class SystemMonitor:
    """Combined system monitoring for benchmarks."""

    def __init__(self, enable_memory: bool = True, enable_cpu: bool = True):
        """Initialize system monitor."""
        self.memory_monitor: Optional[MemoryMonitor] = None
        self.cpu_monitor: Optional[CPUMonitor] = None

        if enable_memory and PSUTIL_AVAILABLE:
            try:
                self.memory_monitor = MemoryMonitor()
            except ImportError:
                pass

        if enable_cpu and PSUTIL_AVAILABLE:
            try:
                self.cpu_monitor = CPUMonitor()
            except ImportError:
                pass

    def start(self) -> None:
        """Start all monitoring."""
        if self.memory_monitor:
            self.memory_monitor.start()
        if self.cpu_monitor:
            self.cpu_monitor.start()

    def stop(self) -> tuple[float, float]:
        """Stop all monitoring and return (memory_mb, cpu_percent)."""
        memory_usage = 0.0
        cpu_usage = 0.0

        if self.memory_monitor:
            memory_usage = self.memory_monitor.stop()
        if self.cpu_monitor:
            cpu_usage = self.cpu_monitor.stop()

        return memory_usage, cpu_usage

    def update(self) -> None:
        """Update all monitoring."""
        if self.memory_monitor:
            self.memory_monitor.update()
        if self.cpu_monitor:
            self.cpu_monitor.update()
