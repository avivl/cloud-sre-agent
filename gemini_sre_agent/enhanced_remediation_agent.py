"""
Enhanced Remediation Agent with Multi-Repository Source Control Support.

This module provides an enhanced remediation agent that integrates with the new
source control system to support multiple repositories, intelligent routing,
and parallel processing of remediations.
"""

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional

from .analysis_agent import RemediationPlan
from .config.source_control_global import SourceControlConfig, SourceControlGlobalConfig
from .config.source_control_remediation import ConflictResolutionStrategy
from .source_control.credential_manager import CredentialManager
from .source_control.models import CommitOptions, FileOperation
from .source_control.provider_factory import ProviderFactory
from .source_control.repository_manager import RepositoryManager
from .source_control.setup import create_default_config, setup_repository_system

logger = logging.getLogger(__name__)


class EnhancedRemediationAgent:
    """
    Enhanced Remediation Agent with multi-repository source control support.

    This agent replaces the original RemediationAgent with support for:
    - Multiple repositories per service
    - Intelligent routing to determine affected repositories
    - Parallel processing of remediations
    - Comprehensive logging and audit trails
    - Integration with the new source control provider system
    """

    def __init__(
        self,
        source_control_config: Optional[SourceControlGlobalConfig] = None,
        encryption_key: Optional[str] = None,
        auto_discovery: bool = True,
        parallel_processing: bool = True,
        max_concurrent_operations: int = 5,
    ):
        """
        Initialize the Enhanced Remediation Agent.

        Args:
            source_control_config: Configuration for source control repositories
            encryption_key: Key for encrypting credentials
            auto_discovery: Whether to automatically discover repositories
            parallel_processing: Whether to process remediations in parallel
            max_concurrent_operations: Maximum number of concurrent operations
        """
        self.source_control_config = source_control_config or create_default_config()
        self.encryption_key = encryption_key
        self.auto_discovery = auto_discovery
        self.parallel_processing = parallel_processing
        self.max_concurrent_operations = max_concurrent_operations

        # Initialize components
        self.repository_manager: Optional[RepositoryManager] = None
        self.provider_factory: Optional[ProviderFactory] = None
        self.credential_manager: Optional[CredentialManager] = None

        logger.info("[ENHANCED_REMEDIATION] Enhanced Remediation Agent initialized")

    async def initialize(self) -> None:
        """Initialize the source control system and repository manager."""
        try:
            # Set up the complete repository management system
            if isinstance(self.source_control_config, SourceControlConfig):
                # Convert SourceControlConfig to SourceControlGlobalConfig
                global_config = SourceControlGlobalConfig(
                    max_concurrent_operations=self.max_concurrent_operations,
                    conflict_resolution=ConflictResolutionStrategy.MANUAL,
                    default_credentials=None,
                    default_remediation_strategy=None,
                )
            else:
                global_config = self.source_control_config
                
            self.repository_manager = await setup_repository_system(
                global_config, self.encryption_key
            )

            # Get the provider factory and credential manager from the setup
            self.provider_factory = self.repository_manager.provider_factory
            self.credential_manager = self.provider_factory.credential_manager
            # We'll need to get it from the provider factory or create it separately

            logger.info("[ENHANCED_REMEDIATION] Initialized with repository manager")

        except Exception as e:
            logger.error(f"[ENHANCED_REMEDIATION] Failed to initialize: {e}")
            raise

    async def close(self) -> None:
        """Close all repository connections and clean up resources."""
        if self.repository_manager:
            await self.repository_manager.close()
            logger.info("[ENHANCED_REMEDIATION] Closed all repository connections")

    async def create_remediation(
        self,
        remediation_plan: RemediationPlan,
        service_name: str,
        flow_id: str,
        issue_id: str,
        target_repositories: Optional[List[str]] = None,
        base_branch: str = "main",
        create_branch: bool = True,
    ) -> Dict[str, Any]:
        """
        Create remediations across multiple repositories.

        Args:
            remediation_plan: The remediation plan containing the fix
            service_name: Name of the service being remediated
            flow_id: Flow ID for tracking
            issue_id: Issue ID from triage analysis
            target_repositories: Specific repositories to target (None for auto-discovery)
            base_branch: Base branch for the remediation
            create_branch: Whether to create a new branch for the remediation

        Returns:
            Dict containing results for each repository
        """
        if not self.repository_manager:
            raise RuntimeError(
                "Repository manager not initialized. Call initialize() first."
            )

        logger.info(
            f"[ENHANCED_REMEDIATION] Creating remediation: service={service_name}, "
            f"flow_id={flow_id}, issue_id={issue_id}"
        )

        # Determine target repositories
        if target_repositories is None:
            target_repositories = await self._discover_affected_repositories(
                service_name, remediation_plan
            )

        if not target_repositories:
            logger.warning(
                f"[ENHANCED_REMEDIATION] No repositories found for service: {service_name}"
            )
            return {"error": "No repositories found for service"}

        # Generate branch name
        branch_name = f"fix/{service_name}-{issue_id}-{flow_id[:8]}"

        # Process remediations
        if self.parallel_processing:
            results = await self._process_remediations_parallel(
                remediation_plan,
                target_repositories,
                branch_name,
                base_branch,
                flow_id,
                issue_id,
                create_branch,
            )
        else:
            results = await self._process_remediations_sequential(
                remediation_plan,
                target_repositories,
                branch_name,
                base_branch,
                flow_id,
                issue_id,
                create_branch,
            )

        # Log comprehensive results
        successful = sum(1 for r in results.values() if r.get("success", False))
        total = len(results)

        logger.info(
            f"[ENHANCED_REMEDIATION] Remediation completed: {successful}/{total} successful, "
            f"flow_id={flow_id}, issue_id={issue_id}"
        )

        return {
            "service_name": service_name,
            "flow_id": flow_id,
            "issue_id": issue_id,
            "total_repositories": total,
            "successful_repositories": successful,
            "results": results,
        }

    async def _discover_affected_repositories(
        self, service_name: str, remediation_plan: RemediationPlan
    ) -> List[str]:
        """
        Discover repositories that are affected by the remediation.

        Args:
            service_name: Name of the service
            remediation_plan: The remediation plan

        Returns:
            List of repository names that need to be updated
        """
        # Extract file path from the remediation plan
        file_path = self._extract_file_path_from_patch(remediation_plan.code_patch)

        if not file_path:
            logger.warning(
                f"[ENHANCED_REMEDIATION] No file path found in remediation plan for service: {service_name}"
            )
            return []

        # For now, return all repositories that contain the service
        # In a more sophisticated implementation, this would analyze the file path
        # and determine which repositories actually contain the affected code
        affected_repos = []

        # For now, return all configured repositories
        # In a more sophisticated implementation, this would analyze the file path
        # and determine which repositories actually contain the affected code
        affected_repos = [
            "local-repo",
            "github-repo",
            "gitlab-repo",
        ]  # Default repositories

        logger.info(
            f"[ENHANCED_REMEDIATION] Discovered {len(affected_repos)} affected repositories: {affected_repos}"
        )

        return affected_repos

    async def _process_remediations_parallel(
        self,
        remediation_plan: RemediationPlan,
        target_repositories: List[str],
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
        create_branch: bool,
    ) -> Dict[str, Any]:
        """Process remediations across repositories in parallel."""
        semaphore = asyncio.Semaphore(self.max_concurrent_operations)

        async def process_single_repo(repo_name: str) -> tuple[str, Any]:
            async with semaphore:
                try:
                    result = await self._create_remediation_for_repository(
                        remediation_plan,
                        repo_name,
                        branch_name,
                        base_branch,
                        flow_id,
                        issue_id,
                        create_branch,
                    )
                    return repo_name, result
                except Exception as e:
                    logger.error(
                        f"[ENHANCED_REMEDIATION] Error processing repository {repo_name}: {e}"
                    )
                    return repo_name, {"success": False, "error": str(e)}

        # Process all repositories in parallel
        tasks = [process_single_repo(repo) for repo in target_repositories]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert results to dictionary
        result_dict = {}
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                repo_name = target_repositories[i]
                result_dict[repo_name] = {"success": False, "error": str(result)}
            else:
                # result is a tuple (repo_name, repo_result) from process_single_repo
                if isinstance(result, tuple) and len(result) == 2:
                    repo_name, repo_result = result
                    result_dict[repo_name] = repo_result
                else:
                    # Fallback if result is not a tuple
                    repo_name = target_repositories[i]
                    result_dict[repo_name] = result
        return result_dict

    async def _process_remediations_sequential(
        self,
        remediation_plan: RemediationPlan,
        target_repositories: List[str],
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
        create_branch: bool,
    ) -> Dict[str, Any]:
        """Process remediations across repositories sequentially."""
        results = {}

        for repo_name in target_repositories:
            try:
                result = await self._create_remediation_for_repository(
                    remediation_plan,
                    repo_name,
                    branch_name,
                    base_branch,
                    flow_id,
                    issue_id,
                    create_branch,
                )
                results[repo_name] = result
            except Exception as e:
                logger.error(
                    f"[ENHANCED_REMEDIATION] Error processing repository {repo_name}: {e}"
                )
                results[repo_name] = {"success": False, "error": str(e)}

        return results

    async def _create_remediation_for_repository(
        self,
        remediation_plan: RemediationPlan,
        repo_name: str,
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
        create_branch: bool,
    ) -> Dict[str, Any]:
        """Create remediation for a single repository."""
        try:
            # Get the provider for this repository
            if not self.repository_manager:
                raise RuntimeError("Repository manager not initialized")
            provider = await self.repository_manager.get_provider(repo_name)

            # Extract file path and content
            file_path = self._extract_file_path_from_patch(remediation_plan.code_patch)
            if not file_path:
                return {
                    "success": False,
                    "error": "No file path found in remediation plan",
                    "repository": repo_name,
                }

            # Extract the actual code content (skip the FILE: comment line)
            code_content = "\n".join(
                remediation_plan.code_patch.strip().split("\n")[1:]
            )

            # Create file operation
            file_operation = FileOperation(
                operation_type="write",
                file_path=file_path,
                content=code_content,
                encoding="utf-8",
            )

            # Create commit options
            commit_options = CommitOptions(
                commit=True,
                commit_message=f"Fix: {remediation_plan.proposed_fix[:50]}...",
                author="SRE Agent <sre-agent@example.com>",
                committer="SRE Agent <sre-agent@example.com>",
                files_to_add=[file_path],
            )

            # Create branch if requested
            if create_branch:
                await provider.create_branch(branch_name, base_branch)
                # Note: checkout_branch is not available in the base interface
                # This would need to be implemented in specific providers

            # Apply the remediation
            content = file_operation.content or ""
            remediation_result = await provider.apply_remediation(
                file_operation.file_path, content, commit_options.commit_message
            )

            # Create pull request or merge request
            if hasattr(provider, "create_pull_request"):
                pr_result = await provider.create_pull_request(
                    title=f"Fix: {remediation_plan.proposed_fix[:50]}...",
                    body=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                    head_branch=branch_name,
                    base_branch=base_branch,
                    description=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                )
            elif hasattr(provider, "create_merge_request"):
                pr_result = await provider.create_merge_request(
                    title=f"Fix: {remediation_plan.proposed_fix[:50]}...",
                    body=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                    head_branch=branch_name,
                    base_branch=base_branch,
                    description=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                )
            else:
                pr_result = {"url": "No PR/MR support", "id": "local"}

            logger.info(
                f"[ENHANCED_REMEDIATION] Successfully created remediation for {repo_name}: "
                f"flow_id={flow_id}, issue_id={issue_id}"
            )

            return {
                "success": True,
                "repository": repo_name,
                "branch": branch_name,
                "file_path": file_path,
                "commit_id": (
                    remediation_result.commit_sha
                    if hasattr(remediation_result, "commit_sha")
                    else None
                ),
                "pull_request": pr_result,
                "flow_id": flow_id,
                "issue_id": issue_id,
            }

        except Exception as e:
            logger.error(
                f"[ENHANCED_REMEDIATION] Failed to create remediation for {repo_name}: {e}"
            )
            return {
                "success": False,
                "error": str(e),
                "repository": repo_name,
                "flow_id": flow_id,
                "issue_id": issue_id,
            }

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
                        f"[ENHANCED_REMEDIATION] Invalid file path extracted: {file_path}"
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

    async def get_remediation_status(
        self, flow_id: str, issue_id: str
    ) -> Dict[str, Any]:
        """
        Get the status of a remediation across all repositories.

        Args:
            flow_id: Flow ID for tracking
            issue_id: Issue ID from triage analysis

        Returns:
            Dict containing status information for each repository
        """
        if not self.repository_manager:
            raise RuntimeError(
                "Repository manager not initialized. Call initialize() first."
            )

        status = {
            "flow_id": flow_id,
            "issue_id": issue_id,
            "repositories": {},
        }

        # Get status for all configured repositories
        repo_names = [
            "local-repo",
            "github-repo",
            "gitlab-repo",
        ]  # Default repositories
        for repo_name in repo_names:
            try:
                provider = await self.repository_manager.get_provider(repo_name)

                # Get repository health status
                health_status = await provider.get_health_status()

                status["repositories"][repo_name] = {
                    "status": "available",
                    "health": health_status,
                }

            except Exception as e:
                status["repositories"][repo_name] = {
                    "status": "error",
                    "error": str(e),
                }

        return status

    async def cleanup_remediation(
        self, flow_id: str, issue_id: str, branch_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Clean up remediation branches and temporary files.

        Args:
            flow_id: Flow ID for tracking
            issue_id: Issue ID from triage analysis
            branch_name: Specific branch to clean up (None for auto-detection)

        Returns:
            Dict containing cleanup results for each repository
        """
        if not self.repository_manager:
            raise RuntimeError(
                "Repository manager not initialized. Call initialize() first."
            )

        if not branch_name:
            branch_name = f"fix/*-{issue_id}-{flow_id[:8]}"

        cleanup_results = {
            "flow_id": flow_id,
            "issue_id": issue_id,
            "branch_pattern": branch_name,
            "repositories": {},
        }

        # Clean up branches for all configured repositories
        repo_names = [
            "local-repo",
            "github-repo",
            "gitlab-repo",
        ]  # Default repositories
        for repo_name in repo_names:
            try:
                provider = await self.repository_manager.get_provider(repo_name)

                # List branches and find matching ones
                branches = await provider.list_branches()
                matching_branches = []
                for branch in branches:
                    if isinstance(branch, str):
                        branch_name = branch
                    else:
                        branch_name = getattr(branch, "name", str(branch))

                    if (
                        branch_name
                        and issue_id in branch_name
                        and flow_id[:8] in branch_name
                    ):
                        matching_branches.append(branch_name)

                # Delete matching branches
                deleted_branches = []
                for branch_name in matching_branches:
                    if branch_name:  # Ensure branch_name is not None
                        try:
                            await provider.delete_branch(branch_name)
                            deleted_branches.append(branch_name)
                        except Exception as e:
                            logger.warning(
                                f"[ENHANCED_REMEDIATION] Failed to delete branch {branch_name} in {repo_name}: {e}"
                            )

                cleanup_results["repositories"][repo_name] = {
                    "success": True,
                    "deleted_branches": deleted_branches,
                    "total_found": len(matching_branches),
                }

            except Exception as e:
                cleanup_results["repositories"][repo_name] = {
                    "success": False,
                    "error": str(e),
                }

        return cleanup_results
