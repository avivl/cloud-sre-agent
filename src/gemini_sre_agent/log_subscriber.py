import logging
import json # Added
from concurrent.futures import TimeoutError
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message
from typing import Callable, Awaitable, Any, Dict # Added for type hinting
import asyncio # Added for asyncio.create_task

logger = logging.getLogger(__name__)

class LogSubscriber:
    """
    A class responsible for subscribing to Google Cloud Pub/Sub for real-time log ingestion.
    """
    def __init__(self, project_id: str, subscription_id: str, triage_callback: Callable[[Dict], Awaitable[Any]] = None):
        """
        Initializes the LogSubscriber with GCP project and Pub/Sub subscription details.

        Args:
            project_id (str): The Google Cloud project ID.
            subscription_id (str): The ID of the Pub/Sub subscription to listen to.
            triage_callback (Callable[[Dict], Awaitable[Any]]): An async callback function
                                                                 to process received log data.
        """
        self.subscriber = pubsub_v1.SubscriberClient()
        self.subscription_path = self.subscriber.subscription_path(project_id, subscription_id)
        self.triage_callback = triage_callback # Store the callback
        logger.info(f"LogSubscriber initialized for subscription: {self.subscription_path}")

    def start(self):
        """
        Starts listening for messages on the Pub/Sub subscription.
        This method blocks until the subscription is cancelled or a timeout occurs.
        """
        # The callback needs to be wrapped to handle async processing
        def _callback_wrapper(message: Message):
            asyncio.create_task(self._process_message(message))

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=_callback_wrapper # Use the wrapper
        )
        logger.info(f"Listening for messages on {self.subscription_path}..")

        try:
            streaming_pull_future.result(timeout=60)
        except TimeoutError:
            streaming_pull_future.cancel()
            logger.warning(f"Pub/Sub subscription timed out after 60 seconds.")
        except Exception as e:
            logger.error(f"An error occurred during Pub/Sub subscription: {e}")
            streaming_pull_future.cancel()

    async def _process_message(self, message: Message):
        """
        Internal async method to process received Pub/Sub messages.
        """
        try:
            log_data = json.loads(message.data.decode('utf-8'))
            logger.info(f"Received message: {log_data.get('insertId', 'N/A')}") # Log with insertId if available

            if self.triage_callback:
                await self.triage_callback(log_data) # Call the async callback

            message.ack()
            logger.debug(f"Message {message.message_id} acknowledged.")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from message {message.message_id}: {e}. Data: {message.data.decode('utf-8')}")
            message.nack() # Negative acknowledgment
        except Exception as e:
            logger.error(f"Failed to process message {message.message_id}: {e}")
            message.nack() # Negative acknowledgment