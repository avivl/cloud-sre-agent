import pytest
import os
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import patch

from gemini_sre_agent.triage_agent import TriageAgent, TriagePacket
from gemini_sre_agent.analysis_agent import AnalysisAgent, RemediationPlan
from gemini_sre_agent.remediation_agent import RemediationAgent
from gemini_sre_agent.config import load_config

# --- Fixtures for Configuration and Credentials ---

@pytest.fixture(scope="session")
def integration_config():
    # Load the main config file
    config = load_config()
    return config.gemini_cloud_log_monitor

@pytest.fixture(scope="session")
def gcp_project_id(integration_config):
    # Use the project_id from the first service in the config for integration tests
    # In a real scenario, you might want a dedicated test project ID
    return integration_config.services[0].project_id

@pytest.fixture(scope="session")
def gcp_location(integration_config):
    # Use the location from the first service in the config
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
    triage_model = integration_config.default_model_selection.triage_model
    agent = TriageAgent(project_id=gcp_project_id, location=gcp_location, triage_model=triage_model)

    # Use a realistic, but simple, log entry for testing
    sample_log = {
        "insertId": "1234567890abcdef",
        "logName": "projects/your-gcp-project/logs/cloud_run_events",
        "receiveTimestamp": "2025-08-31T10:00:00.000Z",
        "resource": {"type": "cloud_run_revision", "labels": {"service_name": "my-test-service"}},
        "severity": "ERROR",
        "textPayload": "Error: Failed to connect to database. Connection refused.",
        "timestamp": "2025-08-31T09:59:58.123Z"
    }
    logs = [json.dumps(sample_log)]

    # Call the actual Gemini API
    flow_id = "test-integration-flow-001"
    triage_packet = await agent.analyze_logs(logs, flow_id)

    # Assertions for a successful triage (adjust expectations based on model behavior)
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
async def test_analysis_agent_live_call(gcp_project_id, gcp_location, integration_config):
    analysis_model = integration_config.default_model_selection.analysis_model
    agent = AnalysisAgent(project_id=gcp_project_id, location=gcp_location, analysis_model=analysis_model)

    # Create a dummy TriagePacket for analysis
    dummy_triage_packet = TriagePacket(
        issue_id="test-analysis-issue-1",
        initial_timestamp="2025-08-31T10:00:00Z",
        detected_pattern="High CPU usage in web server",
        preliminary_severity_score=7,
        affected_services=["web-service"],
        sample_log_entries=["CPU utilization 95%", "High load average"],
        natural_language_summary="Web service experiencing high CPU, potentially impacting performance."
    )

    # Sample historical logs and configs (can be empty for basic test)
    historical_logs = [
        "2025-08-31T09:50:00Z - INFO - Web server started",
        "2025-08-31T09:55:00Z - WARN - High CPU alert triggered",
        "2025-08-31T10:00:00Z - ERROR - Request timeout on /api/data"
    ]
    configs = {"nginx.conf": "worker_processes auto;", "app.py": "import time; time.sleep(10)"}

    # Call the actual Gemini API
    remediation_plan = await agent.analyze_issue(dummy_triage_packet, historical_logs, configs)

    # Assertions for a successful analysis (adjust expectations based on model behavior)
    assert isinstance(remediation_plan, RemediationPlan)
    assert remediation_plan.root_cause_analysis is not None
    assert remediation_plan.proposed_fix is not None
    # code_patch and iac_fix might be empty if the model determines no code/iac change is needed
    # assert remediation_plan.code_patch is not None
    # assert remediation_plan.iac_fix is not None

@pytest.mark.integration
@pytest.mark.asyncio
async def test_remediation_agent_live_github(github_token, github_repo_name, github_base_branch):
    # This test will create a real branch and PR on GitHub.
    # It is highly recommended to use a dedicated test repository for this.

    agent = RemediationAgent(github_token=github_token, repo_name=github_repo_name)

    # Create a unique branch name for each test run
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    branch_name = f"test-fix-integration-{timestamp}"

    # Create a dummy remediation plan with some content
    remediation_plan = RemediationPlan(
        root_cause_analysis=f"Integration test: Simulated root cause for {branch_name}",
        proposed_fix=f"Integration test: Apply a dummy fix for {branch_name}",
        code_patch=f"# FILE: {branch_name}/dummy_code.py\nprint(\"Hello from integration test {timestamp}\")",
        iac_fix=f"# FILE: {branch_name}/dummy_iac.tf\nresource \"null_resource\" \"test_iac_{timestamp}\" {{}}"
    )

    pr_url = None
    try:
        pr_url = await agent.create_pull_request(remediation_plan, branch_name, github_base_branch)
        assert pr_url is not None
        assert "https://github.com/" in pr_url
        print(f"Successfully created PR: {pr_url}")

    except Exception as e:
        pytest.fail(f"Failed to create PR: {e}")
    finally:
        # --- Cleanup ---
        # Attempt to close the PR and delete the branch
        if pr_url is not None: 
            try:
                # Extract PR number from URL
                parts = pr_url.split('/') 
                pr_number = int(parts[-1])
                repo = agent.repo
                pull = repo.get_pull(pr_number)
                if pull.state != 'closed':
                    pull.edit(state='closed')
                    print(f"Closed PR: {pr_url}")
            except Exception as e:
                print(f"Warning: Failed to close PR {pr_url}: {e}")

        try:
            # Delete the created branch
            ref_to_delete = f"heads/{branch_name}"
            ref = agent.repo.get_git_ref(ref_to_delete)
            ref.delete()
            print(f"Deleted branch: {branch_name}")
        except Exception as e:
            print(f"Warning: Failed to delete branch {branch_name}: {e}")