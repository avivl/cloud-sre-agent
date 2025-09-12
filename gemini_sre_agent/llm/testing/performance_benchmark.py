# gemini_sre_agent/llm/testing/performance_benchmark.py

"""
Performance Benchmarking Tools for LLM Providers and Models.

This module provides comprehensive performance benchmarking capabilities
including latency, throughput, memory usage, and concurrency testing.

This file has been refactored to use modular components while maintaining
backward compatibility. The original monolithic implementation has been
broken down into focused modules for better maintainability.
"""

import logging

# Import the refactored components
from .benchmark_models import BenchmarkConfig, BenchmarkResult
from .benchmark_monitors import CPUMonitor, MemoryMonitor
from .performance_benchmark_refactored import PerformanceBenchmark

logger = logging.getLogger(__name__)

# Re-export the main classes for backward compatibility
__all__ = [
    "PerformanceBenchmark",
    "BenchmarkResult",
    "BenchmarkConfig",
    "MemoryMonitor",
    "CPUMonitor",
]
