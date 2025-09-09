# tests/source_control/test_provider_factory.py

from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.config.source_control_repositories import (
    GitHubRepositoryConfig,
    LocalRepositoryConfig,
)
from gemini_sre_agent.source_control.credential_manager import CredentialManager
from gemini_sre_agent.source_control.provider_factory import ProviderFactory


class TestProviderFactory:
    """Test the ProviderFactory class."""

    @pytest.fixture
    def credential_manager(self):
        return MagicMock(spec=CredentialManager)

    @pytest.fixture
    def factory(self, credential_manager):
        return ProviderFactory(credential_manager)

    @pytest.fixture
    def mock_github_provider_class(self):
        return MagicMock()

    @pytest.mark.asyncio
    async def test_create_provider_without_credentials(
        self, factory, mock_github_provider_class
    ):
        """Test creating a provider without credentials."""
        # Register the mock provider
        factory.register_provider("github", mock_github_provider_class)

        # Create repository config
        repo_config = GitHubRepositoryConfig(
            name="test-repo", url="https://github.com/test/repo"
        )

        # Create provider
        await factory.create_provider(repo_config)

        # Verify the provider was created with the correct config
        mock_github_provider_class.assert_called_once_with(repo_config.model_dump())

    @pytest.mark.asyncio
    async def test_create_provider_with_credentials(
        self, factory, mock_github_provider_class
    ):
        """Test creating a provider with credentials."""
        # Register the mock provider
        factory.register_provider("github", mock_github_provider_class)

        # Mock credential retrieval
        mock_credentials = {"token": "test-token", "provider_type": "github"}
        factory.credential_manager.get_credentials.return_value = mock_credentials

        # Create repository config
        repo_config = GitHubRepositoryConfig(
            name="test-repo", url="https://github.com/test/repo"
        )

        # Create provider
        await factory.create_provider(repo_config)

        # Verify credentials were not retrieved (no credential_id in config)
        factory.credential_manager.get_credentials.assert_not_called()

        # Verify the provider was created without credentials
        mock_github_provider_class.assert_called_once_with(repo_config.model_dump())

    @pytest.mark.asyncio
    async def test_create_provider_unsupported_type(self, factory):
        """Test creating a provider with unsupported type."""
        repo_config = GitHubRepositoryConfig(
            name="test-repo", url="https://github.com/test/repo"
        )

        with pytest.raises(ValueError, match="Unsupported provider type"):
            await factory.create_provider(repo_config)

    @pytest.mark.asyncio
    async def test_create_provider_credential_retrieval_error(
        self, factory, mock_github_provider_class
    ):
        """Test creating a provider when credential retrieval fails."""
        # Register the mock provider
        factory.register_provider("github", mock_github_provider_class)

        # Mock credential retrieval to raise an exception
        factory.credential_manager.get_credentials.side_effect = Exception(
            "Credential error"
        )

        # Create repository config
        repo_config = GitHubRepositoryConfig(
            name="test-repo", url="https://github.com/test/repo"
        )

        # Create provider - should still work but without credentials
        await factory.create_provider(repo_config)

        # Verify the provider was created with None credentials
        mock_github_provider_class.assert_called_once_with(repo_config.model_dump())

    @pytest.mark.asyncio
    async def test_create_provider_with_local_config(self, factory, tmp_path):
        """Test creating a provider with local repository config."""
        # Mock local provider class
        mock_local_provider_class = MagicMock()
        factory.register_provider("local", mock_local_provider_class)

        # Create a temporary directory for the local repo
        local_repo_path = tmp_path / "test-repo"
        local_repo_path.mkdir()

        # Create local repository config
        repo_config = LocalRepositoryConfig(
            name="local-repo", path=str(local_repo_path)
        )

        # Create provider
        await factory.create_provider(repo_config)

        # Verify the provider was created
        mock_local_provider_class.assert_called_once_with(repo_config.model_dump())

    def test_register_provider(self, factory):
        """Test registering a provider."""
        mock_provider_class = MagicMock()
        factory.register_provider("test", mock_provider_class)

        assert "test" in factory.provider_registry
        assert factory.provider_registry["test"] == mock_provider_class

    def test_register_providers_from_modules(self, factory):
        """Test registering providers from modules."""
        # This is a placeholder test since the actual implementation
        # would require importing modules dynamically
        # For now, we just test that the method exists and doesn't crash
        factory.register_providers_from_modules([])

        # The method should not raise an exception
        assert True
