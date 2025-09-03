# gemini_sre_agent/ingestion/processor/log_processor.py

"""
LogProcessor handles log validation, sanitization, and flow tracking.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List

from ..interfaces import LogEntry, LogSeverity

logger = logging.getLogger(__name__)


class LogProcessor:
    """Processes normalized log entries with validation and sanitization."""

    def __init__(
        self,
        max_message_length: int = 10000,
        enable_pii_detection: bool = True,
        enable_flow_tracking: bool = True,
    ):
        self.max_message_length = max_message_length
        self.enable_pii_detection = enable_pii_detection
        self.enable_flow_tracking = enable_flow_tracking

        # PII detection patterns
        self.pii_patterns = [
            (r'password["\s]*[:=]["\s]*[^\s]+', 'password="***"'),
            (r'api[_-]?key["\s]*[:=]["\s]*[^\s]+', 'api_key="***"'),
            (r'token["\s]*[:=]["\s]*[^\s]+', 'token="***"'),
            (r'secret["\s]*[:=]["\s]*[^\s]+', 'secret="***"'),
            (r'credit[_-]?card["\s]*[:=]["\s]*[^\s]+', 'credit_card="***"'),
            (r'ssn["\s]*[:=]["\s]*[^\s]+', 'ssn="***"'),
            (r'email["\s]*[:=]["\s]*[^\s@]+@[^\s@]+\.[^\s@]+', 'email="***@***.***"'),
        ]

        # Flow ID generation counter
        self.flow_counter = 0

    async def process_log(self, log_entry: LogEntry) -> LogEntry:
        """Process a log entry with validation and sanitization."""
        try:
            # Validate log entry
            validated_entry = await self._validate_log_entry(log_entry)

            # Sanitize log entry
            sanitized_entry = await self._sanitize_log_entry(validated_entry)

            # Add flow tracking
            if self.enable_flow_tracking:
                sanitized_entry = await self._add_flow_tracking(sanitized_entry)

            return sanitized_entry

        except Exception as e:
            logger.error(f"Error processing log entry: {e}")
            # Return original entry with error metadata
            log_entry.metadata["processing_error"] = str(e)
            return log_entry

    async def _validate_log_entry(self, log_entry: LogEntry) -> LogEntry:
        """Validate log entry structure and content."""
        # Check required fields
        if not log_entry.id:
            log_entry.id = self._generate_log_id()

        if not log_entry.timestamp:
            log_entry.timestamp = datetime.now()

        if not log_entry.message:
            raise ValueError("Log message cannot be empty")

        # Truncate message if too long
        if len(log_entry.message) > self.max_message_length:
            log_entry.message = (
                log_entry.message[: self.max_message_length] + "... [TRUNCATED]"
            )
            log_entry.metadata["truncated"] = True

        # Validate severity
        if log_entry.severity and not isinstance(log_entry.severity, LogSeverity):
            try:
                log_entry.severity = LogSeverity(log_entry.severity.upper())
            except ValueError:
                log_entry.severity = LogSeverity.INFO
                log_entry.metadata["severity_parsed"] = False

        return log_entry

    async def _sanitize_log_entry(self, log_entry: LogEntry) -> LogEntry:
        """Sanitize log entry by removing PII and sensitive information."""
        if not self.enable_pii_detection:
            return log_entry

        sanitized_message = log_entry.message

        # Apply PII patterns
        for pattern, replacement in self.pii_patterns:
            sanitized_message = re.sub(
                pattern, replacement, sanitized_message, flags=re.IGNORECASE
            )

        # Check if message was modified
        if sanitized_message != log_entry.message:
            log_entry.message = sanitized_message
            log_entry.metadata["pii_detected"] = True

        # Sanitize metadata
        sanitized_metadata = {}
        for key, value in log_entry.metadata.items():
            if isinstance(value, str):
                # Check for PII in metadata values
                sanitized_value = value
                for pattern, replacement in self.pii_patterns:
                    sanitized_value = re.sub(
                        pattern, replacement, sanitized_value, flags=re.IGNORECASE
                    )
                sanitized_metadata[key] = sanitized_value
            else:
                sanitized_metadata[key] = value

        log_entry.metadata = sanitized_metadata

        return log_entry

    async def _add_flow_tracking(self, log_entry: LogEntry) -> LogEntry:
        """Add flow tracking information to log entry."""
        if not log_entry.flow_id:
            log_entry.flow_id = self._generate_flow_id()

        # Add processing timestamp
        log_entry.metadata["processed_at"] = datetime.now().isoformat()

        return log_entry

    def _generate_log_id(self) -> str:
        """Generate a unique log ID."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        return f"log_{timestamp}"

    def _generate_flow_id(self) -> str:
        """Generate a unique flow ID."""
        self.flow_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"flow_{timestamp}_{self.flow_counter:06d}"

    async def batch_process_logs(self, log_entries: List[LogEntry]) -> List[LogEntry]:
        """Process multiple log entries in batch."""
        processed_entries = []

        for log_entry in log_entries:
            try:
                processed_entry = await self.process_log(log_entry)
                processed_entries.append(processed_entry)
            except Exception as e:
                logger.error(f"Error processing log entry in batch: {e}")
                # Add error metadata and include in results
                log_entry.metadata["batch_processing_error"] = str(e)
                processed_entries.append(log_entry)

        return processed_entries

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "flow_counter": self.flow_counter,
            "max_message_length": self.max_message_length,
            "pii_detection_enabled": self.enable_pii_detection,
            "flow_tracking_enabled": self.enable_flow_tracking,
            "pii_patterns_count": len(self.pii_patterns),
        }
