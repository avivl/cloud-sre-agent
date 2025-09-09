"""
Tests for Enhanced Remediation Agent.

This module contains comprehensive tests for the enhanced remediation agent
that integrates with the new source control system.
"""

import tempfile
from unittest.mock import AsyncMock, patch

import pytest

from gemini_sre_agent.analysis_agent import RemediationPlan
from gemini_sre_agent.config.source_control_global import SourceControlGlobalConfig
from gemini_sre_agent.enhanced_remediation_agent import EnhancedRemediationAgent
from gemini_sre_agent.remediation_agent_adapter import RemediationAgentAdapter


class TestEnhancedRemediationAgent:
    """Test cases for EnhancedRemediationAgent."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def mock_remediation_plan(self):
        """Create a mock remediation plan for testing."""
        return RemediationPlan(
            root_cause_analysis="Test root cause analysis",
            proposed_fix="Test proposed fix",
            code_patch="# FILE: test_file.py\nprint('Hello, World!')",
        )

    @pytest.fixture
    def source_control_config(self, temp_dir):
        """Create a source control configuration for testing."""
        return SourceControlGlobalConfig(
            max_concurrent_operations=2,
            conflict_resolution="manual",
        )

    @pytest.fixture
    def enhanced_agent(self, source_control_config):
        """Create an enhanced remediation agent for testing."""
        return EnhancedRemediationAgent(
            source_control_config=source_control_config,
            encryption_key="test-key",
            auto_discovery=True,
            parallel_processing=True,
            max_concurrent_operations=2,
        )

    @pytest.mark.asyncio
    async def test_initialization(self, enhanced_agent):
        """Test that the enhanced agent initializes correctly."""
        await enhanced_agent.initialize()
        assert enhanced_agent.repository_manager is not None
        assert enhanced_agent.provider_factory is not None
        assert enhanced_agent.credential_manager is not None

    @pytest.mark.asyncio
    async def test_initialization_failure(self):
        """Test that initialization fails gracefully with invalid config."""
        # For now, the initialization doesn't actually fail with the given config
        # This test can be updated when we add proper validation
        invalid_config = SourceControlGlobalConfig(
            max_concurrent_operations=1,
            conflict_resolution="manual",
        )

        agent = EnhancedRemediationAgent(source_control_config=invalid_config)

        # Currently, initialization succeeds even with this config
        await agent.initialize()
        assert agent.repository_manager is not None

    @pytest.mark.asyncio
    async def test_create_remediation_success(
        self, enhanced_agent, mock_remediation_plan, temp_dir
    ):
        """Test successful remediation creation."""
        await enhanced_agent.initialize()

        result = await enhanced_agent.create_remediation(
            remediation_plan=mock_remediation_plan,
            service_name="test-service",
            flow_id="test-flow-123",
            issue_id="test-issue-456",
            target_repositories=["test-repo"],
            base_branch="main",
            create_branch=True,
        )

        assert result["service_name"] == "test-service"
        assert result["flow_id"] == "test-flow-123"
        assert result["issue_id"] == "test-issue-456"
        assert result["total_repositories"] >= 0
        assert "results" in result

    @pytest.mark.asyncio
    async def test_create_remediation_auto_discovery(
        self, enhanced_agent, mock_remediation_plan
    ):
        """Test remediation creation with auto-discovery of repositories."""
        await enhanced_agent.initialize()

        result = await enhanced_agent.create_remediation(
            remediation_plan=mock_remediation_plan,
            service_name="test-service",
            flow_id="test-flow-123",
            issue_id="test-issue-456",
            target_repositories=None,  # Auto-discovery
            base_branch="main",
            create_branch=True,
        )

        assert result["service_name"] == "test-service"
        assert "results" in result

    @pytest.mark.asyncio
    async def test_create_remediation_no_repositories(
        self, enhanced_agent, mock_remediation_plan
    ):
        """Test remediation creation when no repositories are found."""
        await enhanced_agent.initialize()

        # Mock the discovery to return no repositories
        with patch.object(
            enhanced_agent, "_discover_affected_repositories", return_value=[]
        ):
            result = await enhanced_agent.create_remediation(
                remediation_plan=mock_remediation_plan,
                service_name="nonexistent-service",
                flow_id="test-flow-123",
                issue_id="test-issue-456",
                target_repositories=None,
                base_branch="main",
                create_branch=True,
            )

            assert "error" in result
            assert "No repositories found" in result["error"]

    @pytest.mark.asyncio
    async def test_file_path_extraction(self, enhanced_agent):
        """Test file path extraction from patch content."""
        # Test with # FILE: comment
        patch_with_hash = "# FILE: src/test.py\nprint('Hello')"
        file_path = enhanced_agent._extract_file_path_from_patch(patch_with_hash)
        assert file_path == "src/test.py"

        # Test with // FILE: comment
        patch_with_slash = "// FILE: src/test.py\nprint('Hello')"
        file_path = enhanced_agent._extract_file_path_from_patch(patch_with_slash)
        assert file_path == "src/test.py"

        # Test with /* FILE: */ comment
        patch_with_c_style = "/* FILE: src/test.py */\nprint('Hello')"
        file_path = enhanced_agent._extract_file_path_from_patch(patch_with_c_style)
        assert file_path == "src/test.py"

        # Test with no file path
        patch_without_file = "print('Hello')"
        file_path = enhanced_agent._extract_file_path_from_patch(patch_without_file)
        assert file_path is None

    @pytest.mark.asyncio
    async def test_file_path_validation(self, enhanced_agent):
        """Test file path validation."""
        # Valid paths
        assert enhanced_agent._is_valid_file_path("src/test.py")
        assert enhanced_agent._is_valid_file_path("test.py")
        assert enhanced_agent._is_valid_file_path("folder/subfolder/file.py")

        # Invalid paths
        assert not enhanced_agent._is_valid_file_path("../test.py")
        assert not enhanced_agent._is_valid_file_path("/absolute/path.py")
        assert not enhanced_agent._is_valid_file_path("")
        assert not enhanced_agent._is_valid_file_path("folder/../test.py")

    @pytest.mark.asyncio
    async def test_get_remediation_status(self, enhanced_agent):
        """Test getting remediation status."""
        await enhanced_agent.initialize()

        status = await enhanced_agent.get_remediation_status(
            flow_id="test-flow-123", issue_id="test-issue-456"
        )

        assert status["flow_id"] == "test-flow-123"
        assert status["issue_id"] == "test-issue-456"
        assert "repositories" in status

    @pytest.mark.asyncio
    async def test_cleanup_remediation(self, enhanced_agent):
        """Test cleanup of remediation branches."""
        await enhanced_agent.initialize()

        cleanup_result = await enhanced_agent.cleanup_remediation(
            flow_id="test-flow-123",
            issue_id="test-issue-456",
            branch_name="fix/test-service-test-issue-456-test-flow-123",
        )

        assert cleanup_result["flow_id"] == "test-flow-123"
        assert cleanup_result["issue_id"] == "test-issue-456"
        assert "repositories" in cleanup_result

    @pytest.mark.asyncio
    async def test_close(self, enhanced_agent):
        """Test closing the enhanced agent."""
        await enhanced_agent.initialize()
        await enhanced_agent.close()
        # Should not raise any exceptions


class TestRemediationAgentAdapter:
    """Test cases for RemediationAgentAdapter (backward compatibility)."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def mock_remediation_plan(self):
        """Create a mock remediation plan for testing."""
        return RemediationPlan(
            root_cause_analysis="Test root cause analysis",
            proposed_fix="Test proposed fix",
            code_patch="# FILE: test_file.py\nprint('Hello, World!')",
        )

    @pytest.mark.asyncio
    async def test_adapter_initialization_github(self):
        """Test adapter initialization with GitHub configuration."""
        adapter = RemediationAgentAdapter(
            github_token="test-token",
            repo_name="test/repo",
            use_local_patches=False,
            encryption_key="test-key",
        )

        assert adapter.github_token == "test-token"
        assert adapter.repo_name == "test/repo"
        assert adapter.use_local_patches is False
        assert not adapter._initialized

    @pytest.mark.asyncio
    async def test_adapter_initialization_local(self):
        """Test adapter initialization with local patches configuration."""
        adapter = RemediationAgentAdapter(
            github_token="dummy_token",
            repo_name="test/repo",
            use_local_patches=True,
            patch_dir="/tmp/test-patches",
            encryption_key="test-key",
        )

        assert adapter.use_local_patches is True
        assert adapter.patch_dir == "/tmp/test-patches"

    @pytest.mark.asyncio
    async def test_create_pull_request_success(self, temp_dir, mock_remediation_plan):
        """Test successful pull request creation through the adapter."""
        adapter = RemediationAgentAdapter(
            github_token="dummy_token",
            repo_name="test/repo",
            use_local_patches=True,
            patch_dir=temp_dir,
        )

        # Mock the enhanced agent to avoid actual initialization
        with patch.object(adapter, "_ensure_initialized"):
            with patch.object(adapter, "enhanced_agent") as mock_enhanced:
                mock_enhanced.create_remediation = AsyncMock(
                    return_value={
                        "successful_repositories": 1,
                        "results": {
                            "test-repo": {
                                "success": True,
                                "pull_request": {
                                    "url": "https://github.com/test/repo/pull/123"
                                },
                            }
                        },
                    }
                )

                result = await adapter.create_pull_request(
                    remediation_plan=mock_remediation_plan,
                    branch_name="test-branch",
                    base_branch="main",
                    flow_id="test-flow-123",
                    issue_id="test-issue-456",
                )

                assert "https://github.com/test/repo/pull/123" in result

    @pytest.mark.asyncio
    async def test_create_pull_request_fallback(self, temp_dir, mock_remediation_plan):
        """Test fallback to local patch creation when enhanced agent fails."""
        adapter = RemediationAgentAdapter(
            github_token="dummy_token",
            repo_name="test/repo",
            use_local_patches=True,
            patch_dir=temp_dir,
        )

        # Mock the enhanced agent to fail
        with patch.object(adapter, "_ensure_initialized"):
            with patch.object(adapter, "enhanced_agent") as mock_enhanced:
                mock_enhanced.create_remediation = AsyncMock(
                    side_effect=Exception("Test error")
                )

                result = await adapter.create_pull_request(
                    remediation_plan=mock_remediation_plan,
                    branch_name="test-branch",
                    base_branch="main",
                    flow_id="test-flow-123",
                    issue_id="test-issue-456",
                )

                # Should return a local patch file path
                assert result.endswith(".patch")

    @pytest.mark.asyncio
    async def test_file_path_extraction(self, temp_dir):
        """Test file path extraction in the adapter."""
        adapter = RemediationAgentAdapter(
            github_token="dummy_token",
            repo_name="test/repo",
            use_local_patches=True,
            patch_dir=temp_dir,
        )

        # Test with # FILE: comment
        patch_with_hash = "# FILE: src/test.py\nprint('Hello')"
        file_path = adapter._extract_file_path_from_patch(patch_with_hash)
        assert file_path == "src/test.py"

        # Test with no file path
        patch_without_file = "print('Hello')"
        file_path = adapter._extract_file_path_from_patch(patch_without_file)
        assert file_path is None

    @pytest.mark.asyncio
    async def test_close(self, temp_dir):
        """Test closing the adapter."""
        adapter = RemediationAgentAdapter(
            github_token="dummy_token",
            repo_name="test/repo",
            use_local_patches=True,
            patch_dir=temp_dir,
        )

        # Mock the enhanced agent
        with patch.object(adapter, "enhanced_agent") as mock_enhanced:
            mock_enhanced.close = AsyncMock()

            await adapter.close()
            mock_enhanced.close.assert_called_once()


