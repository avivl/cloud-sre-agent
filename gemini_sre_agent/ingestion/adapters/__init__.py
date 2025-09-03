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

from .file_system import FileSystemAdapter
from .gcp_logging import GCPLoggingAdapter
from .gcp_pubsub import GCPPubSubAdapter

__all__ = [
    "GCPPubSubAdapter",
    "GCPLoggingAdapter",
    "FileSystemAdapter",
]
