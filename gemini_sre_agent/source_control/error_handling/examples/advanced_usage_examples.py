# gemini_sre_agent/source_control/error_handling/examples/advanced_usage_examples.py

"""
Advanced usage examples for the error handling system.

This module demonstrates how to use the advanced error handling components
in real-world scenarios with comprehensive examples.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from ..advanced_circuit_breaker import AdvancedCircuitBreaker
from ..core import CircuitBreakerConfig, ErrorType
from ..custom_fallback_strategies import (
    CustomFallbackManager,
    FallbackStrategyBase,
)
from ..error_recovery_automation import SelfHealingManager
from ..monitoring_dashboard import MonitoringDashboard


class GitHubAPIFallbackStrategy(FallbackStrategyBase):
    """Fallback strategy for GitHub API errors."""

    def __init__(self):
        super().__init__(name="github_api_fallback", priority=1)

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if this strategy can handle the error."""
        return (
            error_type in [ErrorType.RATE_LIMIT_ERROR, ErrorType.TIMEOUT_ERROR]
            and "github" in context.get("service", "").lower()
        )

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute the fallback strategy."""
        self.logger.info("Executing GitHub API fallback strategy")

        # Simulate fallback behavior
        await asyncio.sleep(0.1)  # Simulate processing time

        # Return fallback data
        return {
            "status": "fallback",
            "data": {"message": "Using cached GitHub data"},
            "source": "fallback_strategy",
        }


class DatabaseFallbackStrategy(FallbackStrategyBase):
    """Fallback strategy for database errors."""

    def __init__(self):
        super().__init__(name="database_fallback", priority=1)

    async def can_handle(
        self, operation_type: str, error_type: ErrorType, context: Dict[str, Any]
    ) -> bool:
        """Check if this strategy can handle the error."""
        return (
            error_type in [ErrorType.CONNECTION_RESET_ERROR, ErrorType.TIMEOUT_ERROR]
            and "database" in context.get("service", "").lower()
        )

    async def execute(
        self, operation_type: str, original_func: Any, *args, **kwargs
    ) -> Any:
        """Execute the fallback strategy."""
        self.logger.info("Executing database fallback strategy")

        # Simulate fallback behavior
        await asyncio.sleep(0.1)  # Simulate processing time

        # Return fallback data
        return {
            "status": "fallback",
            "data": {"message": "Using cached database data"},
            "source": "fallback_strategy",
        }


class AdvancedErrorHandlingExample:
    """Comprehensive example of advanced error handling usage."""

    def __init__(self):
        self.logger = logging.getLogger("AdvancedErrorHandlingExample")
        self.setup_logging()

        # Initialize components
        self.circuit_breakers: Dict[str, AdvancedCircuitBreaker] = {}
        self.fallback_manager: Optional[CustomFallbackManager] = None
        self.self_healing_manager: Optional[SelfHealingManager] = None
        self.dashboard: Optional[MonitoringDashboard] = None

    def setup_logging(self):
        """Setup logging configuration."""
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    async def initialize_components(self):
        """Initialize all error handling components."""
        self.logger.info("Initializing error handling components...")

        # Initialize circuit breakers
        await self._setup_circuit_breakers()

        # Initialize fallback manager
        await self._setup_fallback_manager()

        # Initialize self-healing manager
        await self._setup_self_healing_manager()

        # Initialize monitoring dashboard
        await self._setup_monitoring_dashboard()

        self.logger.info("All components initialized successfully")

    async def _setup_circuit_breakers(self):
        """Setup circuit breakers for different operations."""
        # GitHub API circuit breaker
        github_config = CircuitBreakerConfig()
        github_config.failure_threshold = 5
        github_config.recovery_timeout = 30.0
        github_config.success_threshold = 3
        github_config.timeout = 15.0
        self.circuit_breakers["github_api"] = AdvancedCircuitBreaker(
            github_config, "github_api"
        )

        # Database circuit breaker
        db_config = CircuitBreakerConfig()
        db_config.failure_threshold = 3
        db_config.recovery_timeout = 20.0
        db_config.success_threshold = 2
        db_config.timeout = 10.0
        self.circuit_breakers["database"] = AdvancedCircuitBreaker(
            db_config, "database"
        )

    async def _setup_fallback_manager(self):
        """Setup fallback manager with custom strategies."""
        self.fallback_manager = CustomFallbackManager()

        # Register fallback strategies
        await self._register_fallback_strategies()

    async def _register_fallback_strategies(self):
        """Register custom fallback strategies."""
        if not self.fallback_manager:
            return

        # GitHub API fallback strategy
        github_fallback = GitHubAPIFallbackStrategy()
        self.fallback_manager.add_strategy(github_fallback)

        # Database fallback strategy
        db_fallback = DatabaseFallbackStrategy()
        self.fallback_manager.add_strategy(db_fallback)

    async def _github_api_fallback_action(
        self, error_type: ErrorType, error_message: str, context: Dict[str, Any]
    ) -> Any:
        """GitHub API fallback action."""
        self.logger.info("Executing GitHub API fallback strategy")

        if error_type == ErrorType.RATE_LIMIT_ERROR:
            await asyncio.sleep(60)
            return {"status": "retry_after_rate_limit", "message": "Rate limit handled"}
        elif error_type == ErrorType.TIMEOUT_ERROR:
            cached_data = context.get("cached_data")
            if cached_data:
                return {"status": "cached_data", "data": cached_data}
            else:
                return {
                    "status": "no_fallback_available",
                    "message": "No cached data available",
                }

        return {"status": "fallback_failed", "message": "Unsupported error type"}

    async def _database_fallback_action(
        self, error_type: ErrorType, error_message: str, context: Dict[str, Any]
    ) -> Any:
        """Database fallback action."""
        self.logger.info("Executing database fallback strategy")

        if error_type == ErrorType.CONNECTION_RESET_ERROR:
            await asyncio.sleep(2)
            return {
                "status": "reconnection_attempted",
                "message": "Attempting to reconnect",
            }
        elif error_type == ErrorType.TIMEOUT_ERROR:
            read_replica = context.get("read_replica")
            if read_replica:
                return {"status": "read_replica", "data": "Using read replica"}
            else:
                return {
                    "status": "no_fallback_available",
                    "message": "No read replica available",
                }

        return {"status": "fallback_failed", "message": "Unsupported error type"}

    async def _setup_self_healing_manager(self):
        """Setup self-healing manager."""
        self.self_healing_manager = SelfHealingManager()

    async def _setup_monitoring_dashboard(self):
        """Setup monitoring dashboard."""
        self.dashboard = MonitoringDashboard()

        # Register all components
        for name, cb in self.circuit_breakers.items():
            self.dashboard.register_circuit_breaker(name, cb)

        if self.fallback_manager:
            self.dashboard.register_fallback_manager(self.fallback_manager)

        if self.self_healing_manager:
            self.dashboard.register_self_healing_manager(self.self_healing_manager)

    async def demonstrate_github_api_operations(self):
        """Demonstrate GitHub API operations with error handling."""
        self.logger.info("Demonstrating GitHub API operations...")

        github_cb = self.circuit_breakers["github_api"]

        # Simulate GitHub API calls
        async def github_api_call(operation: str, **kwargs) -> Dict[str, Any]:
            """Simulate GitHub API call with potential failures."""
            if (
                operation == "get_repository"
                and kwargs.get("repo_name") == "nonexistent"
            ):
                raise Exception("Repository not found")
            elif (
                operation == "create_issue" and kwargs.get("title") == "rate_limit_test"
            ):
                raise Exception("API rate limit exceeded")
            else:
                return {
                    "status": "success",
                    "operation": operation,
                    "data": f"Mock data for {operation}",
                }

        # Test successful operation
        try:
            result = await github_cb.call(
                github_api_call, "get_repository", repo_name="test_repo"
            )
            self.logger.info(f"GitHub API call successful: {result}")
        except Exception as e:
            self.logger.error(f"GitHub API call failed: {e}")

        # Test error handling with fallback
        try:
            result = await github_cb.call(
                github_api_call, "create_issue", title="rate_limit_test"
            )
            self.logger.info(f"GitHub API call successful: {result}")
        except Exception as e:
            self.logger.error(f"GitHub API call failed: {e}")
            # Execute fallback
            if self.fallback_manager:
                fallback_result = await self.fallback_manager.execute_fallback(
                    "create_issue",
                    ErrorType.RATE_LIMIT_ERROR,
                    github_api_call,
                    {"service": "github"},
                )
                self.logger.info(f"Fallback result: {fallback_result}")

    async def demonstrate_monitoring(self):
        """Demonstrate monitoring capabilities."""
        self.logger.info("Demonstrating monitoring capabilities...")

        if not self.dashboard:
            self.logger.warning("Dashboard not initialized")
            return

        # Refresh dashboard data
        await self.dashboard.refresh_dashboard_data()

        # Get dashboard summary
        summary = self.dashboard.get_dashboard_summary()
        self.logger.info(f"Dashboard summary: {summary}")

        # Get circuit breaker status
        cb_status = self.dashboard.get_circuit_breaker_status()
        self.logger.info(f"Circuit breaker status: {cb_status}")

        # Get alerts
        alerts = self.dashboard.get_alerts()
        if alerts:
            self.logger.info(f"Active alerts: {len(alerts)}")
            for alert in alerts:
                self.logger.info(f"  - {alert['type']}: {alert['message']}")
        else:
            self.logger.info("No active alerts")

    async def run_comprehensive_demo(self):
        """Run comprehensive demonstration of all features."""
        self.logger.info("Starting comprehensive error handling demonstration...")

        # Initialize all components
        await self.initialize_components()

        # Demonstrate different operations
        await self.demonstrate_github_api_operations()
        await asyncio.sleep(1)

        await self.demonstrate_monitoring()

        self.logger.info("Comprehensive demonstration completed")


async def main():
    """Main function to run the demonstration."""
    example = AdvancedErrorHandlingExample()
    await example.run_comprehensive_demo()


if __name__ == "__main__":
    asyncio.run(main())
