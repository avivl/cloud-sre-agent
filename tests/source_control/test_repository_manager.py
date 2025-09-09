# tests/source_control/test_repository_manager.py

from unittest.mock import AsyncMock, MagicMock

import pytest

from gemini_sre_agent.config.source_control_global import SourceControlGlobalConfig
from gemini_sre_agent.source_control.provider_factory import ProviderFactory
from gemini_sre_agent.source_control.repository_manager import RepositoryManager


class TestRepositoryManager:
    """Test the RepositoryManager class."""

    @pytest.fixture
    def mock_provider_factory(self):
        return MagicMock(spec=ProviderFactory)

    @pytest.fixture
    def mock_global_config(self):
        return SourceControlGlobalConfig(
            default_credentials=None, default_remediation_strategy=None
        )

    @pytest.fixture
    def repository_manager(self, mock_global_config, mock_provider_factory):
        return RepositoryManager(mock_global_config, mock_provider_factory)

    @pytest.fixture
    def mock_provider(self):
        provider = AsyncMock()
        provider.__aenter__ = AsyncMock(return_value=provider)
        provider.__aexit__ = AsyncMock(return_value=None)
        provider.test_connection = AsyncMock(return_value=True)
        provider.get_repository_info = AsyncMock(return_value={"name": "test-repo"})
        provider.list_branches = AsyncMock(return_value=[])
        provider.apply_remediation = AsyncMock(return_value={"success": True})
        return provider

    @pytest.mark.asyncio
    async def test_initialization_success(
        self, repository_manager, mock_provider_factory, mock_provider
    ):
        """Test successful repository initialization."""
        # For now, this tests the placeholder implementation
        await repository_manager.initialize()

        # The placeholder implementation doesn't create any repositories
        assert len(repository_manager.repositories) == 0

    @pytest.mark.asyncio
    async def test_initialization_failure(
        self, repository_manager, mock_provider_factory
    ):
        """Test repository initialization failure."""
        # For now, this tests the placeholder implementation
        # which doesn't raise exceptions
        await repository_manager.initialize()

        # The placeholder implementation should complete successfully
        assert len(repository_manager.repositories) == 0

    @pytest.mark.asyncio
    async def test_close(self, repository_manager, mock_provider):
        """Test closing repository connections."""
        repository_manager.repositories["test-repo"] = mock_provider

        await repository_manager.close()

        assert len(repository_manager.repositories) == 0

    @pytest.mark.asyncio
    async def test_get_provider_success(self, repository_manager, mock_provider):
        """Test getting a valid provider."""
        repository_manager.repositories["test-repo"] = mock_provider

        result = await repository_manager.get_provider("test-repo")

        assert result == mock_provider

    @pytest.mark.asyncio
    async def test_get_provider_not_found(self, repository_manager):
        """Test getting a non-existent provider."""
        with pytest.raises(ValueError, match="Repository 'nonexistent' not found"):
            await repository_manager.get_provider("nonexistent")

    @pytest.mark.asyncio
    async def test_execute_across_repos_all_repos(
        self, repository_manager, mock_provider
    ):
        """Test executing operation across all repositories."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        async def test_operation(provider):
            return await provider.test_connection()

        results = await repository_manager.execute_across_repos(test_operation)

        assert len(results) == 2
        assert "repo1" in results
        assert "repo2" in results
        assert results["repo1"] is True
        assert results["repo2"] is True

    @pytest.mark.asyncio
    async def test_execute_across_repos_specific_repos(
        self, repository_manager, mock_provider
    ):
        """Test executing operation across specific repositories."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        async def test_operation(provider):
            return await provider.test_connection()

        results = await repository_manager.execute_across_repos(
            test_operation, ["repo1"]
        )

        assert len(results) == 1
        assert "repo1" in results
        assert "repo2" not in results

    @pytest.mark.asyncio
    async def test_execute_across_repos_with_error(
        self, repository_manager, mock_provider
    ):
        """Test executing operation with errors."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        # Make one provider fail
        mock_provider.test_connection.side_effect = [
            True,
            Exception("Connection failed"),
        ]

        async def test_operation(provider):
            return await provider.test_connection()

        results = await repository_manager.execute_across_repos(test_operation)

        assert len(results) == 2
        assert results["repo1"] is True
        assert "error" in results["repo2"]
        assert "Connection failed" in results["repo2"]["error"]

    @pytest.mark.asyncio
    async def test_execute_across_repos_skip_nonexistent(
        self, repository_manager, mock_provider
    ):
        """Test executing operation skips non-existent repositories."""
        repository_manager.repositories = {"repo1": mock_provider}

        async def test_operation(provider):
            return await provider.test_connection()

        results = await repository_manager.execute_across_repos(
            test_operation, ["repo1", "nonexistent"]
        )

        assert len(results) == 1
        assert "repo1" in results
        assert "nonexistent" not in results

    @pytest.mark.asyncio
    async def test_health_check(self, repository_manager, mock_provider):
        """Test health check across repositories."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        results = await repository_manager.health_check()

        assert len(results) == 2
        assert results["repo1"] is True
        assert results["repo2"] is True

    @pytest.mark.asyncio
    async def test_get_repository_info_success(self, repository_manager, mock_provider):
        """Test getting repository info successfully."""
        repository_manager.repositories["test-repo"] = mock_provider

        result = await repository_manager.get_repository_info("test-repo")

        assert result == {"name": "test-repo"}
        mock_provider.get_repository_info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_repository_info_failure(self, repository_manager, mock_provider):
        """Test getting repository info with failure."""
        repository_manager.repositories["test-repo"] = mock_provider
        mock_provider.get_repository_info.side_effect = Exception(
            "Info retrieval failed"
        )

        result = await repository_manager.get_repository_info("test-repo")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_all_branches(self, repository_manager, mock_provider):
        """Test listing branches across repositories."""
        from datetime import datetime

        from gemini_sre_agent.source_control.models import BranchInfo

        mock_branches = [
            BranchInfo(
                name="main", sha="abc123", is_protected=True, last_commit=datetime.now()
            ),
            BranchInfo(
                name="feature",
                sha="def456",
                is_protected=False,
                last_commit=datetime.now(),
            ),
        ]
        mock_provider.list_branches.return_value = mock_branches

        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        results = await repository_manager.list_all_branches()

        assert len(results) == 2
        assert "repo1" in results
        assert "repo2" in results
        assert results["repo1"] == ["main", "feature"]
        assert results["repo2"] == ["main", "feature"]

    @pytest.mark.asyncio
    async def test_apply_remediation_across_repos(
        self, repository_manager, mock_provider
    ):
        """Test applying remediation across repositories."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        results = await repository_manager.apply_remediation_across_repos(
            "test.py", "new content", "test message"
        )

        assert len(results) == 2
        assert "repo1" in results
        assert "repo2" in results
        assert results["repo1"]["success"] is True
        assert results["repo2"]["success"] is True

    @pytest.mark.asyncio
    async def test_apply_remediation_with_error(
        self, repository_manager, mock_provider
    ):
        """Test applying remediation with errors."""
        repository_manager.repositories = {
            "repo1": mock_provider,
            "repo2": mock_provider,
        }

        # Make one provider fail
        mock_provider.apply_remediation.side_effect = [
            {"success": True},
            Exception("Apply failed"),
        ]

        results = await repository_manager.apply_remediation_across_repos(
            "test.py", "new content", "test message"
        )

        assert len(results) == 2
        assert results["repo1"]["success"] is True
        assert "error" in results["repo2"]
        assert "Apply failed" in results["repo2"]["error"]

    def test_initialization_with_empty_config(self):
        """Test initialization with empty configuration."""
        empty_config = SourceControlGlobalConfig(
            default_credentials=None, default_remediation_strategy=None
        )
        factory = MagicMock()
        manager = RepositoryManager(empty_config, factory)

        # Should not raise an exception
        assert len(manager.repositories) == 0

    def test_logger_initialization(self, repository_manager):
        """Test that logger is properly initialized."""
        assert repository_manager.logger is not None
        assert (
            repository_manager.logger.name
            == "gemini_sre_agent.source_control.repository_manager"
        )
