import pytest
from unittest.mock import patch
from gemini_sre_agent.analysis_agent import AnalysisAgent, RemediationPlan
from gemini_sre_agent.triage_agent import TriagePacket

@pytest.fixture
def mock_aiplatform():
    with patch('gemini_sre_agent.analysis_agent.aiplatform') as mock_aiplatform:
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
        natural_language_summary="The billing service is experiencing a high rate of 500 errors."
    )

def test_analyze_issue(mock_aiplatform, triage_packet):
    # Arrange
    agent = AnalysisAgent(
        project_id="test-project",
        location="us-central1",
        analysis_model="gemini-1.5-pro-001"
    )
    historical_logs = ["log1", "log2"]
    configs = {"main.tf": "..."}

    # Act
    remediation_plan = agent.analyze_issue(triage_packet, historical_logs, configs)

    # Assert
    assert isinstance(remediation_plan, RemediationPlan)
    assert remediation_plan.root_cause_analysis == "The root cause of the issue is a memory leak in the billing service."
    assert remediation_plan.proposed_fix == "The proposed fix is to patch the memory leak."