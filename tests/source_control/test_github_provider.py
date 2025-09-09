# tests/source_control/test_github_provider.py

"""
Tests for GitHub provider implementation.

This module contains comprehensive tests for the GitHubProvider class,
including unit tests, integration tests, and error handling tests.
"""

import base64
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.config.source_control_credentials import CredentialConfig
from gemini_sre_agent.config.source_control_repositories import GitHubRepositoryConfig
from gemini_sre_agent.source_control.models import OperationStatus
from gemini_sre_agent.source_control.providers.github_provider import GitHubProvider


@pytest.fixture
def github_credentials():
    """Create test GitHub credentials."""
    return CredentialConfig(token="test_token_123")


@pytest.fixture
def repository_config():
    """Create test repository configuration."""
    return GitHubRepositoryConfig(name="test-repo", url="owner/repo", branch="main")


@pytest.fixture
def github_provider(github_credentials, repository_config):
    """Create test GitHub provider."""
    return GitHubProvider(repository_config, github_credentials)


class TestGitHubProviderInitialization:
    """Test GitHub provider initialization."""

    def test_init_with_credentials(self, github_credentials, repository_config):
        """Test initialization with credentials."""
        provider = GitHubProvider(repository_config, github_credentials)
        assert provider.repo_config == repository_config
        assert provider.credentials == github_credentials
        assert provider.base_url == repository_config.api_base_url

    def test_init_without_credentials_raises_error(self, repository_config):
        """Test initialization without credentials raises error."""
        with pytest.raises(ValueError, match="GitHub credentials are required"):
            GitHubProvider(repository_config, None)

    def test_init_with_invalid_credentials_raises_error(self, repository_config):
        """Test initialization with invalid credentials raises error."""
        invalid_creds = CredentialConfig()  # No token provided
        GitHubProvider(repository_config, invalid_creds)

        with pytest.raises(ValueError, match="GitHub token is required"):
            # This will be raised during _setup_client
            pass


class TestGitHubProviderConnection:
    """Test GitHub provider connection methods."""

    @pytest.mark.asyncio
    async def test_setup_client_success(self, github_provider):
        """Test successful client setup."""
        with patch("github.Github") as mock_github_class:
            mock_github = MagicMock()
            mock_repo = MagicMock()
            mock_github.get_repo.return_value = mock_repo
            mock_github_class.return_value = mock_github

            await github_provider._setup_client()

            assert github_provider.client is not None
            assert github_provider.repo is not None
            mock_github_class.assert_called_once_with(
                base_url=github_provider.base_url, login_or_token="test_token_123"
            )

    @pytest.mark.asyncio
    async def test_setup_client_without_token_raises_error(self, repository_config):
        """Test client setup without token raises error."""
        invalid_creds = CredentialConfig()  # No token
        provider = GitHubProvider(repository_config, invalid_creds)

        with pytest.raises(ValueError, match="GitHub token is required"):
            await provider._setup_client()

    @pytest.mark.asyncio
    async def test_teardown_client(self, github_provider):
        """Test client teardown."""
        # Setup mocks
        github_provider.client = MagicMock()
        github_provider.session = AsyncMock()

        await github_provider._teardown_client()

        github_provider.client.close.assert_called_once()
        github_provider.session.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_test_connection_success(self, github_provider):
        """Test successful connection test."""
        mock_repo = MagicMock()
        mock_branch = MagicMock()
        mock_repo.get_branches.return_value = [mock_branch]
        github_provider.repo = mock_repo

        result = await github_provider.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, github_provider):
        """Test failed connection test."""
        mock_repo = MagicMock()
        mock_repo.get_branches.side_effect = Exception("Connection failed")
        github_provider.repo = mock_repo

        result = await github_provider.test_connection()
        assert result is False


