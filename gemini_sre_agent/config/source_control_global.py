# gemini_sre_agent/config/source_control_global.py

"""
Global source control configuration models.
"""

from enum import Enum
from typing import List, Optional, Union

from pydantic import Field, field_validator, model_validator

from .base import BaseConfig
from .source_control_credentials import CredentialConfig
from .source_control_remediation import (
    ConflictResolutionStrategy,
    RemediationStrategyConfig,
)
from .source_control_repositories import (
    GitHubRepositoryConfig,
    GitLabRepositoryConfig,
    LocalRepositoryConfig,
)


class CredentialStore(str, Enum):
    """Available credential storage backends."""

    ENV = "env"
    VAULT = "vault"
    AWS_SECRETS = "aws-secrets"
    GCP_SECRETS = "gcp-secrets"
    AZURE_KEY_VAULT = "azure-key-vault"


class SourceControlGlobalConfig(BaseConfig):
    """Global source control configuration."""

    # Default provider and settings
    default_provider: str = Field(default="github", description="Default provider type")
    credential_store: CredentialStore = Field(
        default=CredentialStore.ENV, description="Credential storage backend"
    )

    # Discovery and automation
    auto_discovery: bool = Field(
        default=False, description="Enable automatic repository discovery"
    )
    conflict_resolution: ConflictResolutionStrategy = Field(
        default=ConflictResolutionStrategy.MANUAL,
        description="Conflict resolution strategy",
    )

    # Logging and monitoring
    audit_logging: bool = Field(
        default=True, description="Enable audit logging for all operations"
    )
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")

    # Performance settings
    max_concurrent_operations: int = Field(
        default=5, ge=1, le=100, description="Maximum concurrent repository operations"
    )
    operation_timeout_seconds: int = Field(
        default=300, ge=30, description="Timeout for repository operations in seconds"
    )
    retry_attempts: int = Field(
        default=3,
        ge=0,
        le=10,
        description="Number of retry attempts for failed operations",
    )
    retry_delay_seconds: int = Field(
        default=5, ge=1, description="Delay between retry attempts in seconds"
    )

    # Rate limiting
    enable_rate_limiting: bool = Field(
        default=True, description="Enable rate limiting for API calls"
    )
    rate_limit_requests_per_minute: int = Field(
        default=60, ge=1, description="Maximum requests per minute per provider"
    )
    rate_limit_burst_size: int = Field(
        default=10, ge=1, description="Burst size for rate limiting"
    )

    # Caching
    enable_caching: bool = Field(
        default=True, description="Enable caching for repository operations"
    )
    cache_ttl_seconds: int = Field(
        default=3600, ge=60, description="Cache TTL in seconds"
    )
    max_cache_size_mb: int = Field(
        default=100, ge=1, description="Maximum cache size in MB"
    )

    # Security settings
    enable_credential_rotation: bool = Field(
        default=False, description="Enable automatic credential rotation"
    )
    credential_rotation_interval_days: int = Field(
        default=90, ge=1, description="Credential rotation interval in days"
    )
    enable_encryption: bool = Field(
        default=True, description="Enable encryption for sensitive data"
    )

    # Default credentials (optional)
    default_credentials: Optional[CredentialConfig] = Field(
        None,
        description="Default credentials for repositories without specific credentials",
    )

    # Default remediation strategy (optional)
    default_remediation_strategy: Optional[RemediationStrategyConfig] = Field(
        None,
        description="Default remediation strategy for repositories without specific strategy",
    )

    @field_validator("default_provider")
    @classmethod
    def validate_default_provider(cls, v):
        """Validate default provider type."""
        valid_providers = ["github", "gitlab", "local"]
        if v not in valid_providers:
            raise ValueError(f"Default provider must be one of {valid_providers}")
        return v

    @field_validator("max_concurrent_operations")
    @classmethod
    def validate_max_concurrent_operations(cls, v):
        """Validate maximum concurrent operations."""
        if v < 1:
            raise ValueError("Maximum concurrent operations must be at least 1")
        if v > 100:
            raise ValueError("Maximum concurrent operations cannot exceed 100")
        return v

    @field_validator("rate_limit_requests_per_minute")
    @classmethod
    def validate_rate_limit(cls, v):
        """Validate rate limit settings."""
        if v < 1:
            raise ValueError("Rate limit must be at least 1 request per minute")
        if v > 10000:
            raise ValueError("Rate limit cannot exceed 10000 requests per minute")
        return v

    @field_validator("rate_limit_burst_size")
    @classmethod
    def validate_burst_size(cls, v):
        """Validate burst size."""
        if v < 1:
            raise ValueError("Burst size must be at least 1")
        if v > 1000:
            raise ValueError("Burst size cannot exceed 1000")
        return v

    @model_validator(mode="after")
    def validate_rate_limiting_config(self):
        """Validate rate limiting configuration."""
        if self.enable_rate_limiting:
            if self.rate_limit_burst_size > self.rate_limit_requests_per_minute:
                raise ValueError(
                    "Burst size cannot be greater than requests per minute"
                )
        return self

    def get_effective_credentials(
        self, repo_credentials: Optional[CredentialConfig]
    ) -> Optional[CredentialConfig]:
        """Get effective credentials for a repository."""
        return repo_credentials or self.default_credentials

    def get_effective_remediation_strategy(
        self, repo_strategy: Optional[RemediationStrategyConfig]
    ) -> RemediationStrategyConfig:
        """Get effective remediation strategy for a repository."""
        return (
            repo_strategy
            or self.default_remediation_strategy
            or RemediationStrategyConfig()
        )

    def should_use_caching(self) -> bool:
        """Check if caching should be used."""
        return self.enable_caching

    def should_use_rate_limiting(self) -> bool:
        """Check if rate limiting should be used."""
        return self.enable_rate_limiting


