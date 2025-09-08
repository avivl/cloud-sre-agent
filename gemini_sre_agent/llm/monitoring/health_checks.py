"""
Health Check System for LLM Providers.

This module provides comprehensive health checking capabilities for LLM providers,
including connectivity tests, performance validation, and status monitoring.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from ..base import LLMRequest, ModelType
from ..factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels for LLM providers."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Result of a health check for an LLM provider."""

    provider: str
    model: str
    status: HealthStatus
    message: str
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class ProviderHealth:
    """Overall health status for a provider."""

    provider: str
    status: HealthStatus
    last_check: datetime
    check_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_response_time_ms: float = 0.0
    models: Dict[str, HealthCheckResult] = field(default_factory=dict)
    issues: List[str] = field(default_factory=list)


class LLMHealthChecker:
    """Health checker for LLM providers and models."""

    def __init__(self, provider_factory: LLMProviderFactory):
        """Initialize the LLM health checker."""
        self.provider_factory = provider_factory
        self.provider_health: Dict[str, ProviderHealth] = {}
        self.health_check_interval = 30  # seconds
        self.health_check_timeout = 10  # seconds
        self._running = False
        self._health_check_task: Optional[asyncio.Task] = None

        # Simple test prompts for health checks
        self.test_prompts = {
            ModelType.FAST: "Hello, please respond with 'OK' to confirm you're working.",
            ModelType.SMART: "Please respond with a single word: 'healthy'",
            ModelType.DEEP_THINKING: "Respond with 'operational' to confirm system status.",
            ModelType.CODE: "Print 'health_check_passed' in Python.",
            ModelType.ANALYSIS: "Analyze this simple statement: 'The system is working correctly.' Respond with 'confirmed'.",
        }

        logger.info("LLMHealthChecker initialized")

    async def start_continuous_health_checks(self):
        """Start continuous health checking in the background."""
        if self._running:
            return

        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Continuous health checks started")

    async def stop_continuous_health_checks(self):
        """Stop continuous health checking."""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Continuous health checks stopped")

    async def _health_check_loop(self):
        """Main health check loop."""
        while self._running:
            try:
                await self.check_all_providers()
                await asyncio.sleep(self.health_check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.health_check_interval)

    async def check_all_providers(self) -> Dict[str, ProviderHealth]:
        """Check health of all available providers."""
        providers = self.provider_factory.list_providers()
        results = {}

        for provider_name in providers:
            try:
                health = await self.check_provider(provider_name)
                results[provider_name] = health
            except Exception as e:
                logger.error(f"Error checking provider {provider_name}: {e}")
                results[provider_name] = ProviderHealth(
                    provider=provider_name,
                    status=HealthStatus.UNKNOWN,
                    last_check=datetime.now(),
                    issues=[f"Health check failed: {str(e)}"],
                )

        return results

    async def check_provider(self, provider_name: str) -> ProviderHealth:
        """Check health of a specific provider."""

        try:
            # Get provider instance
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                return ProviderHealth(
                    provider=provider_name,
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(),
                    issues=["Provider not available"],
                )

            # Get available models for this provider
            models = []  # Simplified for now - would get from provider factory
            if not models:
                return ProviderHealth(
                    provider=provider_name,
                    status=HealthStatus.UNHEALTHY,
                    last_check=datetime.now(),
                    issues=["No models available"],
                )

            # Check each model
            model_results = {}
            successful_checks = 0
            total_checks = 0
            total_response_time = 0.0
            issues = []

            for model_info in models[:3]:  # Check up to 3 models per provider
                try:
                    result = await self.check_model(
                        provider_name, model_info.name, model_info.semantic_type
                    )
                    model_results[model_info.name] = result
                    total_checks += 1

                    if result.status == HealthStatus.HEALTHY:
                        successful_checks += 1
                        total_response_time += result.duration_ms
                    elif result.status == HealthStatus.DEGRADED:
                        successful_checks += 0.5  # Partial success
                        total_response_time += result.duration_ms
                        issues.append(f"Model {model_info.name}: {result.message}")
                    else:
                        issues.append(f"Model {model_info.name}: {result.message}")

                except Exception as e:
                    logger.error(f"Error checking model {model_info.name}: {e}")
                    issues.append(
                        f"Model {model_info.name}: Health check failed - {str(e)}"
                    )
                    total_checks += 1

            # Determine overall provider status
            if total_checks == 0:
                status = HealthStatus.UNKNOWN
            elif successful_checks == total_checks:
                status = HealthStatus.HEALTHY
            elif successful_checks >= total_checks * 0.5:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY

            # Calculate average response time
            avg_response_time = (
                total_response_time / successful_checks
                if successful_checks > 0
                else 0.0
            )

            # Update or create provider health record
            if provider_name in self.provider_health:
                health = self.provider_health[provider_name]
                health.status = status
                health.last_check = datetime.now()
                health.check_count += 1
                health.success_count += int(successful_checks)
                health.failure_count += total_checks - int(successful_checks)
                health.avg_response_time_ms = avg_response_time
                health.models.update(model_results)
                health.issues = issues
            else:
                health = ProviderHealth(
                    provider=provider_name,
                    status=status,
                    last_check=datetime.now(),
                    check_count=1,
                    success_count=int(successful_checks),
                    failure_count=total_checks - int(successful_checks),
                    avg_response_time_ms=avg_response_time,
                    models=model_results,
                    issues=issues,
                )
                self.provider_health[provider_name] = health

            return health

        except Exception as e:
            logger.error(f"Error checking provider {provider_name}: {e}")
            return ProviderHealth(
                provider=provider_name,
                status=HealthStatus.UNHEALTHY,
                last_check=datetime.now(),
                issues=[f"Provider check failed: {str(e)}"],
            )

    async def check_model(
        self, provider_name: str, model_name: str, model_type: ModelType
    ) -> HealthCheckResult:
        """Check health of a specific model."""
        start_time = time.time()

        try:
            # Get provider instance
            provider = self.provider_factory.get_provider(provider_name)
            if not provider:
                return HealthCheckResult(
                    provider=provider_name,
                    model=model_name,
                    status=HealthStatus.UNHEALTHY,
                    message="Provider not available",
                    error="Provider not found",
                )

            # Create a simple test request
            test_prompt = self.test_prompts.get(
                model_type, "Hello, please respond with 'OK'."
            )
            request = LLMRequest(
                prompt=test_prompt,
                model_type=model_type,
                max_tokens=10,
                temperature=0.0,
            )

            # Make the request with timeout
            try:
                response = await asyncio.wait_for(
                    provider.generate(request), timeout=self.health_check_timeout
                )

                duration_ms = (time.time() - start_time) * 1000

                # Validate response
                if response and response.content:
                    content = response.content.strip().lower()
                    if any(
                        keyword in content
                        for keyword in [
                            "ok",
                            "healthy",
                            "operational",
                            "confirmed",
                            "health_check_passed",
                        ]
                    ):
                        return HealthCheckResult(
                            provider=provider_name,
                            model=model_name,
                            status=HealthStatus.HEALTHY,
                            message="Model responding correctly",
                            duration_ms=duration_ms,
                            details={
                                "response_content": response.content,
                                "input_tokens": (
                                    response.usage.get("input_tokens", 0)
                                    if response.usage
                                    else 0
                                ),
                                "output_tokens": (
                                    response.usage.get("output_tokens", 0)
                                    if response.usage
                                    else 0
                                ),
                            },
                        )
                    else:
                        return HealthCheckResult(
                            provider=provider_name,
                            model=model_name,
                            status=HealthStatus.DEGRADED,
                            message="Model responding but with unexpected content",
                            duration_ms=duration_ms,
                            details={
                                "response_content": response.content,
                                "expected_keywords": [
                                    "ok",
                                    "healthy",
                                    "operational",
                                    "confirmed",
                                ],
                            },
                        )
                else:
                    return HealthCheckResult(
                        provider=provider_name,
                        model=model_name,
                        status=HealthStatus.UNHEALTHY,
                        message="No response content received",
                        duration_ms=duration_ms,
                    )

            except asyncio.TimeoutError:
                return HealthCheckResult(
                    provider=provider_name,
                    model=model_name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Request timed out after {self.health_check_timeout}s",
                    duration_ms=(time.time() - start_time) * 1000,
                    error="Timeout",
                )

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return HealthCheckResult(
                provider=provider_name,
                model=model_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                duration_ms=duration_ms,
                error=str(e),
            )

    def get_provider_health(self, provider_name: str) -> Optional[ProviderHealth]:
        """Get health status for a specific provider."""
        return self.provider_health.get(provider_name)

    def get_all_provider_health(self) -> Dict[str, ProviderHealth]:
        """Get health status for all providers."""
        return self.provider_health.copy()

    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of all provider health statuses."""
        if not self.provider_health:
            return {
                "overall_status": HealthStatus.UNKNOWN.value,
                "total_providers": 0,
                "healthy_providers": 0,
                "degraded_providers": 0,
                "unhealthy_providers": 0,
                "unknown_providers": 0,
            }

        status_counts = {
            HealthStatus.HEALTHY: 0,
            HealthStatus.DEGRADED: 0,
            HealthStatus.UNHEALTHY: 0,
            HealthStatus.UNKNOWN: 0,
        }

        for health in self.provider_health.values():
            status_counts[health.status] += 1

        # Determine overall status
        if status_counts[HealthStatus.HEALTHY] == len(self.provider_health):
            overall_status = HealthStatus.HEALTHY
        elif status_counts[HealthStatus.UNHEALTHY] > 0:
            overall_status = HealthStatus.UNHEALTHY
        elif status_counts[HealthStatus.DEGRADED] > 0:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN

        return {
            "overall_status": overall_status.value,
            "total_providers": len(self.provider_health),
            "healthy_providers": status_counts[HealthStatus.HEALTHY],
            "degraded_providers": status_counts[HealthStatus.DEGRADED],
            "unhealthy_providers": status_counts[HealthStatus.UNHEALTHY],
            "unknown_providers": status_counts[HealthStatus.UNKNOWN],
            "last_updated": datetime.now().isoformat(),
        }

    def get_unhealthy_providers(self) -> List[str]:
        """Get list of unhealthy providers."""
        return [
            provider
            for provider, health in self.provider_health.items()
            if health.status in [HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]
        ]

    def get_degraded_providers(self) -> List[str]:
        """Get list of degraded providers."""
        return [
            provider
            for provider, health in self.provider_health.items()
            if health.status == HealthStatus.DEGRADED
        ]

    def is_provider_healthy(self, provider_name: str) -> bool:
        """Check if a specific provider is healthy."""
        health = self.provider_health.get(provider_name)
        return health is not None and health.status == HealthStatus.HEALTHY

    def get_provider_issues(self, provider_name: str) -> List[str]:
        """Get issues for a specific provider."""
        health = self.provider_health.get(provider_name)
        return health.issues if health else []
