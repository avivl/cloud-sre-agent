"""
Comprehensive unit tests for LogSanitizer.

Tests sensitive data detection and removal across various patterns
including PII, credentials, and security-sensitive information.
"""

from datetime import datetime, timezone

import pytest

from gemini_sre_agent.ml.log_sanitizer import LogSanitizer
from gemini_sre_agent.pattern_detector.models import LogEntry


class TestLogSanitizerInit:
    """Test LogSanitizer initialization."""

    def test_init_creates_patterns(self):
        """Test initialization creates all expected patterns."""
        sanitizer = LogSanitizer()

        expected_patterns = [
            "ip_addresses",
            "email_addresses",
            "credit_cards",
            "social_security",
            "phone_numbers",
            "api_keys",
            "jwt_tokens",
            "passwords",
            "secrets",
            "auth_tokens",
        ]

        for pattern_name in expected_patterns:
            assert pattern_name in sanitizer.sensitive_patterns
            assert pattern_name in sanitizer.replacements

    def test_init_creates_compiled_patterns(self):
        """Test that patterns are properly compiled regex objects."""
        sanitizer = LogSanitizer()

        for pattern in sanitizer.sensitive_patterns.values():
            assert hasattr(pattern, "sub")  # Compiled regex has sub method
            assert hasattr(pattern, "findall")  # Compiled regex has findall method


class TestLogSanitizerTextSanitization:
    """Test text sanitization functionality."""

    @pytest.fixture
    def sanitizer(self):
        """Create sanitizer instance for tests."""
        return LogSanitizer()

    def test_sanitize_ip_addresses(self, sanitizer):
        """Test IP address sanitization."""
        text = "Error connecting to server 192.168.1.100 and 10.0.0.1"
        sanitized = sanitizer.sanitize_text(text)

        assert "192.168.1.100" not in sanitized
        assert "10.0.0.1" not in sanitized
        assert "[IP_REDACTED]" in sanitized

    def test_sanitize_email_addresses(self, sanitizer):
        """Test email address sanitization."""
        text = "User john.doe@example.com reported error"
        sanitized = sanitizer.sanitize_text(text)

        assert "john.doe@example.com" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized

    def test_sanitize_credit_cards(self, sanitizer):
        """Test credit card number sanitization."""
        text = "Payment failed for card 4111-1111-1111-1111"  # Standard test card
        sanitized = sanitizer.sanitize_text(text)

        assert "4111-1111-1111-1111" not in sanitized
        assert "[CC_REDACTED]" in sanitized

    def test_sanitize_social_security(self, sanitizer):
        """Test social security number sanitization."""
        text = "SSN validation failed for 123-45-6789"
        sanitized = sanitizer.sanitize_text(text)

        assert "123-45-6789" not in sanitized
        assert "[SSN_REDACTED]" in sanitized

    def test_sanitize_phone_numbers(self, sanitizer):
        """Test phone number sanitization."""
        text = "Contact support at 555-123-4567"
        sanitized = sanitizer.sanitize_text(text)

        assert "555-123-4567" not in sanitized
        assert "[PHONE_REDACTED]" in sanitized

    def test_sanitize_api_keys(self, sanitizer):
        """Test API key sanitization."""
        text = "API key " + "a" * 32 + "b" * 8  # Create 40-char test key
        sanitized = sanitizer.sanitize_text(text)

        assert ("a" * 32 + "b" * 8) not in sanitized
        assert "[API_KEY_REDACTED]" in sanitized

    def test_sanitize_jwt_tokens(self, sanitizer):
        """Test JWT token sanitization."""
        jwt = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.test_signature_here_not_real"
        text = f"Authorization failed with token {jwt}"
        sanitized = sanitizer.sanitize_text(text)

        assert jwt not in sanitized
        assert "[JWT_REDACTED]" in sanitized

    def test_sanitize_passwords(self, sanitizer):
        """Test password sanitization."""
        test_cases = [
            'password="secretpass123"',
            "password: mypassword",
            'password = "hidden123"',
        ]

        for text in test_cases:
            sanitized = sanitizer.sanitize_text(text)
            assert "secretpass123" not in sanitized
            assert "mypassword" not in sanitized
            assert "hidden123" not in sanitized
            assert "[PASSWORD_REDACTED]" in sanitized

    def test_sanitize_secrets(self, sanitizer):
        """Test secret sanitization."""
        test_cases = [
            'secret="mysecretkey"',
            "secret: topsecret123",
            'SECRET = "confidential"',
        ]

        for text in test_cases:
            sanitized = sanitizer.sanitize_text(text)
            assert "mysecretkey" not in sanitized
            assert "topsecret123" not in sanitized
            assert "confidential" not in sanitized
            assert "[SECRET_REDACTED]" in sanitized

    def test_sanitize_auth_tokens(self, sanitizer):
        """Test authentication token sanitization."""
        test_cases = [
            'token="bearer_abc123"',
            "token: access_token_xyz",
            'TOKEN = "refresh_token_456"',
        ]

        for text in test_cases:
            sanitized = sanitizer.sanitize_text(text)
            assert "bearer_abc123" not in sanitized
            assert "access_token_xyz" not in sanitized
            assert "refresh_token_456" not in sanitized
            assert "[TOKEN_REDACTED]" in sanitized

    def test_sanitize_multiple_patterns(self, sanitizer):
        """Test sanitization of multiple patterns in one text."""
        text = "User admin@company.com with IP 192.168.1.1 failed login with password=secret123"
        sanitized = sanitizer.sanitize_text(text)

        assert "admin@company.com" not in sanitized
        assert "192.168.1.1" not in sanitized
        assert "secret123" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized
        assert "[IP_REDACTED]" in sanitized
        assert "[PASSWORD_REDACTED]" in sanitized

    def test_sanitize_empty_text(self, sanitizer):
        """Test sanitization of empty or None text."""
        assert sanitizer.sanitize_text("") == ""
        assert sanitizer.sanitize_text(None) is None

    def test_sanitize_text_without_sensitive_data(self, sanitizer):
        """Test text with no sensitive patterns remains unchanged."""
        text = "Normal error message without sensitive data"
        sanitized = sanitizer.sanitize_text(text)
        assert sanitized == text


