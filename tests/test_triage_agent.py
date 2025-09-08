import json
from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.triage_agent import TriageAgent, TriagePacket


@pytest.fixture
def mock_aiplatform():
    with patch("gemini_sre_agent.triage_agent.aiplatform") as mock_aiplatform:
        yield mock_aiplatform


@pytest.fixture
def mock_gemini_response():
    return {
        "issue_id": "test-triage-123",
        "initial_timestamp": "2025-08-31T12:00:00Z",
        "detected_pattern": "Simulated high rate of 500 errors",
        "preliminary_severity_score": 7,
        "affected_services": ["test-service"],
        "sample_log_entries": ["test log 1", "test log 2"],
        "natural_language_summary": "Simulated summary of test issue.",
    }


@patch("gemini_sre_agent.triage_agent.GenerativeModel")
@pytest.mark.asyncio
async def test_analyze_logs(
    mock_generative_model, mock_aiplatform, mock_gemini_response
):
    # Arrange
    # Configure the mock GenerativeModel to return a predefined response
    mock_instance = MagicMock()
    mock_instance.generate_content.return_value.text = json.dumps(mock_gemini_response)
    mock_generative_model.return_value = mock_instance

    agent = TriageAgent(
        project_id="test-project",
        location="us-central1",
        triage_model="gemini-1.5-flash-001",
    )
    logs = ["log entry 1", "log entry 2"]

    # Act
    flow_id = "test-flow-001"
    triage_packet = await agent.analyze_logs(logs, flow_id)

    # Assert
    assert isinstance(triage_packet, TriagePacket)
    assert triage_packet.issue_id == mock_gemini_response["issue_id"]
    assert (
        triage_packet.preliminary_severity_score
        == mock_gemini_response["preliminary_severity_score"]
    )
    assert triage_packet.affected_services == mock_gemini_response["affected_services"]
    assert (
        triage_packet.sample_log_entries == mock_gemini_response["sample_log_entries"]
    )
    assert (
        triage_packet.natural_language_summary
        == mock_gemini_response["natural_language_summary"]
    )

    # Verify that generate_content was called with the correct prompt
    expected_prompt_part = "You are an expert SRE Triage Agent"
    mock_instance.generate_content.assert_called_once()
    call_args = mock_instance.generate_content.call_args[0][0]
    assert expected_prompt_part in call_args
    assert "log entry 1" in call_args
    assert "log entry 2" in call_args
