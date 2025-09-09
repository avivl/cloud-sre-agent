# tests/source_control/test_github_models.py

"""
Tests for GitHub-specific data models.

This module contains tests for GitHub-specific data models including
GitHubCredentials, PullRequestInfo, and other GitHub-related structures.
"""

from datetime import datetime

import pytest

from gemini_sre_agent.source_control.providers.github_models import (
    GitHubAuthType,
    GitHubBranchInfo,
    GitHubCommitInfo,
    GitHubCredentials,
    GitHubFileInfo,
    GitHubIssueInfo,
    GitHubRepositoryInfo,
    GitHubWebhookInfo,
    MergeMethod,
    PullRequestInfo,
    PullRequestStatus,
)


class TestGitHubAuthType:
    """Test GitHub authentication type enum."""

    def test_auth_type_values(self):
        """Test authentication type enum values."""
        assert GitHubAuthType.TOKEN == "token"
        assert GitHubAuthType.APP == "app"


class TestGitHubCredentials:
    """Test GitHub credentials model."""

    def test_token_credentials_valid(self):
        """Test valid token credentials."""
        creds = GitHubCredentials(
            auth_type=GitHubAuthType.TOKEN, token="test_token_123"
        )
        assert creds.auth_type == GitHubAuthType.TOKEN
        assert creds.token == "test_token_123"
        assert creds.app_id is None
        assert creds.private_key is None

    def test_app_credentials_valid(self):
        """Test valid app credentials."""
        creds = GitHubCredentials(
            auth_type=GitHubAuthType.APP,
            app_id="12345",
            private_key="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
        )
        assert creds.auth_type == GitHubAuthType.APP
        assert creds.app_id == "12345"
        assert (
            creds.private_key
            == "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
        )
        assert creds.token is None

    def test_token_credentials_missing_token_raises_error(self):
        """Test token credentials without token raises error."""
        with pytest.raises(
            ValueError, match="Token is required when auth_type is 'token'"
        ):
            GitHubCredentials(auth_type=GitHubAuthType.TOKEN)

    def test_app_credentials_missing_app_id_raises_error(self):
        """Test app credentials without app_id raises error."""
        with pytest.raises(
            ValueError,
            match="app_id and private_key are required when auth_type is 'app'",
        ):
            GitHubCredentials(
                auth_type=GitHubAuthType.APP,
                private_key="-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----",
            )

    def test_app_credentials_missing_private_key_raises_error(self):
        """Test app credentials without private_key raises error."""
        with pytest.raises(
            ValueError,
            match="app_id and private_key are required when auth_type is 'app'",
        ):
            GitHubCredentials(auth_type=GitHubAuthType.APP, app_id="12345")

    def test_credentials_with_api_url(self):
        """Test credentials with custom API URL."""
        creds = GitHubCredentials(
            auth_type=GitHubAuthType.TOKEN,
            token="test_token",
            api_url="https://github.company.com/api/v3",
        )
        assert creds.api_url == "https://github.company.com/api/v3"


class TestPullRequestStatus:
    """Test pull request status enum."""

    def test_status_values(self):
        """Test pull request status enum values."""
        assert PullRequestStatus.OPEN == "open"
        assert PullRequestStatus.CLOSED == "closed"
        assert PullRequestStatus.MERGED == "merged"
        assert PullRequestStatus.DRAFT == "draft"


class TestMergeMethod:
    """Test merge method enum."""

    def test_merge_method_values(self):
        """Test merge method enum values."""
        assert MergeMethod.MERGE == "merge"
        assert MergeMethod.SQUASH == "squash"
        assert MergeMethod.REBASE == "rebase"


