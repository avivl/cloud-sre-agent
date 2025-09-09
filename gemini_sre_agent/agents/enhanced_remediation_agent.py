"""
Enhanced Remediation Agent with Multi-Provider Support.

This module provides an enhanced RemediationAgent that uses the new multi-provider
LLM system while maintaining backward compatibility with the original interface.
"""

import asyncio
import functools
import logging
import re
from typing import Any, List, Optional, Union

from github import Github as GitHubClient, GithubException
from github.Branch import Branch
from github.ContentFile import ContentFile
from github.PullRequest import PullRequest
from github.Repository import Repository

from ..llm.base import ModelType
from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .enhanced_base import EnhancedBaseAgent
from .response_models import RemediationResponse
from ..local_patch_manager import LocalPatchManager

logger = logging.getLogger(__name__)


class EnhancedRemediationAgent(EnhancedBaseAgent[RemediationResponse]):
    """
    Enhanced Remediation Agent with multi-provider support.
    
    Provides intelligent model selection for remediation tasks while maintaining
    backward compatibility with the original RemediationAgent interface.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        github_token: Optional[str] = None,
        repo_name: Optional[str] = None,
        use_local_patches: bool = False,
        patch_dir: str = "/tmp/real_patches",
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced remediation agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            github_token: GitHub personal access token
            repo_name: Name of the GitHub repository (e.g., "owner/repo")
            use_local_patches: Whether to use local patches instead of GitHub
            patch_dir: Directory for local patches when use_local_patches is True
            primary_model: Primary model for remediation tasks
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=RemediationResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.SMART,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        # Initialize GitHub and local patch management
        self.use_local_patches = use_local_patches
        self.repo_name = repo_name
        self.github: Optional[GitHubClient] = None
        self.repo: Optional[Repository] = None
        self.local_patch_manager: Optional[LocalPatchManager] = None
        
        if use_local_patches or not github_token or github_token == "dummy_token":
            self.local_patch_manager = LocalPatchManager(patch_dir)
            logger.info(
                f"[ENHANCED_REMEDIATION] EnhancedRemediationAgent initialized with local patches in: {patch_dir}"
            )
        else:
            self.github = GitHubClient(github_token)
            if repo_name:
                self.repo = self.github.get_repo(repo_name)
            logger.info(
                f"[ENHANCED_REMEDIATION] EnhancedRemediationAgent initialized for repository: {repo_name}"
            )

        logger.info("EnhancedRemediationAgent initialized with quality-focused optimization")

    async def create_pull_request(
        self,
        remediation_plan: RemediationResponse,
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Create a pull request on GitHub with the proposed service code fix.
        Falls back to local patches if GitHub is not available.

        Args:
            remediation_plan: The remediation plan containing the service code fix
            branch_name: The name of the new branch to create for the pull request
            base_branch: The name of the base branch to merge into (e.g., "main")
            flow_id: The flow ID for tracking this processing pipeline
            issue_id: The issue ID from the triage analysis

        Returns:
            str: The HTML URL of the created pull request or local patch file path
        """
        logger.info(
            f"[ENHANCED_REMEDIATION] Attempting to create pull request: flow_id={flow_id}, "
            f"issue_id={issue_id}, branch={branch_name}, target={base_branch}"
        )

        # If using local patches or GitHub is not available, create local patch
        if self.use_local_patches or self.github is None:
            return await self._create_local_patch(remediation_plan, flow_id, issue_id)

        try:
            # Check if GitHub repo is available
            if self.repo is None:
                logger.error(f"[ENHANCED_REMEDIATION] GitHub repository not available: flow_id={flow_id}, issue_id={issue_id}")
                return await self._create_local_patch(remediation_plan, flow_id, issue_id)
            
            # Get event loop for async operations
            loop = asyncio.get_event_loop()
            
            # 1. Get the base branch (non-blocking)
            base: Branch = await loop.run_in_executor(None, self.repo.get_branch, base_branch)
            logger.debug(
                f"[ENHANCED_REMEDIATION] Base branch found: flow_id={flow_id}, issue_id={issue_id}, "
                f"branch={base_branch}, sha={base.commit.sha}"
            )

            # 2. Create a new branch (idempotent, non-blocking)
            ref: str = f"refs/heads/{branch_name}"
            try:
                if self.repo is not None:
                    await loop.run_in_executor(
                        None,
                        functools.partial(self.repo.create_git_ref, ref=ref, sha=base.commit.sha)
                    )
                logger.info(
                    f"[ENHANCED_REMEDIATION] Branch created successfully: flow_id={flow_id}, "
                    f"issue_id={issue_id}, branch={branch_name}"
                )
            except GithubException as e:
                if e.status == 422 and "Reference already exists" in str(e.data):
                    # Branch already exists - this is fine for retry scenarios
                    logger.info(
                        f"[ENHANCED_REMEDIATION] Branch already exists (idempotent): flow_id={flow_id}, "
                        f"issue_id={issue_id}, branch={branch_name}"
                    )
                else:
                    raise

            # 3. Apply the service code fix (non-blocking operations)
            if remediation_plan.code_patch:
                file_path = self._extract_file_path_from_patch(remediation_plan.code_patch)
                if not file_path:
                    logger.warning(
                        f"[ENHANCED_REMEDIATION] Service code patch provided but no target file path found: "
                        f"flow_id={flow_id}, issue_id={issue_id}"
                    )
                else:
                    # Extract code content (skip the first line with FILE: comment)
                    content_to_write = "\n".join(
                        remediation_plan.code_patch.strip().split("\n")[1:]
                    )
                    try:
                        if self.repo is not None:
                            contents: Union[ContentFile, List[ContentFile]] = await loop.run_in_executor(
                                None, functools.partial(self.repo.get_contents, file_path, ref=branch_name)
                            )
                        else:
                            raise Exception("GitHub repository not available")
                        if isinstance(contents, list):  # Handle case where get_contents returns a list
                            logger.error(
                                f"[ERROR_HANDLING] Cannot update directory: flow_id={flow_id}, "
                                f"issue_id={issue_id}, path={file_path}"
                            )
                            raise RuntimeError(
                                f"Cannot update directory {file_path}. Expected a service code file."
                            )
                        
                        if self.repo is not None:
                            await loop.run_in_executor(
                                None,
                                functools.partial(
                                    self.repo.update_file,
                                    contents.path,
                                    f"Fix service issue in {file_path}",
                                    content_to_write,
                                    contents.sha,
                                    branch=branch_name
                                )
                            )
                        logger.info(
                            f"[ENHANCED_REMEDIATION] Updated service code file: flow_id={flow_id}, "
                            f"issue_id={issue_id}, file={file_path}"
                        )
                    except GithubException as e:
                        if e.status == 404:  # File does not exist, create it
                            if self.repo is not None:
                                await loop.run_in_executor(
                                    None,
                                    functools.partial(
                                        self.repo.create_file,
                                        file_path,
                                        f"Add service code fix in {file_path}",
                                        content_to_write,
                                        branch=branch_name
                                    )
                                )
                            logger.info(
                                f"[ENHANCED_REMEDIATION] Created service code file: flow_id={flow_id}, "
                                f"issue_id={issue_id}, file={file_path}"
                            )
                        else:
                            raise
            else:
                logger.warning(
                    f"[ENHANCED_REMEDIATION] No service code patch provided: flow_id={flow_id}, issue_id={issue_id}"
                )

            # 4. Create a pull request (non-blocking)
            title = f"Fix: {remediation_plan.proposed_fix[:50]}..."
            body = f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}"
            if self.repo is not None:
                pull_request: PullRequest = await loop.run_in_executor(
                    None,
                    functools.partial(
                        self.repo.create_pull,
                        title=title,
                        body=body,
                        head=branch_name,
                        base=base_branch
                    )
                )
                logger.info(
                    f"[ENHANCED_REMEDIATION] Pull request created successfully: flow_id={flow_id}, "
                    f"issue_id={issue_id}, pr_url={pull_request.html_url}"
                )
                return pull_request.html_url
            else:
                logger.error(f"[ENHANCED_REMEDIATION] Cannot create pull request - repository not available: flow_id={flow_id}, issue_id={issue_id}")
                return await self._create_local_patch(remediation_plan, flow_id, issue_id)

        except GithubException as e:
            logger.error(
                f"[ERROR_HANDLING] GitHub API error during PR creation: flow_id={flow_id}, "
                f"issue_id={issue_id}, status={e.status}, data={e.data}"
            )
            raise RuntimeError(
                f"Failed to create pull request due to GitHub API error: {e.data}"
            ) from e
        except Exception as e:
            logger.error(
                f"[ERROR_HANDLING] An unexpected error occurred during PR creation: flow_id={flow_id}, "
                f"issue_id={issue_id}, error={e}"
            )
            raise RuntimeError(f"Failed to create pull request: {e}") from e

    def _extract_file_path_from_patch(self, patch_content: str) -> Optional[str]:
        """
        Extract the target file path from a special comment in the patch content.
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
        Validate that the extracted file path is safe and reasonable.
        Prevent directory traversal and absolute paths.
        """
        if not path or ".." in path or path.startswith("/") or path.startswith("\\"):
            return False
        return True

    async def _create_local_patch(
        self,
        remediation_plan: RemediationResponse,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Create a local patch file when GitHub is not available.

        Args:
            remediation_plan: The remediation plan containing the service code fix
            flow_id: The flow ID for tracking this processing pipeline
            issue_id: The issue ID from the triage analysis

        Returns:
            str: Path to the created local patch file
        """
        logger.info(
            f"[ENHANCED_REMEDIATION] Creating local patch: flow_id={flow_id}, issue_id={issue_id}"
        )

        try:
            # Extract file path from the service code patch
            file_path = self._extract_file_path_from_patch(remediation_plan.code_patch)
            if not file_path:
                logger.warning(
                    f"[ENHANCED_REMEDIATION] Service code patch provided but no target file path found: "
                    f"flow_id={flow_id}, issue_id={issue_id}"
                )
                file_path = "unknown_file.py"  # fallback

            # Create local patch
            if self.local_patch_manager is None:
                raise RuntimeError("Local patch manager is not initialized")
            patch_file_path = self.local_patch_manager.create_patch(
                issue_id=issue_id,
                file_path=file_path,
                patch_content=remediation_plan.code_patch,
                description=remediation_plan.proposed_fix,
                severity=remediation_plan.priority
            )

            logger.info(
                f"[ENHANCED_REMEDIATION] Local patch created successfully: flow_id={flow_id}, "
                f"issue_id={issue_id}, patch_file={patch_file_path}"
            )
            return patch_file_path

        except Exception as e:
            logger.error(
                f"[ERROR_HANDLING] Error creating local patch: flow_id={flow_id}, "
                f"issue_id={issue_id}, error={e}"
            )
            raise RuntimeError(f"Failed to create local patch: {e}") from e

    # Backward compatibility method
    async def create_pull_request_legacy(
        self,
        remediation_plan: Any,  # Original RemediationPlan type
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Legacy compatibility method that accepts the old RemediationPlan format.
        
        Args:
            remediation_plan: Original RemediationPlan object
            branch_name: The name of the new branch to create for the pull request
            base_branch: The name of the base branch to merge into
            flow_id: The flow ID for tracking this processing pipeline
            issue_id: The issue ID from the triage analysis
            
        Returns:
            str: The HTML URL of the created pull request or local patch file path
        """
        # Convert legacy RemediationPlan to new RemediationResponse
        if hasattr(remediation_plan, 'model_dump'):
            plan_data = remediation_plan.model_dump()
        elif hasattr(remediation_plan, 'dict'):
            plan_data = remediation_plan.dict()
        else:
            plan_data = remediation_plan.__dict__
        
        # Create new RemediationResponse
        new_plan = RemediationResponse(
            root_cause_analysis=plan_data.get("root_cause_analysis", ""),
            proposed_fix=plan_data.get("proposed_fix", ""),
            code_patch=plan_data.get("code_patch", ""),
            priority="medium",  # Default priority
            estimated_effort="unknown",  # Default effort
        )
        
        return await self.create_pull_request(new_plan, branch_name, base_branch, flow_id, issue_id)
