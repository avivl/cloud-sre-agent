# gemini_sre_agent/ingestion/adapters/gcp_logging.py

"""
Google Cloud Logging adapter for log ingestion.

This adapter implements the LogIngestionInterface for consuming logs
from Google Cloud Logging API.
"""

import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Dict, Any, Optional

logger = logging.getLogger(__name__)

from ...config.ingestion_config import GCPLoggingConfig
from ..interfaces.core import (
    LogEntry,
    LogIngestionInterface,
    LogSeverity,
    SourceConfig,
    SourceHealth,
)
from ..interfaces.errors import (
    LogParsingError,
    SourceConnectionError,
    SourceNotRunningError,
)
from ..interfaces.resilience import HyxResilientClient, create_resilience_config


class GCPLoggingAdapter(LogIngestionInterface):
    """Adapter for Google Cloud Logging API log consumption."""

    def __init__(self, config: GCPLoggingConfig):
        self.config = config
        self.project_id = config.project_id
        self.log_filter = config.log_filter
        self.credentials_path = config.credentials_path
        self.poll_interval = config.poll_interval
        self.max_results = config.max_results

        # Initialize resilience client
        resilience_config = create_resilience_config()
        self.resilient_client = HyxResilientClient(resilience_config)

        # State management
        self._is_running = False
        self._logging_client = None
        self._last_poll_time = None

        # Health tracking
        self._last_health_check = datetime.now()
        self._consecutive_failures = 0
        self._total_logs_processed = 0
        self._total_logs_failed = 0

    async def start(self) -> None:
        """Start the Cloud Logging consumer."""
        if self._is_running:
            return

        try:
            # Import here to avoid dependency issues if not installed
            from google.cloud import logging_v2

            # Initialize logging client
            if self.credentials_path:
                self._logging_client = logging_v2.Client.from_service_account_file(
                    self.credentials_path
                )
            else:
                self._logging_client = logging_v2.Client()

            self._is_running = True
            self._last_poll_time = datetime.now() - timedelta(
                seconds=self.poll_interval
            )

        except Exception as e:
            raise SourceConnectionError(
                f"Failed to start Cloud Logging adapter: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the Cloud Logging consumer."""
        self._is_running = False
        if self._logging_client:
            # Close the client
            self._logging_client.close()
            self._logging_client = None

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from Cloud Logging API."""
        if not self._is_running:
            raise SourceNotRunningError("Cloud Logging adapter is not running")

        if not self._logging_client:
            raise SourceConnectionError("Cloud Logging client not initialized")

        try:
            # Calculate time range for polling
            current_time = datetime.now()
            start_time = self._last_poll_time or (
                current_time - timedelta(seconds=self.poll_interval)
            )

            # Build filter with time range
            time_filter = f'timestamp>="{start_time.isoformat()}Z" timestamp<="{current_time.isoformat()}Z"'
            full_filter = f"{self.log_filter} AND {time_filter}"

            # Fetch logs with resilience
            async def _fetch_logs():
                entries = self._logging_client.list_entries(
                    filter_=full_filter,
                    max_results=self.max_results,
                    order_by=logging_v2.DESCENDING,
                )
                return list(entries)

            entries = await self.resilient_client.execute(_fetch_logs)

            for entry in entries:
                try:
                    # Parse log entry
                    log_data = self._parse_log_entry(entry)
                    if log_data:
                        self._total_logs_processed += 1
                        yield log_data

                except Exception as e:
                    self._total_logs_failed += 1
                    self._consecutive_failures += 1
                    raise LogParsingError(
                        f"Failed to parse Cloud Logging entry: {e}"
                    ) from e

            # Update last poll time
            self._last_poll_time = current_time

            # Reset failure count on successful processing
            self._consecutive_failures = 0

        except Exception as e:
            self._consecutive_failures += 1
            raise SourceConnectionError(
                f"Failed to get logs from Cloud Logging: {e}"
            ) from e

    def _parse_log_entry(self, entry) -> Optional[LogEntry]:
        """Parse a Cloud Logging entry into a LogEntry."""
        try:
            # Extract basic fields
            message = (
                entry.payload.get("message", "")
                if hasattr(entry.payload, "get")
                else str(entry.payload)
            )
            timestamp = entry.timestamp
            severity = entry.severity
            source = entry.resource.type if entry.resource else "cloud-logging"

            # Parse severity
            if severity:
                try:
                    severity_enum = LogSeverity(severity.name.upper())
                except (ValueError, AttributeError):
                    severity_enum = LogSeverity.INFO
            else:
                severity_enum = LogSeverity.INFO

            # Create log entry
            return LogEntry(
                id=entry.insert_id or f"gcp-log-{timestamp.isoformat()}",
                message=message,
                timestamp=timestamp,
                severity=severity_enum,
                source=source,
                metadata={
                    "log_name": entry.log_name,
                    "insert_id": entry.insert_id,
                    "labels": dict(entry.labels) if entry.labels else {},
                    "resource": {
                        "type": entry.resource.type if entry.resource else None,
                        "labels": (
                            dict(entry.resource.labels)
                            if entry.resource and entry.resource.labels
                            else {}
                        ),
                    },
                    "http_request": (
                        entry.http_request.__dict__ if entry.http_request else None
                    ),
                    "operation": entry.operation.__dict__ if entry.operation else None,
                    "source_location": (
                        entry.source_location.__dict__
                        if entry.source_location
                        else None
                    ),
                    "raw_payload": str(entry.payload),
                },
            )

        except Exception as e:
            raise LogParsingError(f"Failed to parse log entry: {e}") from e

    async def get_health(self) -> SourceHealth:
        """Get health status of the Cloud Logging adapter."""
        current_time = datetime.now()

        # Calculate health metrics
        total_logs = self._total_logs_processed + self._total_logs_failed
        error_rate = self._total_logs_failed / max(total_logs, 1)

        # Determine health status
        if not self._is_running:
            status = "unhealthy"
        elif self._consecutive_failures > 5:
            status = "unhealthy"
        elif error_rate > 0.1:  # 10% error rate
            status = "degraded"
        else:
            status = "healthy"

        return SourceHealth(
            is_healthy=(status == "healthy"),
            last_success=current_time.isoformat() if status == "healthy" else None,
            error_count=self._consecutive_failures,
            last_error=None if status == "healthy" else f"Status: {status}",
            metrics={
                "status": status,
                "last_check": current_time,
                "consecutive_failures": self._consecutive_failures,
                "total_processed": self._total_logs_processed,
                "total_failed": self._total_logs_failed,
                "error_rate": error_rate,
                "project_id": self.project_id,
                "log_filter": self.log_filter,
                "is_running": self._is_running,
                "last_poll_time": (
                    self._last_poll_time.isoformat() if self._last_poll_time else None
                ),
                "resilience_stats": self.resilient_client.get_health_stats(),
            },
        )

    def get_config(self) -> SourceConfig:
        """Get adapter configuration."""
        return self.config  # type: ignore

    async def health_check(self) -> SourceHealth:
        """Check the health status of the GCP logging source."""
        return await self.get_health()

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration for this source."""
        if isinstance(config, GCPLoggingConfig):
            self.config = config
            self.project_id = config.project_id
            self.log_filter = config.log_filter
            self.credentials_path = config.credentials_path
            self.poll_interval = config.poll_interval
            self.max_results = config.max_results
        else:
            raise ValueError("Config must be GCPLoggingConfig")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors with context. Return True if recoverable."""
        logger.error(f"GCP Logging adapter error: {error} in context: {context}")
        self._consecutive_failures += 1
        
        # Consider GCP API errors as potentially recoverable
        if hasattr(error, 'code') and error.code in [429, 500, 502, 503, 504]:
            return True
        return False

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health and performance metrics."""
        return {
            "is_running": self._is_running,
            "consecutive_failures": self._consecutive_failures,
            "total_logs_processed": self._total_logs_processed,
            "total_logs_failed": self._total_logs_failed,
            "last_poll_time": self._last_poll_time.isoformat() if self._last_poll_time else None,
            "project_id": self.project_id,
            "log_filter": self.log_filter,
            "resilience_stats": self.resilient_client.get_health_stats()
        }
