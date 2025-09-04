# gemini_sre_agent/ingestion/adapters/aws_cloudwatch.py

"""
AWS CloudWatch Logs adapter for log ingestion.
"""

import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict

from ...config.ingestion_config import AWSCloudWatchConfig
from ..interfaces.core import (
    LogEntry,
    LogIngestionInterface,
    LogSeverity,
    SourceConfig,
    SourceHealth,
)
from ..interfaces.errors import SourceConnectionError

logger = logging.getLogger(__name__)

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    AWS_AVAILABLE = True
except ImportError:
    AWS_AVAILABLE = False
    boto3 = None
    ClientError = Exception
    NoCredentialsError = Exception


class AWSCloudWatchAdapter(LogIngestionInterface):
    """Adapter for AWS CloudWatch Logs."""

    def __init__(self, config: AWSCloudWatchConfig):
        if not AWS_AVAILABLE:
            raise ImportError("boto3 is required for AWS CloudWatch adapter")

        self.config = config
        self.client = None
        self.running = False
        self._last_check_time = None
        self._error_count = 0
        self._last_error = None

    async def start(self) -> None:
        """Start the AWS CloudWatch adapter."""
        try:
            # Initialize AWS client
            session_kwargs = {}
            if self.config.credentials_profile:
                session_kwargs["profile_name"] = self.config.credentials_profile

            if boto3 is None:
                raise SourceConnectionError("boto3 not available")
            session = boto3.Session(**session_kwargs)
            self.client = session.client("logs", region_name=self.config.region)

            # Test connection
            await self._test_connection()

            self.running = True
            self._last_check_time = datetime.now(timezone.utc)
            logger.info(
                f"Started AWS CloudWatch adapter for log group: {self.config.log_group_name}"
            )

        except Exception as e:
            logger.error(f"Failed to start AWS CloudWatch adapter: {e}")
            raise SourceConnectionError(
                f"Failed to start AWS CloudWatch adapter: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the AWS CloudWatch adapter."""
        self.running = False
        self.client = None
        logger.info("Stopped AWS CloudWatch adapter")

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from AWS CloudWatch."""
        if not self.running or not self.client:
            raise SourceConnectionError("AWS CloudWatch adapter is not running")

        try:
            # Get log streams
            streams = await self._get_log_streams()

            for stream_name in streams:
                try:
                    # Get log events from stream
                    events = await self._get_log_events(stream_name)

                    for event in events:
                        if not self.running:
                            break

                        # Convert CloudWatch event to LogEntry
                        log_entry = self._convert_to_log_entry(event, stream_name)
                        yield log_entry

                except Exception as e:
                    logger.error(f"Error processing stream {stream_name}: {e}")
                    self._error_count += 1
                    self._last_error = str(e)
                    continue

        except Exception as e:
            logger.error(f"Error getting logs from CloudWatch: {e}")
            self._error_count += 1
            self._last_error = str(e)
            raise SourceConnectionError(
                f"Failed to get logs from CloudWatch: {e}"
            ) from e

    async def health_check(self) -> SourceHealth:
        """Check the health of the AWS CloudWatch adapter."""
        try:
            if not self.running or not self.client:
                return SourceHealth(
                    is_healthy=False,
                    last_success=None,
                    error_count=self._error_count,
                    last_error="Adapter not running",
                    metrics={"status": "stopped"},
                )

            # Test connection
            await self._test_connection()

            return SourceHealth(
                is_healthy=True,
                last_success=datetime.now(timezone.utc).isoformat(),
                error_count=self._error_count,
                last_error=self._last_error,
                metrics={
                    "log_group": self.config.log_group_name,
                    "region": self.config.region,
                    "last_check": (
                        self._last_check_time.isoformat()
                        if self._last_check_time
                        else None
                    ),
                },
            )

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            return SourceHealth(
                is_healthy=False,
                last_success=None,
                error_count=self._error_count,
                last_error=str(e),
                metrics={"status": "error"},
            )

    def get_config(self) -> SourceConfig:
        """Get the current configuration."""
        return self.config  # type: ignore

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration."""
        if isinstance(config, AWSCloudWatchConfig):
            self.config = config
            # Restart if running
            if self.running:
                await self.stop()
                await self.start()
        else:
            raise ValueError("Invalid config type for AWS CloudWatch adapter")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors from the adapter."""
        logger.error(
            f"AWS CloudWatch error in {context.get('operation', 'unknown')}: {error}"
        )
        self._error_count += 1
        self._last_error = str(error)

        # Return True if error should be retried
        if isinstance(error, (ClientError, NoCredentialsError)):
            return False  # Don't retry credential/connection errors
        return True

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health metrics."""
        return {
            "log_group_name": self.config.log_group_name,
            "log_stream_name": self.config.log_stream_name,
            "region": self.config.region,
            "running": self.running,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "aws_available": AWS_AVAILABLE,
        }

    async def _test_connection(self) -> None:
        """Test the AWS CloudWatch connection."""
        if self.client is None:
            raise SourceConnectionError("AWS client not initialized")
            
        try:
            # Try to describe log groups
            self.client.describe_log_groups(
                logGroupNamePrefix=self.config.log_group_name, limit=1
            )
        except ClientError as e:
            if hasattr(e, "response") and getattr(e, "response", {}).get("Error", {}).get("Code") == "ResourceNotFoundException":
                # Log group doesn't exist, but connection is working
                pass
            else:
                raise
        except NoCredentialsError as e:
            raise SourceConnectionError("AWS credentials not found") from e

    async def _get_log_streams(self) -> list[str]:
        """Get list of log streams."""
        try:
            kwargs = {
                "logGroupName": self.config.log_group_name,
                "orderBy": "LastEventTime",
                "descending": True,
                "limit": 10,  # Limit to recent streams
            }

            if self.config.log_stream_name:
                kwargs["logStreamNamePrefix"] = self.config.log_stream_name

            if self.client is None:
                return []
            response = self.client.describe_log_streams(**kwargs)
            return [
                stream["logStreamName"] for stream in response.get("logStreams", [])
            ]

        except ClientError as e:
            logger.error(f"Error getting log streams: {e}")
            return []

    async def _get_log_events(self, stream_name: str) -> list[Dict[str, Any]]:
        """Get log events from a specific stream."""
        try:
            kwargs = {
                "logGroupName": self.config.log_group_name,
                "logStreamName": stream_name,
                "limit": self.config.max_events,
            }

            # Add start time if we have a last check time
            if self._last_check_time:
                kwargs["startTime"] = int(self._last_check_time.timestamp() * 1000)

            if self.client is None:
                return []
            response = self.client.get_log_events(**kwargs)
            return response.get("events", [])

        except ClientError as e:
            logger.error(f"Error getting log events from {stream_name}: {e}")
            return []

    def _convert_to_log_entry(
        self, event: Dict[str, Any], stream_name: str
    ) -> LogEntry:
        """Convert CloudWatch log event to LogEntry."""
        # Extract timestamp
        timestamp = datetime.fromtimestamp(event["timestamp"] / 1000, tz=timezone.utc)

        # Extract message
        message = event.get("message", "")

        # Try to parse severity from message
        severity = LogSeverity.INFO
        message_upper = message.upper()
        if "ERROR" in message_upper or "FATAL" in message_upper:
            severity = LogSeverity.ERROR
        elif "WARN" in message_upper or "WARNING" in message_upper:
            severity = LogSeverity.WARN
        elif "DEBUG" in message_upper:
            severity = LogSeverity.DEBUG
        elif "CRITICAL" in message_upper:
            severity = LogSeverity.CRITICAL

        # Generate unique ID
        log_id = f"aws-cw-{stream_name}-{event['timestamp']}-{hash(message) % 10000}"

        return LogEntry(
            id=log_id,
            timestamp=timestamp,
            message=message,
            source=f"aws-cloudwatch-{self.config.log_group_name}",
            severity=severity,
            metadata={
                "log_group": self.config.log_group_name,
                "log_stream": stream_name,
                "aws_region": self.config.region,
                "event_id": event.get("eventId", ""),
                "ingestion_time": event.get("ingestionTime", 0),
            },
        )
