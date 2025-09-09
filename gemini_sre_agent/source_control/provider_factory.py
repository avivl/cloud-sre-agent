# gemini_sre_agent/source_control/provider_factory.py

import importlib
import logging
from typing import Dict, Type

from ..config.source_control_repositories import RepositoryConfig
from .base import SourceControlProvider
from .credential_manager import CredentialManager


class ProviderFactory:
    """Creates and manages source control provider instances."""

    def __init__(self, credential_manager: CredentialManager):
        self.credential_manager = credential_manager
        self.provider_registry: Dict[str, Type[SourceControlProvider]] = {}
        self.logger = logging.getLogger(__name__)

    def register_provider(
        self, provider_type: str, provider_class: Type[SourceControlProvider]
    ) -> None:
        """Register a provider class for a specific provider type."""
        self.provider_registry[provider_type] = provider_class
        self.logger.debug(f"Registered provider: {provider_type}")

    def register_providers_from_modules(self, module_names: list) -> None:
        """Dynamically load and register providers from specified modules."""
        for module_name in module_names:
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, "register_providers"):
                    module.register_providers(self)
                    self.logger.info(f"Registered providers from module: {module_name}")
            except ImportError as e:
                self.logger.error(
                    f"Failed to import provider module {module_name}: {str(e)}"
                )

    async def create_provider(
        self, repo_config: RepositoryConfig
    ) -> SourceControlProvider:
        """Create a provider instance based on repository configuration."""
        provider_type = repo_config.type

        if provider_type not in self.provider_registry:
            raise ValueError(f"Unsupported provider type: {provider_type}")

        provider_class = self.provider_registry[provider_type]

        # Create and return the provider instance
        # The provider will handle credential management internally
        return provider_class(repo_config.model_dump())
