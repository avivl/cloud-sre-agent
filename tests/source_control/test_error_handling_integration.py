# tests/source_control/test_error_handling_integration.py

"""
Integration tests for error handling across all source control providers.

This module tests the integration of the error handling system with GitHub,
GitLab, and Local providers to ensure comprehensive error handling works
correctly across all provider types.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.source_control.error_handling import (
    create_provider_error_handling_with_preset,
    get_provider_config,
)
from gemini_sre_agent.source_control.providers.github.enhanced_github_provider import (
    EnhancedGitHubProvider,
)
from gemini_sre_agent.source_control.providers.gitlab.enhanced_gitlab_provider import (
    EnhancedGitLabProvider,
)
from gemini_sre_agent.source_control.providers.local.enhanced_local_provider import (
    EnhancedLocalProvider,
)


class TestErrorHandlingIntegration:
    """Test error handling integration across providers."""

    @pytest.fixture
    def mock_github_config(self):
        """Mock GitHub configuration."""
        return {
            "provider": "github",
            "name": "test/repo",
            "token": "test_token",
            "error_handling": {
                "circuit_breaker": {
                    "failure_threshold": 3,
                    "recovery_timeout": 30.0,
                    "success_threshold": 2,
                    "timeout": 15.0,
                },
                "retry": {
                    "max_retries": 2,
                    "base_delay": 0.5,
                    "max_delay": 10.0,
                    "backoff_factor": 1.5,
                    "jitter": True,
                },
            },
        }

    @pytest.fixture
    def mock_gitlab_config(self):
        """Mock GitLab configuration."""
        return {
            "provider": "gitlab",
            "name": "test/project",
            "token": "test_token",
            "url": "https://gitlab.com",
            "error_handling": {
                "circuit_breaker": {
                    "failure_threshold": 3,
                    "recovery_timeout": 30.0,
                    "success_threshold": 2,
                    "timeout": 15.0,
                },
                "retry": {
                    "max_retries": 2,
                    "base_delay": 0.5,
                    "max_delay": 10.0,
                    "backoff_factor": 1.5,
                    "jitter": True,
                },
            },
        }

    @pytest.fixture
    def mock_local_config(self):
        """Mock Local configuration."""
        return {
            "provider": "local",
            "path": "/tmp/test_repo",
            "git_enabled": True,
            "error_handling": {
                "circuit_breaker": {
                    "failure_threshold": 5,
                    "recovery_timeout": 15.0,
                    "success_threshold": 3,
                    "timeout": 30.0,
                },
                "retry": {
                    "max_retries": 1,
                    "base_delay": 0.1,
                    "max_delay": 5.0,
                    "backoff_factor": 1.2,
                    "jitter": False,
                },
            },
        }

    def test_get_provider_config(self):
        """Test getting provider-specific configurations."""
        # Test GitHub config
        github_config = get_provider_config("github")
        assert "error_handling" in github_config
        assert (
            github_config["error_handling"]["circuit_breaker"]["failure_threshold"] == 5
        )

        # Test GitLab config
        gitlab_config = get_provider_config("gitlab")
        assert "error_handling" in gitlab_config
        assert (
            gitlab_config["error_handling"]["circuit_breaker"]["failure_threshold"] == 5
        )

        # Test Local config
        local_config = get_provider_config("local")
        assert "error_handling" in local_config
        assert (
            local_config["error_handling"]["circuit_breaker"]["failure_threshold"] == 10
        )

        # Test unknown provider (should return GitHub config)
        unknown_config = get_provider_config("unknown")
        assert unknown_config == github_config

    def test_create_provider_error_handling_with_preset(self):
        """Test creating error handling components with provider presets."""
        # Test GitHub
        github_components = create_provider_error_handling_with_preset("github")
        assert "error_classifier" in github_components
        assert "resilient_manager" in github_components
        assert "graceful_degradation_manager" in github_components
        assert "health_check_manager" in github_components
        assert "error_handling_metrics" in github_components

        # Test GitLab
        gitlab_components = create_provider_error_handling_with_preset("gitlab")
        assert "error_classifier" in gitlab_components
        assert "resilient_manager" in gitlab_components
        assert "graceful_degradation_manager" in gitlab_components
        assert "health_check_manager" in gitlab_components
        assert "error_handling_metrics" in gitlab_components

        # Test Local
        local_components = create_provider_error_handling_with_preset("local")
        assert "error_classifier" in local_components
        assert "resilient_manager" in local_components
        assert "graceful_degradation_manager" in local_components
        assert "health_check_manager" in local_components
        assert "error_handling_metrics" in local_components

    @pytest.mark.asyncio
    async def test_enhanced_github_provider_initialization(self, mock_github_config):
        """Test enhanced GitHub provider initialization with error handling."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)

            # Initialize provider
            await provider.initialize()

            # Verify error handling components are initialized
            assert provider.error_classifier is not None
            assert provider.resilient_manager is not None
            assert provider.graceful_degradation_manager is not None
            assert provider.health_check_manager is not None
            assert provider.error_handling_metrics is not None

            # Verify GitHub client is initialized
            assert provider.client == mock_client
            assert provider.repo == mock_repo

    @pytest.mark.asyncio
    async def test_enhanced_gitlab_provider_initialization(self, mock_gitlab_config):
        """Test enhanced GitLab provider initialization with error handling."""
        with patch("gitlab.Gitlab") as mock_gitlab_class:
            # Mock GitLab client and project
            mock_client = MagicMock()
            mock_project = MagicMock()
            mock_gitlab_class.return_value = mock_client
            mock_client.projects.get.return_value = mock_project

            # Create provider
            provider = EnhancedGitLabProvider(mock_gitlab_config)

            # Initialize provider
            await provider.initialize()

            # Verify error handling components are initialized
            assert provider.error_classifier is not None
            assert provider.resilient_manager is not None
            assert provider.graceful_degradation_manager is not None
            assert provider.health_check_manager is not None
            assert provider.error_handling_metrics is not None

            # Verify GitLab client is initialized
            assert provider.gl == mock_client
            assert provider.project == mock_project

    @pytest.mark.asyncio
    async def test_enhanced_local_provider_initialization(self, mock_local_config):
        """Test enhanced Local provider initialization with error handling."""
        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.is_dir", return_value=True
        ), patch("pathlib.Path.write_text"), patch("pathlib.Path.unlink"):

            # Create provider
            provider = EnhancedLocalProvider(mock_local_config)

            # Initialize provider
            await provider.initialize()

            # Verify error handling components are initialized
            assert provider.error_classifier is not None
            assert provider.resilient_manager is not None
            assert provider.graceful_degradation_manager is not None
            assert provider.health_check_manager is not None
            assert provider.error_handling_metrics is not None

            # Verify local components are initialized
            assert provider.file_ops is not None
            assert provider.git_ops is not None
            assert provider.batch_ops is not None

    @pytest.mark.asyncio
    async def test_github_provider_error_handling(self, mock_github_config):
        """Test GitHub provider error handling integration."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)
            await provider.initialize()

            # Mock operations module
            provider.operations = MagicMock()
            provider.operations.get_file_content = AsyncMock(
                side_effect=Exception("Network error")
            )

            # Test error handling
            with pytest.raises(Exception) as exc_info:
                await provider.get_file_content("test.py")

            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_gitlab_provider_error_handling(self, mock_gitlab_config):
        """Test GitLab provider error handling integration."""
        with patch("gitlab.Gitlab") as mock_gitlab_class:
            # Mock GitLab client and project
            mock_client = MagicMock()
            mock_project = MagicMock()
            mock_gitlab_class.return_value = mock_client
            mock_client.projects.get.return_value = mock_project

            # Create provider
            provider = EnhancedGitLabProvider(mock_gitlab_config)
            await provider.initialize()

            # Mock file operations
            provider.file_ops = MagicMock()
            provider.file_ops.get_file_content = AsyncMock(
                side_effect=Exception("API error")
            )

            # Test error handling
            with pytest.raises(Exception) as exc_info:
                await provider.get_file_content("test.py")

            assert "API error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_local_provider_error_handling(self, mock_local_config):
        """Test Local provider error handling integration."""
        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.is_dir", return_value=True
        ), patch("pathlib.Path.write_text"), patch("pathlib.Path.unlink"):

            # Create provider
            provider = EnhancedLocalProvider(mock_local_config)
            await provider.initialize()

            # Mock file operations to raise an error
            provider.file_ops.get_file_content = MagicMock(
                side_effect=Exception("File system error")
            )

            # Test error handling
            with pytest.raises(Exception) as exc_info:
                await provider.get_file_content("test.py")

            assert "File system error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_provider_health_status_integration(self, mock_github_config):
        """Test provider health status integration with error handling."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_user = MagicMock()
            mock_user.login = "testuser"
            mock_repo.raw_data = {
                "full_name": "test/repo",
                "id": 12345,
                "default_branch": "main",
                "private": False,
            }

            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo
            mock_client.get_user.return_value = mock_user

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)
            await provider.initialize()

            # Test health status
            health = await provider.get_health_status()

            assert health.status == "healthy"
            assert "GitHub provider is operational" in health.message
            assert "basic_health" in health.additional_info
            assert "error_handling_health" in health.additional_info
            assert "circuit_breakers" in health.additional_info
            assert "operation_types" in health.additional_info

    @pytest.mark.asyncio
    async def test_batch_operations_error_handling(self, mock_local_config):
        """Test batch operations error handling integration."""
        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.is_dir", return_value=True
        ), patch("pathlib.Path.write_text"), patch("pathlib.Path.unlink"):

            # Create provider
            provider = EnhancedLocalProvider(mock_local_config)
            await provider.initialize()

            # Mock batch operations to raise an error
            provider.batch_ops.batch_operations = AsyncMock(
                side_effect=Exception("Batch error")
            )

            # Test batch operations error handling
            from gemini_sre_agent.source_control.models import BatchOperation

            operations = [
                BatchOperation(
                    operation_id="1",
                    operation_type="create_file",
                    file_path="test.py",
                    content="print('hello')",
                )
            ]

            with pytest.raises(Exception) as exc_info:
                await provider.batch_operations(operations)

            assert "Batch error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_graceful_degradation_integration(self, mock_github_config):
        """Test graceful degradation integration with providers."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)
            await provider.initialize()

            # Mock operations to fail
            provider.operations = MagicMock()
            provider.operations.get_file_content = AsyncMock(
                side_effect=Exception("Network error")
            )

            # Mock graceful degradation to return a fallback result
            provider.graceful_degradation_manager.execute_with_graceful_degradation = (
                AsyncMock(return_value="fallback_content")
            )

            # Test graceful degradation
            result = await provider.get_file_content("test.py")
            assert result == "fallback_content"

    @pytest.mark.asyncio
    async def test_circuit_breaker_integration(self, mock_github_config):
        """Test circuit breaker integration with providers."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider with low failure threshold for testing
            test_config = mock_github_config.copy()
            test_config["error_handling"]["circuit_breaker"]["failure_threshold"] = 2

            provider = EnhancedGitHubProvider(test_config)
            await provider.initialize()

            # Mock operations to fail multiple times
            provider.operations = MagicMock()
            provider.operations.get_file_content = AsyncMock(
                side_effect=Exception("API error")
            )

            # Test circuit breaker behavior
            # First few calls should fail with the original error
            for _ in range(2):
                with pytest.raises(Exception) as exc_info:
                    await provider.get_file_content("test.py")
                assert "API error" in str(exc_info.value)

            # After the failure threshold, circuit breaker should be open
            # and subsequent calls should fail with circuit breaker error
            with pytest.raises(Exception) as exc_info:
                await provider.get_file_content("test.py")

            # The error should be related to circuit breaker being open
            assert (
                "circuit" in str(exc_info.value).lower()
                or "open" in str(exc_info.value).lower()
            )

    @pytest.mark.asyncio
    async def test_metrics_integration(self, mock_github_config):
        """Test metrics integration with providers."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)
            await provider.initialize()

            # Mock operations
            provider.operations = MagicMock()
            provider.operations.get_file_content = AsyncMock(
                return_value="file content"
            )

            # Test metrics collection
            await provider.get_file_content("test.py")

            # Verify metrics were recorded
            assert provider.error_handling_metrics is not None
            # Note: In a real test, you would verify that metrics were actually recorded
            # by checking the metrics collector's data

    @pytest.mark.asyncio
    async def test_error_classification_integration(self, mock_github_config):
        """Test error classification integration with providers."""
        with patch("github.Github") as mock_github_class, patch(
            "github.Repository.Repository"
        ):

            # Mock GitHub client and repository
            mock_client = MagicMock()
            mock_repo = MagicMock()
            mock_github_class.return_value = mock_client
            mock_client.get_repo.return_value = mock_repo

            # Create provider
            provider = EnhancedGitHubProvider(mock_github_config)
            await provider.initialize()

            # Mock operations to raise different types of errors
            provider.operations = MagicMock()

            # Test network error classification
            provider.operations.get_file_content = AsyncMock(
                side_effect=Exception("Connection timeout")
            )

            with pytest.raises(Exception) as exc_info:
                await provider.get_file_content("test.py")
            assert "Connection timeout" in str(exc_info.value)

            # Verify error classifier is available
            assert provider.error_classifier is not None

            # Test error classification directly
            error = Exception("Connection timeout")
            classification = provider.error_classifier.classify_error(error)
            assert classification.error_type.value == "network_error"
            assert classification.is_retryable is True
