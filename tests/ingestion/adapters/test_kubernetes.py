# tests/ingestion/adapters/test_kubernetes.py

"""
Tests for the Kubernetes adapter.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.config.ingestion_config import KubernetesConfig, SourceType
from gemini_sre_agent.ingestion.adapters.kubernetes import KubernetesAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity, SourceHealth
from gemini_sre_agent.ingestion.interfaces.errors import SourceConnectionError


class TestKubernetesAdapter:
    """Test cases for KubernetesAdapter."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return KubernetesConfig(
            name="test_kubernetes",
            type=SourceType.KUBERNETES,
            namespace="default",
            pod_name_pattern="app-*",
            container_name_pattern="main",
            max_pods=10,
            tail_lines=100,
            follow_logs=True,
        )

    @pytest.fixture
    def adapter(self, config):
        """Create a test adapter instance."""
        return KubernetesAdapter(config)

    def test_init(self, adapter, config):
        """Test adapter initialization."""
        assert adapter.config == config
        assert adapter.namespace == config.namespace
        assert adapter.pod_name_pattern == config.pod_name_pattern
        assert adapter.container_name_pattern == config.container_name_pattern
        assert not adapter.running

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_start_success(self, mock_kubernetes, adapter):
        """Test successful adapter start."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock successful namespace validation
        mock_client.list_namespace.return_value = MagicMock(
            items=[MagicMock(metadata=MagicMock(name="default"))]
        )
        
        await adapter.start()
        
        assert adapter.running
        assert adapter.client is not None

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_start_invalid_namespace(self, mock_kubernetes, adapter):
        """Test adapter start with invalid namespace."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock namespace not found
        mock_client.list_namespace.return_value = MagicMock(items=[])
        
        with pytest.raises(SourceConnectionError):
            await adapter.start()

    @pytest.mark.asyncio
    async def test_stop(self, adapter):
        """Test adapter stop."""
        await adapter.start()
        assert adapter.running
        
        await adapter.stop()
        assert not adapter.running

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_get_logs_empty(self, mock_kubernetes, adapter):
        """Test getting logs when no pods exist."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock empty pod list
        mock_client.list_namespaced_pod.return_value = MagicMock(items=[])
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break
        
        # Should not raise an error even with no logs
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_get_logs_with_content(self, mock_kubernetes, adapter):
        """Test getting logs from Kubernetes pods with content."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock pod with logs
        mock_pod = MagicMock()
        mock_pod.metadata.name = "app-123"
        mock_pod.spec.containers = [MagicMock(name="main")]
        
        mock_client.list_namespaced_pod.return_value = MagicMock(items=[mock_pod])
        mock_client.read_namespaced_pod_log.return_value = "2024-01-01T10:00:00Z INFO Application started\n"
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break
        
        assert len(logs) >= 1
        for log in logs:
            assert isinstance(log, LogEntry)
            assert log.source == "test_kubernetes"
            assert log.timestamp is not None

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, adapter):
        """Test health check when adapter is healthy."""
        await adapter.start()
        
        health = await adapter.health_check()
        
        assert isinstance(health, SourceHealth)
        assert health.is_healthy
        assert health.error_count == 0
        assert health.last_error is None

    @pytest.mark.asyncio
    async def test_health_check_stopped(self, adapter):
        """Test health check when adapter is stopped."""
        health = await adapter.health_check()
        
        assert isinstance(health, SourceHealth)
        assert not health.is_healthy
        assert "not running" in health.last_error.lower()

    @pytest.mark.asyncio
    async def test_update_config(self, adapter):
        """Test configuration update."""
        new_config = KubernetesConfig(
            name="updated_kubernetes",
            type=SourceType.KUBERNETES,
            namespace="production",
            pod_name_pattern="prod-*",
            container_name_pattern="app",
            max_pods=20,
        )
        
        await adapter.update_config(new_config)
        
        assert adapter.config == new_config
        assert adapter.namespace == "production"
        assert adapter.pod_name_pattern == "prod-*"
        assert adapter.container_name_pattern == "app"

    @pytest.mark.asyncio
    async def test_handle_error(self, adapter):
        """Test error handling."""
        error = Exception("Test error")
        context = {"operation": "test"}
        
        result = await adapter.handle_error(error, context)
        
        # Kubernetes API errors are generally recoverable
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_get_health_metrics(self, adapter):
        """Test getting health metrics."""
        await adapter.start()
        
        metrics = await adapter.get_health_metrics()
        
        assert isinstance(metrics, dict)
        assert "total_logs_processed" in metrics
        assert "total_logs_failed" in metrics
        assert "last_poll_time" in metrics
        assert "namespace" in metrics
        assert "pod_count" in metrics
        assert "resilience_stats" in metrics

    def test_get_config(self, adapter, config):
        """Test getting configuration."""
        returned_config = adapter.get_config()
        assert returned_config == config

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_pod_discovery(self, mock_kubernetes, adapter):
        """Test pod discovery functionality."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock pods matching the pattern
        mock_pod1 = MagicMock()
        mock_pod1.metadata.name = "app-123"
        mock_pod1.spec.containers = [MagicMock(name="main")]
        
        mock_pod2 = MagicMock()
        mock_pod2.metadata.name = "app-456"
        mock_pod2.spec.containers = [MagicMock(name="main")]
        
        mock_pod3 = MagicMock()
        mock_pod3.metadata.name = "other-pod"
        mock_pod3.spec.containers = [MagicMock(name="main")]
        
        mock_client.list_namespaced_pod.return_value = MagicMock(
            items=[mock_pod1, mock_pod2, mock_pod3]
        )
        
        await adapter.start()
        
        # Should only discover pods matching the pattern
        pods = await adapter._discover_pods()
        pod_names = [pod.metadata.name for pod in pods]
        
        assert "app-123" in pod_names
        assert "app-456" in pod_names
        assert "other-pod" not in pod_names

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_container_filtering(self, mock_kubernetes, adapter):
        """Test container name filtering."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock pod with multiple containers
        mock_pod = MagicMock()
        mock_pod.metadata.name = "app-123"
        mock_pod.spec.containers = [
            MagicMock(name="main"),
            MagicMock(name="sidecar"),
            MagicMock(name="init"),
        ]
        
        mock_client.list_namespaced_pod.return_value = MagicMock(items=[mock_pod])
        
        await adapter.start()
        
        # Should only process containers matching the pattern
        containers = await adapter._get_containers_for_pod(mock_pod)
        container_names = [container.name for container in containers]
        
        assert "main" in container_names
        assert "sidecar" not in container_names
        assert "init" not in container_names

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_kubernetes_api_error_handling(self, mock_kubernetes, adapter):
        """Test handling of Kubernetes API errors."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock Kubernetes API error
        from kubernetes.client.rest import ApiException
        mock_client.list_namespace.side_effect = ApiException(
            status=403, reason="Forbidden"
        )
        
        with pytest.raises(SourceConnectionError):
            await adapter.start()

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.kubernetes.kubernetes")
    async def test_log_parsing(self, mock_kubernetes, adapter):
        """Test log parsing functionality."""
        # Mock kubernetes client
        mock_client = MagicMock()
        mock_kubernetes.client.CoreV1Api.return_value = mock_client
        
        # Mock pod with logs
        mock_pod = MagicMock()
        mock_pod.metadata.name = "app-123"
        mock_pod.spec.containers = [MagicMock(name="main")]
        
        mock_client.list_namespaced_pod.return_value = MagicMock(items=[mock_pod])
        mock_client.read_namespaced_pod_log.return_value = (
            "2024-01-01T10:00:00Z INFO Application started\n"
            "2024-01-01T10:01:00Z ERROR Database connection failed\n"
            "2024-01-01T10:02:00Z WARN High memory usage detected\n"
        )
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 3:  # Limit to prevent infinite loop
                break
        
        assert len(logs) >= 1
        # Should parse different log levels correctly
        for log in logs:
            assert isinstance(log, LogEntry)
            assert log.severity in [LogSeverity.INFO, LogSeverity.ERROR, LogSeverity.WARN]
