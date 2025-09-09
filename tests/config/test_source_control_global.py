# tests/config/test_source_control_global.py

"""
Tests for source control global configuration models.
"""

import pytest
from pydantic import ValidationError

from gemini_sre_agent.config.source_control_credentials import CredentialConfig
from gemini_sre_agent.config.source_control_global import (
    CredentialStore,
    SourceControlConfig,
    SourceControlGlobalConfig,
)
from gemini_sre_agent.config.source_control_remediation import RemediationStrategyConfig
from gemini_sre_agent.config.source_control_repositories import (
    GitHubRepositoryConfig,
    GitLabRepositoryConfig,
)


class TestSourceControlGlobalConfig:
    """Test cases for SourceControlGlobalConfig."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = SourceControlGlobalConfig()

        assert config.default_provider == "github"
        assert config.credential_store == CredentialStore.ENV
        assert config.auto_discovery is False
        assert config.audit_logging is True
        assert config.enable_metrics is True
        assert config.max_concurrent_operations == 5
        assert config.operation_timeout_seconds == 300
        assert config.retry_attempts == 3
        assert config.retry_delay_seconds == 5
        assert config.enable_rate_limiting is True
        assert config.rate_limit_requests_per_minute == 60
        assert config.rate_limit_burst_size == 10
        assert config.enable_caching is True
        assert config.cache_ttl_seconds == 3600
        assert config.max_cache_size_mb == 100
        assert config.enable_credential_rotation is False
        assert config.credential_rotation_interval_days == 90
        assert config.enable_encryption is True
        assert config.default_credentials is None
        assert config.default_remediation_strategy is None

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = SourceControlGlobalConfig(
            default_provider="gitlab",
            credential_store=CredentialStore.VAULT,
            auto_discovery=True,
            audit_logging=False,
            enable_metrics=False,
            max_concurrent_operations=10,
            operation_timeout_seconds=600,
            retry_attempts=5,
            retry_delay_seconds=10,
            enable_rate_limiting=False,
            rate_limit_requests_per_minute=120,
            rate_limit_burst_size=20,
            enable_caching=False,
            cache_ttl_seconds=7200,
            max_cache_size_mb=200,
            enable_credential_rotation=True,
            credential_rotation_interval_days=30,
            enable_encryption=False,
        )

        assert config.default_provider == "gitlab"
        assert config.credential_store == CredentialStore.VAULT
        assert config.auto_discovery is True
        assert config.audit_logging is False
        assert config.enable_metrics is False
        assert config.max_concurrent_operations == 10
        assert config.operation_timeout_seconds == 600
        assert config.retry_attempts == 5
        assert config.retry_delay_seconds == 10
        assert config.enable_rate_limiting is False
        assert config.rate_limit_requests_per_minute == 120
        assert config.rate_limit_burst_size == 20
        assert config.enable_caching is False
        assert config.cache_ttl_seconds == 7200
        assert config.max_cache_size_mb == 200
        assert config.enable_credential_rotation is True
        assert config.credential_rotation_interval_days == 30
        assert config.enable_encryption is False

    def test_default_provider_validation(self):
        """Test default provider validation."""
        # Valid providers
        valid_providers = ["github", "gitlab", "local"]
        for provider in valid_providers:
            config = SourceControlGlobalConfig(default_provider=provider)
            assert config.default_provider == provider

        # Invalid provider
        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(default_provider="invalid")
        assert "Default provider must be one of" in str(exc_info.value)

    def test_max_concurrent_operations_validation(self):
        """Test max concurrent operations validation."""
        # Valid values
        valid_values = [1, 5, 50, 100]
        for value in valid_values:
            config = SourceControlGlobalConfig(max_concurrent_operations=value)
            assert config.max_concurrent_operations == value

        # Invalid values
        invalid_cases = [
            (0, "Input should be greater than or equal to 1"),
            (101, "Input should be less than or equal to 100"),
        ]

        for invalid_value, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                SourceControlGlobalConfig(max_concurrent_operations=invalid_value)
            assert expected_error in str(exc_info.value)

    def test_rate_limit_validation(self):
        """Test rate limit validation."""
        # Valid values
        config = SourceControlGlobalConfig(
            rate_limit_requests_per_minute=1000, rate_limit_burst_size=100
        )
        assert config.rate_limit_requests_per_minute == 1000
        assert config.rate_limit_burst_size == 100

        # Invalid rate limit
        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(rate_limit_requests_per_minute=0)
        assert "Input should be greater than or equal to 1" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(rate_limit_requests_per_minute=10001)
        assert "Rate limit cannot exceed 10000 requests per minute" in str(
            exc_info.value
        )

        # Invalid burst size
        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(rate_limit_burst_size=0)
        assert "Input should be greater than or equal to 1" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(rate_limit_burst_size=1001)
        assert "Burst size cannot exceed 1000" in str(exc_info.value)

    def test_rate_limiting_config_validation(self):
        """Test rate limiting configuration validation."""
        # Burst size greater than requests per minute should raise error
        with pytest.raises(ValidationError) as exc_info:
            SourceControlGlobalConfig(
                rate_limit_requests_per_minute=10, rate_limit_burst_size=20
            )
        assert "Burst size cannot be greater than requests per minute" in str(
            exc_info.value
        )

    def test_get_effective_credentials(self):
        """Test getting effective credentials."""
        config = SourceControlGlobalConfig()

        # No default credentials
        effective = config.get_effective_credentials(None)
        assert effective is None

        # With default credentials
        default_creds = CredentialConfig(token_env="DEFAULT_TOKEN")
        config.default_credentials = default_creds

        effective = config.get_effective_credentials(None)
        assert effective == default_creds

        # With repository-specific credentials
        repo_creds = CredentialConfig(token_env="REPO_TOKEN")
        effective = config.get_effective_credentials(repo_creds)
        assert effective == repo_creds

    def test_get_effective_remediation_strategy(self):
        """Test getting effective remediation strategy."""
        config = SourceControlGlobalConfig()

        # No default strategy
        effective = config.get_effective_remediation_strategy(None)
        assert isinstance(effective, RemediationStrategyConfig)

        # With default strategy
        default_strategy = RemediationStrategyConfig()
        config.default_remediation_strategy = default_strategy

        effective = config.get_effective_remediation_strategy(None)
        assert effective == default_strategy

        # With repository-specific strategy
        repo_strategy = RemediationStrategyConfig()
        effective = config.get_effective_remediation_strategy(repo_strategy)
        assert effective == repo_strategy

    def test_should_use_caching(self):
        """Test caching check."""
        config = SourceControlGlobalConfig(enable_caching=True)
        assert config.should_use_caching() is True

        config = SourceControlGlobalConfig(enable_caching=False)
        assert config.should_use_caching() is False

    def test_should_use_rate_limiting(self):
        """Test rate limiting check."""
        config = SourceControlGlobalConfig(enable_rate_limiting=True)
        assert config.should_use_rate_limiting() is True

        config = SourceControlGlobalConfig(enable_rate_limiting=False)
        assert config.should_use_rate_limiting() is False


class TestSourceControlConfig:
    """Test cases for SourceControlConfig."""

    def test_empty_repositories_raises_error(self):
        """Test that empty repositories list raises error."""
        with pytest.raises(ValidationError) as exc_info:
            SourceControlConfig(repositories=[])
        assert "At least one repository must be configured" in str(exc_info.value)

    def test_duplicate_repository_names_raises_error(self):
        """Test that duplicate repository names raise error."""
        repo1 = GitHubRepositoryConfig(name="test-repo", url="owner/repo1")
        repo2 = GitHubRepositoryConfig(name="test-repo", url="owner/repo2")

        with pytest.raises(ValidationError) as exc_info:
            SourceControlConfig(repositories=[repo1, repo2])
        assert "Repository names must be unique within a service" in str(exc_info.value)

    def test_valid_repositories(self):
        """Test valid repository configuration."""
        repo1 = GitHubRepositoryConfig(name="repo1", url="owner/repo1")
        repo2 = GitLabRepositoryConfig(
            name="repo2", url="https://gitlab.com/owner/repo2"
        )

        config = SourceControlConfig(repositories=[repo1, repo2])
        assert len(config.repositories) == 2
        assert config.repositories[0].name == "repo1"
        assert config.repositories[1].name == "repo2"

    def test_get_repository_by_name(self):
        """Test getting repository by name."""
        repo1 = GitHubRepositoryConfig(name="repo1", url="owner/repo1")
        repo2 = GitLabRepositoryConfig(
            name="repo2", url="https://gitlab.com/owner/repo2"
        )

        config = SourceControlConfig(repositories=[repo1, repo2])

        # Existing repository
        found_repo = config.get_repository_by_name("repo1")
        assert found_repo == repo1

        found_repo = config.get_repository_by_name("repo2")
        assert found_repo == repo2

        # Non-existing repository
        found_repo = config.get_repository_by_name("non-existing")
        assert found_repo is None

    def test_get_repositories_by_type(self):
        """Test getting repositories by type."""
        repo1 = GitHubRepositoryConfig(name="repo1", url="owner/repo1")
        repo2 = GitLabRepositoryConfig(
            name="repo2", url="https://gitlab.com/owner/repo2"
        )
        repo3 = GitHubRepositoryConfig(name="repo3", url="owner/repo3")

        config = SourceControlConfig(repositories=[repo1, repo2, repo3])

        # GitHub repositories
        github_repos = config.get_repositories_by_type("github")
        assert len(github_repos) == 2
        assert github_repos[0].name == "repo1"
        assert github_repos[1].name == "repo3"

        # GitLab repositories
        gitlab_repos = config.get_repositories_by_type("gitlab")
        assert len(gitlab_repos) == 1
        assert gitlab_repos[0].name == "repo2"

        # Non-existing type
        other_repos = config.get_repositories_by_type("other")
        assert len(other_repos) == 0

    def test_get_repositories_for_path(self):
        """Test getting repositories for a specific path."""
        repo1 = GitHubRepositoryConfig(name="repo1", url="owner/repo1", paths=["/src"])
        repo2 = GitLabRepositoryConfig(
            name="repo2", url="https://gitlab.com/owner/repo2", paths=["/docs"]
        )
        repo3 = GitHubRepositoryConfig(
            name="repo3", url="owner/repo3", paths=["/src", "/config"]
        )

        config = SourceControlConfig(repositories=[repo1, repo2, repo3])

        # Paths that match
        matching_repos = config.get_repositories_for_path("/src/main.py")
        assert len(matching_repos) == 2
        assert matching_repos[0].name == "repo1"
        assert matching_repos[1].name == "repo3"

        matching_repos = config.get_repositories_for_path("/docs/readme.md")
        assert len(matching_repos) == 1
        assert matching_repos[0].name == "repo2"

        matching_repos = config.get_repositories_for_path("/config/settings.yaml")
        assert len(matching_repos) == 1
        assert matching_repos[0].name == "repo3"

        # Path that doesn't match
        matching_repos = config.get_repositories_for_path("/tests/test.py")
        assert len(matching_repos) == 0
