"""
Log source adapters for the ingestion system.

This module provides adapters for different log sources including:
- Google Cloud Pub/Sub
- Google Cloud Logging
- File System
- AWS CloudWatch
- Kubernetes
- Syslog
"""

from .aws_cloudwatch import AWSCloudWatchAdapter
from .file_system import FileSystemAdapter
from .file_system_queued import QueuedFileSystemAdapter
from .gcp_logging import GCPLoggingAdapter
from .gcp_pubsub import GCPPubSubAdapter
from .kubernetes import KubernetesAdapter

__all__ = [
    "FileSystemAdapter",
    "QueuedFileSystemAdapter",
    "GCPLoggingAdapter",
    "GCPPubSubAdapter",
    "AWSCloudWatchAdapter",
    "KubernetesAdapter",
]
