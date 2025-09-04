"""Tests for AuditLogger."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.security.audit_logger import (
    AuditEvent,
    AuditEventType,
    AuditLogger,
)


@pytest.fixture
def audit_logger():
    """Create an AuditLogger instance."""
    return AuditLogger(enable_console=True)


@pytest.fixture
def sample_audit_event():
    """Create a sample audit event."""
    return AuditEvent(
        event_id="test-event-123",
        event_type=AuditEventType.PROVIDER_REQUEST,
        user_id="user123",
        provider="gemini",
        model="gemini-pro",
        request_id="req-456",
        success=True,
        metadata={"test": "data"},
    )


class TestAuditLogger:
    """Test cases for AuditLogger."""

    def test_initialization(self):
        """Test AuditLogger initialization."""
        logger = AuditLogger()
        assert logger.log_file is None
        assert logger.max_file_size == 100 * 1024 * 1024
        assert logger.backup_count == 5
        assert logger.enable_console is False

    def test_initialization_with_params(self):
        """Test AuditLogger initialization with parameters."""
        logger = AuditLogger(
            log_file="/tmp/audit.log",
            max_file_size=50 * 1024 * 1024,
            backup_count=3,
            enable_console=True,
        )
        assert logger.log_file == "/tmp/audit.log"
        assert logger.max_file_size == 50 * 1024 * 1024
        assert logger.backup_count == 3
        assert logger.enable_console is True

    @pytest.mark.asyncio
    async def test_log_event(self, audit_logger):
        """Test logging an audit event."""
        with patch.object(
            audit_logger, "_write_event", new_callable=MagicMock
        ) as mock_write:
            event_id = await audit_logger.log_event(
                event_type=AuditEventType.PROVIDER_REQUEST,
                user_id="user123",
                provider="gemini",
                model="gemini-pro",
                request_id="req-456",
                success=True,
                metadata={"test": "data"},
            )

            assert event_id is not None
            assert len(event_id) > 0
            mock_write.assert_called_once()

            # Check that event was added to buffer
            assert len(audit_logger._event_buffer) == 1
            event = audit_logger._event_buffer[0]
            assert event.event_type == AuditEventType.PROVIDER_REQUEST
            assert event.user_id == "user123"
            assert event.provider == "gemini"

    @pytest.mark.asyncio
    async def test_log_provider_request(self, audit_logger):
        """Test logging a provider request."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_provider_request(
                provider="gemini",
                model="gemini-pro",
                request_id="req-456",
                user_id="user123",
                metadata={"test": "data"},
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.PROVIDER_REQUEST,
                provider="gemini",
                model="gemini-pro",
                request_id="req-456",
                user_id="user123",
                session_id=None,
                metadata={"test": "data"},
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_log_provider_response(self, audit_logger):
        """Test logging a provider response."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_provider_response(
                provider="gemini",
                model="gemini-pro",
                request_id="req-456",
                success=True,
                error_message=None,
                metadata={"test": "data"},
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.PROVIDER_RESPONSE,
                provider="gemini",
                model="gemini-pro",
                request_id="req-456",
                success=True,
                error_message=None,
                metadata={"test": "data"},
                user_id=None,
                session_id=None,
            )

    @pytest.mark.asyncio
    async def test_log_config_change(self, audit_logger):
        """Test logging a configuration change."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_config_change(
                change_type="model_update",
                old_value="gemini-pro",
                new_value="gemini-pro-vision",
                user_id="user123",
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.CONFIG_CHANGE,
                user_id="user123",
                session_id=None,
                provider=None,
                model=None,
                request_id=None,
                success=True,
                error_message=None,
                metadata={
                    "change_type": "model_update",
                    "old_value": "gemini-pro",
                    "new_value": "gemini-pro-vision",
                },
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_log_key_rotation(self, audit_logger):
        """Test logging a key rotation event."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_key_rotation(
                provider="gemini",
                key_id="key-123",
                user_id="user123",
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.KEY_ROTATION,
                provider="gemini",
                user_id="user123",
                session_id=None,
                model=None,
                request_id=None,
                success=True,
                error_message=None,
                metadata={
                    "key_id": "key-123",
                    "provider": "gemini",
                },
                ip_address=None,
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_log_access_attempt_granted(self, audit_logger):
        """Test logging a granted access attempt."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_access_attempt(
                resource="config",
                action="read",
                granted=True,
                user_id="user123",
                ip_address="192.168.1.1",
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.ACCESS_GRANTED,
                user_id="user123",
                session_id=None,
                provider=None,
                model=None,
                request_id=None,
                success=True,
                error_message=None,
                metadata={
                    "resource": "config",
                    "action": "read",
                },
                ip_address="192.168.1.1",
                user_agent=None,
            )

    @pytest.mark.asyncio
    async def test_log_access_attempt_denied(self, audit_logger):
        """Test logging a denied access attempt."""
        with patch.object(
            audit_logger, "log_event", new_callable=MagicMock
        ) as mock_log:
            await audit_logger.log_access_attempt(
                resource="config",
                action="write",
                granted=False,
                user_id="user123",
            )

            mock_log.assert_called_once_with(
                event_type=AuditEventType.ACCESS_DENIED,
                user_id="user123",
                session_id=None,
                provider=None,
                model=None,
                request_id=None,
                success=False,
                error_message=None,
                metadata={
                    "resource": "config",
                    "action": "write",
                },
                ip_address=None,
                user_agent=None,
            )

    def test_get_recent_events(self, audit_logger):
        """Test getting recent events from buffer."""
        # Add some test events
        event1 = AuditEvent(
            event_id="event1",
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider="gemini",
            user_id="user1",
        )
        event2 = AuditEvent(
            event_id="event2",
            event_type=AuditEventType.PROVIDER_RESPONSE,
            provider="openai",
            user_id="user2",
        )
        event3 = AuditEvent(
            event_id="event3",
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider="gemini",
            user_id="user1",
        )

        audit_logger._event_buffer = [event1, event2, event3]

        # Get all events
        all_events = audit_logger.get_recent_events()
        assert len(all_events) == 3

        # Filter by event type
        request_events = audit_logger.get_recent_events(
            event_type=AuditEventType.PROVIDER_REQUEST
        )
        assert len(request_events) == 2
        assert all(
            e.event_type == AuditEventType.PROVIDER_REQUEST for e in request_events
        )

        # Filter by provider
        gemini_events = audit_logger.get_recent_events(provider="gemini")
        assert len(gemini_events) == 2
        assert all(e.provider == "gemini" for e in gemini_events)

        # Filter by user
        user1_events = audit_logger.get_recent_events(user_id="user1")
        assert len(user1_events) == 2
        assert all(e.user_id == "user1" for e in user1_events)

        # Test limit
        limited_events = audit_logger.get_recent_events(limit=2)
        assert len(limited_events) == 2

    @pytest.mark.asyncio
    async def test_export_events(self, audit_logger):
        """Test exporting events for compliance."""
        # Add some test events
        event1 = AuditEvent(
            event_id="event1",
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider="gemini",
            user_id="user1",
            timestamp=datetime(2023, 1, 1, 12, 0, 0),
        )
        event2 = AuditEvent(
            event_id="event2",
            event_type=AuditEventType.PROVIDER_RESPONSE,
            provider="openai",
            user_id="user2",
            timestamp=datetime(2023, 1, 2, 12, 0, 0),
        )

        audit_logger._event_buffer = [event1, event2]

        # Export all events
        all_events = await audit_logger.export_events()
        assert len(all_events) == 2

        # Export with time filter
        start_time = datetime(2023, 1, 1, 11, 0, 0)
        end_time = datetime(2023, 1, 1, 13, 0, 0)
        filtered_events = await audit_logger.export_events(
            start_time=start_time,
            end_time=end_time,
        )
        assert len(filtered_events) == 1
        assert filtered_events[0].event_id == "event1"

        # Export with event type filter
        request_events = await audit_logger.export_events(
            event_types=[AuditEventType.PROVIDER_REQUEST],
        )
        assert len(request_events) == 1
        assert request_events[0].event_type == AuditEventType.PROVIDER_REQUEST

        # Export with provider filter
        gemini_events = await audit_logger.export_events(
            providers=["gemini"],
        )
        assert len(gemini_events) == 1
        assert gemini_events[0].provider == "gemini"

    def test_get_statistics(self, audit_logger):
        """Test getting audit log statistics."""
        # Add some test events
        event1 = AuditEvent(
            event_id="event1",
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider="gemini",
            success=True,
        )
        event2 = AuditEvent(
            event_id="event2",
            event_type=AuditEventType.PROVIDER_RESPONSE,
            provider="openai",
            success=False,
        )
        event3 = AuditEvent(
            event_id="event3",
            event_type=AuditEventType.PROVIDER_REQUEST,
            provider="gemini",
            success=True,
        )

        audit_logger._event_buffer = [event1, event2, event3]

        stats = audit_logger.get_statistics()

        assert stats["total_events"] == 3
        assert stats["success_count"] == 2
        assert stats["error_count"] == 1
        assert stats["success_rate"] == 2 / 3
        assert stats["event_type_counts"][AuditEventType.PROVIDER_REQUEST] == 2
        assert stats["event_type_counts"][AuditEventType.PROVIDER_RESPONSE] == 1
        assert stats["provider_counts"]["gemini"] == 2
        assert stats["provider_counts"]["openai"] == 1

    def test_get_statistics_empty_buffer(self, audit_logger):
        """Test getting statistics with empty buffer."""
        stats = audit_logger.get_statistics()
        assert stats == {}

    @pytest.mark.asyncio
    async def test_write_event_success(self, audit_logger):
        """Test writing a successful event."""
        event = AuditEvent(
            event_id="test-event",
            event_type=AuditEventType.PROVIDER_REQUEST,
            success=True,
        )

        with patch.object(audit_logger.logger, "info") as mock_info:
            await audit_logger._write_event(event)
            mock_info.assert_called_once()
            call_args = mock_info.call_args[0][0]
            assert "AUDIT:" in call_args
            assert "test-event" in call_args

    @pytest.mark.asyncio
    async def test_write_event_error(self, audit_logger):
        """Test writing an error event."""
        event = AuditEvent(
            event_id="test-event",
            event_type=AuditEventType.PROVIDER_ERROR,
            success=False,
            error_message="Test error",
        )

        with patch.object(audit_logger.logger, "error") as mock_error:
            await audit_logger._write_event(event)
            mock_error.assert_called_once()
            call_args = mock_error.call_args[0][0]
            assert "AUDIT_ERROR:" in call_args
            assert "test-event" in call_args

    @pytest.mark.asyncio
    async def test_write_event_exception(self, audit_logger):
        """Test handling exceptions in _write_event."""
        event = AuditEvent(
            event_id="test-event",
            event_type=AuditEventType.PROVIDER_REQUEST,
        )

        with patch.object(
            audit_logger.logger, "info", side_effect=Exception("Test error")
        ):
            # Should not raise an exception
            await audit_logger._write_event(event)


