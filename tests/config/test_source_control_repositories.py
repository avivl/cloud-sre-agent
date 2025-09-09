# tests/config/test_source_control_repositories.py

"""
Tests for source control repository configuration models.
"""

import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from gemini_sre_agent.config.source_control_remediation import RemediationStrategyConfig
from gemini_sre_agent.config.source_control_repositories import (
    GitHubRepositoryConfig,
    GitLabRepositoryConfig,
    LocalRepositoryConfig,
    RepositoryConfig,
)


class TestRepositoryConfig:
    """Test cases for base RepositoryConfig."""

    def test_minimal_valid_config(self):
        """Test minimal valid configuration."""
        config = RepositoryConfig(
            type="github", name="test-repo", branch="main", paths=["/src"]
        )

        assert config.type == "github"
        assert config.name == "test-repo"
        assert config.branch == "main"
        assert config.paths == ["/src"]
        assert config.credentials is None
        assert isinstance(config.remediation, RemediationStrategyConfig)

    def test_default_values(self):
        """Test default values."""
        config = RepositoryConfig(type="github", name="test-repo")

        assert config.branch == "main"
        assert config.paths == ["/"]
        assert config.credentials is None

    def test_name_validation(self):
        """Test repository name validation."""
        # Valid names
        valid_names = ["test-repo", "test_repo", "test.repo", "test123"]
        for name in valid_names:
            config = RepositoryConfig(type="github", name=name)
            assert config.name == name

        # Invalid names
        invalid_cases = [
            ("", "Repository name cannot be empty"),
            ("a" * 101, "Repository name cannot exceed 100 characters"),
            (
                "invalid@name",
                "Repository name can only contain alphanumeric characters",
            ),
            (
                "invalid name",
                "Repository name can only contain alphanumeric characters",
            ),
        ]

        for invalid_name, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                RepositoryConfig(type="github", name=invalid_name)
            assert expected_error in str(exc_info.value)

    def test_branch_validation(self):
        """Test branch name validation."""
        # Valid branches
        valid_branches = ["main", "develop", "feature/branch", "hotfix-123"]
        for branch in valid_branches:
            config = RepositoryConfig(type="github", name="test", branch=branch)
            assert config.branch == branch

        # Invalid branches
        invalid_cases = [
            ("", "Branch name cannot be empty"),
            ("a" * 256, "Branch name cannot exceed 255 characters"),
            ("invalid@branch", "Branch name can only contain alphanumeric characters"),
        ]

        for invalid_branch, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                RepositoryConfig(type="github", name="test", branch=invalid_branch)
            assert expected_error in str(exc_info.value)

    def test_paths_validation(self):
        """Test paths validation."""
        # Valid paths
        valid_paths = ["/", "/src", "/src/api", "/docs"]
        config = RepositoryConfig(type="github", name="test", paths=valid_paths)
        assert config.paths == valid_paths

        # Invalid paths
        invalid_cases = [
            ([], "At least one path must be specified"),
            ([""], "Paths cannot be empty"),
            (["relative/path"], "Path 'relative/path' must start with '/'"),
            (["/path", ""], "Paths cannot be empty"),
            (["/path", "a" * 501], "Path '{}' must start with '/'".format("a" * 501)),
        ]

        for invalid_paths, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                RepositoryConfig(type="github", name="test", paths=invalid_paths)
            assert expected_error in str(exc_info.value)

    def test_matches_path(self):
        """Test path matching functionality."""
        config = RepositoryConfig(
            type="github", name="test", paths=["/src", "/docs", "/config"]
        )

        # Matching paths
        assert config.matches_path("/src/main.py") is True
        assert config.matches_path("/docs/readme.md") is True
        assert config.matches_path("/config/settings.yaml") is True
        assert config.matches_path("/src/api/endpoint.py") is True

        # Non-matching paths
        assert config.matches_path("/tests/test.py") is False
        assert config.matches_path("/other/file.py") is False


