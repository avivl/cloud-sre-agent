# gemini_sre_agent/ml/log_sanitizer.py

"""
Log sanitization utilities for enhanced code generation.

This module provides functionality to sanitize logs by removing
sensitive information and formatting them for safe processing.
"""

import re
from typing import List


class LogSanitizer:
    """
    Sanitizes log entries by removing sensitive information.

    This class provides methods to clean log data before processing
    or storage to ensure no sensitive information is exposed.
    """

    def __init__(self):
        """Initialize the log sanitizer."""
        # Common patterns for sensitive data
        self.sensitive_patterns = [
            r'password["\s]*[:=]["\s]*[^\s\n]+',
            r'api[_-]?key["\s]*[:=]["\s]*[^\s\n]+',
            r'token["\s]*[:=]["\s]*[^\s\n]+',
            r'secret["\s]*[:=]["\s]*[^\s\n]+',
            r'authorization["\s]*[:=]["\s]*[^\s\n]+',
            r'bearer["\s]*[:=]["\s]*[^\s\n]+',
        ]

        # Compile patterns for efficiency
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.sensitive_patterns
        ]

        # Track replacements made
        self.replacements: List[str] = []

    def sanitize_log(self, log_entry: str) -> str:
        """
        Sanitize a log entry by removing sensitive information.

        Args:
            log_entry: Raw log entry string

        Returns:
            Sanitized log entry
        """
        sanitized = log_entry

        # Replace sensitive patterns
        for pattern in self.compiled_patterns:
            sanitized = pattern.sub("[REDACTED]", sanitized)

        # Remove potential file paths with sensitive info
        sanitized = re.sub(r"/[^\s]*[Pp]assword[^\s]*", "[REDACTED_PATH]", sanitized)
        sanitized = re.sub(r"/[^\s]*[Kk]ey[^\s]*", "[REDACTED_PATH]", sanitized)

        return sanitized

    def sanitize_logs(self, logs: List[str]) -> List[str]:
        """
        Sanitize multiple log entries.

        Args:
            logs: List of log entry strings

        Returns:
            List of sanitized log entries
        """
        return [self.sanitize_log(log) for log in logs]

    def is_sensitive(self, text: str) -> bool:
        """
        Check if text contains sensitive information.

        Args:
            text: Text to check

        Returns:
            True if sensitive information is detected
        """
        for pattern in self.compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def get_sensitive_fields(self, log_entry: str) -> List[str]:
        """
        Get list of fields that contain sensitive information.

        Args:
            log_entry: Log entry to analyze

        Returns:
            List of field names that contain sensitive data
        """
        sensitive_fields = []

        for pattern in self.compiled_patterns:
            matches = pattern.findall(log_entry)
            for match in matches:
                # Extract field name from match
                field_match = re.search(r'([a-zA-Z_]+)["\s]*[:=]', match)
                if field_match:
                    sensitive_fields.append(field_match.group(1))

        return list(set(sensitive_fields))
