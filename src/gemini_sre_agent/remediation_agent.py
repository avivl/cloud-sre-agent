import logging
from github import Github, GithubException
from .analysis_agent import RemediationPlan
from github.Repository import Repository
from github.Branch import Branch
from github.PullRequest import PullRequest
from github.ContentFile import ContentFile
import re
from typing import Optional, Union, List

logger = logging.getLogger(__name__)


class RemediationAgent:
    """
    A class responsible for creating pull requests on GitHub with proposed remediation plans.
    """

    def __init__(self, github_token: str, repo_name: str):
        """
        Initializes the RemediationAgent with a GitHub token and repository name.

        Args:
            github_token (str): The GitHub personal access token.
            repo_name (str): The name of the GitHub repository (e.g., "owner/repo").
        """
        self.github: Github = Github(github_token)
        self.repo: Repository = self.github.get_repo(repo_name)
        logger.info(f"RemediationAgent initialized for repository: {repo_name}")

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
                    logger.warning(f"Invalid file path extracted: {file_path}")
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

    async def create_pull_request(
        self, remediation_plan: RemediationPlan, branch_name: str, base_branch: str
    ) -> str:  # Changed to async def
        """
        Creates a pull request on GitHub with the proposed fix.

        Args:
            remediation_plan (RemediationPlan): The remediation plan containing the fix details.
            branch_name (str): The name of the new branch to create for the pull request.
            base_branch (str): The name of the base branch to merge into (e.g., "main").

        Returns:
            str: The HTML URL of the created pull request.
        """
        logger.info(
            f"Attempting to create pull request for branch {branch_name} targeting {base_branch}..."
        )

        try:
            # 1. Get the base branch
            base: Branch = self.repo.get_branch(base_branch)
            logger.debug(
                f"Base branch '{base_branch}' found with SHA: {base.commit.sha}"
            )

            # 2. Create a new branch
            ref: str = f"refs/heads/{branch_name}"
            self.repo.create_git_ref(ref=ref, sha=base.commit.sha)
            logger.info(f"Branch '{branch_name}' created successfully.")

            # 3. Create/Update files with the proposed fix
            # Process code_patch
            if remediation_plan.code_patch:
                file_path_code = self._extract_file_path_from_patch(
                    remediation_plan.code_patch
                )
                if not file_path_code:
                    logger.warning(
                        "Code patch provided but no target file path found in comment. Skipping code patch."
                    )
                else:
                    content_to_write = "\n".join(
                        remediation_plan.code_patch.strip().split("\n")[1:]
                    )
                    try:
                        contents: Union[ContentFile, List[ContentFile]] = (
                            self.repo.get_contents(file_path_code, ref=branch_name)
                        )
                        if isinstance(
                            contents, list
                        ):  # Handle case where get_contents returns a list (i.e., it's a directory)
                            logger.error(
                                f"Cannot update directory {file_path_code}. Expected a file."
                            )
                            raise RuntimeError(
                                f"Cannot update directory {file_path_code}. Expected a file."
                            )
                        self.repo.update_file(
                            contents.path,
                            f"Update {file_path_code}",
                            content_to_write,
                            contents.sha,
                            branch=branch_name,
                        )
                        logger.info(f"Updated code patch file: {file_path_code}")
                    except GithubException as e:
                        if e.status == 404:  # File does not exist, create it
                            self.repo.create_file(
                                file_path_code,
                                f"Add {file_path_code}",
                                content_to_write,
                                branch=branch_name,
                            )
                            logger.info(f"Created code patch file: {file_path_code}")
                        else:
                            raise

            # Process iac_fix
            if remediation_plan.iac_fix:
                file_path_iac = self._extract_file_path_from_patch(
                    remediation_plan.iac_fix
                )
                if not file_path_iac:
                    logger.warning(
                        "IaC patch provided but no target file path found in comment. Skipping IaC patch."
                    )
                else:
                    content_to_write = "\n".join(
                        remediation_plan.iac_fix.strip().split("\n")[1:]
                    )
                    try:
                        contents: Union[ContentFile, List[ContentFile]] = (
                            self.repo.get_contents(file_path_iac, ref=branch_name)
                        )
                        if isinstance(
                            contents, list
                        ):  # Handle case where get_contents returns a list (i.e., it's a directory)
                            logger.error(
                                f"Cannot update directory {file_path_iac}. Expected a file."
                            )
                            raise RuntimeError(
                                f"Cannot update directory {file_path_iac}. Expected a file."
                            )
                        self.repo.update_file(
                            contents.path,
                            f"Update {file_path_iac}",
                            content_to_write,
                            contents.sha,
                            branch=branch_name,
                        )
                        logger.info(f"Updated IaC patch file: {file_path_iac}")
                    except GithubException as e:
                        if e.status == 404:  # File does not exist, create it
                            self.repo.create_file(
                                file_path_iac,
                                f"Add {file_path_iac}",
                                content_to_write,
                                branch=branch_name,
                            )
                            logger.info(f"Created IaC patch file: {file_path_iac}")
                        else:
                            raise

            # 4. Create a pull request
            pull_request: PullRequest = self.repo.create_pull(
                title=f"Fix: {remediation_plan.proposed_fix[:50]}...",  # Truncate title if too long
                body=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                head=branch_name,
                base=base_branch,
            )
            logger.info(f"Pull request created successfully: {pull_request.html_url}")
            return pull_request.html_url

        except GithubException as e:
            logger.error(f"GitHub API error during PR creation: {e.status} - {e.data}")
            raise RuntimeError(
                f"Failed to create pull request due to GitHub API error: {e.data}"
            ) from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during PR creation: {e}")
            raise RuntimeError(f"Failed to create pull request: {e}") from e
