# tests/source_control/test_setup.py

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.config.source_control_global import (
    SourceControlConfig,
    SourceControlGlobalConfig,
)
from gemini_sre_agent.source_control.setup import (
    create_default_config,
    setup_repository_system,
)


class TestSetupRepositorySystem:
    """Test the setup_repository_system function."""

    @pytest.fixture
    def mock_config(self):

        return SourceControlGlobalConfig(
            default_credentials=None, default_remediation_strategy=None
        )

    @pytest.mark.asyncio
    async def test_setup_with_encryption_key(self, mock_config):
        """Test setting up repository system with encryption key."""
        with patch(
            "gemini_sre_agent.source_control.setup.RepositoryManager"
        ) as mock_repo_manager_class:
            mock_repo_manager = AsyncMock()
            mock_repo_manager_class.return_value = mock_repo_manager

            result = await setup_repository_system(mock_config, "test-encryption-key")

            assert result == mock_repo_manager
            mock_repo_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_without_encryption_key(self, mock_config):
        """Test setting up repository system without encryption key."""
        with patch(
            "gemini_sre_agent.source_control.setup.RepositoryManager"
        ) as mock_repo_manager_class:
            mock_repo_manager = AsyncMock()
            mock_repo_manager_class.return_value = mock_repo_manager

            result = await setup_repository_system(mock_config, None)

            assert result == mock_repo_manager
            mock_repo_manager.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_setup_credential_manager_configuration(self, mock_config):
        """Test that credential manager is properly configured."""
        with patch(
            "gemini_sre_agent.source_control.setup.CredentialManager"
        ) as mock_cred_manager_class:
            mock_cred_manager = MagicMock()
            mock_cred_manager_class.return_value = mock_cred_manager

            with patch(
                "gemini_sre_agent.source_control.setup.ProviderFactory"
            ) as mock_factory_class:
                mock_factory = MagicMock()
                mock_factory_class.return_value = mock_factory

                with patch(
                    "gemini_sre_agent.source_control.setup.RepositoryManager"
                ) as mock_repo_manager_class:
                    mock_repo_manager = AsyncMock()
                    mock_repo_manager_class.return_value = mock_repo_manager

                    await setup_repository_system(mock_config, "test-key")

                    # Verify credential manager was created with encryption key
                    mock_cred_manager_class.assert_called_once_with(
                        encryption_key="test-key"
                    )

                    # Verify backends were registered
                    assert mock_cred_manager.register_backend.call_count == 2

                    # Verify provider factory was created with credential manager
                    mock_factory_class.assert_called_once_with(mock_cred_manager)

    @pytest.mark.asyncio
    async def test_setup_provider_registration(self, mock_config):
        """Test that providers are properly registered."""
        with patch("gemini_sre_agent.source_control.setup.CredentialManager"):
            with patch(
                "gemini_sre_agent.source_control.setup.ProviderFactory"
            ) as mock_factory_class:
                mock_factory = MagicMock()
                mock_factory_class.return_value = mock_factory

                with patch(
                    "gemini_sre_agent.source_control.setup.RepositoryManager"
                ) as mock_repo_manager_class:
                    mock_repo_manager = AsyncMock()
                    mock_repo_manager_class.return_value = mock_repo_manager
                    await setup_repository_system(mock_config)

                    # Verify providers were registered
                    assert mock_factory.register_provider.call_count == 1
                    mock_factory.register_provider.assert_any_call(
                        "github", mock_factory.register_provider.call_args_list[0][0][1]
                    )


class TestCreateDefaultConfig:
    """Test the create_default_config function."""

    def test_create_default_config(self):
        """Test creating default configuration."""
        config = create_default_config()

        assert isinstance(config, SourceControlConfig)
        assert len(config.repositories) == 1

        # Check GitHub repository
        github_repo = config.repositories[0]
        assert github_repo.name == "test-github-repo"
        assert github_repo.url == "test/repo"

    def test_create_default_config_repository_types(self):
        """Test that default config creates correct repository types."""
        config = create_default_config()

        from gemini_sre_agent.config.source_control_repositories import (
            GitHubRepositoryConfig,
        )

        assert isinstance(config.repositories[0], GitHubRepositoryConfig)

    def test_create_default_config_immutable(self):
        """Test that default config can be created multiple times independently."""
        config1 = create_default_config()
        config2 = create_default_config()

        # They should be different instances
        assert config1 is not config2
        assert config1.repositories is not config2.repositories
