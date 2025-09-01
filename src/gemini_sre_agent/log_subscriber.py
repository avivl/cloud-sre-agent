import logging
import json
from concurrent.futures import TimeoutError, ThreadPoolExecutor
from google.cloud import pubsub_v1
from google.cloud.pubsub_v1.subscriber.message import Message
from typing import Callable, Awaitable, Any, Dict, Optional
import asyncio

logger = logging.getLogger(__name__)

class LogSubscriber:
    """
    A class responsible for subscribing to Google Cloud Pub/Sub for real-time log ingestion.
    """
    def __init__(self, project_id: str, subscription_id: str, triage_callback: Optional[Callable[[Dict], Awaitable[Any]]] = None):
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
        self.triage_callback = triage_callback
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._loop = None
        logger.info(f"[LOG_INGESTION] LogSubscriber initialized for subscription: {self.subscription_path}")

    async def start(self):
        """
        Starts listening for messages on the Pub/Sub subscription.
        This method blocks until the subscription is cancelled or a timeout occurs.
        """
        self._loop = asyncio.get_running_loop()

        def _callback_wrapper(message: Message):
            if self._loop is None:
                logger.error("[LOG_INGESTION] Event loop not initialized")
                message.nack()
                return
            future = asyncio.run_coroutine_threadsafe(
                self._process_message(message),
                self._loop
            )
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.error(f"[ERROR_HANDLING] Failed to process message in callback wrapper: {e}")
                message.nack()

        streaming_pull_future = self.subscriber.subscribe(
            self.subscription_path, callback=_callback_wrapper
        )
        logger.info(f"[LOG_INGESTION] Listening for messages on {self.subscription_path}..\n")

        try:
            streaming_pull_future.result(timeout=60)
        except TimeoutError:
            streaming_pull_future.cancel()
            logger.warning(f"[LOG_INGESTION] Pub/Sub subscription timed out after 60 seconds.")
        except Exception as e:
            logger.error(f"[ERROR_HANDLING] An error occurred during Pub/Sub subscription: {e}")
            streaming_pull_future.cancel()
        finally:
            self._executor.shutdown(wait=True)

    async def _process_message(self, message: Message):
        """
        Internal async method to process received Pub/Sub messages.
        """
        try:
            log_data = json.loads(message.data.decode('utf-8'))
            flow_id = log_data.get('insertId', 'N/A')
            logger.info(f"[LOG_INGESTION] Received message: flow_id={flow_id}")

            if self.triage_callback:
                await self.triage_callback(log_data)

            message.ack()
            logger.debug(f"[LOG_INGESTION] Message acknowledged: flow_id={flow_id}, message_id={message.message_id}")
        except json.JSONDecodeError as e:
            logger.error(f"[ERROR_HANDLING] Failed to decode JSON from message {message.message_id}: {e}. Data: {message.data.decode('utf-8')}")
            message.nack()
        except Exception as e:
            logger.error(f"[ERROR_HANDLING] Failed to process message {message.message_id}: {e}")
            message.nack()