class SourceControlConfig(BaseConfig):
    """Source control configuration for a service."""

    repositories: List[
        Union[GitHubRepositoryConfig, GitLabRepositoryConfig, LocalRepositoryConfig]
    ] = Field(default_factory=list, description="List of repositories for this service")

    @field_validator("repositories")
    @classmethod
    def validate_repository_names(cls, v):
        """Validate that repository names are unique within a service."""
        if not v:
            return v

        names = [repo.name for repo in v]
        if len(names) != len(set(names)):
            raise ValueError("Repository names must be unique within a service")

        return v

    @model_validator(mode="after")
    def validate_repositories(self):
        """Validate repository configurations."""
        if not self.repositories:
            raise ValueError("At least one repository must be configured")

        # Validate that each repository has appropriate credentials
        for repo in self.repositories:
            if repo.type in ["github", "gitlab"] and not repo.credentials:
                # This will be handled by the global config's default credentials
                pass

        return self

    def get_repository_by_name(
        self, name: str
    ) -> Optional[
        Union[GitHubRepositoryConfig, GitLabRepositoryConfig, LocalRepositoryConfig]
    ]:
        """Get a repository by name."""
        for repo in self.repositories:
            if repo.name == name:
                return repo
        return None

    def get_repositories_by_type(
        self, repo_type: str
    ) -> List[
        Union[GitHubRepositoryConfig, GitLabRepositoryConfig, LocalRepositoryConfig]
    ]:
        """Get all repositories of a specific type."""
        return [repo for repo in self.repositories if repo.type == repo_type]

    def get_repositories_for_path(
        self, file_path: str
    ) -> List[
        Union[GitHubRepositoryConfig, GitLabRepositoryConfig, LocalRepositoryConfig]
    ]:
        """Get repositories that match the given file path."""
        matching_repos = []
        for repo in self.repositories:
            if repo.matches_path(file_path):
                matching_repos.append(repo)
        return matching_repos
