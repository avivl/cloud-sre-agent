# gemini_sre_agent/config/app_config.py

"""
Main application configuration consolidating all configuration sections.
"""

from typing import List, Optional

from pydantic import Field, field_validator

from .base import BaseConfig
from .ml_config import MLConfig


class ServiceConfig(BaseConfig):
    """Configuration for a service to monitor."""

    name: str = Field(..., description="Service name")
    project_id: str = Field(..., description="GCP project ID")
    location: str = Field(..., description="GCP location/region")
    subscription_id: str = Field(..., description="Pub/Sub subscription ID")

    @field_validator("project_id")
    @classmethod
    def validate_project_id(cls, v):
        if len(v) < 6 or len(v) > 30:
            raise ValueError("Project ID must be 6-30 characters")
        return v

    @field_validator("subscription_id")
    @classmethod
    def validate_subscription_id(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError("Subscription ID cannot be empty")
        return v.strip()


class GitHubConfig(BaseConfig):
    """GitHub configuration."""

    repository: str = Field(..., description="GitHub repository (owner/repo)")
    base_branch: str = Field(default="main", description="Base branch name")
    token: Optional[str] = Field(
        default=None, description="GitHub token (set via env var)"
    )


class LoggingConfig(BaseConfig):
    """Logging configuration."""

    level: str = Field(default="INFO", description="Log level")
    format: str = Field(default="json", description="Log format (json/text)")
    file: Optional[str] = Field(default=None, description="Log file path")
    max_size_mb: int = Field(
        default=100, ge=1, description="Maximum log file size in MB"
    )
    backup_count: int = Field(
        default=5, ge=0, description="Number of backup files to keep"
    )


class SecurityConfig(BaseConfig):
    """Security configuration."""

    enable_secrets_validation: bool = Field(
        default=True, description="Enable secrets validation"
    )
    secrets_rotation_interval_days: int = Field(
        default=90, ge=1, description="Secrets rotation interval"
    )
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")
    max_failed_attempts: int = Field(
        default=5, ge=1, description="Maximum failed authentication attempts"
    )
    lockout_duration_minutes: int = Field(
        default=30, ge=1, description="Account lockout duration"
    )


class MonitoringConfig(BaseConfig):
    """Monitoring configuration."""

    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_endpoint: Optional[str] = Field(
        default=None, description="Metrics endpoint URL"
    )
    enable_health_checks: bool = Field(default=True, description="Enable health checks")
    health_check_interval_seconds: int = Field(
        default=60, ge=1, description="Health check interval"
    )
    enable_alerting: bool = Field(default=True, description="Enable alerting")
    alert_webhook_url: Optional[str] = Field(
        default=None, description="Alert webhook URL"
    )


class PerformanceConfig(BaseConfig):
    """Performance configuration."""

    cache_max_size_mb: int = Field(
        default=100, ge=1, description="Maximum cache size in MB"
    )
    cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="Cache TTL in seconds"
    )
    max_concurrent_requests: int = Field(
        default=10, ge=1, description="Maximum concurrent requests"
    )
    request_timeout_seconds: int = Field(
        default=30, ge=1, description="Request timeout in seconds"
    )


class AppConfig(BaseConfig):
    """Main application configuration."""

    # Core service configuration
    services: List[ServiceConfig] = Field(
        default_factory=list, description="Services to monitor"
    )

    # Sub-configurations
    ml: MLConfig = Field(default_factory=MLConfig, description="ML configuration")
    performance: PerformanceConfig = Field(
        default_factory=PerformanceConfig, description="Performance configuration"
    )
    security: SecurityConfig = Field(
        default_factory=SecurityConfig, description="Security configuration"
    )
    monitoring: MonitoringConfig = Field(
        default_factory=MonitoringConfig, description="Monitoring configuration"
    )

    # GitHub configuration
    github: GitHubConfig = Field(
        default_factory=lambda: GitHubConfig(repository="owner/repo"),
        description="GitHub configuration",
    )

    # Logging configuration
    logging: LoggingConfig = Field(
        default_factory=LoggingConfig, description="Logging configuration"
    )

    @field_validator("services")
    @classmethod
    def validate_services(cls, v):
        """Validate service configurations."""
        if not v:
            raise ValueError("At least one service must be configured")

        service_names = [s.name for s in v]
        if len(service_names) != len(set(service_names)):
            raise ValueError("Service names must be unique")

        return v