class TestLogSanitizerLogSanitization:
    """Test log entry sanitization functionality."""

    @pytest.fixture
    def sanitizer(self):
        """Create sanitizer instance for tests."""
        return LogSanitizer()

    @pytest.fixture
    def sample_log_entry(self):
        """Create sample log entry with sensitive data."""
        return LogEntry(
            insert_id="test_log_1",
            timestamp=datetime.now(timezone.utc),
            service_name="api-service",
            severity="ERROR",
            error_message="Authentication failed for user admin@test.com from IP 192.168.1.100",
            raw_data={},
        )

    def test_sanitize_single_log(self, sanitizer, sample_log_entry):
        """Test sanitization of single log entry."""
        sanitized_logs = sanitizer.sanitize_logs([sample_log_entry])

        assert len(sanitized_logs) == 1
        sanitized_log = sanitized_logs[0]

        # Check that structure is preserved
        assert sanitized_log.insert_id == sample_log_entry.insert_id
        assert sanitized_log.timestamp == sample_log_entry.timestamp
        assert sanitized_log.service_name == sample_log_entry.service_name
        assert sanitized_log.severity == sample_log_entry.severity

        # Check that sensitive data is removed
        assert "admin@test.com" not in sanitized_log.error_message
        assert "192.168.1.100" not in sanitized_log.error_message
        assert "[EMAIL_REDACTED]" in sanitized_log.error_message
        assert "[IP_REDACTED]" in sanitized_log.error_message

    def test_sanitize_multiple_logs(self, sanitizer):
        """Test sanitization of multiple log entries."""
        logs = [
            LogEntry(
                insert_id="log1",
                timestamp=datetime.now(timezone.utc),
                service_name="api-service",
                severity="ERROR",
                error_message="Failed auth for user@test.com",
                raw_data={},
            ),
            LogEntry(
                insert_id="log2",
                timestamp=datetime.now(timezone.utc),
                service_name="db-service",
                severity="WARNING",
                error_message="Connection timeout to 10.0.0.1",
                raw_data={},
            ),
        ]

        sanitized_logs = sanitizer.sanitize_logs(logs)

        assert len(sanitized_logs) == 2
        assert "[EMAIL_REDACTED]" in sanitized_logs[0].error_message
        assert "[IP_REDACTED]" in sanitized_logs[1].error_message

    def test_sanitize_log_with_none_error_message(self, sanitizer):
        """Test sanitization of log with None error message."""
        log = LogEntry(
            insert_id="log1",
            timestamp=datetime.now(timezone.utc),
            service_name="api-service",
            severity="INFO",
            error_message=None,
            raw_data={},
        )

        sanitized_logs = sanitizer.sanitize_logs([log])
        assert len(sanitized_logs) == 1
        assert sanitized_logs[0].error_message is None

    def test_sanitize_empty_log_list(self, sanitizer):
        """Test sanitization of empty log list."""
        sanitized_logs = sanitizer.sanitize_logs([])
        assert len(sanitized_logs) == 0


class TestLogSanitizerValidation:
    """Test sanitization validation functionality."""

    @pytest.fixture
    def sanitizer(self):
        """Create sanitizer instance for tests."""
        return LogSanitizer()

    def test_validate_sanitization_with_removals(self, sanitizer):
        """Test validation counts removed sensitive items."""
        original = "User admin@test.com at 192.168.1.1 with secret=password123"
        sanitized = sanitizer.sanitize_text(original)

        validation_result = sanitizer.validate_sanitization(original, sanitized)

        # Should show items were removed
        assert validation_result["email_addresses"] == 1
        assert validation_result["ip_addresses"] == 1
        assert validation_result["secrets"] == 1

        # Patterns not in text should show 0 removals
        assert validation_result["credit_cards"] == 0
        assert validation_result["phone_numbers"] == 0

    def test_validate_sanitization_no_sensitive_data(self, sanitizer):
        """Test validation with no sensitive data."""
        original = "Normal log message without sensitive information"
        sanitized = sanitizer.sanitize_text(original)

        validation_result = sanitizer.validate_sanitization(original, sanitized)

        # All counts should be 0
        for count in validation_result.values():
            assert count == 0

    def test_validate_sanitization_multiple_same_pattern(self, sanitizer):
        """Test validation with multiple instances of same pattern."""
        original = "Servers 192.168.1.1 and 10.0.0.1 and 172.16.0.1 failed"
        sanitized = sanitizer.sanitize_text(original)

        validation_result = sanitizer.validate_sanitization(original, sanitized)

        # Should count all IP addresses removed
        assert validation_result["ip_addresses"] == 3