class TestGitHubProviderFileOperations:
    """Test GitHub provider file operations."""

    @pytest.mark.asyncio
    async def test_get_file_content_success(self, github_provider):
        """Test successful file content retrieval."""
        mock_repo = MagicMock()
        mock_content = MagicMock()
        mock_content.content = base64.b64encode(b"file content").decode("utf-8")
        mock_repo.get_contents.return_value = mock_content
        github_provider.repo = mock_repo

        content = await github_provider.get_file_content("path/to/file.txt")

        assert content == "file content"
        mock_repo.get_contents.assert_called_once_with("path/to/file.txt", ref="main")

    @pytest.mark.asyncio
    async def test_get_file_content_with_ref(self, github_provider):
        """Test file content retrieval with specific ref."""
        mock_repo = MagicMock()
        mock_content = MagicMock()
        mock_content.content = base64.b64encode(b"file content").decode("utf-8")
        mock_repo.get_contents.return_value = mock_content
        github_provider.repo = mock_repo

        content = await github_provider.get_file_content(
            "path/to/file.txt", "feature-branch"
        )

        assert content == "file content"
        mock_repo.get_contents.assert_called_once_with(
            "path/to/file.txt", ref="feature-branch"
        )

    @pytest.mark.asyncio
    async def test_get_file_content_not_found(self, github_provider):
        """Test file content retrieval when file not found."""
        from github import GithubException

        mock_repo = MagicMock()
        mock_repo.get_contents.side_effect = GithubException(404, "Not found")
        github_provider.repo = mock_repo

        with pytest.raises(FileNotFoundError, match="File path/to/file.txt not found"):
            await github_provider.get_file_content("path/to/file.txt")

    @pytest.mark.asyncio
    async def test_get_file_content_directory_raises_error(self, github_provider):
        """Test file content retrieval for directory raises error."""
        mock_repo = MagicMock()
        mock_repo.get_contents.return_value = [MagicMock()]  # List indicates directory
        github_provider.repo = mock_repo

        with pytest.raises(
            ValueError, match="Path path/to/dir is a directory, not a file"
        ):
            await github_provider.get_file_content("path/to/dir")


class TestGitHubProviderBranchOperations:
    """Test GitHub provider branch operations."""

    @pytest.mark.asyncio
    async def test_create_branch_success(self, github_provider):
        """Test successful branch creation."""
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_ref.object.sha = "abc123"
        mock_repo.get_git_ref.return_value = mock_ref
        github_provider.repo = mock_repo

        result = await github_provider.create_branch("new-feature")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("heads/main")
        mock_repo.create_git_ref.assert_called_once_with(
            "refs/heads/new-feature", "abc123"
        )

    @pytest.mark.asyncio
    async def test_create_branch_with_base_ref(self, github_provider):
        """Test branch creation with specific base ref."""
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_ref.object.sha = "def456"
        mock_repo.get_git_ref.return_value = mock_ref
        github_provider.repo = mock_repo

        result = await github_provider.create_branch("new-feature", "develop")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("heads/develop")
        mock_repo.create_git_ref.assert_called_once_with(
            "refs/heads/new-feature", "def456"
        )

    @pytest.mark.asyncio
    async def test_delete_branch_success(self, github_provider):
        """Test successful branch deletion."""
        mock_repo = MagicMock()
        mock_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_ref
        github_provider.repo = mock_repo

        result = await github_provider.delete_branch("old-feature")

        assert result is True
        mock_repo.get_git_ref.assert_called_once_with("heads/old-feature")
        mock_ref.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_branch_not_found(self, github_provider):
        """Test branch deletion when branch not found."""
        from github import GithubException

        mock_repo = MagicMock()
        mock_repo.get_git_ref.side_effect = GithubException(404, "Not found")
        github_provider.repo = mock_repo

        result = await github_provider.delete_branch("nonexistent-branch")

        assert result is False

    @pytest.mark.asyncio
    async def test_list_branches_success(self, github_provider):
        """Test successful branch listing."""
        mock_repo = MagicMock()
        mock_branch1 = MagicMock()
        mock_branch1.name = "main"
        mock_branch2 = MagicMock()
        mock_branch2.name = "feature"
        mock_repo.get_branches.return_value = [mock_branch1, mock_branch2]
        github_provider.repo = mock_repo

        branches = await github_provider.list_branches()

        assert branches == ["main", "feature"]


