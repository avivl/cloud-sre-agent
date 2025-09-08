import json
from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.analysis_agent import AnalysisAgent, RemediationPlan
from gemini_sre_agent.triage_agent import TriagePacket


@pytest.fixture
def mock_aiplatform():
    with patch("gemini_sre_agent.analysis_agent.aiplatform") as mock_aiplatform:
        yield mock_aiplatform


@pytest.fixture
def triage_packet():
    return TriagePacket(
        issue_id="12345",
        initial_timestamp="2025-08-31T12:00:00Z",
        detected_pattern="High rate of 500 errors",
        preliminary_severity_score=8,
        affected_services=["billing-service"],
        sample_log_entries=["log entry 1", "log entry 2"],
        natural_language_summary="The billing service is experiencing a high rate of 500 errors.",
    )


@pytest.fixture
def mock_gemini_response_analysis():
    return {
        "root_cause_analysis": "Simulated root cause: memory leak in billing service.",
        "proposed_fix": "Simulated fix: apply patch to address memory leak.",
        "code_patch": "def fix_memory_leak():\n    pass",
    }


@patch("gemini_sre_agent.analysis_agent.GenerativeModel")
def test_analyze_issue(
    mock_generative_model, mock_aiplatform, triage_packet, mock_gemini_response_analysis
):
    # Arrange
    # Configure the mock GenerativeModel to return a predefined response
    mock_instance = MagicMock()
    mock_instance.generate_content.return_value.text = json.dumps(
        mock_gemini_response_analysis
    )
    mock_generative_model.return_value = mock_instance

    agent = AnalysisAgent(
        project_id="test-project",
        location="us-central1",
        analysis_model="gemini-1.5-pro-001",
    )
    historical_logs = ["log1", "log2"]
    configs = {"main.tf": "..."}

    # Act
    flow_id = "test-flow-001"
    remediation_plan = agent.analyze_issue(
        triage_packet, historical_logs, configs, flow_id
    )

    # Assert
    assert isinstance(remediation_plan, RemediationPlan)
    assert (
        remediation_plan.root_cause_analysis
        == mock_gemini_response_analysis["root_cause_analysis"]
    )
    assert (
        remediation_plan.proposed_fix == mock_gemini_response_analysis["proposed_fix"]
    )
    assert remediation_plan.code_patch == mock_gemini_response_analysis["code_patch"]
    # Note: iac_fix is no longer part of RemediationPlan in this version

    # Verify that generate_content was called with the correct prompt
    expected_prompt_part = "You are an expert SRE Analysis Agent."
    mock_instance.generate_content.assert_called_once()
    call_args = mock_instance.generate_content.call_args[0][0]
    assert expected_prompt_part in call_args
    assert triage_packet.model_dump_json() in call_args
    assert json.dumps(historical_logs, indent=2) in call_args
    assert json.dumps(configs, indent=2) in call_args
