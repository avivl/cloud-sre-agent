# tests/config/test_source_control_remediation.py

"""
Tests for source control remediation strategy configuration models.
"""

import pytest
from pydantic import ValidationError

from gemini_sre_agent.config.source_control_remediation import (
    ConflictResolutionStrategy,
    PatchFormat,
    RemediationStrategy,
    RemediationStrategyConfig,
)


class TestRemediationStrategyConfig:
    """Test cases for RemediationStrategyConfig."""

    def test_default_configuration(self):
        """Test default configuration values."""
        config = RemediationStrategyConfig()

        assert config.strategy == RemediationStrategy.PULL_REQUEST
        assert config.auto_merge is False
        assert config.require_review is True
        assert config.labels == []
        assert config.assignees == []
        assert config.reviewers == []
        assert config.commit_message_template is None
        assert config.commit_author_name is None
        assert config.commit_author_email is None
        assert config.output_path is None
        assert config.format == PatchFormat.UNIFIED
        assert config.include_metadata is True
        assert config.branch_prefix == "sre-fix"
        assert config.branch_suffix is None
        assert config.conflict_resolution == ConflictResolutionStrategy.MANUAL
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 5

    def test_custom_configuration(self):
        """Test custom configuration values."""
        config = RemediationStrategyConfig(
            strategy=RemediationStrategy.DIRECT_COMMIT,
            auto_merge=True,
            require_review=False,
            labels=["bug", "urgent"],
            assignees=["user1", "user2"],
            reviewers=["reviewer1"],
            commit_message_template="Fix: {issue_id} - {description}",
            commit_author_name="SRE Bot",
            commit_author_email="sre@company.com",
            output_path="/tmp/patches",
            format=PatchFormat.GIT,
            include_metadata=False,
            branch_prefix="hotfix",
            branch_suffix="urgent",
            conflict_resolution=ConflictResolutionStrategy.AUTO_MERGE,
            max_retries=5,
            retry_delay_seconds=10,
        )

        assert config.strategy == RemediationStrategy.DIRECT_COMMIT
        assert config.auto_merge is True
        assert config.require_review is False
        assert config.labels == ["bug", "urgent"]
        assert config.assignees == ["user1", "user2"]
        assert config.reviewers == ["reviewer1"]
        assert config.commit_message_template == "Fix: {issue_id} - {description}"
        assert config.commit_author_name == "SRE Bot"
        assert config.commit_author_email == "sre@company.com"
        assert config.output_path == "/tmp/patches"
        assert config.format == PatchFormat.GIT
        assert config.include_metadata is False
        assert config.branch_prefix == "hotfix"
        assert config.branch_suffix == "urgent"
        assert config.conflict_resolution == ConflictResolutionStrategy.AUTO_MERGE
        assert config.max_retries == 5
        assert config.retry_delay_seconds == 10

    def test_label_validation(self):
        """Test label validation."""
        # Valid labels
        config = RemediationStrategyConfig(labels=["bug", "urgent", "sre-fix"])
        assert config.labels == ["bug", "urgent", "sre-fix"]

        # Empty label should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(labels=["", "valid"])
        assert "Labels cannot be empty" in str(exc_info.value)

        # Label too long should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(labels=["a" * 51])
        assert "Labels cannot exceed 50 characters" in str(exc_info.value)

        # Invalid characters should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(labels=["invalid@label"])
        assert "Labels can only contain alphanumeric characters" in str(exc_info.value)

    def test_user_validation(self):
        """Test user validation for assignees and reviewers."""
        # Valid users
        config = RemediationStrategyConfig(
            assignees=["user1", "user2"], reviewers=["reviewer1"]
        )
        assert config.assignees == ["user1", "user2"]
        assert config.reviewers == ["reviewer1"]

        # Empty user should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(assignees=["", "valid"])
        assert "Users cannot be empty" in str(exc_info.value)

        # User too long should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(assignees=["a" * 101])
        assert "Usernames cannot exceed 100 characters" in str(exc_info.value)

    def test_commit_message_template_validation(self):
        """Test commit message template validation."""
        # Valid template
        config = RemediationStrategyConfig(
            commit_message_template="Fix: {issue_id} - {description}"
        )
        assert config.commit_message_template == "Fix: {issue_id} - {description}"

        # Empty template should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(commit_message_template="")
        assert "Commit message template cannot be empty" in str(exc_info.value)

        # Template too long should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(commit_message_template="a" * 501)
        assert "Commit message template cannot exceed 500 characters" in str(
            exc_info.value
        )

        # Missing required placeholders should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(commit_message_template="Fix: {issue_id}")
        assert "Commit message template must include {description}" in str(
            exc_info.value
        )

        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(commit_message_template="Fix: {description}")
        assert "Commit message template must include {issue_id}" in str(exc_info.value)

    def test_output_path_validation(self):
        """Test output path validation."""
        # Valid absolute path
        config = RemediationStrategyConfig(output_path="/tmp/patches")
        assert config.output_path == "/tmp/patches"

        # Empty path should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(output_path="")
        assert "Output path cannot be empty" in str(exc_info.value)

        # Relative path should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(output_path="patches")
        assert "Output path must be absolute" in str(exc_info.value)

    def test_branch_component_validation(self):
        """Test branch prefix and suffix validation."""
        # Valid components
        config = RemediationStrategyConfig(
            branch_prefix="sre-fix", branch_suffix="urgent"
        )
        assert config.branch_prefix == "sre-fix"
        assert config.branch_suffix == "urgent"

        # Empty prefix should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(branch_prefix="")
        assert "Branch component cannot be empty" in str(exc_info.value)

        # Component too long should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(branch_prefix="a" * 21)
        assert "Branch component cannot exceed 20 characters" in str(exc_info.value)

        # Invalid characters should raise error
        with pytest.raises(ValidationError) as exc_info:
            RemediationStrategyConfig(branch_prefix="invalid@prefix")
        assert "Branch components can only contain alphanumeric characters" in str(
            exc_info.value
        )

    def test_get_branch_name(self):
        """Test branch name generation."""
        config = RemediationStrategyConfig(
            branch_prefix="sre-fix", branch_suffix="urgent"
        )

        branch_name = config.get_branch_name("123")
        assert branch_name == "sre-fix-123-urgent"

        # Without suffix
        config_no_suffix = RemediationStrategyConfig(branch_prefix="sre-fix")
        branch_name = config_no_suffix.get_branch_name("456")
        assert branch_name == "sre-fix-456"

    def test_get_commit_message(self):
        """Test commit message generation."""
        config = RemediationStrategyConfig(
            commit_message_template="Fix: {issue_id} - {description}"
        )

        message = config.get_commit_message("123", "Fix critical bug")
        assert message == "Fix: 123 - Fix critical bug"

        # Without template
        config_no_template = RemediationStrategyConfig()
        message = config_no_template.get_commit_message("456", "Fix another bug")
        assert message == "SRE Fix: 456 - Fix another bug"

    def test_strategy_checks(self):
        """Test strategy type checks."""
        # Patch strategy
        patch_config = RemediationStrategyConfig(strategy=RemediationStrategy.PATCH)
        assert patch_config.is_patch_strategy() is True
        assert patch_config.is_direct_commit_strategy() is False
        assert patch_config.requires_branch_creation() is False

        # Direct commit strategy
        direct_config = RemediationStrategyConfig(
            strategy=RemediationStrategy.DIRECT_COMMIT
        )
        assert direct_config.is_patch_strategy() is False
        assert direct_config.is_direct_commit_strategy() is True
        assert direct_config.requires_branch_creation() is False

        # Pull request strategy
        pr_config = RemediationStrategyConfig(strategy=RemediationStrategy.PULL_REQUEST)
        assert pr_config.is_patch_strategy() is False
        assert pr_config.is_direct_commit_strategy() is False
        assert pr_config.requires_branch_creation() is True

        # Merge request strategy
        mr_config = RemediationStrategyConfig(
            strategy=RemediationStrategy.MERGE_REQUEST
        )
        assert mr_config.is_patch_strategy() is False
        assert mr_config.is_direct_commit_strategy() is False
        assert mr_config.requires_branch_creation() is True