class TestGitHubProviderRemediation:
    """Test GitHub provider remediation operations."""

    @pytest.mark.asyncio
    async def test_apply_remediation_success(self, github_provider):
        """Test successful remediation application."""
        mock_repo = MagicMock()

        # Mock branch creation
        mock_ref = MagicMock()
        mock_ref.object.sha = "abc123"
        mock_repo.get_git_ref.return_value = mock_ref

        # Mock file update
        mock_file = MagicMock()
        mock_file.sha = "file-sha-123"
        mock_repo.get_contents.return_value = mock_file

        # Mock PR creation
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.html_url = "https://github.com/owner/repo/pull/123"
        mock_pr.head.sha = "pr-sha-456"
        mock_repo.create_pull.return_value = mock_pr

        github_provider.repo = mock_repo

        result = await github_provider.apply_remediation(
            "path/to/file.py", "print('Hello, World!')", "Fix critical bug"
        )

        assert result.success is True
        assert result.status == OperationStatus.SUCCESS
        assert result.commit_id == "pr-sha-456"
        assert "Created PR #123" in result.message
        assert result.details["pull_request_number"] == 123

    @pytest.mark.asyncio
    async def test_apply_remediation_create_new_file(self, github_provider):
        """Test remediation application for new file."""
        from github import GithubException

        mock_repo = MagicMock()

        # Mock branch creation
        mock_ref = MagicMock()
        mock_ref.object.sha = "abc123"
        mock_repo.get_git_ref.return_value = mock_ref

        # Mock file not found (404), then successful creation
        mock_repo.get_contents.side_effect = [
            GithubException(404, "Not found"),  # First call fails
            None,  # Second call succeeds
        ]

        # Mock PR creation
        mock_pr = MagicMock()
        mock_pr.number = 123
        mock_pr.html_url = "https://github.com/owner/repo/pull/123"
        mock_pr.head.sha = "pr-sha-456"
        mock_repo.create_pull.return_value = mock_pr

        github_provider.repo = mock_repo

        result = await github_provider.apply_remediation(
            "path/to/newfile.py", "print('Hello, World!')", "Add new feature"
        )

        assert result.success is True
        mock_repo.create_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_remediation_failure(self, github_provider):
        """Test remediation application failure."""
        mock_repo = MagicMock()
        mock_repo.get_git_ref.side_effect = Exception("Network error")
        github_provider.repo = mock_repo

        result = await github_provider.apply_remediation(
            "path/to/file.py", "print('Hello, World!')", "Fix critical bug"
        )

        assert result.success is False
        assert result.status == OperationStatus.FAILURE
        assert "Network error" in result.error


class TestGitHubProviderRepositoryInfo:
    """Test GitHub provider repository information."""

    @pytest.mark.asyncio
    async def test_get_repository_info_success(self, github_provider):
        """Test successful repository info retrieval."""
        mock_repo = MagicMock()
        mock_repo.name = "test-repo"
        mock_repo.owner.login = "test-owner"
        mock_repo.default_branch = "main"
        mock_repo.html_url = "https://github.com/test-owner/test-repo"
        mock_repo.private = False
        mock_repo.created_at = datetime(2023, 1, 1)
        mock_repo.updated_at = datetime(2023, 12, 1)
        mock_repo.description = "Test repository"
        mock_repo.language = "Python"
        mock_repo.stargazers_count = 42
        mock_repo.forks_count = 5
        github_provider.repo = mock_repo

        info = await github_provider.get_repository_info()

        assert info.name == "test-repo"
        assert info.owner == "test-owner"
        assert info.default_branch == "main"
        assert info.url == "https://github.com/test-owner/test-repo"
        assert info.is_private is False
        assert info.description == "Test repository"
        assert info.additional_info["language"] == "Python"
        assert info.additional_info["stars"] == 42
        assert info.additional_info["forks"] == 5


