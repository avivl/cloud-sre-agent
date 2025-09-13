# gemini_sre_agent/core/quality/gates.py
"""
Core quality gate definitions and management.

This module implements the quality gate system that enforces code quality
standards across the entire codebase.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol

from ..logging import get_logger

logger = get_logger(__name__)


class QualityGateStatus(Enum):
    """Status of a quality gate check."""
    PASSED = "passed"
    FAILED = "failed"
    WARNING = "warning"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class QualityGateResult:
    """Result of a quality gate check."""
    gate_name: str
    status: QualityGateStatus
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_success(self) -> bool:
        """Check if the gate passed."""
        return self.status == QualityGateStatus.PASSED

    @property
    def is_failure(self) -> bool:
        """Check if the gate failed."""
        return self.status in [QualityGateStatus.FAILED, QualityGateStatus.ERROR]


@dataclass
class QualityGateConfig:
    """Configuration for quality gates."""
    # Static analysis
    enable_pyright: bool = True
    enable_ruff: bool = True
    pyright_strict: bool = True
    ruff_strict: bool = True

    # Test coverage
    enable_coverage: bool = True
    min_coverage: float = 80.0
    coverage_file: str = "coverage.xml"

    # Security
    enable_security: bool = True
    security_tools: list[str] = field(default_factory=lambda: ["bandit", "safety"])

    # Performance
    enable_performance: bool = True
    max_memory_mb: int = 512
    max_cpu_percent: float = 80.0

    # Documentation
    enable_docs: bool = True
    require_docstrings: bool = True
    min_docstring_coverage: float = 90.0

    # Style
    enable_style: bool = True
    max_line_length: int = 100
    require_type_hints: bool = True

    # General
    fail_on_warning: bool = False
    parallel_execution: bool = True
    timeout_seconds: int = 300


class QualityGate(Protocol):
    """Protocol for quality gate implementations."""

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run the quality gate check."""
        ...


class QualityGateManager:
    """Manages and executes quality gates."""

    def __init__(self, config: QualityGateConfig | None = None):
        """Initialize the quality gate manager.
        
        Args:
            config: Quality gate configuration. Uses default if None.
        """
        self.config = config or QualityGateConfig()
        self.gates: dict[str, QualityGate] = {}
        self.logger = get_logger(__name__)

    def register_gate(self, name: str, gate: QualityGate) -> None:
        """Register a quality gate.
        
        Args:
            name: Name of the gate.
            gate: Gate implementation.
        """
        self.gates[name] = gate
        self.logger.debug(f"Registered quality gate: {name}")

    async def run_gate(self, name: str) -> QualityGateResult:
        """Run a specific quality gate.
        
        Args:
            name: Name of the gate to run.
            
        Returns:
            Result of the gate check.
            
        Raises:
            QualityGateError: If gate is not found or fails to run.
        """
        if name not in self.gates:
            raise QualityGateError(f"Quality gate not found: {name}")

        gate = self.gates[name]
        start_time = datetime.now()

        try:
            self.logger.info(f"Running quality gate: {name}")
            result = await gate.check(self.config)
            result.duration = (datetime.now() - start_time).total_seconds()

            if result.is_success:
                self.logger.info(f"Quality gate passed: {name}")
            else:
                self.logger.warning(f"Quality gate failed: {name} - {result.message}")

            return result

        except Exception as e:
            self.logger.error(f"Quality gate error: {name} - {e!s}")
            return QualityGateResult(
                gate_name=name,
                status=QualityGateStatus.ERROR,
                message=f"Gate execution failed: {e!s}",
                duration=(datetime.now() - start_time).total_seconds()
            )

    async def run_all_gates(self) -> list[QualityGateResult]:
        """Run all registered quality gates.
        
        Returns:
            List of results from all gates.
        """
        if not self.gates:
            self.logger.warning("No quality gates registered")
            return []

        self.logger.info(f"Running {len(self.gates)} quality gates")

        if self.config.parallel_execution:
            tasks = [self.run_gate(name) for name in self.gates.keys()]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Handle exceptions from parallel execution
            processed_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    gate_name = list(self.gates.keys())[i]
                    processed_results.append(QualityGateResult(
                        gate_name=gate_name,
                        status=QualityGateStatus.ERROR,
                        message=f"Gate execution failed: {result!s}"
                    ))
                else:
                    processed_results.append(result)

            return processed_results
        else:
            results = []
            for name in self.gates.keys():
                result = await self.run_gate(name)
                results.append(result)
            return results

    def get_failed_gates(self, results: list[QualityGateResult]) -> list[QualityGateResult]:
        """Get gates that failed.
        
        Args:
            results: List of gate results.
            
        Returns:
            List of failed gate results.
        """
        return [r for r in results if r.is_failure]

    def get_passed_gates(self, results: list[QualityGateResult]) -> list[QualityGateResult]:
        """Get gates that passed.
        
        Args:
            results: List of gate results.
            
        Returns:
            List of passed gate results.
        """
        return [r for r in results if r.is_success]

    def should_fail_build(self, results: list[QualityGateResult]) -> bool:
        """Determine if the build should fail based on gate results.
        
        Args:
            results: List of gate results.
            
        Returns:
            True if build should fail, False otherwise.
        """
        failed_gates = self.get_failed_gates(results)

        if not failed_gates:
            return False

        # Check if any failed gates are critical
        critical_failures = [
            r for r in failed_gates
            if r.status == QualityGateStatus.ERROR
        ]

        if critical_failures:
            return True

        # If fail_on_warning is enabled, fail on any failure
        if self.config.fail_on_warning:
            return True

        return False


class QualityGateError(Exception):
    """Base exception for quality gate errors."""
    pass


class QualityGateFailureError(QualityGateError):
    """Exception raised when a quality gate fails."""
    pass
