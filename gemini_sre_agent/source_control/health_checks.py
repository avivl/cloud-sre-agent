# gemini_sre_agent/source_control/health_checks.py

"""
Comprehensive health check implementations for source control providers.

This module provides detailed health check implementations that can be used
to monitor the health and performance of source control providers.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .base import SourceControlProvider
from .monitoring import HealthCheck, HealthStatus


class HealthCheckRegistry:
    """Registry for health check implementations."""

    def __init__(self):
        self.checks: Dict[
            str, Callable[[SourceControlProvider], Awaitable[HealthCheck]]
        ] = {}
        self.logger = logging.getLogger("HealthCheckRegistry")

    def register(
        self,
        name: str,
        check_func: Callable[[SourceControlProvider], Awaitable[HealthCheck]],
    ):
        """Register a health check function."""
        self.checks[name] = check_func
        self.logger.debug(f"Registered health check: {name}")

    def get_check(
        self, name: str
    ) -> Optional[Callable[[SourceControlProvider], Awaitable[HealthCheck]]]:
        """Get a health check function by name."""
        return self.checks.get(name)

    def list_checks(self) -> List[str]:
        """List all registered health check names."""
        return list(self.checks.keys())


# Global registry instance
health_check_registry = HealthCheckRegistry()


def register_health_check(name: str):
    """Decorator to register a health check function."""

    def decorator(func: Callable[[SourceControlProvider], Awaitable[HealthCheck]]):
        health_check_registry.register(name, func)
        return func

    return decorator


@register_health_check("basic_connectivity")
async def check_basic_connectivity(provider: SourceControlProvider) -> HealthCheck:
    """Check basic connectivity to the provider."""
    start_time = time.time()
    try:
        is_connected = await provider.test_connection()
        duration_ms = (time.time() - start_time) * 1000

        return HealthCheck(
            name="basic_connectivity",
            status=HealthStatus.HEALTHY if is_connected else HealthStatus.UNHEALTHY,
            message="Connection successful" if is_connected else "Connection failed",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"connected": is_connected, "response_time_ms": duration_ms},
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="basic_connectivity",
            status=HealthStatus.UNHEALTHY,
            message=f"Connection error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("credential_validation")
async def check_credential_validation(provider: SourceControlProvider) -> HealthCheck:
    """Check credential validation."""
    start_time = time.time()
    try:
        are_valid = await provider.validate_credentials()
        duration_ms = (time.time() - start_time) * 1000

        return HealthCheck(
            name="credential_validation",
            status=HealthStatus.HEALTHY if are_valid else HealthStatus.UNHEALTHY,
            message=(
                "Credentials valid" if are_valid else "Credentials invalid or expired"
            ),
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"valid": are_valid, "response_time_ms": duration_ms},
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="credential_validation",
            status=HealthStatus.UNHEALTHY,
            message=f"Credential validation error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("repository_access")
async def check_repository_access(provider: SourceControlProvider) -> HealthCheck:
    """Check if repository information can be accessed."""
    start_time = time.time()
    try:
        repo_info = await provider.get_repository_info()
        duration_ms = (time.time() - start_time) * 1000

        # Check if we got meaningful repository information
        has_name = bool(repo_info.name)
        has_url = bool(repo_info.url)
        has_default_branch = bool(repo_info.default_branch)

        is_healthy = has_name and has_url and has_default_branch

        return HealthCheck(
            name="repository_access",
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
            message=(
                "Repository access successful"
                if is_healthy
                else "Repository access limited"
            ),
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={
                "has_name": has_name,
                "has_url": has_url,
                "has_default_branch": has_default_branch,
                "repository_name": repo_info.name,
                "response_time_ms": duration_ms,
            },
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="repository_access",
            status=HealthStatus.UNHEALTHY,
            message=f"Repository access error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("file_operations")
async def check_file_operations(provider: SourceControlProvider) -> HealthCheck:
    """Check if file operations work correctly."""
    start_time = time.time()
    try:
        # Try to check if a common file exists (like README.md)
        file_exists = await provider.file_exists("README.md")
        duration_ms = (time.time() - start_time) * 1000

        # Check if we got a reasonable response
        is_healthy = isinstance(file_exists, bool)

        return HealthCheck(
            name="file_operations",
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
            message=(
                f"File operations working (README.md exists: {file_exists})"
                if is_healthy
                else "File operations limited"
            ),
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={
                "readme_exists": file_exists,
                "is_bool": isinstance(file_exists, bool),
                "response_time_ms": duration_ms,
            },
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="file_operations",
            status=HealthStatus.UNHEALTHY,
            message=f"File operations error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("branch_operations")
async def check_branch_operations(provider: SourceControlProvider) -> HealthCheck:
    """Check if branch operations work correctly."""
    start_time = time.time()
    try:
        # Try to list branches
        branches = await provider.list_branches()
        duration_ms = (time.time() - start_time) * 1000

        # Check if we got a valid list of branches
        is_healthy = isinstance(branches, list) and len(branches) > 0

        return HealthCheck(
            name="branch_operations",
            status=HealthStatus.HEALTHY if is_healthy else HealthStatus.DEGRADED,
            message=(
                f"Branch operations working (found {len(branches)} branches)"
                if is_healthy
                else "Branch operations limited"
            ),
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={
                "branch_count": len(branches),
                "is_list": isinstance(branches, list),
                "response_time_ms": duration_ms,
            },
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="branch_operations",
            status=HealthStatus.UNHEALTHY,
            message=f"Branch operations error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("performance_benchmark")
async def check_performance_benchmark(provider: SourceControlProvider) -> HealthCheck:
    """Check provider performance with a benchmark operation."""
    start_time = time.time()
    try:
        # Perform a series of operations to benchmark performance
        operations = [
            provider.test_connection(),
            provider.validate_credentials(),
            provider.get_repository_info(),
            provider.list_branches(),
        ]

        # Execute operations concurrently
        results = await asyncio.gather(*operations, return_exceptions=True)
        duration_ms = (time.time() - start_time) * 1000

        # Count successful operations
        successful_ops = sum(
            1 for result in results if not isinstance(result, Exception)
        )
        total_ops = len(operations)
        success_rate = successful_ops / total_ops

        # Determine health status based on success rate and response time
        if success_rate >= 0.9 and duration_ms < 2000:
            status = HealthStatus.HEALTHY
        elif success_rate >= 0.7 and duration_ms < 5000:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.UNHEALTHY

        return HealthCheck(
            name="performance_benchmark",
            status=status,
            message=f"Performance: {success_rate:.1%} success, {duration_ms:.0f}ms",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={
                "success_rate": success_rate,
                "successful_operations": successful_ops,
                "total_operations": total_ops,
                "response_time_ms": duration_ms,
                "operations_per_second": (
                    total_ops / (duration_ms / 1000) if duration_ms > 0 else 0
                ),
            },
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="performance_benchmark",
            status=HealthStatus.UNHEALTHY,
            message=f"Performance benchmark error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


@register_health_check("rate_limit_status")
async def check_rate_limit_status(provider: SourceControlProvider) -> HealthCheck:
    """Check rate limit status for the provider."""
    start_time = time.time()
    try:
        # Get health status which should include rate limit info
        health_status = await provider.get_health_status()
        duration_ms = (time.time() - start_time) * 1000

        # Extract rate limit information from details
        rate_limit_info = (
            health_status.additional_info.get("rate_limit", {})
            if health_status.additional_info
            else {}
        )
        remaining = rate_limit_info.get("remaining", None)
        limit = rate_limit_info.get("limit", None)
        reset_time = rate_limit_info.get("reset_time", None)

        # Determine health status based on rate limit
        if remaining is None or limit is None:
            status = HealthStatus.UNKNOWN
            message = "Rate limit information not available"
        elif remaining > limit * 0.2:  # More than 20% remaining
            status = HealthStatus.HEALTHY
            message = f"Rate limit healthy ({remaining}/{limit} remaining)"
        elif remaining > limit * 0.1:  # More than 10% remaining
            status = HealthStatus.DEGRADED
            message = f"Rate limit low ({remaining}/{limit} remaining)"
        else:
            status = HealthStatus.UNHEALTHY
            message = f"Rate limit critical ({remaining}/{limit} remaining)"

        return HealthCheck(
            name="rate_limit_status",
            status=status,
            message=message,
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={
                "remaining": remaining,
                "limit": limit,
                "reset_time": reset_time,
                "utilization": (
                    (limit - remaining) / limit
                    if limit and remaining is not None
                    else None
                ),
                "response_time_ms": duration_ms,
            },
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        return HealthCheck(
            name="rate_limit_status",
            status=HealthStatus.UNKNOWN,
            message=f"Rate limit check error: {e}",
            timestamp=datetime.now(),
            duration_ms=duration_ms,
            details={"error": str(e), "error_type": type(e).__name__},
        )


class ComprehensiveHealthChecker:
    """Comprehensive health checker that runs all registered checks."""

    def __init__(self):
        self.registry = health_check_registry
        self.logger = logging.getLogger("ComprehensiveHealthChecker")

    async def run_all_checks(
        self, provider: SourceControlProvider
    ) -> List[HealthCheck]:
        """Run all registered health checks on a provider."""
        checks = []
        check_names = self.registry.list_checks()

        self.logger.info(
            f"Running {len(check_names)} health checks on {provider.__class__.__name__}"
        )

        for check_name in check_names:
            check_func = self.registry.get_check(check_name)
            if check_func:
                try:
                    check_result = await check_func(provider)
                    checks.append(check_result)
                    self.logger.debug(
                        f"Health check {check_name}: {check_result.status.value}"
                    )
                except Exception as e:
                    self.logger.error(f"Health check {check_name} failed: {e}")
                    checks.append(
                        HealthCheck(
                            name=check_name,
                            status=HealthStatus.UNKNOWN,
                            message=f"Check execution failed: {e}",
                            timestamp=datetime.now(),
                            duration_ms=0.0,
                            details={"error": str(e), "error_type": type(e).__name__},
                        )
                    )

        return checks

    async def run_specific_checks(
        self, provider: SourceControlProvider, check_names: List[str]
    ) -> List[HealthCheck]:
        """Run specific health checks on a provider."""
        checks = []

        for check_name in check_names:
            check_func = self.registry.get_check(check_name)
            if check_func:
                try:
                    check_result = await check_func(provider)
                    checks.append(check_result)
                except Exception as e:
                    self.logger.error(f"Health check {check_name} failed: {e}")
                    checks.append(
                        HealthCheck(
                            name=check_name,
                            status=HealthStatus.UNKNOWN,
                            message=f"Check execution failed: {e}",
                            timestamp=datetime.now(),
                            duration_ms=0.0,
                            details={"error": str(e), "error_type": type(e).__name__},
                        )
                    )
            else:
                self.logger.warning(f"Health check {check_name} not found")
                checks.append(
                    HealthCheck(
                        name=check_name,
                        status=HealthStatus.UNKNOWN,
                        message=f"Check not found: {check_name}",
                        timestamp=datetime.now(),
                        duration_ms=0.0,
                    )
                )

        return checks

    def get_available_checks(self) -> List[str]:
        """Get list of available health check names."""
        return self.registry.list_checks()

    def get_check_summary(self, checks: List[HealthCheck]) -> Dict[str, Any]:
        """Get a summary of health check results."""
        if not checks:
            return {
                "total": 0,
                "healthy": 0,
                "degraded": 0,
                "unhealthy": 0,
                "unknown": 0,
            }

        summary: Dict[str, Any] = {
            "total": len(checks),
            "healthy": sum(1 for c in checks if c.status == HealthStatus.HEALTHY),
            "degraded": sum(1 for c in checks if c.status == HealthStatus.DEGRADED),
            "unhealthy": sum(1 for c in checks if c.status == HealthStatus.UNHEALTHY),
            "unknown": sum(1 for c in checks if c.status == HealthStatus.UNKNOWN),
        }

        # Calculate overall health score
        if summary["total"] > 0:
            healthy_weight = 1.0
            degraded_weight = 0.5
            unknown_weight = 0.3
            unhealthy_weight = 0.0

            score = (
                (summary["healthy"] * healthy_weight)
                + (summary["degraded"] * degraded_weight)
                + (summary["unknown"] * unknown_weight)
                + (summary["unhealthy"] * unhealthy_weight)
            ) / summary["total"]

            summary["health_score"] = float(score)
            summary["overall_status"] = (
                "healthy"
                if score >= 0.8
                else "degraded" if score >= 0.5 else "unhealthy"
            )

        return summary
