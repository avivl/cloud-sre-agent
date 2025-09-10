# gemini_sre_agent/source_control/error_handling/resilient_operations.py

"""
Resilient operation management with circuit breaker and retry logic.

This module provides a comprehensive manager that combines circuit breaker patterns
with retry mechanisms for robust source control operations.
"""

import logging
from typing import Any, Callable, Dict, Optional

from ..models import ProviderHealth
from .circuit_breaker import CircuitBreaker
from .core import CircuitBreakerConfig, CircuitBreakerOpenError, CircuitBreakerTimeoutError, CircuitState, OperationCircuitBreakerConfig, RetryConfig
from .metrics_integration import ErrorHandlingMetrics
from .retry_manager import RetryManager


class ResilientOperationManager:
    """Manages resilient operations with circuit breaker and retry logic."""

    def __init__(
        self,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        operation_circuit_breaker_config: Optional[
            OperationCircuitBreakerConfig
        ] = None,
        retry_config: Optional[RetryConfig] = None,
        metrics: Optional[ErrorHandlingMetrics] = None,
    ):
        self.circuit_breaker_config = circuit_breaker_config or CircuitBreakerConfig()
        self.operation_circuit_breaker_config = (
            operation_circuit_breaker_config or OperationCircuitBreakerConfig()
        )
        self.retry_config = retry_config or RetryConfig()
        self.metrics = metrics

        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.retry_manager = RetryManager(self.retry_config, metrics)
        self.logger = logging.getLogger("ResilientOperationManager")

    def _determine_operation_type(self, operation_name: str) -> str:
        """Determine the operation type based on the operation name."""
        operation_name_lower = operation_name.lower()

        # File operations
        if any(
            keyword in operation_name_lower
            for keyword in [
                "file",
                "content",
                "read",
                "write",
                "create_file",
                "update_file",
                "delete_file",
                "get_file",
                "list_files",
            ]
        ):
            return "file_operations"

        # Branch operations
        elif any(
            keyword in operation_name_lower
            for keyword in [
                "branch",
                "create_branch",
                "delete_branch",
                "list_branches",
                "checkout",
                "merge",
                "conflict",
            ]
        ):
            return "branch_operations"

        # Pull request operations
        elif any(
            keyword in operation_name_lower
            for keyword in [
                "pull_request",
                "merge_request",
                "pr",
                "mr",
                "review",
                "approve",
            ]
        ):
            return "pull_request_operations"

        # Batch operations
        elif any(
            keyword in operation_name_lower
            for keyword in ["batch", "bulk", "multiple", "batch_operations"]
        ):
            return "batch_operations"

        # Authentication operations
        elif any(
            keyword in operation_name_lower
            for keyword in ["auth", "login", "credential", "token", "authenticate"]
        ):
            return "auth_operations"

        # Default fallback
        return "default"

    def get_circuit_breaker(self, name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for the given name with operation-specific config."""
        if name not in self.circuit_breakers:
            operation_type = self._determine_operation_type(name)
            config = getattr(
                self.operation_circuit_breaker_config,
                operation_type,
                self.operation_circuit_breaker_config.default,
            )
            self.circuit_breakers[name] = CircuitBreaker(config, name, self.metrics)
            self.logger.debug(
                f"Created circuit breaker for {name} with {operation_type} config"
            )
        return self.circuit_breakers[name]

    async def execute_resilient_operation(
        self, operation_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Execute an operation with full resilience (circuit breaker + retry)."""
        circuit_breaker = self.get_circuit_breaker(operation_name)

        try:
            # First try with circuit breaker
            return await circuit_breaker.call(func, *args, **kwargs)
        except (CircuitBreakerOpenError, CircuitBreakerTimeoutError):
            # Circuit breaker is open or timed out, don't retry
            raise
        except Exception:
            # Other errors, try with retry logic
            try:
                return await self.retry_manager.execute_with_retry(
                    func, *args, **kwargs
                )
            except Exception as retry_error:
                # If retry also fails, record the failure in circuit breaker
                await circuit_breaker._record_failure()
                raise retry_error

    def get_operation_config(self, operation_name: str) -> CircuitBreakerConfig:
        """Get the circuit breaker configuration for a specific operation."""
        operation_type = self._determine_operation_type(operation_name)
        return getattr(
            self.operation_circuit_breaker_config,
            operation_type,
            self.operation_circuit_breaker_config.default,
        )

    def get_health_status(self) -> ProviderHealth:
        """Get overall health status of all circuit breakers."""
        circuit_stats = []
        overall_healthy = True
        operation_type_stats = {}

        for name, circuit in self.circuit_breakers.items():
            stats = circuit.get_stats()
            operation_type = self._determine_operation_type(name)
            stats["operation_type"] = operation_type
            circuit_stats.append(stats)

            # Track stats by operation type
            if operation_type not in operation_type_stats:
                operation_type_stats[operation_type] = {
                    "total": 0,
                    "healthy": 0,
                    "open_circuits": 0,
                }

            operation_type_stats[operation_type]["total"] += 1
            if circuit.state != CircuitState.OPEN and stats["failure_rate"] <= 0.5:
                operation_type_stats[operation_type]["healthy"] += 1
            else:
                if circuit.state == CircuitState.OPEN:
                    operation_type_stats[operation_type]["open_circuits"] += 1
                overall_healthy = False

        return ProviderHealth(
            status="healthy" if overall_healthy else "unhealthy",
            message=(
                "All circuits healthy"
                if overall_healthy
                else "Some circuits are unhealthy"
            ),
            additional_info={
                "circuit_breakers": circuit_stats,
                "total_circuits": len(self.circuit_breakers),
                "healthy_circuits": sum(
                    1 for stats in circuit_stats if stats["failure_rate"] <= 0.5
                ),
                "operation_type_stats": operation_type_stats,
                "operation_configs": {
                    op_type: {
                        "failure_threshold": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).failure_threshold,
                        "recovery_timeout": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).recovery_timeout,
                        "timeout": getattr(
                            self.operation_circuit_breaker_config,
                            op_type,
                            self.operation_circuit_breaker_config.default,
                        ).timeout,
                    }
                    for op_type in [
                        "file_operations",
                        "branch_operations",
                        "pull_request_operations",
                        "batch_operations",
                        "auth_operations",
                        "default",
                    ]
                },
            },
        )


# Global instance for easy access with operation-specific configurations
resilient_manager = ResilientOperationManager(
    operation_circuit_breaker_config=OperationCircuitBreakerConfig()
)
