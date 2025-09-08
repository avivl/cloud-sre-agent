from unittest.mock import MagicMock, patch

import pytest
from github import GithubException  # Import GithubException for testing

from gemini_sre_agent.analysis_agent import RemediationPlan
from gemini_sre_agent.remediation_agent import RemediationAgent


@pytest.fixture
def mock_github():
    with patch("gemini_sre_agent.remediation_agent.Github") as mock_github:
        yield mock_github


@pytest.fixture
def remediation_plan_with_code_iac():
    return RemediationPlan(
        root_cause_analysis="The root cause is a simulated bug.",
        proposed_fix="Apply a simulated code patch.",
        code_patch="""# FILE: fix/code_patch.py
def new_feature():
    return "fixed"
""",
    )


@pytest.fixture
def remediation_plan_no_patches():
    return RemediationPlan(
        root_cause_analysis="No code changes needed.",
        proposed_fix="Configuration update.",
        code_patch="",
    )


@pytest.mark.asyncio  # Added async marker
async def test_create_pull_request_with_patches(
    mock_github, remediation_plan_with_code_iac
):  # Changed to async def
    # Arrange
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo

    # Mock get_branch
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    # Mock get_contents for existing files (simulate file not found initially)
    mock_repo.get_contents.side_effect = GithubException(status=404, data={})

    # Mock create_pull
    mock_pull = MagicMock()
    mock_pull.html_url = "https://github.com/owner/repo/pull/1"
    mock_repo.create_pull.return_value = mock_pull

    agent = RemediationAgent(github_token="test-token", repo_name="owner/repo")
    branch_name = "fix/simulated-issue"
    base_branch = "main"

    # Act
    flow_id = "test-flow-001"
    issue_id = "test-issue-001"
    pr_url = await agent.create_pull_request(
        remediation_plan_with_code_iac, branch_name, base_branch, flow_id, issue_id
    )  # Added await

    # Assert
    mock_github.assert_called_once_with("test-token")
    mock_github.return_value.get_repo.assert_called_once_with("owner/repo")
    mock_repo.get_branch.assert_called_once_with(base_branch)
    # Fixed: Use keyword arguments for create_git_ref assertion
    mock_repo.create_git_ref.assert_called_once_with(
        ref=f"refs/heads/{branch_name}", sha="base_sha"
    )

    # Assert file creation
    mock_repo.create_file.assert_called_once_with(
        "fix/code_patch.py",
        "Add service code fix in fix/code_patch.py",
        'def new_feature():\n    return "fixed"',
        branch=branch_name,
    )

    # Assert pull request creation
    expected_title = f"Fix: {remediation_plan_with_code_iac.proposed_fix[:50]}..."
    expected_body = f"Root Cause Analysis:\n{remediation_plan_with_code_iac.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan_with_code_iac.proposed_fix}"
    mock_repo.create_pull.assert_called_once_with(
        title=expected_title, body=expected_body, head=branch_name, base=base_branch
    )
    assert pr_url == "https://github.com/owner/repo/pull/1"


@pytest.mark.asyncio  # Added async marker
async def test_create_pull_request_no_patches(
    mock_github, remediation_plan_no_patches
):  # Changed to async def
    # Arrange
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo

    # Mock get_branch
    mock_branch = MagicMock()
    mock_branch.commit.sha = "base_sha"
    mock_repo.get_branch.return_value = mock_branch

    # Mock create_pull
    mock_pull = MagicMock()
    mock_pull.html_url = "https://github.com/owner/repo/pull/2"
    mock_repo.create_pull.return_value = mock_pull

    agent = RemediationAgent(github_token="test-token", repo_name="owner/repo")
    branch_name = "fix/no-patches"
    base_branch = "main"

    # Act
    flow_id = "test-flow-002"
    issue_id = "test-issue-002"
    pr_url = await agent.create_pull_request(
        remediation_plan_no_patches, branch_name, base_branch, flow_id, issue_id
    )  # Added await

    # Assert
    mock_repo.create_file.assert_not_called()  # No files should be created
    mock_repo.update_file.assert_not_called()  # No files should be updated

    expected_title = f"Fix: {remediation_plan_no_patches.proposed_fix[:50]}..."
    expected_body = f"Root Cause Analysis:\n{remediation_plan_no_patches.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan_no_patches.proposed_fix}"
    mock_repo.create_pull.assert_called_once_with(
        title=expected_title, body=expected_body, head=branch_name, base=base_branch
    )
    assert pr_url == "https://github.com/owner/repo/pull/2"


@pytest.mark.asyncio  # Added async marker
async def test_create_pull_request_github_exception(
    mock_github, remediation_plan_with_code_iac
):  # Changed to async def
    # Arrange
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo

    # Simulate a GitHubException during branch creation
    mock_repo.create_git_ref.side_effect = GithubException(status=422, data={})

    agent = RemediationAgent(github_token="test-token", repo_name="owner/repo")
    branch_name = "fix/simulated-error"
    base_branch = "main"

    # Act & Assert
    flow_id = "test-flow-003"
    issue_id = "test-issue-003"
    with pytest.raises(
        RuntimeError, match="Failed to create pull request due to GitHub API error"
    ):
        await agent.create_pull_request(
            remediation_plan_with_code_iac, branch_name, base_branch, flow_id, issue_id
        )  # Added await

    mock_repo.create_git_ref.assert_called_once()
    mock_repo.create_pull.assert_not_called()  # PR should not be created
