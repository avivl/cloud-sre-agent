import json
import os
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.analysis_agent import AnalysisAgent, RemediationPlan
from gemini_sre_agent.config import load_config
from gemini_sre_agent.remediation_agent import RemediationAgent
from gemini_sre_agent.triage_agent import TriageAgent, TriagePacket

# --- Fixtures for Configuration and Credentials ---


@pytest.fixture(scope="session")
def integration_config():
    """Load config or use mock config if real config is unavailable"""
    try:
        config = load_config()
        return config.gemini_cloud_log_monitor
    except Exception:
        # Use mock config if real config fails to load
        return {
            "services": [
                {
                    "project_id": "test-project",
                    "location": "us-central1",
                    "service_name": "test-service",
                    "subscription_id": "test-subscription",
                }
            ],
            "default_model_selection": {
                "triage_model": "gemini-1.5-flash",
                "analysis_model": "gemini-1.5-pro",
                "classification_model": "gemini-2.5-flash-lite",
            },
            "default_github_config": {"repository": "test/repo", "base_branch": "main"},
        }


@pytest.fixture(scope="session")
def gcp_project_id(integration_config):
    return integration_config.services[0].project_id


@pytest.fixture(scope="session")
def gcp_location(integration_config):
    return integration_config.services[0].location


@pytest.fixture(scope="session")
def github_token():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        pytest.skip("GITHUB_TOKEN environment variable not set for integration tests")
    return token


@pytest.fixture(scope="session")
def github_repo_name(integration_config):
    return integration_config.default_github_config.repository


@pytest.fixture(scope="session")
def github_base_branch(integration_config):
    return integration_config.default_github_config.base_branch


# --- Integration Tests ---


@pytest.mark.integration
@pytest.mark.asyncio
async def test_triage_agent_live_call(gcp_project_id, gcp_location, integration_config):
    """Test triage agent with mocked Gemini API calls"""
    triage_model = integration_config.default_model_selection.triage_model

    # Mock the Gemini model to avoid real API calls
    with patch("gemini_sre_agent.triage_agent.GenerativeModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Mock the generate_content response
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "issue_id": "test-issue-123",
                "initial_timestamp": "2025-08-31T10:00:00Z",
                "detected_pattern": "Database connection failure",
                "preliminary_severity_score": 8,
                "affected_services": ["database-service", "web-service"],
                "sample_log_entries": ["Connection refused", "Timeout error"],
                "natural_language_summary": "Database connection issues causing service failures",
            }
        )
        mock_model.generate_content.return_value = mock_response

        agent = TriageAgent(
            project_id=gcp_project_id, location=gcp_location, triage_model=triage_model
        )

        # Use a realistic, but simple, log entry for testing
        sample_log = {
            "insertId": "1234567890abcdef",
            "logName": "projects/your-gcp-project/logs/cloud_run_events",
            "receiveTimestamp": "2025-08-31T10:00:00.000Z",
            "resource": {
                "type": "cloud_run_revision",
                "labels": {"service_name": "my-test-service"},
            },
            "severity": "ERROR",
            "textPayload": "Error: Failed to connect to database. Connection refused.",
            "timestamp": "2025-08-31T09:59:58.123Z",
        }
        logs = [json.dumps(sample_log)]

        # Call the mocked Gemini API
        flow_id = "test-integration-flow-001"
        triage_packet = await agent.analyze_logs(logs, flow_id)

        # Assertions for a successful triage
        assert isinstance(triage_packet, TriagePacket)
        assert triage_packet.issue_id is not None
        assert triage_packet.initial_timestamp is not None
        assert triage_packet.detected_pattern is not None
        assert 1 <= triage_packet.preliminary_severity_score <= 10
        assert len(triage_packet.affected_services) > 0
        assert len(triage_packet.sample_log_entries) > 0
        assert triage_packet.natural_language_summary is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_analysis_agent_live_call(
    gcp_project_id, gcp_location, integration_config
):
    """Test analysis agent with mocked Gemini API calls"""
    analysis_model = integration_config.default_model_selection.analysis_model

    # Mock the Gemini model to avoid real API calls
    with patch("gemini_sre_agent.analysis_agent.GenerativeModel") as mock_model_class:
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        # Mock the generate_content response
        mock_response = MagicMock()
        mock_response.text = json.dumps(
            {
                "root_cause_analysis": "High CPU usage caused by inefficient database queries",
                "proposed_fix": "Optimize database queries and add connection pooling",
                "code_patch": "# Optimize database connection\npool_size = 20\nmax_overflow = 30",
            }
        )
        mock_model.generate_content.return_value = mock_response

        agent = AnalysisAgent(
            project_id=gcp_project_id,
            location=gcp_location,
            analysis_model=analysis_model,
        )

        # Create a dummy TriagePacket for analysis
        dummy_triage_packet = TriagePacket(
            issue_id="test-analysis-issue-1",
            initial_timestamp="2025-08-31T10:00:00Z",
            detected_pattern="High CPU usage in web server",
            preliminary_severity_score=7,
            affected_services=["web-service"],
            sample_log_entries=["CPU utilization 95%", "High load average"],
            natural_language_summary="Web service experiencing high CPU, potentially impacting performance.",
        )

        # Sample historical logs and configs
        historical_logs = [
            "2025-08-31T09:50:00Z - INFO - Web server started",
            "2025-08-31T09:55:00Z - WARN - High CPU alert triggered",
            "2025-08-31T10:00:00Z - ERROR - Request timeout on /api/data",
        ]
        configs = {
            "nginx.conf": "worker_processes auto;",
            "app.py": "import time; time.sleep(10)",
        }

        # Call the mocked Gemini API
        flow_id = "test-integration-flow-002"
        remediation_plan = agent.analyze_issue(
            dummy_triage_packet, historical_logs, configs, flow_id
        )

        # Assertions for a successful analysis
        assert isinstance(remediation_plan, RemediationPlan)
        assert remediation_plan.root_cause_analysis is not None
        assert remediation_plan.proposed_fix is not None
        assert remediation_plan.code_patch is not None


