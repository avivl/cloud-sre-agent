# gemini_sre_agent/core/quality/validators.py
"""
Quality gate validators for different aspects of code quality.

This module implements specific validators for static analysis,
test coverage, security, performance, documentation, and style.
"""

import asyncio
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from ..logging import get_logger
from .gates import QualityGateConfig, QualityGateResult, QualityGateStatus

logger = get_logger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    success: bool
    message: str
    details: dict[str, Any]
    errors: list[str] = None
    warnings: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.warnings is None:
            self.warnings = []


class StaticAnalysisValidator:
    """Validator for static analysis using pyright and ruff."""

    def __init__(self):
        """Initialize the static analysis validator."""
        self.logger = get_logger(__name__)

    async def run_pyright(self, config: QualityGateConfig) -> ValidationResult:
        """Run pyright static analysis.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result from pyright.
        """
        try:
            self.logger.info("Running pyright static analysis")

            cmd = ["pyright", "--outputjson"]
            if config.pyright_strict:
                cmd.append("--strict")

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                return ValidationResult(
                    success=True,
                    message="Pyright analysis passed",
                    details={"returncode": result.returncode}
                )
            else:
                # Parse pyright output
                try:
                    output = json.loads(stdout.decode())
                    errors = output.get("generalDiagnostics", [])
                    error_count = len([e for e in errors if e.get("severity") == "error"])
                    warning_count = len([e for e in errors if e.get("severity") == "warning"])

                    return ValidationResult(
                        success=False,
                        message=f"Pyright found {error_count} errors, {warning_count} warnings",
                        details={
                            "returncode": result.returncode,
                            "error_count": error_count,
                            "warning_count": warning_count,
                            "errors": errors
                        },
                        errors=[
                            e.get("message", "") 
                            for e in errors if e.get("severity") == "error"
                        ],
                        warnings=[
                            e.get("message", "") 
                            for e in errors if e.get("severity") == "warning"
                        ]
                    )
                except json.JSONDecodeError:
                    return ValidationResult(
                        success=False,
                        message="Pyright analysis failed",
                        details={"returncode": result.returncode, "output": stdout.decode()},
                        errors=[stdout.decode()]
                    )

        except Exception as e:
            self.logger.error(f"Pyright execution failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Pyright execution failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )

    async def run_ruff(self, config: QualityGateConfig) -> ValidationResult:
        """Run ruff linting and formatting.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result from ruff.
        """
        try:
            self.logger.info("Running ruff linting")

            cmd = ["ruff", "check", "--output-format=json"]
            if config.ruff_strict:
                cmd.append("--select=ALL")

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                return ValidationResult(
                    success=True,
                    message="Ruff linting passed",
                    details={"returncode": result.returncode}
                )
            else:
                try:
                    output = json.loads(stdout.decode())
                    # Ruff returns a list of violations, not a dict with "violations" key
                    if isinstance(output, list):
                        violations = output
                    else:
                        violations = output.get("violations", [])

                    return ValidationResult(
                        success=False,
                        message=f"Ruff found {len(violations)} violations",
                        details={
                            "returncode": result.returncode,
                            "violation_count": len(violations),
                            "violations": violations
                        },
                        errors=[v.get("message", "") for v in violations]
                    )
                except json.JSONDecodeError:
                    return ValidationResult(
                        success=False,
                        message="Ruff linting failed",
                        details={"returncode": result.returncode, "output": stdout.decode()},
                        errors=[stdout.decode()]
                    )

        except Exception as e:
            self.logger.error(f"Ruff execution failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Ruff execution failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


class TestCoverageValidator:
    """Validator for test coverage."""

    def __init__(self):
        """Initialize the test coverage validator."""
        self.logger = get_logger(__name__)

    async def check_coverage(self, config: QualityGateConfig) -> ValidationResult:
        """Check test coverage.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result for coverage.
        """
        try:
            self.logger.info("Checking test coverage")

            # Run pytest with coverage
            cmd = [
                "pytest",
                "--cov=gemini_sre_agent",
                "--cov-report=xml",
                "--cov-report=term-missing",
                f"--cov-fail-under={config.min_coverage}"
            ]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            if result.returncode == 0:
                return ValidationResult(
                    success=True,
                    message=f"Test coverage meets minimum requirement ({config.min_coverage}%)",
                    details={"returncode": result.returncode}
                )
            else:
                return ValidationResult(
                    success=False,
                    message=f"Test coverage below minimum requirement ({config.min_coverage}%)",
                    details={"returncode": result.returncode, "output": stdout.decode()},
                    errors=[stdout.decode()]
                )

        except Exception as e:
            self.logger.error(f"Coverage check failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Coverage check failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


class SecurityValidator:
    """Validator for security issues."""

    def __init__(self):
        """Initialize the security validator."""
        self.logger = get_logger(__name__)

    async def run_bandit(self, config: QualityGateConfig) -> ValidationResult:
        """Run bandit security analysis.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result from bandit.
        """
        try:
            self.logger.info("Running bandit security analysis")

            cmd = ["bandit", "-r", "gemini_sre_agent", "-f", "json"]

            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await result.communicate()

            try:
                output = json.loads(stdout.decode())
                issues = output.get("results", [])
                high_severity = [i for i in issues if i.get("issue_severity") == "HIGH"]
                medium_severity = [i for i in issues if i.get("issue_severity") == "MEDIUM"]

                if not high_severity and not medium_severity:
                    return ValidationResult(
                        success=True,
                        message="Bandit security analysis passed",
                        details={"returncode": result.returncode, "issues": len(issues)}
                    )
                else:
                    return ValidationResult(
                        success=False,
                        message=(
                            f"Bandit found {len(high_severity)} high, "
                            f"{len(medium_severity)} medium severity issues"
                        ),
                        details={
                            "returncode": result.returncode,
                            "high_severity": len(high_severity),
                            "medium_severity": len(medium_severity),
                            "issues": issues
                        },
                        errors=[i.get("issue_text", "") for i in high_severity + medium_severity]
                    )

            except json.JSONDecodeError:
                return ValidationResult(
                    success=False,
                    message="Bandit analysis failed to parse output",
                    details={"returncode": result.returncode, "output": stdout.decode()},
                    errors=[stdout.decode()]
                )

        except Exception as e:
            self.logger.error(f"Bandit execution failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Bandit execution failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


class PerformanceValidator:
    """Validator for performance metrics."""

    def __init__(self):
        """Initialize the performance validator."""
        self.logger = get_logger(__name__)

    async def check_performance(self, config: QualityGateConfig) -> ValidationResult:
        """Check performance metrics.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result for performance.
        """
        try:
            self.logger.info("Checking performance metrics")

            # This is a placeholder - in a real implementation,
            # you would run performance benchmarks and check against thresholds
            import psutil

            # Check memory usage
            memory = psutil.virtual_memory()
            memory_usage_mb = (memory.total - memory.available) / 1024 / 1024

            # Check CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)

            memory_ok = memory_usage_mb < config.max_memory_mb
            cpu_ok = cpu_percent < config.max_cpu_percent

            if memory_ok and cpu_ok:
                return ValidationResult(
                    success=True,
                    message="Performance metrics within acceptable limits",
                    details={
                        "memory_usage_mb": memory_usage_mb,
                        "cpu_percent": cpu_percent,
                        "max_memory_mb": config.max_memory_mb,
                        "max_cpu_percent": config.max_cpu_percent
                    }
                )
            else:
                errors = []
                if not memory_ok:
                    errors.append(
                        f"Memory usage {memory_usage_mb:.1f}MB exceeds limit "
                        f"{config.max_memory_mb}MB"
                    )
                if not cpu_ok:
                    errors.append(
                        f"CPU usage {cpu_percent:.1f}% exceeds limit "
                        f"{config.max_cpu_percent}%"
                    )

                return ValidationResult(
                    success=False,
                    message="Performance metrics exceed limits",
                    details={
                        "memory_usage_mb": memory_usage_mb,
                        "cpu_percent": cpu_percent,
                        "max_memory_mb": config.max_memory_mb,
                        "max_cpu_percent": config.max_cpu_percent
                    },
                    errors=errors
                )

        except Exception as e:
            self.logger.error(f"Performance check failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Performance check failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


class DocumentationValidator:
    """Validator for documentation quality."""

    def __init__(self):
        """Initialize the documentation validator."""
        self.logger = get_logger(__name__)

    async def check_documentation(self, config: QualityGateConfig) -> ValidationResult:
        """Check documentation quality.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result for documentation.
        """
        try:
            self.logger.info("Checking documentation quality")

            # This is a placeholder - in a real implementation,
            # you would use tools like pydocstyle or custom checks
            python_files = list(Path("gemini_sre_agent").rglob("*.py"))
            total_functions = 0
            documented_functions = 0

            for file_path in python_files:
                if file_path.name == "__init__.py":
                    continue

                try:
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()

                    # Simple check for docstrings (this is very basic)
                    lines = content.split("\n")
                    for i, line in enumerate(lines):
                        if line.strip().startswith("def ") or line.strip().startswith("async def "):
                            total_functions += 1
                            # Check if next non-empty line is a docstring
                            for j in range(i + 1, len(lines)):
                                next_line = lines[j].strip()
                                if next_line:
                                    if next_line.startswith('"""') or next_line.startswith("'''"):
                                        documented_functions += 1
                                    break
                except Exception:
                    continue

            if total_functions == 0:
                docstring_coverage = 100.0
            else:
                docstring_coverage = (documented_functions / total_functions) * 100

            if docstring_coverage >= config.min_docstring_coverage:
                return ValidationResult(
                    success=True,
                    message=f"Documentation coverage {docstring_coverage:.1f}% meets requirement",
                    details={
                        "docstring_coverage": docstring_coverage,
                        "total_functions": total_functions,
                        "documented_functions": documented_functions,
                        "min_required": config.min_docstring_coverage
                    }
                )
            else:
                return ValidationResult(
                    success=False,
                    message=f"Documentation coverage {docstring_coverage:.1f}% below requirement",
                    details={
                        "docstring_coverage": docstring_coverage,
                        "total_functions": total_functions,
                        "documented_functions": documented_functions,
                        "min_required": config.min_docstring_coverage
                    },
                    errors=[
                        f"Documentation coverage {docstring_coverage:.1f}% below required "
                        f"{config.min_docstring_coverage}%"
                    ]
                )

        except Exception as e:
            self.logger.error(f"Documentation check failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Documentation check failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


class StyleValidator:
    """Validator for code style."""

    def __init__(self):
        """Initialize the style validator."""
        self.logger = get_logger(__name__)

    async def check_style(self, config: QualityGateConfig) -> ValidationResult:
        """Check code style.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Validation result for style.
        """
        try:
            self.logger.info("Checking code style")

            # Check line length
            python_files = list(Path("gemini_sre_agent").rglob("*.py"))
            long_lines = []

            for file_path in python_files:
                try:
                    with open(file_path, encoding="utf-8") as f:
                        for line_num, line in enumerate(f, 1):
                            if len(line.rstrip()) > config.max_line_length:
                                long_lines.append(f"{file_path}:{line_num}")
                except Exception:
                    continue

            if not long_lines:
                return ValidationResult(
                    success=True,
                    message="Code style checks passed",
                    details={
                        "max_line_length": config.max_line_length,
                        "files_checked": len(python_files)
                    }
                )
            else:
                return ValidationResult(
                    success=False,
                    message=(
                        f"Found {len(long_lines)} lines exceeding "
                        f"{config.max_line_length} characters"
                    ),
                    details={
                        "max_line_length": config.max_line_length,
                        "files_checked": len(python_files),
                        "long_lines": long_lines[:10]  # Limit output
                    },
                    errors=[f"Line too long: {line}" for line in long_lines[:10]]
                )

        except Exception as e:
            self.logger.error(f"Style check failed: {e!s}")
            return ValidationResult(
                success=False,
                message=f"Style check failed: {e!s}",
                details={"error": str(e)},
                errors=[str(e)]
            )


# Quality Gate Implementations
class StaticAnalysisGate:
    """Quality gate for static analysis."""

    def __init__(self):
        """Initialize the static analysis gate."""
        self.validator = StaticAnalysisValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run static analysis checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of static analysis checks.
        """
        if not config.enable_pyright and not config.enable_ruff:
            return QualityGateResult(
                gate_name="static_analysis",
                status=QualityGateStatus.SKIPPED,
                message="Static analysis disabled"
            )

        results = []

        if config.enable_pyright:
            pyright_result = await self.validator.run_pyright(config)
            results.append(("pyright", pyright_result))

        if config.enable_ruff:
            ruff_result = await self.validator.run_ruff(config)
            results.append(("ruff", ruff_result))

        # Determine overall status
        failed_checks = [name for name, result in results if not result.success]

        if not failed_checks:
            return QualityGateResult(
                gate_name="static_analysis",
                status=QualityGateStatus.PASSED,
                message="All static analysis checks passed",
                details={name: result.details for name, result in results}
            )
        else:
            return QualityGateResult(
                gate_name="static_analysis",
                status=QualityGateStatus.FAILED,
                message=f"Static analysis failed: {', '.join(failed_checks)}",
                details={name: result.details for name, result in results}
            )


class TestCoverageGate:
    """Quality gate for test coverage."""

    def __init__(self):
        """Initialize the test coverage gate."""
        self.validator = TestCoverageValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run test coverage checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of test coverage checks.
        """
        if not config.enable_coverage:
            return QualityGateResult(
                gate_name="test_coverage",
                status=QualityGateStatus.SKIPPED,
                message="Test coverage checks disabled"
            )

        result = await self.validator.check_coverage(config)

        if result.success:
            return QualityGateResult(
                gate_name="test_coverage",
                status=QualityGateStatus.PASSED,
                message=result.message,
                details=result.details
            )
        else:
            return QualityGateResult(
                gate_name="test_coverage",
                status=QualityGateStatus.FAILED,
                message=result.message,
                details=result.details
            )


class SecurityGate:
    """Quality gate for security."""

    def __init__(self):
        """Initialize the security gate."""
        self.validator = SecurityValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run security checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of security checks.
        """
        if not config.enable_security:
            return QualityGateResult(
                gate_name="security",
                status=QualityGateStatus.SKIPPED,
                message="Security checks disabled"
            )

        result = await self.validator.run_bandit(config)

        if result.success:
            return QualityGateResult(
                gate_name="security",
                status=QualityGateStatus.PASSED,
                message=result.message,
                details=result.details
            )
        else:
            return QualityGateResult(
                gate_name="security",
                status=QualityGateStatus.FAILED,
                message=result.message,
                details=result.details
            )


class PerformanceGate:
    """Quality gate for performance."""

    def __init__(self):
        """Initialize the performance gate."""
        self.validator = PerformanceValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run performance checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of performance checks.
        """
        if not config.enable_performance:
            return QualityGateResult(
                gate_name="performance",
                status=QualityGateStatus.SKIPPED,
                message="Performance checks disabled"
            )

        result = await self.validator.check_performance(config)

        if result.success:
            return QualityGateResult(
                gate_name="performance",
                status=QualityGateStatus.PASSED,
                message=result.message,
                details=result.details
            )
        else:
            return QualityGateResult(
                gate_name="performance",
                status=QualityGateStatus.FAILED,
                message=result.message,
                details=result.details
            )


class DocumentationGate:
    """Quality gate for documentation."""

    def __init__(self):
        """Initialize the documentation gate."""
        self.validator = DocumentationValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run documentation checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of documentation checks.
        """
        if not config.enable_docs:
            return QualityGateResult(
                gate_name="documentation",
                status=QualityGateStatus.SKIPPED,
                message="Documentation checks disabled"
            )

        result = await self.validator.check_documentation(config)

        if result.success:
            return QualityGateResult(
                gate_name="documentation",
                status=QualityGateStatus.PASSED,
                message=result.message,
                details=result.details
            )
        else:
            return QualityGateResult(
                gate_name="documentation",
                status=QualityGateStatus.FAILED,
                message=result.message,
                details=result.details
            )


class StyleGate:
    """Quality gate for code style."""

    def __init__(self):
        """Initialize the style gate."""
        self.validator = StyleValidator()
        self.logger = get_logger(__name__)

    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        """Run style checks.
        
        Args:
            config: Quality gate configuration.
            
        Returns:
            Result of style checks.
        """
        if not config.enable_style:
            return QualityGateResult(
                gate_name="style",
                status=QualityGateStatus.SKIPPED,
                message="Style checks disabled"
            )

        result = await self.validator.check_style(config)

        if result.success:
            return QualityGateResult(
                gate_name="style",
                status=QualityGateStatus.PASSED,
                message=result.message,
                details=result.details
            )
        else:
            return QualityGateResult(
                gate_name="style",
                status=QualityGateStatus.FAILED,
                message=result.message,
                details=result.details
            )
