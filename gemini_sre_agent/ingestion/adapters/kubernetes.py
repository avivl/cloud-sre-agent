# gemini_sre_agent/ingestion/adapters/kubernetes.py

"""
Kubernetes adapter for log ingestion from pods and containers.
"""

import logging
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

from ...config.ingestion_config import KubernetesConfig
from ..interfaces.core import (
    LogEntry,
    LogIngestionInterface,
    LogSeverity,
    SourceConfig,
    SourceHealth,
)
from ..interfaces.errors import SourceConnectionError

logger = logging.getLogger(__name__)

try:
    from kubernetes import client, config
    from kubernetes.client.rest import ApiException

    KUBERNETES_AVAILABLE = True
except ImportError:
    KUBERNETES_AVAILABLE = False
    client = None
    config = None
    ApiException = Exception


class KubernetesAdapter(LogIngestionInterface):
    """Adapter for Kubernetes pod logs."""

    def __init__(self, config: KubernetesConfig):
        if not KUBERNETES_AVAILABLE:
            raise ImportError("kubernetes client is required for Kubernetes adapter")

        self.config = config
        self.v1 = None
        self.running = False
        self._last_check_time = None
        self._error_count = 0
        self._last_error = None
        self._watched_pods = set()

    async def start(self) -> None:
        """Start the Kubernetes adapter."""
        if not KUBERNETES_AVAILABLE or config is None or client is None:
            raise SourceConnectionError("Kubernetes client not available")
            
        try:
            # Load Kubernetes configuration
            if self.config.kubeconfig_path:
                config.load_kube_config(config_file=self.config.kubeconfig_path)
            else:
                # Try in-cluster config first, then fallback to default
                try:
                    config.load_incluster_config()
                except config.ConfigException:
                    config.load_kube_config()

            # Initialize Kubernetes client
            self.v1 = client.CoreV1Api()

            # Test connection
            await self._test_connection()

            self.running = True
            self._last_check_time = datetime.now(timezone.utc)
            logger.info(
                f"Started Kubernetes adapter for namespace: {self.config.namespace}"
            )

        except Exception as e:
            logger.error(f"Failed to start Kubernetes adapter: {e}")
            raise SourceConnectionError(
                f"Failed to start Kubernetes adapter: {e}"
            ) from e

    async def stop(self) -> None:
        """Stop the Kubernetes adapter."""
        self.running = False
        self.v1 = None
        self._watched_pods.clear()
        logger.info("Stopped Kubernetes adapter")

    async def get_logs(self) -> AsyncGenerator[LogEntry, None]:  # type: ignore
        """Get logs from Kubernetes pods."""
        if not self.running or not self.v1:
            raise SourceConnectionError("Kubernetes adapter is not running")

        try:
            # Get pods matching the selector
            pods = await self._get_pods()

            for pod in pods:
                try:
                    # Get logs from each container in the pod
                    containers = await self._get_pod_containers(pod)

                    for container_name in containers:
                        try:
                            logs = await self._get_pod_logs(
                                pod.metadata.name, container_name
                            )

                            for log_line in logs:
                                if not self.running:
                                    break

                                # Convert to LogEntry
                                log_entry = self._convert_to_log_entry(
                                    log_line, pod, container_name
                                )
                                yield log_entry

                        except Exception as e:
                            logger.error(
                                f"Error getting logs from {pod.metadata.name}/{container_name}: {e}"
                            )
                            self._error_count += 1
                            self._last_error = str(e)
                            continue

                except Exception as e:
                    logger.error(f"Error processing pod {pod.metadata.name}: {e}")
                    self._error_count += 1
                    self._last_error = str(e)
                    continue

        except Exception as e:
            logger.error(f"Error getting logs from Kubernetes: {e}")
            self._error_count += 1
            self._last_error = str(e)
            raise SourceConnectionError(
                f"Failed to get logs from Kubernetes: {e}"
            ) from e

    async def health_check(self) -> SourceHealth:
        """Check the health of the Kubernetes adapter."""
        try:
            if not self.running or not self.v1:
                return SourceHealth(
                    is_healthy=False,
                    last_success=None,
                    error_count=self._error_count,
                    last_error="Adapter not running",
                    metrics={"status": "stopped"},
                )

            # Test connection
            await self._test_connection()

            return SourceHealth(
                is_healthy=True,
                last_success=datetime.now(timezone.utc).isoformat(),
                error_count=self._error_count,
                last_error=self._last_error,
                metrics={
                    "namespace": self.config.namespace,
                    "label_selector": self.config.label_selector,
                    "watched_pods": len(self._watched_pods),
                    "last_check": (
                        self._last_check_time.isoformat()
                        if self._last_check_time
                        else None
                    ),
                },
            )

        except Exception as e:
            self._error_count += 1
            self._last_error = str(e)
            return SourceHealth(
                is_healthy=False,
                last_success=None,
                error_count=self._error_count,
                last_error=str(e),
                metrics={"status": "error"},
            )

    def get_config(self) -> SourceConfig:
        """Get the current configuration."""
        return self.config  # type: ignore

    async def update_config(self, config: SourceConfig) -> None:
        """Update the configuration."""
        if isinstance(config, KubernetesConfig):
            self.config = config
            # Restart if running
            if self.running:
                await self.stop()
                await self.start()
        else:
            raise ValueError("Invalid config type for Kubernetes adapter")

    async def handle_error(self, error: Exception, context: Dict[str, Any]) -> bool:
        """Handle errors from the adapter."""
        logger.error(
            f"Kubernetes error in {context.get('operation', 'unknown')}: {error}"
        )
        self._error_count += 1
        self._last_error = str(error)

        # Return True if error should be retried
        if isinstance(error, ApiException):
            status = getattr(error, "status", None)
            if status == 404:
                return False  # Don't retry not found errors
            elif status is not None and status >= 500:
                return True  # Retry server errors
        return True

    async def get_health_metrics(self) -> Dict[str, Any]:
        """Get detailed health metrics."""
        return {
            "namespace": self.config.namespace,
            "label_selector": self.config.label_selector,
            "kubeconfig_path": self.config.kubeconfig_path,
            "running": self.running,
            "error_count": self._error_count,
            "last_error": self._last_error,
            "last_check_time": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
            "watched_pods": len(self._watched_pods),
            "kubernetes_available": KUBERNETES_AVAILABLE,
        }

    async def _test_connection(self) -> None:
        """Test the Kubernetes connection."""
        if self.v1 is None:
            raise SourceConnectionError("Kubernetes client not initialized")
            
        try:
            # Try to list namespaces
            self.v1.list_namespace(limit=1)
        except ApiException as e:
            status = getattr(e, "status", None)
            if status == 403:
                # Forbidden, but connection is working
                pass
            else:
                raise
        except Exception as e:
            raise SourceConnectionError(f"Kubernetes connection failed: {e}") from e

    async def _get_pods(self) -> List[Any]:
        """Get pods matching the selector."""
        if self.v1 is None:
            return []
            
        try:
            kwargs = {"namespace": self.config.namespace, "limit": self.config.max_pods}

            if self.config.label_selector:
                kwargs["label_selector"] = self.config.label_selector

            response = self.v1.list_namespaced_pod(**kwargs)
            return response.items

        except ApiException as e:
            logger.error(f"Error getting pods: {e}")
            return []

    async def _get_pod_containers(self, pod: Any) -> List[str]:
        """Get container names from a pod."""
        containers = []

        # Get init containers
        for container in pod.spec.init_containers or []:
            containers.append(container.name)

        # Get regular containers
        for container in pod.spec.containers:
            containers.append(container.name)

        return containers

    async def _get_pod_logs(self, pod_name: str, container_name: str) -> List[str]:
        """Get logs from a specific pod and container."""
        try:
            kwargs = {
                "name": pod_name,
                "namespace": self.config.namespace,
                "container": container_name,
                "tail_lines": self.config.tail_lines,
                "timestamps": True,
            }

            # Add since_time if we have a last check time
            if self._last_check_time:
                kwargs["since_time"] = self._last_check_time

            if self.v1 is None:
                return []
                
            response = self.v1.read_namespaced_pod_log(**kwargs)

            # Split into lines and filter empty ones
            logs = [line.strip() for line in response.split("\n") if line.strip()]
            return logs

        except ApiException as e:
            logger.error(f"Error getting logs from {pod_name}/{container_name}: {e}")
            return []

    def _convert_to_log_entry(
        self, log_line: str, pod: Any, container_name: str
    ) -> LogEntry:
        """Convert Kubernetes log line to LogEntry."""
        # Parse timestamp if present (Kubernetes logs include timestamps)
        timestamp = datetime.now(timezone.utc)
        message = log_line

        # Try to extract timestamp from log line
        if " " in log_line and len(log_line) > 20:
            try:
                # Kubernetes timestamp format: 2024-01-01T10:00:00.000000000Z
                timestamp_str = log_line.split(" ")[0]
                if "T" in timestamp_str and "Z" in timestamp_str:
                    timestamp = datetime.fromisoformat(
                        timestamp_str.replace("Z", "+00:00")
                    )
                    message = " ".join(log_line.split(" ")[1:])
            except (ValueError, IndexError):
                # If parsing fails, use current time
                pass

        # Try to parse severity from message
        severity = LogSeverity.INFO
        message_upper = message.upper()
        if "ERROR" in message_upper or "FATAL" in message_upper:
            severity = LogSeverity.ERROR
        elif "WARN" in message_upper or "WARNING" in message_upper:
            severity = LogSeverity.WARN
        elif "DEBUG" in message_upper:
            severity = LogSeverity.DEBUG
        elif "CRITICAL" in message_upper:
            severity = LogSeverity.CRITICAL

        # Generate unique ID
        log_id = f"k8s-{pod.metadata.name}-{container_name}-{hash(log_line) % 10000}"

        return LogEntry(
            id=log_id,
            timestamp=timestamp,
            message=message,
            source=f"kubernetes-{self.config.namespace}",
            severity=severity,
            metadata={
                "namespace": self.config.namespace,
                "pod_name": pod.metadata.name,
                "container_name": container_name,
                "pod_ip": pod.status.pod_ip,
                "node_name": pod.spec.node_name,
                "labels": dict(pod.metadata.labels) if pod.metadata.labels else {},
                "annotations": (
                    dict(pod.metadata.annotations) if pod.metadata.annotations else {}
                ),
            },
        )