class TestAuditEvent:
    """Test cases for AuditEvent model."""

    def test_audit_event_creation(self):
        """Test AuditEvent creation."""
        event = AuditEvent(
            event_id="test-event",
            event_type=AuditEventType.PROVIDER_REQUEST,
        )

        assert event.event_id == "test-event"
        assert event.event_type == AuditEventType.PROVIDER_REQUEST
        assert event.success is True
        assert event.metadata == {}

    def test_audit_event_with_all_fields(self):
        """Test AuditEvent with all fields."""
        timestamp = datetime.utcnow()
        event = AuditEvent(
            event_id="test-event",
            event_type=AuditEventType.PROVIDER_REQUEST,
            timestamp=timestamp,
            user_id="user123",
            session_id="session456",
            provider="gemini",
            model="gemini-pro",
            request_id="req789",
            success=False,
            error_message="Test error",
            metadata={"test": "data"},
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

        assert event.event_id == "test-event"
        assert event.event_type == AuditEventType.PROVIDER_REQUEST
        assert event.timestamp == timestamp
        assert event.user_id == "user123"
        assert event.session_id == "session456"
        assert event.provider == "gemini"
        assert event.model == "gemini-pro"
        assert event.request_id == "req789"
        assert event.success is False
        assert event.error_message == "Test error"
        assert event.metadata == {"test": "data"}
        assert event.ip_address == "192.168.1.1"
        assert event.user_agent == "TestAgent/1.0"


class TestAuditEventType:
    """Test cases for AuditEventType enum."""

    def test_audit_event_types(self):
        """Test that all expected event types exist."""
        expected_types = [
            "provider_request",
            "provider_response",
            "provider_error",
            "config_change",
            "key_rotation",
            "access_granted",
            "access_denied",
            "data_export",
            "compliance_check",
        ]

        for event_type in expected_types:
            assert hasattr(AuditEventType, event_type.upper())
            assert getattr(AuditEventType, event_type.upper()) == event_type
