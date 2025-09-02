"""
Log sanitization for removing sensitive data before Gemini AI processing.

Provides comprehensive PII and sensitive data detection and removal
to ensure secure AI analysis of log data.
"""

import re
from typing import Dict, List

from ..pattern_detector.models import LogEntry


class LogSanitizer:
    """Sanitize sensitive data before sending to Gemini."""

    def __init__(self):
        """Initialize sanitizer with comprehensive sensitive data patterns."""
        # Common patterns for sensitive data - order matters for JWT vs API key matching
        self.sensitive_patterns = {
            "ip_addresses": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            "email_addresses": re.compile(
                r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
            ),
            "credit_cards": re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"),
            "social_security": re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b"),
            "phone_numbers": re.compile(r"\b\d{3}-?\d{3}-?\d{4}\b"),
            "jwt_tokens": re.compile(
                r"\bey[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*\b"
            ),
            "api_keys": re.compile(r"\b[A-Za-z0-9]{32,}\b"),
            "passwords": re.compile(r'(?i)password["\s]*[:=]["\s]*[^\s"]+'),
            "secrets": re.compile(r'(?i)secret["\s]*[:=]["\s]*[^\s"]+'),
            "auth_tokens": re.compile(r'(?i)token["\s]*[:=]["\s]*[^\s"]+'),
        }

        # Replacement patterns
        self.replacements = {
            "ip_addresses": "[IP_REDACTED]",
            "email_addresses": "[EMAIL_REDACTED]",
            "credit_cards": "[CC_REDACTED]",
            "social_security": "[SSN_REDACTED]",
            "phone_numbers": "[PHONE_REDACTED]",
            "api_keys": "[API_KEY_REDACTED]",
            "jwt_tokens": "[JWT_REDACTED]",
            "passwords": "[PASSWORD_REDACTED]",
            "secrets": "[SECRET_REDACTED]",
            "auth_tokens": "[TOKEN_REDACTED]",
        }

    def sanitize_logs(self, logs: List[LogEntry]) -> List[LogEntry]:
        """Remove sensitive data from log entries before AI processing.

        Args:
            logs: List of log entries to sanitize

        Returns:
            List of sanitized log entries with sensitive data redacted
        """
        sanitized_logs = []

        for log in logs:
            sanitized_log = LogEntry(
                insert_id=log.insert_id,
                timestamp=log.timestamp,
                service_name=log.service_name,
                severity=log.severity,
                error_message=(
                    self.sanitize_text(log.error_message)
                    if log.error_message
                    else None
                ),
                raw_data=log.raw_data,
            )
            sanitized_logs.append(sanitized_log)

        return sanitized_logs

    def sanitize_text(self, text: str) -> str:
        """Sanitize sensitive data from text content.

        Args:
            text: Text content to sanitize

        Returns:
            Sanitized text with sensitive data replaced
        """
        if not text:
            return text

        sanitized = text
        for pattern_name, pattern in self.sensitive_patterns.items():
            replacement = self.replacements[pattern_name]
            sanitized = pattern.sub(replacement, sanitized)

        return sanitized

    def validate_sanitization(self, original: str, sanitized: str) -> Dict[str, int]:
        """Validate that sensitive data was properly removed.

        Args:
            original: Original text before sanitization
            sanitized: Sanitized text after processing

        Returns:
            Dictionary mapping pattern names to count of items removed
        """
        removed_counts = {}

        for pattern_name, pattern in self.sensitive_patterns.items():
            original_matches = len(pattern.findall(original))
            sanitized_matches = len(pattern.findall(sanitized))
            removed_counts[pattern_name] = original_matches - sanitized_matches

        return removed_counts
