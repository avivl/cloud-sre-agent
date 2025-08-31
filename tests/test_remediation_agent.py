import pytest
from unittest.mock import patch, MagicMock
from gemini_sre_agent.remediation_agent import RemediationAgent
from gemini_sre_agent.analysis_agent import RemediationPlan

@pytest.fixture
def mock_github():
    with patch('gemini_sre_agent.remediation_agent.Github') as mock_github:
        yield mock_github

@pytest.fixture
def remediation_plan():
    return RemediationPlan(
        root_cause_analysis="The root cause of the issue is a memory leak in the billing service.",
        proposed_fix="The proposed fix is to patch the memory leak.",
        code_patch="...",
        iac_fix="..."
    )

def test_create_pull_request(mock_github, remediation_plan):
    # Arrange
    mock_repo = MagicMock()
    mock_github.return_value.get_repo.return_value = mock_repo
    agent = RemediationAgent(github_token="test-token", repo_name="owner/repo")

    # Act
    agent.create_pull_request(remediation_plan, "fix/memory-leak", "main")

    # Assert
    mock_github.assert_called_once_with("test-token")
    mock_github.return_value.get_repo.assert_called_once_with("owner/repo")
    # In a real implementation, we would assert that the correct GitHub API
    # methods were called with the correct parameters.