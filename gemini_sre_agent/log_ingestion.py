import logging
from google.cloud.logging_v2.services.logging_service_v2 import LoggingServiceV2Client
from typing import List

logger = logging.getLogger(__name__)

class LogIngestor:
    """
    A class responsible for ingesting logs from Google Cloud Logging.
    """
    def __init__(self, project_id: str):
        """
        Initializes the LogIngestor with a GCP project ID.

        Args:
            project_id (str): The Google Cloud project ID.
        """
        self.client = LoggingServiceV2Client()
        self.project_id = project_id
        logger.info(f"LogIngestor initialized for project: {project_id}")

    def get_logs(self, filter_str: str, limit: int = 100) -> List[str]:
        """
        Gets logs from Google Cloud Logging based on a filter string.

        Args:
            filter_str (str): The filter string to apply to log entries (e.g., 'severity>=ERROR').
            limit (int): The maximum number of log entries to retrieve.

        Returns:
            List[str]: A list of log entry payloads.
        """
        logger.info(f"Fetching logs with filter: {filter_str} and limit: {limit}")
        resource_names = [f"projects/{self.project_id}"]
        # Use request object format for newer API versions
        pager = self.client.list_log_entries(
            request={
                "resource_names": resource_names,
                "filter": filter_str,
                "page_size": limit,
            }
        )
        logs = [entry.payload for entry in pager]
        logger.info(f"Fetched {len(logs)} logs.")
        return logs

# Removed start_monitoring method
# def start_monitoring(self):
#     """
#     Starts monitoring logs in near real-time.
#     This is a placeholder for the real-time monitoring logic, which would typically
#     use Pub/Sub for an event-driven approach.
#     """
#     logger.info("Starting log monitoring...")

# Example usage:
# ingestor = LogIngestor(project_id="your-gcp-project")
# logs = ingestor.get_logs(filter_str='severity>=ERROR')
# for log in logs:
#     print(log)
