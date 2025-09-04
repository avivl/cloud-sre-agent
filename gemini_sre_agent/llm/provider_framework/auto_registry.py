"""
Automatic Provider Registration System.

This module provides automatic discovery and registration of provider implementations,
making it easy to add new providers without manual registration.
"""

import importlib
import importlib.util
import inspect
import logging
import os
import pkgutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..base import LLMProvider
from ..factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class ProviderAutoRegistry:
    """
    Automatic provider registration system.

    Discovers and registers provider implementations automatically,
    supporting both built-in and external providers.
    """

    def __init__(self):
        self.discovered_providers: Dict[str, Type[LLMProvider]] = {}
        self.external_providers: Dict[str, str] = {}  # name -> module_path
        self._initialized = False

    def discover_builtin_providers(
        self, package_path: str = "gemini_sre_agent.llm.providers"
    ) -> None:
        """
        Discover built-in provider implementations.

        Args:
            package_path: Path to the providers package
        """
        try:
            package = importlib.import_module(package_path)
            if package.__file__ is None:
                logger.warning(f"Package {package_path} has no __file__ attribute")
                return
            package_dir = Path(package.__file__).parent

            # Discover all Python files in the package
            for module_info in pkgutil.iter_modules([str(package_dir)]):
                if module_info.name.startswith("_"):
                    continue

                try:
                    module_name = f"{package_path}.{module_info.name}"
                    module = importlib.import_module(module_name)

                    # Find provider classes in the module
                    for name, obj in inspect.getmembers(module, inspect.isclass):
                        if (
                            issubclass(obj, LLMProvider)
                            and obj != LLMProvider
                            and not inspect.isabstract(obj)
                        ):

                            # Extract provider name from class name
                            provider_name = self._extract_provider_name(name)
                            if provider_name:
                                self.discovered_providers[provider_name] = obj
                                logger.info(
                                    f"Discovered built-in provider: {provider_name}"
                                )

                except Exception as e:
                    logger.warning(
                        f"Failed to discover provider in {module_info.name}: {e}"
                    )

        except Exception as e:
            logger.error(f"Failed to discover built-in providers: {e}")

    def discover_external_providers(
        self, search_paths: Optional[List[str]] = None
    ) -> None:
        """
        Discover external provider implementations.

        Args:
            search_paths: List of paths to search for external providers
        """
        if search_paths is None:
            search_paths = [
                os.path.expanduser("~/.gemini-sre-agent/providers"),
                "./providers",
                "./external_providers",
            ]

        for search_path in search_paths:
            if os.path.exists(search_path):
                self._discover_providers_in_path(search_path)

    def _discover_providers_in_path(self, path: str) -> None:
        """Discover providers in a specific path."""
        try:
            for root, _, files in os.walk(path):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        module_path = os.path.join(root, file)
                        self._load_provider_from_file(module_path)
        except Exception as e:
            logger.warning(f"Failed to discover providers in {path}: {e}")

    def _load_provider_from_file(self, file_path: str) -> None:
        """Load provider from a Python file."""
        try:
            # Create a module spec and load it
            spec = importlib.util.spec_from_file_location(
                "external_provider", file_path
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Find provider classes
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, LLMProvider)
                        and obj != LLMProvider
                        and not inspect.isabstract(obj)
                    ):

                        provider_name = self._extract_provider_name(name)
                        if provider_name:
                            self.discovered_providers[provider_name] = obj
                            self.external_providers[provider_name] = file_path
                            logger.info(
                                f"Discovered external provider: {provider_name} from {file_path}"
                            )

        except Exception as e:
            logger.warning(f"Failed to load provider from {file_path}: {e}")

    def _extract_provider_name(self, class_name: str) -> Optional[str]:
        """Extract provider name from class name."""
        # Remove "Provider" suffix and convert to lowercase
        if class_name.endswith("Provider"):
            name = class_name[:-8].lower()
            # Handle special cases
            name_mapping = {
                "openai": "openai",
                "anthropic": "anthropic",
                "gemini": "gemini",
                "grok": "grok",
                "ollama": "ollama",
                "bedrock": "bedrock",
            }
            return name_mapping.get(name, name)
        return None

    def register_discovered_providers(self) -> None:
        """Register all discovered providers with the factory."""
        for provider_name, provider_class in self.discovered_providers.items():
            try:
                LLMProviderFactory.register_provider(provider_name, provider_class)
                logger.info(f"Registered provider: {provider_name}")
            except Exception as e:
                logger.error(f"Failed to register provider {provider_name}: {e}")

    def auto_discover_and_register(
        self,
        include_builtin: bool = True,
        include_external: bool = True,
        external_paths: Optional[List[str]] = None,
    ) -> None:
        """
        Automatically discover and register all providers.

        Args:
            include_builtin: Whether to discover built-in providers
            include_external: Whether to discover external providers
            external_paths: Custom paths for external provider discovery
        """
        if self._initialized:
            return

        logger.info("Starting automatic provider discovery...")

        if include_builtin:
            self.discover_builtin_providers()

        if include_external:
            self.discover_external_providers(external_paths)

        self.register_discovered_providers()
        self._initialized = True

        logger.info(
            f"Provider discovery complete. Found {len(self.discovered_providers)} providers"
        )

    def get_discovered_providers(self) -> Dict[str, Type[LLMProvider]]:
        """Get all discovered providers."""
        return self.discovered_providers.copy()

    def get_external_providers(self) -> Dict[str, str]:
        """Get all external providers with their file paths."""
        return self.external_providers.copy()

    def reload_external_provider(self, provider_name: str) -> bool:
        """
        Reload an external provider from its file.

        Args:
            provider_name: Name of the provider to reload

        Returns:
            True if reloaded successfully, False otherwise
        """
        if provider_name not in self.external_providers:
            logger.warning(f"Provider {provider_name} is not external")
            return False

        file_path = self.external_providers[provider_name]
        try:
            # Remove from registry
            if provider_name in self.discovered_providers:
                del self.discovered_providers[provider_name]
            LLMProviderFactory.unregister_provider(provider_name)

            # Reload from file
            self._load_provider_from_file(file_path)
            LLMProviderFactory.register_provider(
                provider_name, self.discovered_providers[provider_name]
            )

            logger.info(f"Reloaded external provider: {provider_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload provider {provider_name}: {e}")
            return False

    def validate_discovered_providers(self) -> Dict[str, List[str]]:
        """
        Validate all discovered providers.

        Returns:
            Dictionary mapping provider names to lists of validation errors
        """
        from .validator import ProviderValidator

        validator = ProviderValidator()
        validation_results = {}

        for provider_name, provider_class in self.discovered_providers.items():
            try:
                errors = validator.validate_provider_class(provider_class)
                if errors:
                    validation_results[provider_name] = errors
            except Exception as e:
                validation_results[provider_name] = [f"Validation failed: {e}"]

        return validation_results

    def get_provider_info(self, provider_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a discovered provider.

        Args:
            provider_name: Name of the provider

        Returns:
            Dictionary with provider information or None if not found
        """
        if provider_name not in self.discovered_providers:
            return None

        provider_class = self.discovered_providers[provider_name]

        info = {
            "name": provider_name,
            "class": provider_class.__name__,
            "module": provider_class.__module__,
            "is_external": provider_name in self.external_providers,
            "file_path": self.external_providers.get(provider_name),
            "docstring": provider_class.__doc__,
            "methods": [
                method for method in dir(provider_class) if not method.startswith("_")
            ],
        }

        return info

    def list_providers_by_capability(self) -> Dict[str, List[str]]:
        """
        List providers grouped by their capabilities.

        Returns:
            Dictionary mapping capability names to lists of provider names
        """
        capabilities = {
            "streaming": [],
            "tools": [],
            "embeddings": [],
            "external": [],
        }

        for provider_name, provider_class in self.discovered_providers.items():
            # Check capabilities (this would need actual provider instances)
            # For now, we'll use class attributes or method names as indicators
            if "stream" in provider_class.__name__.lower() or "streaming" in str(
                provider_class.__doc__ or ""
            ):
                capabilities["streaming"].append(provider_name)

            if "tool" in provider_class.__name__.lower() or "tools" in str(
                provider_class.__doc__ or ""
            ):
                capabilities["tools"].append(provider_name)

            if "embed" in provider_class.__name__.lower() or "embeddings" in str(
                provider_class.__doc__ or ""
            ):
                capabilities["embeddings"].append(provider_name)

            if provider_name in self.external_providers:
                capabilities["external"].append(provider_name)

        return capabilities


# Global registry instance
_global_registry = ProviderAutoRegistry()


def get_auto_registry() -> ProviderAutoRegistry:
    """Get the global auto registry instance."""
    return _global_registry


def auto_discover_providers(
    include_builtin: bool = True,
    include_external: bool = True,
    external_paths: Optional[List[str]] = None,
) -> None:
    """
    Convenience function to automatically discover and register providers.

    Args:
        include_builtin: Whether to discover built-in providers
        include_external: Whether to discover external providers
        external_paths: Custom paths for external provider discovery
    """
    _global_registry.auto_discover_and_register(
        include_builtin=include_builtin,
        include_external=include_external,
        external_paths=external_paths,
    )