class TestGitHubProviderBatchOperations:
    """Test GitHub provider batch operations."""

    @pytest.mark.asyncio
    async def test_batch_operations_success(self, github_provider):
        """Test successful batch operations."""
        from gemini_sre_agent.source_control.models import BatchOperation

        # Mock the apply_remediation method
        with patch.object(
            github_provider, "apply_remediation", return_value=MagicMock(success=True)
        ):
            with patch.object(github_provider, "create_branch", return_value=True):
                operations = [
                    BatchOperation(
                        operation_type="update_file",
                        path="file1.py",
                        content="content1",
                        message="Update file1",
                    ),
                    BatchOperation(
                        operation_type="create_branch",
                        parameters={"name": "new-branch"},
                    ),
                ]

                results = await github_provider.batch_operations(operations)

                assert len(results) == 2
                assert all(status == OperationStatus.SUCCESS for status in results)

    @pytest.mark.asyncio
    async def test_batch_operations_with_failures(self, github_provider):
        """Test batch operations with some failures."""
        from gemini_sre_agent.source_control.models import BatchOperation

        operations = [
            BatchOperation(
                operation_type="update_file",
                path=None,  # Invalid - will cause failure
                content="content1",
                message="Update file1",
            ),
            BatchOperation(
                operation_type="unknown_operation"  # Invalid operation type
            ),
        ]

        results = await github_provider.batch_operations(operations)

        assert len(results) == 2
        assert all(status == OperationStatus.FAILURE for status in results)


class TestGitHubProviderCapabilities:
    """Test GitHub provider capabilities."""

    @pytest.mark.asyncio
    async def test_get_capabilities(self, github_provider):
        """Test getting provider capabilities."""
        capabilities = await github_provider.get_capabilities()

        assert capabilities["supports_branches"] is True
        assert capabilities["supports_pull_requests"] is True
        assert capabilities["supports_file_operations"] is True
        assert capabilities["supports_batch_operations"] is True
        assert capabilities["supports_conflict_detection"] is False
        assert capabilities["supports_auto_merge"] is True
        assert capabilities["max_file_size"] == 100 * 1024 * 1024
        assert capabilities["rate_limit_requests_per_hour"] == 5000

    @pytest.mark.asyncio
    async def test_validate_credentials_success(self, github_provider):
        """Test successful credential validation."""
        with patch.object(github_provider, "test_connection", return_value=True):
            result = await github_provider.validate_credentials()
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_credentials_failure(self, github_provider):
        """Test failed credential validation."""
        with patch.object(github_provider, "test_connection", return_value=False):
            result = await github_provider.validate_credentials()
            assert result is False

    @pytest.mark.asyncio
    async def test_refresh_credentials(self, github_provider):
        """Test credential refresh."""
        result = await github_provider.refresh_credentials()
        assert result is True  # Token-based auth doesn't need refreshing


class TestGitHubProviderErrorHandling:
    """Test GitHub provider error handling."""

    @pytest.mark.asyncio
    async def test_handle_operation_failure_rate_limit(self, github_provider):
        """Test handling rate limit errors."""
        from github import GithubException

        error = GithubException(403, "API rate limit exceeded")
        result = await github_provider.handle_operation_failure("test_operation", error)

        assert result is True  # Should retry

    @pytest.mark.asyncio
    async def test_handle_operation_failure_not_found(self, github_provider):
        """Test handling not found errors."""
        from github import GithubException

        error = GithubException(404, "Not found")
        result = await github_provider.handle_operation_failure("test_operation", error)

        assert result is False  # Should not retry

    @pytest.mark.asyncio
    async def test_handle_operation_failure_server_error(self, github_provider):
        """Test handling server errors."""
        from github import GithubException

        error = GithubException(500, "Internal server error")
        result = await github_provider.handle_operation_failure("test_operation", error)

        assert result is True  # Should retry

    @pytest.mark.asyncio
    async def test_handle_operation_failure_other_error(self, github_provider):
        """Test handling other errors."""
        error = Exception("Some other error")
        result = await github_provider.handle_operation_failure("test_operation", error)

        assert result is False  # Should not retry