class TestGitHubRepositoryConfig:
    """Test cases for GitHubRepositoryConfig."""

    def test_default_type(self):
        """Test that type is set to github by default."""
        config = GitHubRepositoryConfig(name="test", url="owner/repo")
        assert config.type == "github"

    def test_url_validation(self):
        """Test GitHub URL validation."""
        # Valid URLs
        valid_urls = [
            "owner/repo",
            "user/project-name",
        ]
        for url in valid_urls:
            config = GitHubRepositoryConfig(name="test", url=url)
            assert config.url == url

        # URLs with protocol should be cleaned
        config = GitHubRepositoryConfig(
            name="test", url="https://github.com/owner/repo"
        )
        assert config.url == "owner/repo"

        config = GitHubRepositoryConfig(name="test", url="http://github.com/owner/repo")
        assert config.url == "owner/repo"

        config = GitHubRepositoryConfig(name="test", url="github.com/owner/repo")
        assert config.url == "owner/repo"

        # Invalid URLs
        invalid_cases = [
            ("", "GitHub URL cannot be empty"),
            ("owner", "GitHub URL must be in format 'owner/repo'"),
            ("owner/repo/extra", "GitHub URL must be in format 'owner/repo'"),
            ("owner/", "GitHub URL must have both owner and repository name"),
            ("/repo", "GitHub URL must have both owner and repository name"),
            ("owner@repo", "GitHub URL must be in format 'owner/repo'"),
            ("owner/repo@name", "GitHub repository name contains invalid characters"),
        ]

        for invalid_url, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                GitHubRepositoryConfig(name="test", url=invalid_url)
            assert expected_error in str(exc_info.value)

    def test_api_base_url_validation(self):
        """Test API base URL validation."""
        # Valid URLs
        valid_urls = [
            "https://api.github.com",
            "https://github.company.com/api/v3",
            "http://localhost:3000/api",
        ]
        for url in valid_urls:
            config = GitHubRepositoryConfig(
                name="test", url="owner/repo", api_base_url=url
            )
            assert config.api_base_url == url

        # Invalid URLs
        invalid_cases = [
            ("", "API base URL cannot be empty"),
            ("not-a-url", "API base URL must be a valid URL"),
            ("ftp://api.github.com", "API base URL must use http or https protocol"),
        ]

        for invalid_url, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                GitHubRepositoryConfig(
                    name="test", url="owner/repo", api_base_url=invalid_url
                )
            assert expected_error in str(exc_info.value)

    def test_get_full_url(self):
        """Test getting full GitHub URL."""
        config = GitHubRepositoryConfig(name="test", url="owner/repo")
        assert config.get_full_url() == "https://github.com/owner/repo"

        config = GitHubRepositoryConfig(
            name="test", url="https://github.com/owner/repo"
        )
        assert config.get_full_url() == "https://github.com/owner/repo"

    def test_get_owner_and_repo_name(self):
        """Test getting owner and repository name."""
        config = GitHubRepositoryConfig(name="test", url="owner/repo")
        assert config.get_owner() == "owner"
        assert config.get_repo_name() == "repo"


class TestGitLabRepositoryConfig:
    """Test cases for GitLabRepositoryConfig."""

    def test_default_type(self):
        """Test that type is set to gitlab by default."""
        config = GitLabRepositoryConfig(
            name="test", url="https://gitlab.com/owner/repo"
        )
        assert config.type == "gitlab"

    def test_url_validation(self):
        """Test GitLab URL validation."""
        # Valid URLs
        valid_urls = [
            "https://gitlab.com/owner/repo",
            "https://gitlab.company.com/group/project",
            "http://localhost:8080/user/project",
        ]
        for url in valid_urls:
            config = GitLabRepositoryConfig(name="test", url=url)
            assert config.url == url

        # Invalid URLs
        invalid_cases = [
            ("", "GitLab URL cannot be empty"),
            ("not-a-url", "GitLab URL must be a valid URL"),
            (
                "ftp://gitlab.com/owner/repo",
                "GitLab URL must use http or https protocol",
            ),
        ]

        for invalid_url, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                GitLabRepositoryConfig(name="test", url=invalid_url)
            assert expected_error in str(exc_info.value)

    def test_get_project_id(self):
        """Test getting project ID."""
        config = GitLabRepositoryConfig(
            name="test", url="https://gitlab.com/owner/repo"
        )
        assert config.get_project_id() is None

        config = GitLabRepositoryConfig(
            name="test", url="https://gitlab.com/owner/repo", project_id="123"
        )
        assert config.get_project_id() == "123"


class TestLocalRepositoryConfig:
    """Test cases for LocalRepositoryConfig."""

    def test_default_type(self):
        """Test that type is set to local by default."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = LocalRepositoryConfig(name="test", path=temp_dir)
            assert config.type == "local"

    def test_path_validation(self):
        """Test local path validation."""
        # Valid path
        with tempfile.TemporaryDirectory() as temp_dir:
            config = LocalRepositoryConfig(name="test", path=temp_dir)
            assert config.path == temp_dir

        # Invalid paths
        invalid_cases = [
            ("", "Local repository path cannot be empty"),
            ("relative/path", "Local repository path must be absolute"),
            ("/non/existent/path", "Local repository path does not exist"),
        ]

        for invalid_path, expected_error in invalid_cases:
            with pytest.raises(ValidationError) as exc_info:
                LocalRepositoryConfig(name="test", path=invalid_path)
            assert expected_error in str(exc_info.value)

        # Path that exists but is not a directory
        with tempfile.NamedTemporaryFile() as temp_file:
            with pytest.raises(ValidationError) as exc_info:
                LocalRepositoryConfig(name="test", path=temp_file.name)
            assert "Local repository path is not a directory" in str(exc_info.value)

    def test_get_path(self):
        """Test getting path as Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = LocalRepositoryConfig(name="test", path=temp_dir)
            path_obj = config.get_path()
            assert isinstance(path_obj, Path)
            assert str(path_obj) == temp_dir

    def test_is_git_repository(self):
        """Test Git repository detection."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Not a Git repository
            config = LocalRepositoryConfig(name="test", path=temp_dir)
            assert config.is_git_repository() is False

            # Create .git directory
            git_dir = Path(temp_dir) / ".git"
            git_dir.mkdir()

            config = LocalRepositoryConfig(name="test", path=temp_dir)
            assert config.is_git_repository() is True

            # Git disabled
            config = LocalRepositoryConfig(
                name="test", path=temp_dir, git_enabled=False
            )
            assert config.is_git_repository() is False
