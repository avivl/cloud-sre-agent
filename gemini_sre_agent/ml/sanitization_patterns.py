"""
Sanitization patterns and configurations for sensitive data detection.

This module contains the pattern definitions and configuration for detecting
and removing sensitive information from log data.
"""

import re
from dataclasses import dataclass, field
from typing import Dict
from typing import Pattern as RegexPattern


@dataclass
class SanitizationConfig:
    """Configuration for log sanitization patterns and replacements."""

    # Enable/disable specific sanitization patterns
    sanitize_ip_addresses: bool = True
    sanitize_email_addresses: bool = True
    sanitize_credit_cards: bool = True
    sanitize_social_security: bool = True
    sanitize_phone_numbers: bool = True
    sanitize_api_keys: bool = True
    sanitize_jwt_tokens: bool = True
    sanitize_passwords: bool = True
    sanitize_secrets: bool = True
    sanitize_auth_tokens: bool = True

    # Custom patterns (for project-specific sensitive data)
    custom_patterns: Dict[str, str] = field(default_factory=dict)
    custom_replacements: Dict[str, str] = field(default_factory=dict)


class SanitizationPatterns:
    """Factory for creating sanitization patterns and replacements."""

    @staticmethod
    def build_sensitive_patterns(config: SanitizationConfig) -> Dict[str, RegexPattern]:
        """Build dictionary of compiled regex patterns for sensitive data."""
        patterns = {}

        if config.sanitize_ip_addresses:
            patterns["ip_addresses"] = re.compile(
                r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
                r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
            )

        if config.sanitize_email_addresses:
            patterns["email_addresses"] = re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            )

        if config.sanitize_credit_cards:
            patterns["credit_cards"] = re.compile(
                r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|"
                r"3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b"
            )

        if config.sanitize_social_security:
            patterns["social_security"] = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b")

        if config.sanitize_phone_numbers:
            patterns["phone_numbers"] = re.compile(
                r"\b(?:\+?1[-.\s]?)?(?:\([0-9]{3}\)|[0-9]{3})[-.\s]?"
                r"[0-9]{3}[-.\s]?[0-9]{4}\b"
            )

        if config.sanitize_api_keys:
            patterns["api_keys"] = re.compile(r"\b[A-Za-z0-9_-]{32,}\b")

        if config.sanitize_jwt_tokens:
            patterns["jwt_tokens"] = re.compile(
                r"\bey[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"
            )

        if config.sanitize_passwords:
            patterns["passwords"] = re.compile(
                r'(?i)password["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE
            )

        if config.sanitize_secrets:
            patterns["secrets"] = re.compile(
                r'(?i)secret["\s]*[:=]["\s]*[^\s"]+', re.IGNORECASE
            )

        if config.sanitize_auth_tokens:
            patterns["auth_tokens"] = re.compile(
                r'(?i)token["\s]*[:=]["\s]*(?!\[[A-Z_]+_REDACTED\])[^\s"]+',
                re.IGNORECASE,
            )

        return patterns

    @staticmethod
    def build_replacements() -> Dict[str, str]:
        """Build replacement strings for sanitized patterns."""
        return {
            "ip_addresses": "[IP_REDACTED]",
            "email_addresses": "[EMAIL_REDACTED]",
            "credit_cards": "[CC_REDACTED]",
            "social_security": "[SSN_REDACTED]",
            "phone_numbers": "[PHONE_REDACTED]",
            "api_keys": "[API_KEY_REDACTED]",
            "jwt_tokens": "[JWT_REDACTED]",
            "passwords": "password: [PASSWORD_REDACTED]",
            "secrets": "secret: [SECRET_REDACTED]",
            "auth_tokens": "token: [TOKEN_REDACTED]",
        }

    @staticmethod
    def add_custom_patterns(
        patterns: Dict[str, RegexPattern], config: SanitizationConfig
    ) -> Dict[str, RegexPattern]:
        """Add custom patterns from configuration."""
        for pattern_name, pattern_str in config.custom_patterns.items():
            try:
                patterns[pattern_name] = re.compile(pattern_str)
            except re.error:
                # Log warning but don't fail - handled by caller
                pass

        return patterns
