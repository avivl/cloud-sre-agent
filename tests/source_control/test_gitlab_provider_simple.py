"""Simple tests for the GitLab Provider implementation."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from gemini_sre_agent.config.source_control_repositories import GitLabRepositoryConfig
from gemini_sre_agent.source_control.providers.gitlab_provider import GitLabProvider


class TestGitLabProviderSimple:
    """Simple test cases for GitLab Provider."""

    @pytest.fixture
    def gitlab_provider(self):
        """Create a GitLab provider with mocked dependencies."""
        config = GitLabRepositoryConfig(
            name="test-gitlab-repo",
            project_id="123456",
            url="https://gitlab.com/test/repo",
        )

        provider = GitLabProvider(config.model_dump())
        provider.gl = MagicMock()
        provider.project = MagicMock()
        provider.credentials = MagicMock()

        return provider

    @pytest.mark.asyncio
    async def test_initialization(self, gitlab_provider):
        """Test provider initialization."""
        assert gitlab_provider.repo_config.name == "test-gitlab-repo"
        assert gitlab_provider.repo_config.project_id == "123456"
        assert gitlab_provider.gl is not None
        assert gitlab_provider.project is not None

    @pytest.mark.asyncio
    async def test_test_connection_success(self, gitlab_provider):
        """Test successful connection test."""
        gitlab_provider.gl.user = MagicMock()
        result = await gitlab_provider.test_connection()
        assert result is True

    @pytest.mark.asyncio
    async def test_test_connection_failure(self, gitlab_provider):
        """Test failed connection test."""
        gitlab_provider.gl = None
        result = await gitlab_provider.test_connection()
        assert result is False

    @pytest.mark.asyncio
    async def test_get_repository_info(self, gitlab_provider):
        """Test getting repository information."""
        gitlab_provider.project.name = "test-project"
        gitlab_provider.project.web_url = "https://gitlab.com/test/project"
        gitlab_provider.project.default_branch = "main"
        gitlab_provider.project.description = "Test project"
        gitlab_provider.project.visibility = "private"
        gitlab_provider.project.namespace = {"full_path": "test/project"}

        info = await gitlab_provider.get_repository_info()

        assert info.name == "test-project"
        assert info.url == "https://gitlab.com/test/project"
        assert info.owner == "test"
        assert info.is_private is True
        assert info.default_branch == "main"

    @pytest.mark.asyncio
    async def test_get_capabilities(self, gitlab_provider):
        """Test getting provider capabilities."""
        capabilities = await gitlab_provider.get_capabilities()

        assert capabilities.supports_merge_requests is True
        assert capabilities.supports_direct_commits is True
        assert capabilities.supports_patch_generation is True
        assert capabilities.supports_branch_operations is True
        assert capabilities.supports_file_history is True
        assert capabilities.supports_batch_operations is True

    @pytest.mark.asyncio
    async def test_get_health_status_healthy(self, gitlab_provider):
        """Test health status when healthy."""
        gitlab_provider.test_connection = AsyncMock(return_value=True)

        health = await gitlab_provider.get_health_status()

        assert health.status == "healthy"
        assert "operational" in health.message

    @pytest.mark.asyncio
    async def test_get_health_status_unhealthy(self, gitlab_provider):
        """Test health status when unhealthy."""
        gitlab_provider.test_connection = AsyncMock(return_value=False)

        health = await gitlab_provider.get_health_status()

        assert health.status == "unhealthy"
        assert "connection failed" in health.message
