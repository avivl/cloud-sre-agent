# tests/source_control/test_github_utils.py

"""
Tests for GitHub-specific utility functions.

This module contains tests for GitHub utility functions including
URL parsing, branch name sanitization, and error handling.
"""


import pytest

from gemini_sre_agent.source_control.providers.github_utils import (
    extract_github_links,
    format_github_markdown_table,
    format_pull_request_body,
    format_pull_request_title,
    get_github_emoji_for_status,
    parse_github_error,
    parse_github_url,
    sanitize_branch_name,
    sanitize_commit_message,
    validate_github_webhook_signature,
)


class TestParseGitHubUrl:
    """Test GitHub URL parsing functionality."""

    def test_parse_full_https_url(self):
        """Test parsing full HTTPS GitHub URL."""
        owner, repo = parse_github_url("https://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_full_http_url(self):
        """Test parsing full HTTP GitHub URL."""
        owner, repo = parse_github_url("http://github.com/owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_owner_repo_format(self):
        """Test parsing owner/repo format."""
        owner, repo = parse_github_url("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_url_with_trailing_slash(self):
        """Test parsing URL with trailing slash."""
        owner, repo = parse_github_url("https://github.com/owner/repo/")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_url_with_additional_path(self):
        """Test parsing URL with additional path."""
        owner, repo = parse_github_url("https://github.com/owner/repo/issues/123")
        assert owner == "owner"
        assert repo == "repo"

    def test_parse_invalid_url_raises_error(self):
        """Test parsing invalid URL raises error."""
        with pytest.raises(ValueError, match="Not a GitHub URL"):
            parse_github_url("https://gitlab.com/owner/repo")

    def test_parse_invalid_format_raises_error(self):
        """Test parsing invalid format raises error."""
        with pytest.raises(ValueError, match="Invalid GitHub URL format"):
            parse_github_url("https://github.com/owner")

    def test_parse_owner_repo_invalid_format_raises_error(self):
        """Test parsing invalid owner/repo format raises error."""
        with pytest.raises(ValueError, match="Invalid GitHub repository format"):
            parse_github_url("owner")

    def test_parse_invalid_owner_name_raises_error(self):
        """Test parsing invalid owner name raises error."""
        with pytest.raises(ValueError, match="Invalid owner name"):
            parse_github_url("owner@invalid/repo")

    def test_parse_invalid_repo_name_raises_error(self):
        """Test parsing invalid repo name raises error."""
        with pytest.raises(ValueError, match="Invalid repository name"):
            parse_github_url("owner/repo@invalid")


class TestSanitizeBranchName:
    """Test branch name sanitization functionality."""

    def test_sanitize_valid_branch_name(self):
        """Test sanitizing valid branch name."""
        result = sanitize_branch_name("feature-branch")
        assert result == "feature-branch"

    def test_sanitize_branch_name_with_invalid_characters(self):
        """Test sanitizing branch name with invalid characters."""
        result = sanitize_branch_name("feature@branch#with$invalid%chars")
        assert result == "feature-branch-with-invalid-chars"

    def test_sanitize_branch_name_with_consecutive_separators(self):
        """Test sanitizing branch name with consecutive separators."""
        result = sanitize_branch_name("feature--branch..with...separators")
        assert result == "feature-branch-with-separators"

    def test_sanitize_branch_name_with_leading_trailing_separators(self):
        """Test sanitizing branch name with leading/trailing separators."""
        result = sanitize_branch_name("---feature-branch---")
        assert result == "feature-branch"

    def test_sanitize_branch_name_starting_with_dot(self):
        """Test sanitizing branch name starting with dot."""
        result = sanitize_branch_name(".hidden-branch")
        assert result == "branch-hidden-branch"

    def test_sanitize_empty_branch_name(self):
        """Test sanitizing empty branch name."""
        result = sanitize_branch_name("")
        assert result == "branch"

    def test_sanitize_branch_name_too_long(self):
        """Test sanitizing branch name that's too long."""
        long_name = "a" * 300
        result = sanitize_branch_name(long_name)
        assert len(result) == 255

    def test_sanitize_branch_name_with_slashes(self):
        """Test sanitizing branch name with slashes."""
        result = sanitize_branch_name("feature/branch/name")
        assert result == "feature-branch-name"


class TestSanitizeCommitMessage:
    """Test commit message sanitization functionality."""

    def test_sanitize_valid_commit_message(self):
        """Test sanitizing valid commit message."""
        message = "Add new feature"
        result = sanitize_commit_message(message)
        assert result == message

    def test_sanitize_commit_message_with_control_characters(self):
        """Test sanitizing commit message with control characters."""
        message = "Add\x00new\x01feature\x02with\x03control\x04chars"
        result = sanitize_commit_message(message)
        assert result == "Addnewfeaturewithcontrolchars"

    def test_sanitize_empty_commit_message(self):
        """Test sanitizing empty commit message."""
        result = sanitize_commit_message("")
        assert result == "SRE Fix: Automated remediation"

    def test_sanitize_commit_message_with_whitespace_only(self):
        """Test sanitizing commit message with only whitespace."""
        result = sanitize_commit_message("   \n\t   ")
        assert result == "SRE Fix: Automated remediation"

    def test_sanitize_commit_message_too_long_first_line(self):
        """Test sanitizing commit message with too long first line."""
        long_message = "A" * 80 + "\nSecond line"
        result = sanitize_commit_message(long_message)
        assert len(result.split("\n")[0]) == 72
        assert result.endswith("...")

    def test_sanitize_commit_message_preserves_newlines(self):
        """Test sanitizing commit message preserves newlines."""
        message = "First line\nSecond line\nThird line"
        result = sanitize_commit_message(message)
        assert result == message


class TestFormatPullRequestTitle:
    """Test pull request title formatting functionality."""

    def test_format_title_without_issue_id(self):
        """Test formatting title without issue id."""
        result = format_pull_request_title("Fix critical bug")
        assert result == "Fix critical bug"

    def test_format_title_with_issue_id(self):
        """Test formatting title with issue id."""
        result = format_pull_request_title("Fix critical bug", "ISSUE-123")
        assert result == "[ISSUE-123] Fix critical bug"

    def test_format_title_with_empty_issue_id(self):
        """Test formatting title with empty issue id."""
        result = format_pull_request_title("Fix critical bug", "")
        assert result == "Fix critical bug"


class TestFormatPullRequestBody:
    """Test pull request body formatting functionality."""

    def test_format_body_minimal(self):
        """Test formatting minimal body."""
        result = format_pull_request_body("Fix critical bug")
        expected = "**Description:**\nFix critical bug\n\n---\n*This PR was created automatically by the SRE Agent*"
        assert result == expected

    def test_format_body_with_issue_id(self):
        """Test formatting body with issue id."""
        result = format_pull_request_body("Fix critical bug", "ISSUE-123")
        expected = "**Issue ID:** ISSUE-123\n\n**Description:**\nFix critical bug\n\n---\n*This PR was created automatically by the SRE Agent*"
        assert result == expected

    def test_format_body_with_additional_info(self):
        """Test formatting body with additional info."""
        additional_info = {"severity": "high", "component": "auth"}
        result = format_pull_request_body(
            "Fix critical bug", "ISSUE-123", additional_info
        )

        assert "**Issue ID:** ISSUE-123" in result
        assert "**Description:**" in result
        assert "Fix critical bug" in result
        assert "**Additional Information:**" in result
        assert "**severity:** high" in result
        assert "**component:** auth" in result
        assert "*This PR was created automatically by the SRE Agent*" in result


class TestParseGitHubError:
    """Test GitHub error parsing functionality."""

    def test_parse_rate_limit_error(self):
        """Test parsing rate limit error."""
        result = parse_github_error("API rate limit exceeded")
        assert result["type"] == "rate_limit"
        assert result["retryable"] is True

    def test_parse_unauthorized_error(self):
        """Test parsing unauthorized error."""
        result = parse_github_error("Unauthorized access")
        assert result["type"] == "authentication"
        assert result["retryable"] is False

    def test_parse_forbidden_error(self):
        """Test parsing forbidden error."""
        result = parse_github_error("Forbidden access")
        assert result["type"] == "authentication"
        assert result["retryable"] is False

    def test_parse_not_found_error(self):
        """Test parsing not found error."""
        result = parse_github_error("Resource not found")
        assert result["type"] == "not_found"
        assert result["retryable"] is False

    def test_parse_validation_error(self):
        """Test parsing validation error."""
        result = parse_github_error("Validation failed")
        assert result["type"] == "validation"
        assert result["retryable"] is False

    def test_parse_server_error(self):
        """Test parsing server error."""
        result = parse_github_error("Internal server error")
        assert result["type"] == "server_error"
        assert result["retryable"] is True

    def test_parse_unknown_error(self):
        """Test parsing unknown error."""
        result = parse_github_error("Some random error")
        assert result["type"] == "unknown"
        assert result["retryable"] is False


class TestExtractGitHubLinks:
    """Test GitHub link extraction functionality."""

    def test_extract_no_links(self):
        """Test extracting no links from text."""
        result = extract_github_links("No links here")
        assert result == []

    def test_extract_repository_links(self):
        """Test extracting repository links."""
        text = "Check out https://github.com/owner/repo for more info"
        result = extract_github_links(text)
        assert len(result) == 1
        assert result[0]["owner"] == "owner"
        assert result[0]["repo"] == "repo"
        assert result[0]["type"] == "repo"

    def test_extract_issue_links(self):
        """Test extracting issue links."""
        text = "See issue https://github.com/owner/repo/issues/123"
        result = extract_github_links(text)
        assert len(result) == 1
        assert result[0]["owner"] == "owner"
        assert result[0]["repo"] == "repo"
        assert result[0]["type"] == "issue"

    def test_extract_pull_request_links(self):
        """Test extracting pull request links."""
        text = "See PR https://github.com/owner/repo/pulls/456"
        result = extract_github_links(text)
        assert len(result) == 1
        assert result[0]["owner"] == "owner"
        assert result[0]["repo"] == "repo"
        assert result[0]["type"] == "pull"

    def test_extract_commit_links(self):
        """Test extracting commit links."""
        text = "See commit https://github.com/owner/repo/commit/abc123"
        result = extract_github_links(text)
        assert len(result) == 1
        assert result[0]["owner"] == "owner"
        assert result[0]["repo"] == "repo"
        assert result[0]["type"] == "commit"

    def test_extract_multiple_links(self):
        """Test extracting multiple links."""
        text = "See https://github.com/owner1/repo1 and https://github.com/owner2/repo2"
        result = extract_github_links(text)
        assert len(result) == 2
        assert result[0]["owner"] == "owner1"
        assert result[0]["repo"] == "repo1"
        assert result[1]["owner"] == "owner2"
        assert result[1]["repo"] == "repo2"


class TestValidateGitHubWebhookSignature:
    """Test GitHub webhook signature validation functionality."""

    def test_validate_valid_signature(self):
        """Test validating valid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"

        # Generate valid signature
        import hashlib
        import hmac

        signature = hmac.new(
            secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
        ).hexdigest()

        result = validate_github_webhook_signature(
            payload, f"sha256={signature}", secret
        )
        assert result is True

    def test_validate_invalid_signature(self):
        """Test validating invalid signature."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        invalid_signature = "sha256=invalid"

        result = validate_github_webhook_signature(payload, invalid_signature, secret)
        assert result is False

    def test_validate_invalid_signature_format(self):
        """Test validating signature with invalid format."""
        payload = '{"test": "data"}'
        secret = "test_secret"
        invalid_format = "invalid_signature"

        result = validate_github_webhook_signature(payload, invalid_format, secret)
        assert result is False


class TestGetGitHubEmojiForStatus:
    """Test GitHub emoji for status functionality."""

    def test_get_emoji_for_known_status(self):
        """Test getting emoji for known status."""
        assert get_github_emoji_for_status("success") == "✅"
        assert get_github_emoji_for_status("failure") == "❌"
        assert get_github_emoji_for_status("pending") == "⏳"
        assert get_github_emoji_for_status("open") == "🔓"
        assert get_github_emoji_for_status("closed") == "🔒"

    def test_get_emoji_for_unknown_status(self):
        """Test getting emoji for unknown status."""
        assert get_github_emoji_for_status("unknown") == "❓"

    def test_get_emoji_case_insensitive(self):
        """Test getting emoji is case insensitive."""
        assert get_github_emoji_for_status("SUCCESS") == "✅"
        assert get_github_emoji_for_status("Success") == "✅"


class TestFormatGitHubMarkdownTable:
    """Test GitHub markdown table formatting functionality."""

    def test_format_empty_data(self):
        """Test formatting empty data."""
        result = format_github_markdown_table([], [])
        assert result == ""

    def test_format_empty_headers(self):
        """Test formatting with empty headers."""
        result = format_github_markdown_table([{"col1": "val1"}], [])
        assert result == ""

    def test_format_simple_table(self):
        """Test formatting simple table."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob", "age": 25}]
        headers = ["name", "age"]
        result = format_github_markdown_table(data, headers)

        expected = "| name | age |\n| --- | --- |\n| Alice | 30 |\n| Bob | 25 |"
        assert result == expected

    def test_format_table_with_missing_values(self):
        """Test formatting table with missing values."""
        data = [{"name": "Alice", "age": 30}, {"name": "Bob"}]  # Missing age
        headers = ["name", "age"]
        result = format_github_markdown_table(data, headers)

        expected = "| name | age |\n| --- | --- |\n| Alice | 30 |\n| Bob |  |"
        assert result == expected

    def test_format_table_with_pipe_characters(self):
        """Test formatting table with pipe characters in values."""
        data = [{"description": "Fix | bug", "status": "done"}]
        headers = ["description", "status"]
        result = format_github_markdown_table(data, headers)

        expected = "| description | status |\n| --- | --- |\n| Fix \\| bug | done |"
        assert result == expected
