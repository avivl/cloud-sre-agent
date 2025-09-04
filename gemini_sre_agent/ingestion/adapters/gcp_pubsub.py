# gemini_sre_agent/ingestion/adapters/gcp_pubsub.py

"""
Google Cloud Pub/Sub adapter for log ingestion.

This adapter implements the LogIngestionInterface for consuming logs
from Google Cloud Pub/Sub subscriptions.
"""

import json
import logging
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

from ...config.ingestion_config import GCPPubSubConfig
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

logger = logging.getLogger(__name__)


class GCPPubSubAdapter(LogIngestionInterface):
    """Adapter for Google Cloud Pub/Sub log consumption."""

    def __init__(self, config: GCPPubSubConfig):
        self.config = config
        self.project_id = config.project_id
        self.subscription_id = config.subscription_id
        self.credentials_path = config.credentials_path
        self.max_messages = config.max_messages
        self.ack_deadline_seconds = config.ack_deadline_seconds
        self.flow_control_max_messages = config.flow_control_max_messages
        self.flow_control_max_bytes = config.flow_control_max_bytes

        # Initialize resilience client
        resilience_config = create_resilience_config()
        self.resilient_client = HyxResilientClient(resilience_config)

        # State management
        self._is_running = False
        self._subscriber_client = None
        self._subscription_path = None

        # Health tracking
        self._last_health_check = datetime.now()
        self._consecutive_failures = 0
        self._total_messages_processed = 0
        self._total_messages_failed = 0

    async def start(self) -> None:
        """Start the Pub/Sub consumer."""
        if self._is_running:
            return

        try:
            # Import here to avoid dependency issues if not installed
            from google.cloud import pubsub_v1

            # Initialize subscriber client
            if self.credentials_path:
                self._subscriber_client = (
                    pubsub_v1.SubscriberClient.from_service_account_file(
                        self.credentials_path
                    )
                )
            else:
                self._subscriber_client = pubsub_v1.SubscriberClient()

            # Create subscription path
            self._subscription_path = self._subscriber_client.subscription_path(
                self.project_id, self.subscription_id
            )

            self._is_running = True

        except Exception as e:
            raise SourceConnectionError(f"Failed to start Pub/Sub adapter: {e}") from e

    async def stop(self) -> None:
        """Stop the Pub/Sub consumer."""
        self._is_running = False
        if self._subscriber_client:
            # Close the client
            self._subscriber_client.close()
            self._subscriber_client = None

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from Pub/Sub subscription."""
        if not self._is_running:
            raise SourceNotRunningError("Pub/Sub adapter is not running")

        if not self._subscriber_client:
            raise SourceConnectionError("Pub/Sub client not initialized")

        try:
            # Configure flow control
            flow_control = pubsub_v1.types.FlowControl(
                max_messages=self.flow_control_max_messages,
                max_bytes=self.flow_control_max_bytes,
            )

            # Pull messages with resilience
            async def _pull_messages():
                response = self._subscriber_client.pull(
                    request={
                        "subscription": self._subscription_path,
                        "max_messages": self.max_messages,
                    },
                    flow_control=flow_control,
                    timeout=self.ack_deadline_seconds,
                )
                return response.received_messages

            messages = await self.resilient_client.execute(_pull_messages)

            for message in messages:
                try:
                    # Parse message data
                    log_data = self._parse_message(message)
                    if log_data:
                        self._total_messages_processed += 1
                        yield log_data

                        # Acknowledge the message
                        self._subscriber_client.acknowledge(
                            request={
                                "subscription": self._subscription_path,
                                "ack_ids": [message.ack_id],
                            }
                        )

                except Exception as e:
                    self._total_messages_failed += 1
                    self._consecutive_failures += 1
                    raise LogParsingError(
                        f"Failed to parse Pub/Sub message: {e}"
                    ) from e

            # Reset failure count on successful processing
            self._consecutive_failures = 0

        except Exception as e:
            self._consecutive_failures += 1
            raise SourceConnectionError(f"Failed to get logs from Pub/Sub: {e}") from e

    def _parse_message(self, message) -> Optional[LogEntry]:
        """Parse a Pub/Sub message into a LogEntry."""
        try:
            # Try to parse as JSON first
            try:
                data = json.loads(message.data.decode("utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError):
                # Fall back to raw text
                data = {"message": message.data.decode("utf-8", errors="replace")}

            # Extract log fields
            message_text = data.get("message", "")
            timestamp_str = (
                data.get("timestamp") or data.get("time") or data.get("@timestamp")
            )
            severity_str = (
                data.get("severity") or data.get("level") or data.get("log_level")
            )
            source = data.get("source") or data.get("service") or "pubsub"

            # Parse timestamp
            if timestamp_str:
                try:
                    if isinstance(timestamp_str, str):
                        # Try common timestamp formats
                        for fmt in [
                            "%Y-%m-%dT%H:%M:%S.%fZ",
                            "%Y-%m-%dT%H:%M:%SZ",
                            "%Y-%m-%d %H:%M:%S",
                        ]:
                            try:
                                timestamp = datetime.strptime(timestamp_str, fmt)
                                break
                            except ValueError:
                                continue
                        else:
                            timestamp = datetime.now()
                    else:
                        timestamp = datetime.now()
                except Exception:
                    timestamp = datetime.now()
            else:
                timestamp = datetime.now()

            # Parse severity
            if severity_str:
                try:
                    severity = LogSeverity(severity_str.upper())
                except ValueError:
                    severity = LogSeverity.INFO
            else:
                severity = LogSeverity.INFO

            # Create log entry
            return LogEntry(
                id=message.message_id or f"pubsub-{timestamp.isoformat()}",
                message=message_text,
                timestamp=timestamp,
                severity=severity,
                source=source,
                metadata={
                    "subscription": self.subscription_id,
                    "message_id": message.message_id,
                    "publish_time": (
                        message.publish_time.isoformat()
                        if message.publish_time
                        else None
                    ),
                    "attributes": (
                        dict(message.attributes) if message.attributes else {}
                    ),
                    "raw_data": data,
                },
            )

        except Exception as e:
            raise LogParsingError(f"Failed to parse message: {e}") from e

    async def get_health(self) -> SourceHealth:
        """Get health status of the Pub/Sub adapter."""
        current_time = datetime.now()

        # Calculate health metrics
        total_messages = self._total_messages_processed + self._total_messages_failed
        error_rate = self._total_messages_failed / max(total_messages, 1)

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
                "total_processed": self._total_messages_processed,
                "total_failed": self._total_messages_failed,
                "error_rate": error_rate,
                "subscription": self.subscription_id,
                "project_id": self.project_id,
                "is_running": self._is_running,
                "resilience_stats": self.resilient_client.get_health_stats(),
            },
        )

    def get_config(self) -> SourceConfig:
        """Get adapter configuration."""
        return self.config  # type: ignore

    async def health_check(self) -> SourceHealth:
        """Check the health status of the GCP Pub/Sub source."""
        return await self.get_health()

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration for this source."""
        if isinstance(config, GCPPubSubConfig):
            self.config = config
            self.project_id = config.project_id
            self.subscription_id = config.subscription_id
            self.credentials_path = config.credentials_path
            self.max_messages = config.max_messages
            self.ack_deadline_seconds = config.ack_deadline_seconds
            self.flow_control_max_messages = config.flow_control_max_messages
            self.flow_control_max_bytes = config.flow_control_max_bytes
        else:
            raise ValueError("Config must be GCPPubSubConfig")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors with context. Return True if recoverable."""
        logger.error(f"GCP Pub/Sub adapter error: {error} in context: {context}")
        self._consecutive_failures += 1

        # Consider GCP API errors as potentially recoverable
        if hasattr(error, "code") and error.code in [429, 500, 502, 503, 504]:
            return True
        return False

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health and performance metrics."""
        return {
            "is_running": self._is_running,
            "consecutive_failures": self._consecutive_failures,
            "total_messages_processed": self._total_messages_processed,
            "total_messages_failed": self._total_messages_failed,
            "subscription": self.subscription_id,
            "project_id": self.project_id,
            "resilience_stats": self.resilient_client.get_health_stats(),
        }
