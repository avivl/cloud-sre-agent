"""Audit logging system for all provider interactions."""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AuditEventType(str, Enum):
    """Types of audit events."""

    PROVIDER_REQUEST = "provider_request"
    PROVIDER_RESPONSE = "provider_response"
    PROVIDER_ERROR = "provider_error"
    CONFIG_CHANGE = "config_change"
    KEY_ROTATION = "key_rotation"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    DATA_EXPORT = "data_export"
    DATA_DELETION = "data_deletion"
    COMPLIANCE_CHECK = "compliance_check"


class AuditEvent(BaseModel):
    """Audit event model."""

    event_id: str = Field(..., description="Unique event identifier")
    event_type: AuditEventType = Field(..., description="Type of audit event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: Optional[str] = Field(
        default=None, description="User who triggered the event"
    )
    session_id: Optional[str] = Field(default=None, description="Session identifier")
    provider: Optional[str] = Field(default=None, description="Provider involved")
    model: Optional[str] = Field(default=None, description="Model used")
    request_id: Optional[str] = Field(default=None, description="Request identifier")
    success: bool = Field(default=True, description="Whether the operation succeeded")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    ip_address: Optional[str] = Field(default=None, description="Client IP address")
    user_agent: Optional[str] = Field(default=None, description="Client user agent")


class AuditLogger:
    """Audit logger for tracking all system interactions."""

    def __init__(
        self,
        log_file: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        backup_count: int = 5,
        enable_console: bool = False,
    ):
        """Initialize the audit logger.

        Args:
            log_file: Path to audit log file
            max_file_size: Maximum size of log file before rotation
            backup_count: Number of backup files to keep
            enable_console: Whether to also log to console
        """
        self.log_file = log_file
        self.max_file_size = max_file_size
        self.backup_count = backup_count
        self.enable_console = enable_console

        # Initialize logger
        self.logger = logging.getLogger("audit")
        self.logger.setLevel(logging.INFO)

        # Clear existing handlers
        self.logger.handlers.clear()

        # Add file handler if specified
        if self.log_file:
            from logging.handlers import RotatingFileHandler

            file_handler = RotatingFileHandler(
                self.log_file,
                maxBytes=self.max_file_size,
                backupCount=self.backup_count,
            )
            file_handler.setLevel(logging.INFO)
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

        # Add console handler if enabled
        if self.enable_console:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # In-memory buffer for recent events
        self._event_buffer: List[AuditEvent] = []
        self._buffer_size = 1000

    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        request_id: Optional[str] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Log an audit event.

        Args:
            event_type: Type of event to log
            user_id: User who triggered the event
            session_id: Session identifier
            provider: Provider involved
            model: Model used
            request_id: Request identifier
            success: Whether the operation succeeded
            error_message: Error message if failed
            metadata: Additional metadata
            ip_address: Client IP address
            user_agent: Client user agent

        Returns:
            Event ID
        """
        import uuid

        event_id = str(uuid.uuid4())
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            provider=provider,
            model=model,
            request_id=request_id,
            success=success,
            error_message=error_message,
            metadata=metadata or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # Add to buffer
        self._event_buffer.append(event)
        if len(self._event_buffer) > self._buffer_size:
            self._event_buffer.pop(0)

        # Log the event
        await self._write_event(event)

        return event_id

    async def _write_event(self, event: AuditEvent) -> None:
        """Write an audit event to the log."""
        try:
            # Convert to JSON for structured logging
            event_data = event.dict()
            event_json = json.dumps(event_data, default=str)

            # Log with appropriate level
            if event.success:
                self.logger.info(f"AUDIT: {event_json}")
            else:
                self.logger.error(f"AUDIT_ERROR: {event_json}")

        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")

    async def log_provider_request(
        self,
        provider: str,
        model: str,
        request_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Log a provider request."""
        return await self.log_event(
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider=provider,
            model=model,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

    async def log_provider_response(
        self,
        provider: str,
        model: str,
        request_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log a provider response."""
        return await self.log_event(
            event_type=AuditEventType.PROVIDER_RESPONSE,
            provider=provider,
            model=model,
            request_id=request_id,
            success=success,
            error_message=error_message,
            metadata=metadata,
            user_id=user_id,
            session_id=session_id,
        )

    async def log_config_change(
        self,
        change_type: str,
        old_value: Any,
        new_value: Any,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log a configuration change."""
        metadata = {
            "change_type": change_type,
            "old_value": str(old_value),
            "new_value": str(new_value),
        }

        return await self.log_event(
            event_type=AuditEventType.CONFIG_CHANGE,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
        )

    async def log_key_rotation(
        self,
        provider: str,
        key_id: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """Log a key rotation event."""
        metadata = {
            "key_id": key_id,
            "provider": provider,
        }

        return await self.log_event(
            event_type=AuditEventType.KEY_ROTATION,
            provider=provider,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
        )

    async def log_access_attempt(
        self,
        resource: str,
        action: str,
        granted: bool,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> str:
        """Log an access attempt."""
        event_type = (
            AuditEventType.ACCESS_GRANTED if granted else AuditEventType.ACCESS_DENIED
        )

        metadata = {
            "resource": resource,
            "action": action,
        }

        return await self.log_event(
            event_type=event_type,
            user_id=user_id,
            session_id=session_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
            success=granted,
        )

    def get_recent_events(
        self,
        event_type: Optional[AuditEventType] = None,
        provider: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AuditEvent]:
        """Get recent audit events from the buffer."""
        events = self._event_buffer.copy()

        # Apply filters
        if event_type:
            events = [e for e in events if e.event_type == event_type]
        if provider:
            events = [e for e in events if e.provider == provider]
        if user_id:
            events = [e for e in events if e.user_id == user_id]

        # Sort by timestamp (newest first)
        events.sort(key=lambda e: e.timestamp, reverse=True)

        return events[:limit]

    async def export_events(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[List[AuditEventType]] = None,
        providers: Optional[List[str]] = None,
        user_ids: Optional[List[str]] = None,
    ) -> List[AuditEvent]:
        """Export audit events for compliance reporting.

        Note: This is a simplified implementation. In production, this would
        query a proper audit database or log aggregation system.
        """
        events = self._event_buffer.copy()

        # Apply time filter
        if start_time:
            events = [e for e in events if e.timestamp >= start_time]
        if end_time:
            events = [e for e in events if e.timestamp <= end_time]

        # Apply other filters
        if event_types:
            events = [e for e in events if e.event_type in event_types]
        if providers:
            events = [e for e in events if e.provider in providers]
        if user_ids:
            events = [e for e in events if e.user_id in user_ids]

        # Sort by timestamp
        events.sort(key=lambda e: e.timestamp)

        return events

    def get_statistics(self) -> Dict[str, Any]:
        """Get audit log statistics."""
        if not self._event_buffer:
            return {}

        total_events = len(self._event_buffer)
        success_count = sum(1 for e in self._event_buffer if e.success)
        error_count = total_events - success_count

        # Count by event type
        event_type_counts = {}
        for event in self._event_buffer:
            event_type_counts[event.event_type] = (
                event_type_counts.get(event.event_type, 0) + 1
            )

        # Count by provider
        provider_counts = {}
        for event in self._event_buffer:
            if event.provider:
                provider_counts[event.provider] = (
                    provider_counts.get(event.provider, 0) + 1
                )

        return {
            "total_events": total_events,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": success_count / total_events if total_events > 0 else 0,
            "event_type_counts": event_type_counts,
            "provider_counts": provider_counts,
            "oldest_event": min(e.timestamp for e in self._event_buffer),
            "newest_event": max(e.timestamp for e in self._event_buffer),
        }
