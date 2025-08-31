import logging
from github import Github, GithubException
from .analysis_agent import RemediationPlan
from github.Repository import Repository
from github.Branch import Branch
from github.PullRequest import PullRequest

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

    def create_pull_request(self, remediation_plan: RemediationPlan, branch_name: str, base_branch: str) -> str:
        """
        Creates a pull request on GitHub with the proposed fix.

        Args:
            remediation_plan (RemediationPlan): The remediation plan containing the fix details.
            branch_name (str): The name of the new branch to create for the pull request.
            base_branch (str): The name of the base branch to merge into (e.g., "main").

        Returns:
            str: The HTML URL of the created pull request.
        """
        logger.info(f"Attempting to create pull request for branch {branch_name} targeting {base_branch}...")

        try:
            # 1. Get the base branch
            base: Branch = self.repo.get_branch(base_branch)
            logger.debug(f"Base branch '{base_branch}' found with SHA: {base.commit.sha}")

            # 2. Create a new branch
            ref: str = f"refs/heads/{branch_name}"
            self.repo.create_git_ref(ref=ref, sha=base.commit.sha)
            logger.info(f"Branch '{branch_name}' created successfully.")

            # 3. Create/Update files with the proposed fix
            # This is a simplification. In a real scenario, determining the exact file paths
            # and handling existing file content would be more complex.
            # For now, we assume the code_patch and iac_fix contain the full file content
            # and we'll use placeholder paths.
            
            # Example for code_patch (assuming a file named 'fix.py' in the root of the repo)
            if remediation_plan.code_patch:
                file_path_code: str = "fix/code_patch.py"
                try:
                    contents = self.repo.get_contents(file_path_code, ref=branch_name)
                    self.repo.update_file(contents.path, "Update code patch", remediation_plan.code_patch, contents.sha, branch=branch_name)
                    logger.info(f"Updated code patch file: {file_path_code}")
                except GithubException as e:
                    if e.status == 404: # File does not exist, create it
                        self.repo.create_file(file_path_code, "Add code patch", remediation_plan.code_patch, branch=branch_name)
                        logger.info(f"Created code patch file: {file_path_code}")
                    else:
                        raise
            
            # Example for iac_fix (assuming a file named 'iac_fix.tf' in the root of the repo)
            if remediation_plan.iac_fix:
                file_path_iac: str = "fix/iac_patch.tf"
                try:
                    contents = self.repo.get_contents(file_path_iac, ref=branch_name)
                    self.repo.update_file(contents.path, "Update IaC patch", remediation_plan.iac_fix, contents.sha, branch=branch_name)
                    logger.info(f"Updated IaC patch file: {file_path_iac}")
                except GithubException as e:
                    if e.status == 404: # File does not exist, create it
                        self.repo.create_file(file_path_iac, "Add IaC patch", remediation_plan.iac_fix, branch=branch_name)
                        logger.info(f"Created IaC patch file: {file_path_iac}")
                    else:
                        raise

            # 4. Create a pull request
            pull_request: PullRequest = self.repo.create_pull(
                title=f"Fix: {remediation_plan.proposed_fix[:50]}...", # Truncate title if too long
                body=f"Root Cause Analysis:\n{remediation_plan.root_cause_analysis}\n\nProposed Fix:\n{remediation_plan.proposed_fix}",
                head=branch_name,
                base=base_branch
            )
            logger.info(f"Pull request created successfully: {pull_request.html_url}")
            return pull_request.html_url # Return the URL of the created PR

        except GithubException as e:
            logger.error(f"GitHub API error during PR creation: {e.status} - {e.data}")
            raise RuntimeError(f"Failed to create pull request due to GitHub API error: {e.data}") from e
        except Exception as e:
            logger.error(f"An unexpected error occurred during PR creation: {e}")
            raise RuntimeError(f"Failed to create pull request: {e}") from e
