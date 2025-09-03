# gemini_sre_agent/config/monitoring.py

"""
Configuration monitoring and audit logging.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, Optional


@dataclass
class ConfigChangeEvent:
    """Configuration change event for audit logging."""

    timestamp: datetime
    change_type: str  # 'reload', 'validation_failure', 'drift_detected'
    config_file: Optional[str]
    old_checksum: Optional[str]
    new_checksum: Optional[str]
    validation_errors: Optional[list]
    environment: str
    user_id: Optional[str] = None


class ConfigMonitoring:
    """Configuration monitoring and audit logging."""

    def __init__(self, enable_audit_logging: bool = True):
        self.enable_audit_logging = enable_audit_logging
        self.change_history: list[ConfigChangeEvent] = []
        self.metrics = {
            "config_reloads": 0,
            "validation_failures": 0,
            "drift_detections": 0,
            "last_reload_time": None,
            "last_validation_time": None,
        }

    def record_config_reload(
        self, config_file: str, old_checksum: str, new_checksum: str, environment: str
    ):
        """Record configuration reload event."""
        event = ConfigChangeEvent(
            timestamp=datetime.now(),
            change_type="reload",
            config_file=config_file,
            old_checksum=old_checksum,
            new_checksum=new_checksum,
            validation_errors=None,
            environment=environment,
        )

        self._record_event(event)
        self.metrics["config_reloads"] += 1
        self.metrics["last_reload_time"] = datetime.now()

    def record_validation_failure(
        self, config_file: str, errors: list, environment: str
    ):
        """Record configuration validation failure."""
        event = ConfigChangeEvent(
            timestamp=datetime.now(),
            change_type="validation_failure",
            config_file=config_file,
            old_checksum=None,
            new_checksum=None,
            validation_errors=errors,
            environment=environment,
        )

        self._record_event(event)
        self.metrics["validation_failures"] += 1
        self.metrics["last_validation_time"] = datetime.now()

    def record_drift_detection(
        self,
        config_file: str,
        expected_checksum: str,
        actual_checksum: str,
        environment: str,
    ):
        """Record configuration drift detection."""
        event = ConfigChangeEvent(
            timestamp=datetime.now(),
            change_type="drift_detected",
            config_file=config_file,
            old_checksum=expected_checksum,
            new_checksum=actual_checksum,
            validation_errors=None,
            environment=environment,
        )

        self._record_event(event)
        self.metrics["drift_detections"] += 1

    def _record_event(self, event: ConfigChangeEvent):
        """Record event to history and audit log."""
        self.change_history.append(event)

        if self.enable_audit_logging:
            self._write_audit_log(event)

    def _write_audit_log(self, event: ConfigChangeEvent):
        """Write audit log entry."""
        log_entry = {
            "timestamp": event.timestamp.isoformat(),
            "change_type": event.change_type,
            "config_file": event.config_file,
            "environment": event.environment,
            "checksum_change": (
                {
                    "old": event.old_checksum,
                    "new": event.new_checksum,
                }
                if event.old_checksum or event.new_checksum
                else None
            ),
            "validation_errors": event.validation_errors,
        }

        # Write to structured log
        logger = logging.getLogger("config.audit")
        logger.info("Configuration change event", extra=log_entry)

    def get_change_summary(self, hours: int = 24) -> Dict[str, Any]:
        """Get configuration change summary for specified time period."""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        recent_events = [e for e in self.change_history if e.timestamp >= cutoff_time]

        return {
            "total_changes": len(recent_events),
            "reloads": len([e for e in recent_events if e.change_type == "reload"]),
            "validation_failures": len(
                [e for e in recent_events if e.change_type == "validation_failure"]
            ),
            "drift_detections": len(
                [e for e in recent_events if e.change_type == "drift_detected"]
            ),
            "last_change": recent_events[-1].timestamp if recent_events else None,
            "metrics": self.metrics,
        }
