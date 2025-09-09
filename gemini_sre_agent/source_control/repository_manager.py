# gemini_sre_agent/source_control/repository_manager.py

import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from ..config.source_control_global import SourceControlGlobalConfig
from .base import SourceControlProvider
from .provider_factory import ProviderFactory


class RepositoryManager:
    """Coordinates operations across multiple source control repositories."""

    def __init__(
        self,
        global_config: SourceControlGlobalConfig,
        provider_factory: ProviderFactory,
    ):
        self.global_config = global_config
        self.provider_factory = provider_factory
        self.repositories: Dict[str, SourceControlProvider] = {}
        self.logger = logging.getLogger(__name__)
        self._exit_stack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize all repositories defined in the configuration."""
        # For now, this is a placeholder implementation
        # The actual implementation will depend on how repositories are configured
        # in the global configuration
        self.logger.info("Repository manager initialized (placeholder implementation)")

    async def close(self) -> None:
        """Close all repository connections."""
        await self._exit_stack.aclose()
        self.repositories.clear()

    async def get_provider(self, repo_name: str) -> SourceControlProvider:
        """Get a provider instance by repository name."""
        if repo_name not in self.repositories:
            raise ValueError(f"Repository '{repo_name}' not found or not initialized")
        return self.repositories[repo_name]

    async def execute_across_repos(
        self, operation, repos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Execute an operation across multiple repositories."""
        results = {}
        target_repos = repos or list(self.repositories.keys())

        for repo_name in target_repos:
            if repo_name not in self.repositories:
                self.logger.warning(f"Repository '{repo_name}' not found, skipping")
                continue

            try:
                provider = self.repositories[repo_name]
                results[repo_name] = await operation(provider)
            except Exception as e:
                self.logger.error(
                    f"Operation failed for repository '{repo_name}': {str(e)}"
                )
                results[repo_name] = {"error": str(e)}

        return results

    async def health_check(self) -> Dict[str, bool]:
        """Check the health of all repositories."""

        async def check_health(provider: SourceControlProvider) -> bool:
            try:
                return await provider.test_connection()
            except Exception:
                return False

        return await self.execute_across_repos(check_health)

    async def get_repository_info(self, repo_name: str) -> Optional[Any]:
        """Get information about a specific repository."""
        try:
            provider = await self.get_provider(repo_name)
            return await provider.get_repository_info()
        except Exception as e:
            self.logger.error(
                f"Failed to get repository info for '{repo_name}': {str(e)}"
            )
            return None

    async def list_all_branches(
        self, repos: Optional[List[str]] = None
    ) -> Dict[str, List[str]]:
        """List branches for all or specified repositories."""

        async def get_branches(provider: SourceControlProvider) -> List[str]:
            try:
                branches = await provider.list_branches()
                return [branch.name for branch in branches]
            except Exception:
                return []

        return await self.execute_across_repos(get_branches, repos)

    async def apply_remediation_across_repos(
        self, path: str, content: str, message: str, repos: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Apply remediation across multiple repositories."""

        async def apply_fix(provider: SourceControlProvider) -> Any:
            try:
                return await provider.apply_remediation(path, content, message)
            except Exception as e:
                return {"error": str(e)}

        return await self.execute_across_repos(apply_fix, repos)
