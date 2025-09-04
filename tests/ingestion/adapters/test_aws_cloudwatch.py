# tests/ingestion/adapters/test_aws_cloudwatch.py

"""
Tests for the AWS CloudWatch adapter.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.config.ingestion_config import AWSCloudWatchConfig, SourceType
from gemini_sre_agent.ingestion.adapters.aws_cloudwatch import AWSCloudWatchAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity, SourceHealth
from gemini_sre_agent.ingestion.interfaces.errors import SourceConnectionError


class TestAWSCloudWatchAdapter:
    """Test cases for AWSCloudWatchAdapter."""

    @pytest.fixture
    def config(self):
        """Create a test configuration."""
        return AWSCloudWatchConfig(
            name="test_cloudwatch",
            type=SourceType.AWS_CLOUDWATCH,
            region="us-east-1",
            log_group_name="/aws/lambda/test-function",
            log_stream_name="test-stream",
            start_time_minutes_ago=60,
            max_events_per_request=100,
        )

    @pytest.fixture
    def adapter(self, config):
        """Create a test adapter instance."""
        return AWSCloudWatchAdapter(config)

    def test_init(self, adapter, config):
        """Test adapter initialization."""
        assert adapter.config == config
        assert adapter.region == config.region
        assert adapter.log_group_name == config.log_group_name
        assert adapter.log_stream_name == config.log_stream_name
        assert not adapter.running

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_start_success(self, mock_boto3, adapter):
        """Test successful adapter start."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock successful log group validation
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/lambda/test-function"}]
        }
        
        await adapter.start()
        
        assert adapter.running
        assert adapter.client is not None

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_start_invalid_log_group(self, mock_boto3, adapter):
        """Test adapter start with invalid log group."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock log group not found
        mock_client.describe_log_groups.return_value = {"logGroups": []}
        
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
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_get_logs_empty(self, mock_boto3, adapter):
        """Test getting logs when no events exist."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock empty log events
        mock_client.get_log_events.return_value = {"events": []}
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break
        
        # Should not raise an error even with no logs
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_get_logs_with_content(self, mock_boto3, adapter):
        """Test getting logs from CloudWatch with content."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock log events
        mock_events = [
            {
                "timestamp": 1640995200000,  # 2022-01-01 00:00:00 UTC
                "message": "INFO Application started",
                "logStreamName": "test-stream",
            },
            {
                "timestamp": 1640995260000,  # 2022-01-01 00:01:00 UTC
                "message": "ERROR Database connection failed",
                "logStreamName": "test-stream",
            },
        ]
        mock_client.get_log_events.return_value = {"events": mock_events}
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 2:  # Limit to prevent infinite loop
                break
        
        assert len(logs) >= 1
        for log in logs:
            assert isinstance(log, LogEntry)
            assert log.source == "test_cloudwatch"
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
        new_config = AWSCloudWatchConfig(
            name="updated_cloudwatch",
            type=SourceType.AWS_CLOUDWATCH,
            region="us-west-2",
            log_group_name="/aws/lambda/updated-function",
            log_stream_name="updated-stream",
        )
        
        await adapter.update_config(new_config)
        
        assert adapter.config == new_config
        assert adapter.region == "us-west-2"
        assert adapter.log_group_name == "/aws/lambda/updated-function"
        assert adapter.log_stream_name == "updated-stream"

    @pytest.mark.asyncio
    async def test_handle_error(self, adapter):
        """Test error handling."""
        error = Exception("Test error")
        context = {"operation": "test"}
        
        result = await adapter.handle_error(error, context)
        
        # AWS API errors are generally recoverable
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
        assert "region" in metrics
        assert "log_group_name" in metrics
        assert "resilience_stats" in metrics

    def test_get_config(self, adapter, config):
        """Test getting configuration."""
        returned_config = adapter.get_config()
        assert returned_config == config

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_validate_log_group_exists(self, mock_boto3, adapter):
        """Test log group validation."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock successful log group validation
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/lambda/test-function"}]
        }
        
        await adapter.start()
        
        # Should not raise an exception
        assert adapter.running

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_validate_log_stream_exists(self, mock_boto3, adapter):
        """Test log stream validation."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock successful log group and stream validation
        mock_client.describe_log_groups.return_value = {
            "logGroups": [{"logGroupName": "/aws/lambda/test-function"}]
        }
        mock_client.describe_log_streams.return_value = {
            "logStreams": [{"logStreamName": "test-stream"}]
        }
        
        await adapter.start()
        
        # Should not raise an exception
        assert adapter.running

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_aws_api_error_handling(self, mock_boto3, adapter):
        """Test handling of AWS API errors."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock AWS API error
        from botocore.exceptions import ClientError
        mock_client.describe_log_groups.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}},
            "DescribeLogGroups"
        )
        
        with pytest.raises(SourceConnectionError):
            await adapter.start()

    @pytest.mark.asyncio
    @patch("gemini_sre_agent.ingestion.adapters.aws_cloudwatch.boto3")
    async def test_pagination_handling(self, mock_boto3, adapter):
        """Test handling of paginated log events."""
        # Mock boto3 session and client
        mock_session = MagicMock()
        mock_client = MagicMock()
        mock_boto3.Session.return_value = mock_session
        mock_session.client.return_value = mock_client
        
        # Mock paginated response
        mock_client.get_log_events.return_value = {
            "events": [
                {
                    "timestamp": 1640995200000,
                    "message": "INFO Page 1 event",
                    "logStreamName": "test-stream",
                }
            ],
            "nextForwardToken": "next-token",
        }
        
        await adapter.start()
        
        logs = []
        async for log in adapter.get_logs():
            logs.append(log)
            if len(logs) >= 1:  # Limit to prevent infinite loop
                break
        
        assert len(logs) >= 1
        assert logs[0].message == "INFO Page 1 event"
