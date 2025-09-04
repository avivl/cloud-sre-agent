"""Tests for DataFilter."""

from unittest.mock import patch

import pytest

from gemini_sre_agent.security.data_filter import (
    DataFilter,
    FilterRule,
    SensitiveDataType,
)


@pytest.fixture
def data_filter():
    """Create a DataFilter instance."""
    return DataFilter()


@pytest.fixture
def sample_filter_rule():
    """Create a sample filter rule."""
    return FilterRule(
        data_type=SensitiveDataType.API_KEY,
        pattern=r'(?i)(api[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?',
        replacement=r"\1=[REDACTED]",
        case_sensitive=False,
        enabled=True,
    )


class TestDataFilter:
    """Test cases for DataFilter."""

    def test_initialization(self, data_filter):
        """Test DataFilter initialization."""
        assert len(data_filter.rules) > 0  # Should have default rules
        assert len(data_filter._compiled_patterns) > 0

    def test_filter_text_api_key(self, data_filter):
        """Test filtering API keys from text."""
        text = 'api_key: "sk-1234567890abcdef1234567890abcdef"'
        filtered = data_filter.filter_text(text)
        assert "sk-1234567890abcdef1234567890abcdef" not in filtered
        assert "[REDACTED" in filtered

    def test_filter_text_email(self, data_filter):
        """Test filtering email addresses from text."""
        text = "Contact us at support@example.com for help"
        filtered = data_filter.filter_text(text)
        assert "support@example.com" not in filtered
        assert "[REDACTED_EMAIL]" in filtered

    def test_filter_text_phone(self, data_filter):
        """Test filtering phone numbers from text."""
        text = "Call us at (555) 123-4567 or 555-123-4567"
        filtered = data_filter.filter_text(text)
        assert "(555) 123-4567" not in filtered
        assert "555-123-4567" not in filtered
        assert "[REDACTED_PHONE]" in filtered

    def test_filter_text_ssn(self, data_filter):
        """Test filtering SSNs from text."""
        text = "SSN: 123-45-6789"
        filtered = data_filter.filter_text(text)
        assert "123-45-6789" not in filtered
        assert "[REDACTED_SSN]" in filtered

    def test_filter_text_credit_card(self, data_filter):
        """Test filtering credit card numbers from text."""
        text = "Card: 1234-5678-9012-3456"
        filtered = data_filter.filter_text(text)
        assert "1234-5678-9012-3456" not in filtered
        assert "[REDACTED_CC]" in filtered

    def test_filter_text_ip_address(self, data_filter):
        """Test filtering IP addresses from text."""
        text = "Server IP: 192.168.1.1"
        filtered = data_filter.filter_text(text)
        assert "192.168.1.1" not in filtered
        assert "[REDACTED_IP]" in filtered

    def test_filter_text_password(self, data_filter):
        """Test filtering passwords from text."""
        text = 'password: "secret123"'
        filtered = data_filter.filter_text(text)
        assert "secret123" not in filtered
        assert "password=[REDACTED]" in filtered

    def test_filter_text_jwt_token(self, data_filter):
        """Test filtering JWT tokens from text."""
        text = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        filtered = data_filter.filter_text(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in filtered
        assert "[REDACTED_JWT]" in filtered

    def test_filter_text_multiple_sensitive_data(self, data_filter):
        """Test filtering multiple types of sensitive data."""
        text = """
        User: john@example.com
        API Key: sk-1234567890abcdef1234567890abcdef
        Phone: (555) 123-4567
        SSN: 123-45-6789
        """
        filtered = data_filter.filter_text(text)

        assert "john@example.com" not in filtered
        assert "sk-1234567890abcdef1234567890abcdef" not in filtered
        assert "(555) 123-4567" not in filtered
        assert "123-45-6789" not in filtered

        assert "[REDACTED_EMAIL]" in filtered
        assert "[REDACTED" in filtered
        assert "[REDACTED_PHONE]" in filtered
        assert "[REDACTED_SSN]" in filtered

    def test_filter_text_no_sensitive_data(self, data_filter):
        """Test filtering text with no sensitive data."""
        text = "This is a normal text with no sensitive information."
        filtered = data_filter.filter_text(text)
        assert filtered == text

    def test_filter_text_empty(self, data_filter):
        """Test filtering empty text."""
        assert data_filter.filter_text("") == ""
        assert data_filter.filter_text(None) is None

    def test_filter_dict(self, data_filter):
        """Test filtering sensitive data from dictionary."""
        data = {
            "user": "john@example.com",
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "phone": "(555) 123-4567",
            "normal_field": "normal_value",
        }
        filtered = data_filter.filter_dict(data)

        assert filtered["user"] == "[REDACTED_EMAIL]"
        assert "[REDACTED" in filtered["api_key"]
        assert filtered["phone"] == "[REDACTED_PHONE]"
        assert filtered["normal_field"] == "normal_value"

    def test_filter_dict_nested(self, data_filter):
        """Test filtering sensitive data from nested dictionary."""
        data = {
            "user": {
                "email": "john@example.com",
                "api_key": "sk-1234567890abcdef1234567890abcdef",
            },
            "contact": {
                "phone": "(555) 123-4567",
            },
        }
        filtered = data_filter.filter_dict(data)

        assert filtered["user"]["email"] == "[REDACTED_EMAIL]"
        assert "[REDACTED" in filtered["user"]["api_key"]
        assert filtered["contact"]["phone"] == "[REDACTED_PHONE]"

    def test_filter_list(self, data_filter):
        """Test filtering sensitive data from list."""
        data = [
            "john@example.com",
            "sk-1234567890abcdef1234567890abcdef",
            "normal_text",
            {"email": "jane@example.com", "phone": "(555) 987-6543"},
        ]
        filtered = data_filter.filter_list(data)

        assert filtered[0] == "[REDACTED_EMAIL]"
        assert "[REDACTED" in filtered[1]
        assert filtered[2] == "normal_text"
        assert filtered[3]["email"] == "[REDACTED_EMAIL]"
        assert filtered[3]["phone"] == "[REDACTED_PHONE]"

    def test_filter_any_string(self, data_filter):
        """Test filtering any data type with string."""
        text = "Email: john@example.com"
        filtered = data_filter.filter_any(text)
        assert filtered == "[REDACTED_EMAIL]"

    def test_filter_any_dict(self, data_filter):
        """Test filtering any data type with dictionary."""
        data = {"email": "john@example.com"}
        filtered = data_filter.filter_any(data)
        assert filtered == {"email": "[REDACTED_EMAIL]"}

    def test_filter_any_list(self, data_filter):
        """Test filtering any data type with list."""
        data = ["john@example.com", "normal_text"]
        filtered = data_filter.filter_any(data)
        assert filtered == ["[REDACTED_EMAIL]", "normal_text"]

    def test_filter_any_other_type(self, data_filter):
        """Test filtering any data type with other types."""
        assert data_filter.filter_any(123) == 123
        assert data_filter.filter_any(True) is True
        assert data_filter.filter_any(None) is None

    def test_contains_sensitive_data_true(self, data_filter):
        """Test detecting sensitive data in text."""
        text = "Email: john@example.com"
        assert data_filter.contains_sensitive_data(text) is True

    def test_contains_sensitive_data_false(self, data_filter):
        """Test detecting no sensitive data in text."""
        text = "This is normal text"
        assert data_filter.contains_sensitive_data(text) is False

    def test_contains_sensitive_data_empty(self, data_filter):
        """Test detecting sensitive data in empty text."""
        assert data_filter.contains_sensitive_data("") is False
        assert data_filter.contains_sensitive_data(None) is False

    def test_get_sensitive_data_types(self, data_filter):
        """Test getting types of sensitive data found."""
        text = "Email: john@example.com, API Key: sk-1234567890abcdef1234567890abcdef"
        types = data_filter.get_sensitive_data_types(text)

        assert SensitiveDataType.EMAIL in types
        assert SensitiveDataType.API_KEY in types

    def test_get_sensitive_data_types_none(self, data_filter):
        """Test getting types when no sensitive data found."""
        text = "Normal text"
        types = data_filter.get_sensitive_data_types(text)
        assert len(types) == 0

    def test_add_rule(self, data_filter):
        """Test adding a custom rule."""
        initial_count = len(data_filter.rules)

        rule = FilterRule(
            data_type=SensitiveDataType.CUSTOM,
            pattern=r"custom_pattern",
            replacement="[CUSTOM_REDACTED]",
        )

        data_filter.add_rule(rule)

        assert len(data_filter.rules) == initial_count + 1
        assert rule in data_filter.rules
        assert rule.pattern in data_filter._compiled_patterns

    def test_add_rule_invalid_regex(self, data_filter):
        """Test adding a rule with invalid regex."""
        initial_count = len(data_filter.rules)

        rule = FilterRule(
            data_type=SensitiveDataType.CUSTOM,
            pattern=r"[invalid_regex",  # Missing closing bracket
            replacement="[CUSTOM_REDACTED]",
        )

        with patch("gemini_sre_agent.security.data_filter.logger") as mock_logger:
            data_filter.add_rule(rule)

            assert len(data_filter.rules) == initial_count + 1
            assert rule in data_filter.rules
            assert rule.pattern not in data_filter._compiled_patterns
            mock_logger.warning.assert_called_once()

    def test_remove_rule(self, data_filter):
        """Test removing a rule."""
        # Add a custom rule first
        rule = FilterRule(
            data_type=SensitiveDataType.CUSTOM,
            pattern=r"test_pattern",
            replacement="[TEST_REDACTED]",
        )
        data_filter.add_rule(rule)

        initial_count = len(data_filter.rules)

        result = data_filter.remove_rule(SensitiveDataType.CUSTOM, r"test_pattern")

        assert result is True
        assert len(data_filter.rules) == initial_count - 1
        assert rule not in data_filter.rules
        assert rule.pattern not in data_filter._compiled_patterns

    def test_remove_rule_nonexistent(self, data_filter):
        """Test removing a non-existent rule."""
        result = data_filter.remove_rule(
            SensitiveDataType.CUSTOM, r"nonexistent_pattern"
        )
        assert result is False

    def test_enable_rule(self, data_filter):
        """Test enabling a rule."""
        # Find a disabled rule or create one
        rule = FilterRule(
            data_type=SensitiveDataType.CUSTOM,
            pattern=r"test_pattern",
            replacement="[TEST_REDACTED]",
            enabled=False,
        )
        data_filter.add_rule(rule)

        result = data_filter.enable_rule(SensitiveDataType.CUSTOM, r"test_pattern")

        assert result is True
        assert rule.enabled is True
        assert rule.pattern in data_filter._compiled_patterns

    def test_disable_rule(self, data_filter):
        """Test disabling a rule."""
        # Find an enabled rule
        rule = data_filter.rules[0]  # Get first rule
        rule.enabled = True

        result = data_filter.disable_rule(rule.data_type, rule.pattern)

        assert result is True
        assert rule.enabled is False
        assert rule.pattern not in data_filter._compiled_patterns

    def test_get_rules_by_type(self, data_filter):
        """Test getting rules by data type."""
        api_key_rules = data_filter.get_rules_by_type(SensitiveDataType.API_KEY)

        assert len(api_key_rules) > 0
        assert all(
            rule.data_type == SensitiveDataType.API_KEY for rule in api_key_rules
        )

    def test_get_enabled_rules(self, data_filter):
        """Test getting enabled rules."""
        enabled_rules = data_filter.get_enabled_rules()

        assert len(enabled_rules) > 0
        assert all(rule.enabled for rule in enabled_rules)

    def test_get_disabled_rules(self, data_filter):
        """Test getting disabled rules."""
        # Disable a rule first
        rule = data_filter.rules[0]
        rule.enabled = False

        disabled_rules = data_filter.get_disabled_rules()

        assert len(disabled_rules) > 0
        assert all(not rule.enabled for rule in disabled_rules)

    def test_validate_rules(self, data_filter):
        """Test validating rules."""
        errors = data_filter.validate_rules()

        # Should have no errors with default rules
        assert len(errors) == 0

    def test_validate_rules_with_invalid(self, data_filter):
        """Test validating rules with invalid regex."""
        # Add an invalid rule
        rule = FilterRule(
            data_type=SensitiveDataType.CUSTOM,
            pattern=r"[invalid_regex",  # Missing closing bracket
            replacement="[CUSTOM_REDACTED]",
        )
        data_filter.add_rule(rule)

        errors = data_filter.validate_rules()

        assert len(errors) > 0
        assert any("Invalid regex pattern" in error for error in errors)


class TestFilterRule:
    """Test cases for FilterRule model."""

    def test_filter_rule_creation(self, sample_filter_rule):
        """Test FilterRule creation."""
        assert sample_filter_rule.data_type == SensitiveDataType.API_KEY
        assert (
            sample_filter_rule.pattern
            == r'(?i)(api[_-]?key)\s*[:=]\s*["\']?([a-zA-Z0-9_\-]{20,})["\']?'
        )
        assert sample_filter_rule.replacement == r"\1=[REDACTED]"
        assert sample_filter_rule.case_sensitive is False
        assert sample_filter_rule.enabled is True

    def test_filter_rule_defaults(self):
        """Test FilterRule with default values."""
        rule = FilterRule(
            data_type=SensitiveDataType.EMAIL,
            pattern=r"test@example\.com",
        )

        assert rule.replacement == "[REDACTED]"
        assert rule.case_sensitive is False
        assert rule.enabled is True


class TestSensitiveDataType:
    """Test cases for SensitiveDataType enum."""

    def test_sensitive_data_types(self):
        """Test that all expected sensitive data types exist."""
        expected_types = [
            "api_key",
            "email",
            "phone",
            "ssn",
            "credit_card",
            "ip_address",
            "password",
            "token",
            "secret",
            "custom",
        ]

        for data_type in expected_types:
            assert hasattr(SensitiveDataType, data_type.upper())
            assert getattr(SensitiveDataType, data_type.upper()) == data_type
