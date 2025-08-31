import pytest
from unittest.mock import patch, MagicMock
from gemini_sre_agent.triage_agent import TriageAgent, TriagePacket

@pytest.fixture
def mock_aiplatform():
    with patch('gemini_sre_agent.triage_agent.aiplatform') as mock_aiplatform:
        yield mock_aiplatform

def test_analyze_logs(mock_aiplatform):
    # Arrange
    agent = TriageAgent(
        project_id="test-project",
        location="us-central1",
        triage_model="gemini-1.5-flash-001"
    )
    logs = ["log entry 1", "log entry 2"]

    # Act
    triage_packet = agent.analyze_logs(logs)

    # Assert
    assert isinstance(triage_packet, TriagePacket)
    assert triage_packet.issue_id == "12345"
    assert triage_packet.affected_services == ["billing-service"]
    assert triage_packet.sample_log_entries == logs