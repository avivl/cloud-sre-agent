from unittest.mock import MagicMock, patch

import pytest

from gemini_sre_agent.log_ingestion import LogIngestor


@pytest.fixture
def mock_logging_client():
    with patch("gemini_sre_agent.log_ingestion.LoggingServiceV2Client") as mock_client:
        yield mock_client


def test_get_logs(mock_logging_client):
    # Arrange
    mock_client_instance = mock_logging_client.return_value
    mock_client_instance.list_log_entries.return_value = [
        MagicMock(payload="log entry 1"),
        MagicMock(payload="log entry 2"),
    ]
    ingestor = LogIngestor(project_id="test-project")

    # Act
    logs = ingestor.get_logs(filter_str="severity>=ERROR", limit=2)

    # Assert
    assert logs == ["log entry 1", "log entry 2"]
    mock_client_instance.list_log_entries.assert_called_once_with(
        request={
            "resource_names": ["projects/test-project"],
            "filter": "severity>=ERROR",
            "page_size": 2,
        }
    )
