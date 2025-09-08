import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from google.cloud.pubsub_v1.subscriber.message import Message

from gemini_sre_agent.log_subscriber import LogSubscriber


@pytest.fixture
def mock_pubsub_subscriber_client():
    with patch(
        "gemini_sre_agent.log_subscriber.pubsub_v1.SubscriberClient"
    ) as MockSubscriberClient:
        mock_instance = MockSubscriberClient.return_value
        mock_instance.subscription_path.return_value = (
            "projects/test-project/subscriptions/test-subscription"
        )
        yield mock_instance


@pytest.fixture
def mock_triage_callback():  # Removed async def, will return AsyncMock directly
    # Return an AsyncMock directly
    mock = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_log_subscriber_init(mock_pubsub_subscriber_client):
    subscriber = LogSubscriber("test-project", "test-subscription")
    mock_pubsub_subscriber_client.subscription_path.assert_called_with(
        "test-project", "test-subscription"
    )
    assert (
        subscriber.subscription_path
        == "projects/test-project/subscriptions/test-subscription"
    )


@pytest.mark.asyncio
async def test_log_subscriber_process_message_success(
    mock_pubsub_subscriber_client, mock_triage_callback
):
    subscriber = LogSubscriber(
        "test-project", "test-subscription", triage_callback=mock_triage_callback
    )

    test_log_data = {"insertId": "abc-123", "textPayload": "Test log entry"}
    mock_message = MagicMock(spec=Message)
    mock_message.data = json.dumps(test_log_data).encode("utf-8")
    mock_message.message_id = "msg-1"

    await subscriber._process_message(mock_message)

    mock_triage_callback.assert_awaited_once_with(test_log_data)
    mock_message.ack.assert_called_once()
    mock_message.nack.assert_not_called()


@pytest.mark.asyncio
async def test_log_subscriber_process_message_json_error(
    mock_pubsub_subscriber_client, mock_triage_callback
):
    subscriber = LogSubscriber(
        "test-project", "test-subscription", triage_callback=mock_triage_callback
    )

    mock_message = MagicMock(spec=Message)
    mock_message.data = b"invalid json"
    mock_message.message_id = "msg-2"

    await subscriber._process_message(mock_message)

    mock_triage_callback.assert_not_awaited()
    mock_message.ack.assert_not_called()
    mock_message.nack.assert_called_once()


@pytest.mark.asyncio
async def test_log_subscriber_process_message_callback_error(
    mock_pubsub_subscriber_client, mock_triage_callback
):
    subscriber = LogSubscriber(
        "test-project", "test-subscription", triage_callback=mock_triage_callback
    )

    mock_triage_callback.side_effect = Exception("Callback failed")

    test_log_data = {"insertId": "abc-456", "textPayload": "Another test log entry"}
    mock_message = MagicMock(spec=Message)
    mock_message.data = json.dumps(test_log_data).encode("utf-8")
    mock_message.message_id = "msg-3"

    await subscriber._process_message(mock_message)

    mock_triage_callback.assert_awaited_once_with(test_log_data)
    mock_message.ack.assert_not_called()
    mock_message.nack.assert_called_once()


# Note: Testing the `start` method directly is complex due to its blocking nature
# and reliance on Pub/Sub client's internal threading/asyncio loop.
# The `_process_message` method covers the core logic of message handling.
