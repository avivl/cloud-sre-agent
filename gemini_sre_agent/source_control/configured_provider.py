# gemini_sre_agent/source_control/configured_provider.py

"""
Provider that uses Pydantic configuration models.
"""

from typing import Any, Dict, Optional

from ..config.source_control_global import SourceControlGlobalConfig
from ..config.source_control_repositories import RepositoryConfig
from .base_implementation import BaseSourceControlProvider


class ConfiguredSourceControlProvider(BaseSourceControlProvider):
    """A provider that uses Pydantic configuration models."""

    def __init__(
        self,
        repository_config: RepositoryConfig,
        global_config: Optional[SourceControlGlobalConfig] = None,
    ):
        """Initialize with validated Pydantic configs."""
        # Convert Pydantic models to dictionary for base class
        config_dict = repository_config.model_dump()

        # Add global config if provided
        if global_config:
            config_dict.update(global_config.model_dump())

        super().__init__(config_dict)
        self.repository_config = repository_config
        self.global_config = global_config

    def get_repository_name(self) -> str:
        """Get the repository name from config."""
        return self.repository_config.name

    def get_repository_type(self) -> str:
        """Get the repository type from config."""
        return self.repository_config.type

    def get_branch(self) -> str:
        """Get the default branch from config."""
        return self.repository_config.branch

    def get_paths(self) -> list[str]:
        """Get the configured paths from config."""
        return self.repository_config.paths

    def get_credentials(self):
        """Get the credentials from config."""
        return self.repository_config.credentials

    def get_remediation_strategy(self):
        """Get the remediation strategy from config."""
        return self.repository_config.remediation

    def get_global_config_value(self, key: str, default: Any = None) -> Any:
        """Get a value from the global configuration."""
        if self.global_config is None:
            return default

        return getattr(self.global_config, key, default)

    def should_use_caching(self) -> bool:
        """Check if caching should be used based on global config."""
        if self.global_config is None:
            return False

        return self.global_config.should_use_caching()

    def should_use_rate_limiting(self) -> bool:
        """Check if rate limiting should be used based on global config."""
        if self.global_config is None:
            return False

        return self.global_config.should_use_rate_limiting()

    def get_max_concurrent_operations(self) -> int:
        """Get the maximum concurrent operations from global config."""
        if self.global_config is None:
            return 5  # Default value

        return self.global_config.max_concurrent_operations

    def get_operation_timeout(self) -> int:
        """Get the operation timeout from global config."""
        if self.global_config is None:
            return 300  # Default value

        return self.global_config.operation_timeout_seconds

    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration from global config."""
        if self.global_config is None:
            return {"max_retries": 3, "base_delay": 1.0, "max_delay": 60.0}

        return {
            "max_retries": self.global_config.retry_attempts,
            "base_delay": 1.0,
            "max_delay": 60.0,
        }

    def get_rate_limit_config(self) -> Dict[str, Any]:
        """Get rate limit configuration from global config."""
        if self.global_config is None:
            return {"requests_per_minute": 60, "burst_size": 10}

        return {
            "requests_per_minute": self.global_config.rate_limit_requests_per_minute,
            "burst_size": self.global_config.rate_limit_burst_size,
        }

    def get_cache_config(self) -> Dict[str, Any]:
        """Get cache configuration from global config."""
        if self.global_config is None:
            return {"enabled": False, "ttl_seconds": 3600, "max_size_mb": 100}

        return {
            "enabled": self.global_config.enable_caching,
            "ttl_seconds": self.global_config.cache_ttl_seconds,
            "max_size_mb": self.global_config.max_cache_size_mb,
        }

    def get_security_config(self) -> Dict[str, Any]:
        """Get security configuration from global config."""
        if self.global_config is None:
            return {
                "enable_encryption": True,
                "enable_credential_rotation": False,
                "credential_rotation_interval_days": 90,
            }

        return {
            "enable_encryption": self.global_config.enable_encryption,
            "enable_credential_rotation": self.global_config.enable_credential_rotation,
            "credential_rotation_interval_days": self.global_config.credential_rotation_interval_days,
        }

    def get_monitoring_config(self) -> Dict[str, Any]:
        """Get monitoring configuration from global config."""
        if self.global_config is None:
            return {"enable_metrics": True, "audit_logging": True}

        return {
            "enable_metrics": self.global_config.enable_metrics,
            "audit_logging": self.global_config.audit_logging,
        }

    def is_path_configured(self, file_path: str) -> bool:
        """Check if a file path matches the configured paths."""
        return self.repository_config.matches_path(file_path)

    def get_effective_credentials(self):
        """Get effective credentials (repository-specific or global default)."""
        if self.global_config is None:
            return self.repository_config.credentials

        return self.global_config.get_effective_credentials(
            self.repository_config.credentials
        )

    def get_effective_remediation_strategy(self):
        """Get effective remediation strategy (repository-specific or global default)."""
        if self.global_config is None:
            return self.repository_config.remediation

        return self.global_config.get_effective_remediation_strategy(
            self.repository_config.remediation
        )