class TestPullRequestInfo:
    """Test pull request info model."""

    def test_pull_request_info_minimal(self):
        """Test minimal pull request info."""
        pr = PullRequestInfo(
            id=123,
            title="Test PR",
            url="https://github.com/owner/repo/pull/123",
            status=PullRequestStatus.OPEN,
            head_branch="feature-branch",
            base_branch="main",
        )

        assert pr.id == 123
        assert pr.title == "Test PR"
        assert pr.url == "https://github.com/owner/repo/pull/123"
        assert pr.status == PullRequestStatus.OPEN
        assert pr.head_branch == "feature-branch"
        assert pr.base_branch == "main"
        assert pr.author is None
        assert pr.created_at is None
        assert pr.updated_at is None
        assert pr.merged_at is None
        assert pr.mergeable is None
        assert pr.mergeable_state is None
        assert pr.draft is False
        assert pr.labels == []
        assert pr.reviewers == []
        assert pr.assignees == []
        assert pr.additional_info == {}

    def test_pull_request_info_complete(self):
        """Test complete pull request info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)
        merged_at = datetime(2023, 1, 3, 12, 0, 0)

        pr = PullRequestInfo(
            id=123,
            title="Test PR",
            url="https://github.com/owner/repo/pull/123",
            status=PullRequestStatus.MERGED,
            head_branch="feature-branch",
            base_branch="main",
            author="testuser",
            created_at=created_at,
            updated_at=updated_at,
            merged_at=merged_at,
            mergeable=True,
            mergeable_state="clean",
            draft=False,
            labels=["enhancement", "bug"],
            reviewers=["reviewer1", "reviewer2"],
            assignees=["assignee1"],
            additional_info={"checks": "passed"},
        )

        assert pr.id == 123
        assert pr.title == "Test PR"
        assert pr.status == PullRequestStatus.MERGED
        assert pr.author == "testuser"
        assert pr.created_at == created_at
        assert pr.updated_at == updated_at
        assert pr.merged_at == merged_at
        assert pr.mergeable is True
        assert pr.mergeable_state == "clean"
        assert pr.labels == ["enhancement", "bug"]
        assert pr.reviewers == ["reviewer1", "reviewer2"]
        assert pr.assignees == ["assignee1"]
        assert pr.additional_info == {"checks": "passed"}


class TestGitHubBranchInfo:
    """Test GitHub branch info model."""

    def test_branch_info_minimal(self):
        """Test minimal branch info."""
        branch = GitHubBranchInfo(name="main", commit_id="abc123", protected=True)

        assert branch.name == "main"
        assert branch.commit_id == "abc123"
        assert branch.protected is True
        assert branch.protection_rules is None
        assert branch.last_commit is None
        assert branch.ahead_count == 0
        assert branch.behind_count == 0

    def test_branch_info_complete(self):
        """Test complete branch info."""
        branch = GitHubBranchInfo(
            name="feature-branch",
            commit_id="def456",
            protected=False,
            protection_rules={"required_status_checks": True},
            last_commit={"message": "Latest commit"},
            ahead_count=5,
            behind_count=2,
        )

        assert branch.name == "feature-branch"
        assert branch.commit_id == "def456"
        assert branch.protected is False
        assert branch.protection_rules == {"required_status_checks": True}
        assert branch.last_commit == {"message": "Latest commit"}
        assert branch.ahead_count == 5
        assert branch.behind_count == 2


class TestGitHubFileInfo:
    """Test GitHub file info model."""

    def test_file_info_minimal(self):
        """Test minimal file info."""
        file_info = GitHubFileInfo(
            path="src/main.py",
            size=1024,
            sha="file-sha-123",
            content_type="text/plain",
            is_binary=False,
        )

        assert file_info.path == "src/main.py"
        assert file_info.size == 1024
        assert file_info.sha == "file-sha-123"
        assert file_info.content_type == "text/plain"
        assert file_info.is_binary is False
        assert file_info.download_url is None
        assert file_info.html_url is None
        assert file_info.git_url is None
        assert file_info.last_modified is None
        assert file_info.additional_info == {}

    def test_file_info_complete(self):
        """Test complete file info."""
        last_modified = datetime(2023, 1, 1, 12, 0, 0)

        file_info = GitHubFileInfo(
            path="src/main.py",
            size=1024,
            sha="file-sha-123",
            content_type="text/plain",
            is_binary=False,
            download_url="https://github.com/owner/repo/raw/main/src/main.py",
            html_url="https://github.com/owner/repo/blob/main/src/main.py",
            git_url="https://api.github.com/repos/owner/repo/git/blobs/file-sha-123",
            last_modified=last_modified,
            additional_info={"language": "Python"},
        )

        assert file_info.path == "src/main.py"
        assert (
            file_info.download_url
            == "https://github.com/owner/repo/raw/main/src/main.py"
        )
        assert (
            file_info.html_url == "https://github.com/owner/repo/blob/main/src/main.py"
        )
        assert (
            file_info.git_url
            == "https://api.github.com/repos/owner/repo/git/blobs/file-sha-123"
        )
        assert file_info.last_modified == last_modified
        assert file_info.additional_info == {"language": "Python"}


class TestGitHubRepositoryInfo:
    """Test GitHub repository info model."""

    def test_repository_info_minimal(self):
        """Test minimal repository info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 12, 1, 12, 0, 0)

        repo = GitHubRepositoryInfo(
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            default_branch="main",
            url="https://github.com/test-owner/test-repo",
            html_url="https://github.com/test-owner/test-repo",
            clone_url="https://github.com/test-owner/test-repo.git",
            ssh_url="git@github.com:test-owner/test-repo.git",
            is_private=False,
            created_at=created_at,
            updated_at=updated_at,
        )

        assert repo.name == "test-repo"
        assert repo.owner == "test-owner"
        assert repo.full_name == "test-owner/test-repo"
        assert repo.default_branch == "main"
        assert repo.url == "https://github.com/test-owner/test-repo"
        assert repo.html_url == "https://github.com/test-owner/test-repo"
        assert repo.clone_url == "https://github.com/test-owner/test-repo.git"
        assert repo.ssh_url == "git@github.com:test-owner/test-repo.git"
        assert repo.is_private is False
        assert repo.created_at == created_at
        assert repo.updated_at == updated_at
        assert repo.description is None
        assert repo.language is None
        assert repo.stars == 0
        assert repo.forks == 0
        assert repo.watchers == 0
        assert repo.open_issues == 0
        assert repo.license is None
        assert repo.topics == []
        assert repo.additional_info == {}

    def test_repository_info_complete(self):
        """Test complete repository info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 12, 1, 12, 0, 0)

        repo = GitHubRepositoryInfo(
            name="test-repo",
            owner="test-owner",
            full_name="test-owner/test-repo",
            default_branch="main",
            url="https://github.com/test-owner/test-repo",
            html_url="https://github.com/test-owner/test-repo",
            clone_url="https://github.com/test-owner/test-repo.git",
            ssh_url="git@github.com:test-owner/test-repo.git",
            is_private=True,
            created_at=created_at,
            updated_at=updated_at,
            description="A test repository",
            language="Python",
            stars=42,
            forks=5,
            watchers=10,
            open_issues=3,
            license="MIT",
            topics=["python", "testing"],
            additional_info={"archived": False},
        )

        assert repo.description == "A test repository"
        assert repo.language == "Python"
        assert repo.stars == 42
        assert repo.forks == 5
        assert repo.watchers == 10
        assert repo.open_issues == 3
        assert repo.license == "MIT"
        assert repo.topics == ["python", "testing"]
        assert repo.additional_info == {"archived": False}


class TestGitHubCommitInfo:
    """Test GitHub commit info model."""

    def test_commit_info_minimal(self):
        """Test minimal commit info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)

        commit = GitHubCommitInfo(
            sha="abc123",
            message="Initial commit",
            author="testuser",
            author_email="test@example.com",
            committer="testuser",
            committer_email="test@example.com",
            created_at=created_at,
            url="https://api.github.com/repos/owner/repo/commits/abc123",
            html_url="https://github.com/owner/repo/commit/abc123",
        )

        assert commit.sha == "abc123"
        assert commit.message == "Initial commit"
        assert commit.author == "testuser"
        assert commit.author_email == "test@example.com"
        assert commit.committer == "testuser"
        assert commit.committer_email == "test@example.com"
        assert commit.created_at == created_at
        assert commit.url == "https://api.github.com/repos/owner/repo/commits/abc123"
        assert commit.html_url == "https://github.com/owner/repo/commit/abc123"
        assert commit.parents == []
        assert commit.stats is None
        assert commit.files == []
        assert commit.additional_info == {}

    def test_commit_info_complete(self):
        """Test complete commit info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)

        commit = GitHubCommitInfo(
            sha="abc123",
            message="Add new feature",
            author="testuser",
            author_email="test@example.com",
            committer="testuser",
            committer_email="test@example.com",
            created_at=created_at,
            url="https://api.github.com/repos/owner/repo/commits/abc123",
            html_url="https://github.com/owner/repo/commit/abc123",
            parents=["def456"],
            stats={"additions": 10, "deletions": 2},
            files=[{"filename": "src/main.py", "status": "modified"}],
            additional_info={"verified": True},
        )

        assert commit.parents == ["def456"]
        assert commit.stats == {"additions": 10, "deletions": 2}
        assert commit.files == [{"filename": "src/main.py", "status": "modified"}]
        assert commit.additional_info == {"verified": True}


class TestGitHubWebhookInfo:
    """Test GitHub webhook info model."""

    def test_webhook_info_minimal(self):
        """Test minimal webhook info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)

        webhook = GitHubWebhookInfo(
            id=123,
            name="web",
            events=["push", "pull_request"],
            active=True,
            config={"url": "https://example.com/webhook"},
            url="https://api.github.com/repos/owner/repo/hooks/123",
            created_at=created_at,
            updated_at=updated_at,
        )

        assert webhook.id == 123
        assert webhook.name == "web"
        assert webhook.events == ["push", "pull_request"]
        assert webhook.active is True
        assert webhook.config == {"url": "https://example.com/webhook"}
        assert webhook.url == "https://api.github.com/repos/owner/repo/hooks/123"
        assert webhook.created_at == created_at
        assert webhook.updated_at == updated_at
        assert webhook.last_response is None
        assert webhook.additional_info == {}

    def test_webhook_info_complete(self):
        """Test complete webhook info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)

        webhook = GitHubWebhookInfo(
            id=123,
            name="web",
            events=["push", "pull_request"],
            active=True,
            config={"url": "https://example.com/webhook", "secret": "secret123"},
            url="https://api.github.com/repos/owner/repo/hooks/123",
            created_at=created_at,
            updated_at=updated_at,
            last_response={"code": 200, "message": "OK"},
            additional_info={"deliveries": 42},
        )

        assert webhook.last_response == {"code": 200, "message": "OK"}
        assert webhook.additional_info == {"deliveries": 42}


class TestGitHubIssueInfo:
    """Test GitHub issue info model."""

    def test_issue_info_minimal(self):
        """Test minimal issue info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)

        issue = GitHubIssueInfo(
            id=123,
            title="Test issue",
            body="This is a test issue",
            state="open",
            author="testuser",
            created_at=created_at,
            updated_at=updated_at,
        )

        assert issue.id == 123
        assert issue.title == "Test issue"
        assert issue.body == "This is a test issue"
        assert issue.state == "open"
        assert issue.author == "testuser"
        assert issue.created_at == created_at
        assert issue.updated_at == updated_at
        assert issue.closed_at is None
        assert issue.labels == []
        assert issue.assignees == []
        assert issue.milestone is None
        assert issue.comments == 0
        assert issue.url == ""
        assert issue.html_url == ""
        assert issue.additional_info == {}

    def test_issue_info_complete(self):
        """Test complete issue info."""
        created_at = datetime(2023, 1, 1, 12, 0, 0)
        updated_at = datetime(2023, 1, 2, 12, 0, 0)
        closed_at = datetime(2023, 1, 3, 12, 0, 0)

        issue = GitHubIssueInfo(
            id=123,
            title="Test issue",
            body="This is a test issue",
            state="closed",
            author="testuser",
            created_at=created_at,
            updated_at=updated_at,
            closed_at=closed_at,
            labels=["bug", "high-priority"],
            assignees=["assignee1", "assignee2"],
            milestone="v1.0",
            comments=5,
            url="https://api.github.com/repos/owner/repo/issues/123",
            html_url="https://github.com/owner/repo/issues/123",
            additional_info={"locked": False},
        )

        assert issue.state == "closed"
        assert issue.closed_at == closed_at
        assert issue.labels == ["bug", "high-priority"]
        assert issue.assignees == ["assignee1", "assignee2"]
        assert issue.milestone == "v1.0"
        assert issue.comments == 5
        assert issue.url == "https://api.github.com/repos/owner/repo/issues/123"
        assert issue.html_url == "https://github.com/owner/repo/issues/123"
        assert issue.additional_info == {"locked": False}