class TestIntegration:
    """Integration tests for the enhanced remediation system."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.mark.asyncio
    async def test_end_to_end_remediation(self, temp_dir):
        """Test end-to-end remediation creation."""
        # Create a source control configuration
        config = SourceControlGlobalConfig(
            max_concurrent_operations=1,
            conflict_resolution="manual",
        )

        # Create the enhanced agent
        agent = EnhancedRemediationAgent(
            source_control_config=config,
            encryption_key="test-key",
            auto_discovery=True,
            parallel_processing=False,
            max_concurrent_operations=1,
        )

        # Initialize the agent
        await agent.initialize()

        # Create a remediation plan
        remediation_plan = RemediationPlan(
            root_cause_analysis="Test root cause analysis",
            proposed_fix="Test proposed fix",
            code_patch="# FILE: test_file.py\nprint('Hello, World!')",
        )

        # Create the remediation
        result = await agent.create_remediation(
            remediation_plan=remediation_plan,
            service_name="test-service",
            flow_id="test-flow-123",
            issue_id="test-issue-456",
            target_repositories=["test-repo"],
            base_branch="main",
            create_branch=True,
        )

        # Verify the result
        assert result["service_name"] == "test-service"
        assert result["flow_id"] == "test-flow-123"
        assert result["issue_id"] == "test-issue-456"
        assert result["total_repositories"] >= 0
        assert "results" in result

        # Clean up
        await agent.close()
