# gemini_sre_agent/ingestion/manager/log_manager.py

"""
LogManager orchestrates multiple log sources with health monitoring and failover.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from ..interfaces import (
    BackpressureManager,
    LogEntry,
    LogIngestionInterface,
    SourceAlreadyRunningError,
    SourceConfig,
    SourceHealth,
    SourceNotFoundError,
    SourceNotRunningError,
)

logger = logging.getLogger(__name__)


class LogManager:
    """Orchestrates multiple log sources with health monitoring and failover."""

    def __init__(self, callback: Optional[Callable[[LogEntry], None]] = None):
        self.sources: Dict[str, LogIngestionInterface] = {}
        self.source_configs: Dict[str, SourceConfig] = {}
        self.backpressure_manager = BackpressureManager()
        self.callback = callback
        self.running = False
        self.tasks: List[asyncio.Task] = []
        self.health_check_task: Optional[asyncio.Task] = None

    async def add_source(self, source: LogIngestionInterface) -> None:
        """Add a log source to the manager."""
        config = source.get_config()
        source_name = config.name

        if source_name in self.sources:
            raise ValueError(f"Source '{source_name}' already exists")

        self.sources[source_name] = source
        self.source_configs[source_name] = config
        # Circuit breaker functionality moved to individual adapters
        pass

        logger.info(f"Added source '{source_name}' of type {config.source_type.value}")

    async def remove_source(self, source_name: str) -> None:
        """Remove a log source from the manager."""
        if source_name not in self.sources:
            raise SourceNotFoundError(f"Source '{source_name}' not found")

        source = self.sources[source_name]
        if self.running:
            await source.stop()

        del self.sources[source_name]
        del self.source_configs[source_name]

        logger.info(f"Removed source '{source_name}'")

    async def start(self) -> None:
        """Start all enabled log sources."""
        if self.running:
            raise SourceAlreadyRunningError("LogManager is already running")

        self.running = True

        # Start enabled sources
        for source_name, source in self.sources.items():
            config = self.source_configs[source_name]
            if config.enabled:
                try:
                    await source.start()
                    # Start log processing task for this source
                    task = asyncio.create_task(self._process_source_logs(source_name))
                    self.tasks.append(task)
                    logger.info(f"Started source '{source_name}'")
                except Exception as e:
                    logger.error(f"Failed to start source '{source_name}': {e}")

        # Start health monitoring
        self.health_check_task = asyncio.create_task(self._health_monitor())

        logger.info("LogManager started")

    async def stop(self) -> None:
        """Stop all log sources gracefully."""
        if not self.running:
            raise SourceNotRunningError("LogManager is not running")

        self.running = False

        # Cancel all tasks
        for task in self.tasks:
            task.cancel()

        if self.health_check_task:
            self.health_check_task.cancel()

        # Stop all sources
        for source_name, source in self.sources.items():
            try:
                await source.stop()
                logger.info(f"Stopped source '{source_name}'")
            except Exception as e:
                logger.error(f"Error stopping source '{source_name}': {e}")

        # Wait for tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)

        if self.health_check_task:
            await asyncio.gather(self.health_check_task, return_exceptions=True)

        self.tasks.clear()
        self.health_check_task = None

        logger.info("LogManager stopped")

    async def _process_source_logs(self, source_name: str) -> None:
        """Process logs from a specific source."""
        source = self.sources[source_name]

        while self.running:
            try:
                # Get logs directly from source (resilience handled by source)
                log_iterator = await source.get_logs()
                async for log_entry in log_iterator:
                    # Check backpressure
                    if not await self.backpressure_manager.can_accept():
                        logger.warning(
                            f"Backpressure detected, dropping log from '{source_name}'"
                        )
                        continue

                    # Set source information
                    log_entry.source = source_name

                    # Process log entry
                    if self.callback:
                        try:
                            if asyncio.iscoroutinefunction(self.callback):
                                await self.callback(log_entry)
                            else:
                                self.callback(log_entry)
                        except Exception as e:
                            logger.error(
                                f"Error in callback for source '{source_name}': {e}"
                            )

                    # Update backpressure stats
                    await self.backpressure_manager.increment_queue()
                    await self.backpressure_manager.decrement_queue()

            except Exception as e:
                logger.error(f"Error processing logs from source '{source_name}': {e}")
                # Handle error through source's error handler
                try:
                    await source.handle_error(
                        e, {"source": source_name, "operation": "get_logs"}
                    )
                except Exception as handler_error:
                    logger.error(
                        f"Error handler failed for source '{source_name}': {handler_error}"
                    )

                # Wait before retrying
                await asyncio.sleep(1)

    async def _health_monitor(self) -> None:
        """Monitor health of all sources."""
        while self.running:
            for source_name, source in self.sources.items():
                try:
                    health = await source.health_check()
                    if not health.is_healthy:
                        logger.warning(
                            f"Source '{source_name}' is unhealthy: {health.last_error}"
                        )
                except Exception as e:
                    logger.error(f"Health check failed for source '{source_name}': {e}")

            # Wait before next health check
            await asyncio.sleep(30)

    async def get_health_status(self) -> Dict[str, SourceHealth]:
        """Get health status of all sources."""
        health_status = {}
        for source_name, source in self.sources.items():
            try:
                health = await source.health_check()
                health_status[source_name] = health
            except Exception as e:
                health_status[source_name] = SourceHealth(
                    is_healthy=False, last_error=str(e)
                )
        return health_status

    async def get_metrics(self) -> Dict[str, Any]:
        """Get comprehensive metrics for all sources."""
        metrics = {
            "sources": {},
            "backpressure": self.backpressure_manager.get_stats(),
            "circuit_breakers": {},
            "manager": {
                "running": self.running,
                "total_sources": len(self.sources),
                "enabled_sources": sum(
                    1 for config in self.source_configs.values() if config.enabled
                ),
            },
        }

        # Get metrics for each source
        for source_name, source in self.sources.items():
            try:
                source_metrics = await source.get_health_metrics()
                metrics["sources"][source_name] = source_metrics
            except Exception as e:
                metrics["sources"][source_name] = {"error": str(e)}

        # Circuit breaker states are now handled by individual sources
        # and can be accessed through their health metrics

        return metrics

    def get_source(self, source_name: str) -> LogIngestionInterface:
        """Get a specific source by name."""
        if source_name not in self.sources:
            raise SourceNotFoundError(f"Source '{source_name}' not found")
        return self.sources[source_name]

    def list_sources(self) -> List[str]:
        """List all source names."""
        return list(self.sources.keys())
