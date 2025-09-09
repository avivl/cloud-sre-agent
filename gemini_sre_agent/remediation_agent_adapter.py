"""
Remediation Agent Adapter for Backward Compatibility.

This module provides an adapter that maintains the original RemediationAgent interface
while using the new enhanced source control system under the hood.
"""

import logging
from typing import Optional

from .analysis_agent import RemediationPlan
from .config.source_control_global import SourceControlGlobalConfig
from .enhanced_remediation_agent import EnhancedRemediationAgent

logger = logging.getLogger(__name__)


class RemediationAgentAdapter:
    """
    Adapter that provides backward compatibility with the original RemediationAgent.

    This adapter maintains the same interface as the original RemediationAgent
    while using the new enhanced source control system internally.
    """

    def __init__(
        self,
        github_token: str,
        repo_name: str,
        use_local_patches: bool = False,
        patch_dir: str = "/tmp/real_patches",
        encryption_key: Optional[str] = None,
        auto_discovery: bool = True,
    ):
        """
        Initialize the adapter with backward-compatible parameters.

        Args:
            github_token: GitHub personal access token (for backward compatibility)
            repo_name: Name of the GitHub repository (for backward compatibility)
            use_local_patches: Whether to use local patches instead of GitHub
            patch_dir: Directory for local patches when use_local_patches is True
            encryption_key: Key for encrypting credentials
            auto_discovery: Whether to automatically discover repositories
        """
        self.github_token = github_token
        self.repo_name = repo_name
        self.use_local_patches = use_local_patches
        self.patch_dir = patch_dir
        self.encryption_key = encryption_key
        self.auto_discovery = auto_discovery

        # Initialize the enhanced agent
        self.enhanced_agent: Optional[EnhancedRemediationAgent] = None
        self._initialized = False

        logger.info(
            f"[REMEDIATION_ADAPTER] Adapter initialized for repository: {repo_name}, "
            f"use_local_patches: {use_local_patches}"
        )

    async def _ensure_initialized(self) -> None:
        """Ensure the enhanced agent is initialized."""
        if not self._initialized:
            await self._initialize_enhanced_agent()
            self._initialized = True

    async def _initialize_enhanced_agent(self) -> None:
        """Initialize the enhanced remediation agent with appropriate configuration."""
        try:
            # Create source control configuration based on the original parameters
            if (
                self.use_local_patches
                or not self.github_token
                or self.github_token == "dummy_token"
            ):
                # Use local provider configuration

                config = SourceControlGlobalConfig(
                    max_concurrent_operations=1,
                    default_credentials=None,
                    default_remediation_strategy=None,
                )
            else:
                # Use GitHub provider configuration

                config = SourceControlGlobalConfig(
                    max_concurrent_operations=1,
                    default_credentials=None,
                    default_remediation_strategy=None,
                )

            # Initialize the enhanced agent
            self.enhanced_agent = EnhancedRemediationAgent(
                source_control_config=config,
                encryption_key=self.encryption_key,
                auto_discovery=self.auto_discovery,
                parallel_processing=False,  # Maintain sequential behavior for compatibility
                max_concurrent_operations=1,
            )

            await self.enhanced_agent.initialize()

            # Store credentials if using GitHub
            if (
                not self.use_local_patches
                and self.github_token
                and self.github_token != "dummy_token"
            ):
                # Note: credential_manager is not directly accessible from enhanced_agent
                # This would need to be implemented differently
                pass

            logger.info("[REMEDIATION_ADAPTER] Enhanced agent initialized successfully")

        except Exception as e:
            logger.error(
                f"[REMEDIATION_ADAPTER] Failed to initialize enhanced agent: {e}"
            )
            raise

    async def create_pull_request(
        self,
        remediation_plan: RemediationPlan,
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Creates a pull request on GitHub with the proposed service code fix.
        Falls back to local patches if GitHub is not available.

        This method maintains the exact same interface as the original RemediationAgent.

        Args:
            remediation_plan (RemediationPlan): The remediation plan containing the service code fix.
            branch_name (str): The name of the new branch to create for the pull request.
            base_branch (str): The name of the base branch to merge into (e.g., "main").
            flow_id (str): The flow ID for tracking this processing pipeline.
            issue_id (str): The issue ID from the triage analysis.

        Returns:
            str: The HTML URL of the created pull request or local patch file path.
        """
        await self._ensure_initialized()

        logger.info(
            f"[REMEDIATION_ADAPTER] Creating pull request: flow_id={flow_id}, "
            f"issue_id={issue_id}, branch={branch_name}, target={base_branch}"
        )

        try:
            # Use the enhanced agent to create the remediation
            if self.enhanced_agent is None:
                raise RuntimeError("Enhanced agent not initialized")
            result = await self.enhanced_agent.create_remediation(
                remediation_plan=remediation_plan,
                service_name="service",  # Default service name for backward compatibility
                flow_id=flow_id,
                issue_id=issue_id,
                target_repositories=None,  # Let auto-discovery handle this
                base_branch=base_branch,
                create_branch=True,
            )

            # Extract the result URL or path
            if result.get("successful_repositories", 0) > 0:
                # Get the first successful result
                for repo_result in result.get("results", {}).values():
                    if repo_result.get("success", False):
                        pr_info = repo_result.get("pull_request", {})
                        if isinstance(pr_info, dict):
                            return pr_info.get("url", "No URL available")
                        else:
                            return str(pr_info)

                # If no PR URL found, return a success message
                return f"Remediation created successfully for {result['successful_repositories']} repositories"
            else:
                # Fall back to local patch creation
                return await self._create_local_patch_fallback(
                    remediation_plan, flow_id, issue_id
                )

        except Exception as e:
            logger.error(f"[REMEDIATION_ADAPTER] Error creating pull request: {e}")
            # Fall back to local patch creation
            return await self._create_local_patch_fallback(
                remediation_plan, flow_id, issue_id
            )

    async def _create_local_patch_fallback(
        self,
        remediation_plan: RemediationPlan,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Create a local patch file as a fallback when the enhanced agent fails.

        Args:
            remediation_plan (RemediationPlan): The remediation plan containing the service code fix.
            flow_id (str): The flow ID for tracking this processing pipeline.
            issue_id (str): The issue ID from the triage analysis.

        Returns:
            str: Path to the created local patch file.
        """
        logger.info(
            f"[REMEDIATION_ADAPTER] Creating local patch fallback: flow_id={flow_id}, "
            f"issue_id={issue_id}"
        )

        try:
            # Use the original LocalPatchManager as a fallback
            from .local_patch_manager import LocalPatchManager

            patch_manager = LocalPatchManager(self.patch_dir)

            # Extract file path from the service code patch
            file_path = self._extract_file_path_from_patch(remediation_plan.code_patch)
            if not file_path:
                logger.warning(
                    f"[REMEDIATION_ADAPTER] Service code patch provided but no target file path found: "
                    f"flow_id={flow_id}, issue_id={issue_id}"
                )
                file_path = "unknown_file.py"  # fallback

            # Create local patch
            patch_file_path = patch_manager.create_patch(
                issue_id=issue_id,
                file_path=file_path,
                patch_content=remediation_plan.code_patch,
                description=remediation_plan.proposed_fix,
                severity="medium",  # Default severity since it's not available in this RemediationPlan
            )

            logger.info(
                f"[REMEDIATION_ADAPTER] Local patch created successfully: flow_id={flow_id}, "
                f"issue_id={issue_id}, patch_file={patch_file_path}"
            )
            return patch_file_path

        except Exception as e:
            logger.error(
                f"[REMEDIATION_ADAPTER] Error creating local patch fallback: flow_id={flow_id}, "
                f"issue_id={issue_id}, error={e}"
            )
            raise RuntimeError(f"Failed to create local patch: {e}") from e

    def _extract_file_path_from_patch(self, patch_content: str) -> Optional[str]:
        """
        Extracts the target file path from a special comment in the patch content.
        Supports multiple comment formats (e.g., # FILE:, // FILE:, /* FILE: */).
        Includes basic validation for the extracted file path.
        """
        if not patch_content.strip():
            return None

        lines = patch_content.strip().split("\n")
        if not lines:
            return None

        first_line = lines[0].strip()

        # Support multiple comment formats
        import re

        patterns = [
            r"#\s*FILE:\s*(.+)",  # # FILE: path/to/file
            r"//\s*FILE:\s*(.+)",  # // FILE: path/to/file
            r"/\*\s*FILE:\s*(.+)\s*\*/",  # /* FILE: path/to/file */
        ]

        for pattern in patterns:
            match = re.match(pattern, first_line)
            if match:
                file_path = match.group(1).strip()
                # Basic validation for file path
                if self._is_valid_file_path(file_path):
                    return file_path
                else:
                    logger.warning(
                        f"[REMEDIATION_ADAPTER] Invalid file path extracted: {file_path}"
                    )
                    return None

        return None

    def _is_valid_file_path(self, path: str) -> bool:
        """
        Validates that the extracted file path is safe and reasonable.
        Prevents directory traversal and absolute paths.
        """
        if not path or ".." in path or path.startswith("/") or path.startswith("\\"):
            return False
        return True

    async def close(self) -> None:
        """Close the enhanced agent and clean up resources."""
        if self.enhanced_agent:
            await self.enhanced_agent.close()
            logger.info("[REMEDIATION_ADAPTER] Enhanced agent closed")


# Backward compatibility alias
RemediationAgent = RemediationAgentAdapter
