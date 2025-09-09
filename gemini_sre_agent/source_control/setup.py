# gemini_sre_agent/source_control/setup.py

from typing import Optional

from ..config.source_control_global import (
    SourceControlConfig,
    SourceControlGlobalConfig,
)
from .credential_manager import CredentialManager, EnvironmentBackend, FileBackend
from .provider_factory import ProviderFactory
from .providers.github_provider import GitHubProvider
from .providers.local_provider import LocalProvider
from .repository_manager import RepositoryManager


async def setup_repository_system(
    config: SourceControlGlobalConfig, encryption_key: Optional[str] = None
) -> RepositoryManager:
    """Set up the complete repository management system."""

    # Set up credential manager with backends
    credential_manager = CredentialManager(encryption_key=encryption_key)
    credential_manager.register_backend("env", EnvironmentBackend(), default=True)
    credential_manager.register_backend("file", FileBackend())

    # Set up provider factory
    provider_factory = ProviderFactory(credential_manager)
    provider_factory.register_provider("github", GitHubProvider)
    provider_factory.register_provider("local", LocalProvider)

    # Create and initialize repository manager
    repo_manager = RepositoryManager(config, provider_factory)
    await repo_manager.initialize()

    return repo_manager


def create_default_config() -> SourceControlConfig:
    """Create a default configuration for testing purposes."""
    from ..config.source_control_repositories import (
        GitHubRepositoryConfig,
        LocalRepositoryConfig,
    )

    return SourceControlConfig(
        repositories=[
            GitHubRepositoryConfig(
                name="test-github-repo", url="https://github.com/test/repo"
            ),
            LocalRepositoryConfig(name="test-local-repo", path="/tmp/test-repo"),
        ]
    )