@pytest.mark.integration
@pytest.mark.asyncio
async def test_remediation_agent_live_github(
    github_token, github_repo_name, github_base_branch
):
    """Test remediation agent with mocked GitHub API calls"""
    # Mock the GitHub API to avoid real API calls
    with patch("gemini_sre_agent.remediation_agent.Github") as mock_github_class:
        mock_github = MagicMock()
        mock_github_class.return_value = mock_github

        # Mock the repository
        mock_repo = MagicMock()
        mock_github.get_repo.return_value = mock_repo

        # Mock the branch creation
        mock_branch_ref = MagicMock()
        mock_repo.get_git_ref.return_value = mock_branch_ref

        # Mock the PR creation
        mock_pull = MagicMock()
        mock_pull.html_url = "https://github.com/test/repo/pull/123"
        mock_repo.create_pull.return_value = mock_pull

        agent = RemediationAgent(github_token=github_token, repo_name=github_repo_name)

        # Create a unique branch name for each test run
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        branch_name = f"test-fix-integration-{timestamp}"

        # Create a dummy remediation plan with some content
        remediation_plan = RemediationPlan(
            root_cause_analysis=f"Integration test: Simulated root cause for {branch_name}",
            proposed_fix=f"Integration test: Apply a dummy fix for {branch_name}",
            code_patch=f'# FILE: {branch_name}/dummy_code.py\nprint("Hello from integration test {timestamp}")',
        )

        try:
            flow_id = "test-integration-flow-003"
            issue_id = f"integration-test-issue-{timestamp}"
            pr_url = await agent.create_pull_request(
                remediation_plan, branch_name, github_base_branch, flow_id, issue_id
            )
            assert pr_url is not None
            assert "https://github.com/" in pr_url
            print(f"Successfully created PR: {pr_url}")

        except Exception as e:
            pytest.fail(f"Failed to create PR: {e}")
        finally:
            # Cleanup is not needed with mocked API calls
            pass
