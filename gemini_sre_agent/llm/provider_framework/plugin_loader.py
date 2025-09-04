"""
Plugin Loader for External Provider Implementations.

This module provides support for loading provider implementations from external
modules and packages, enabling a plugin architecture for the provider system.
"""

import importlib
import importlib.util
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from ..base import LLMProvider
from ..factory import LLMProviderFactory

logger = logging.getLogger(__name__)


class ProviderPluginLoader:
    """
    Plugin loader for external provider implementations.

    Supports loading providers from:
    - Python packages
    - Single Python files
    - ZIP files containing provider modules
    - Remote URLs (with caching)
    """

    def __init__(self):
        self.loaded_plugins: Dict[str, Dict[str, Any]] = {}
        self.plugin_paths: List[str] = []
        self._plugin_cache: Dict[str, Any] = {}

    def add_plugin_path(self, path: str) -> None:
        """
        Add a path to search for provider plugins.

        Args:
            path: Path to search for plugins
        """
        if path not in self.plugin_paths:
            self.plugin_paths.append(path)
            logger.info(f"Added plugin path: {path}")

    def load_plugin_from_file(
        self, file_path: str, plugin_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load a provider plugin from a Python file.

        Args:
            file_path: Path to the Python file
            plugin_name: Optional name for the plugin

        Returns:
            Dictionary containing plugin information
        """
        try:
            file_path = os.path.abspath(file_path)

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Plugin file not found: {file_path}")

            if not file_path.endswith(".py"):
                raise ValueError("Plugin file must be a Python file (.py)")

            # Generate plugin name if not provided
            if not plugin_name:
                plugin_name = Path(file_path).stem

            # Check cache first
            cache_key = f"file:{file_path}"
            if cache_key in self._plugin_cache:
                logger.debug(f"Loading plugin from cache: {plugin_name}")
                return self._plugin_cache[cache_key]

            # Load the module
            spec = importlib.util.spec_from_file_location(plugin_name, file_path)
            if not spec or not spec.loader:
                raise ImportError(f"Could not load module from {file_path}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find provider classes
            providers = self._extract_providers_from_module(module, plugin_name)

            plugin_info = {
                "name": plugin_name,
                "type": "file",
                "path": file_path,
                "module": module,
                "providers": providers,
                "loaded_at": "2024-01-01T00:00:00",  # Simplified for now
            }

            # Cache the plugin
            self._plugin_cache[cache_key] = plugin_info
            self.loaded_plugins[plugin_name] = plugin_info

            # Register providers with the factory
            for provider_name, provider_class in providers.items():
                LLMProviderFactory.register_provider(provider_name, provider_class)
                logger.info(
                    f"Registered provider {provider_name} from plugin {plugin_name}"
                )

            logger.info(f"Loaded plugin {plugin_name} with {len(providers)} providers")
            return plugin_info

        except Exception as e:
            logger.error(f"Failed to load plugin from {file_path}: {e}")
            raise

    def load_plugin_from_package(
        self, package_path: str, plugin_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load a provider plugin from a Python package.

        Args:
            package_path: Path to the Python package
            plugin_name: Optional name for the plugin

        Returns:
            Dictionary containing plugin information
        """
        try:
            package_path = os.path.abspath(package_path)

            if not os.path.exists(package_path):
                raise FileNotFoundError(f"Plugin package not found: {package_path}")

            if not os.path.isdir(package_path):
                raise ValueError("Plugin package must be a directory")

            # Generate plugin name if not provided
            if not plugin_name:
                plugin_name = Path(package_path).name

            # Check cache first
            cache_key = f"package:{package_path}"
            if cache_key in self._plugin_cache:
                logger.debug(f"Loading plugin from cache: {plugin_name}")
                return self._plugin_cache[cache_key]

            # Add package to Python path temporarily
            if package_path not in sys.path:
                sys.path.insert(0, package_path)

            try:
                # Import the package
                package = importlib.import_module(plugin_name)

                # Find provider classes in the package
                providers = self._extract_providers_from_package(package, plugin_name)

                plugin_info = {
                    "name": plugin_name,
                    "type": "package",
                    "path": package_path,
                    "module": package,
                    "providers": providers,
                    "loaded_at": "2024-01-01T00:00:00",  # Simplified for now
                }

                # Cache the plugin
                self._plugin_cache[cache_key] = plugin_info
                self.loaded_plugins[plugin_name] = plugin_info

                # Register providers with the factory
                for provider_name, provider_class in providers.items():
                    LLMProviderFactory.register_provider(provider_name, provider_class)
                    logger.info(
                        f"Registered provider {provider_name} from plugin {plugin_name}"
                    )

                logger.info(
                    f"Loaded plugin {plugin_name} with {len(providers)} providers"
                )
                return plugin_info

            finally:
                # Remove package from Python path
                if package_path in sys.path:
                    sys.path.remove(package_path)

        except Exception as e:
            logger.error(f"Failed to load plugin from {package_path}: {e}")
            raise

    def load_plugin_from_zip(
        self, zip_path: str, plugin_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load a provider plugin from a ZIP file.

        Args:
            zip_path: Path to the ZIP file
            plugin_name: Optional name for the plugin

        Returns:
            Dictionary containing plugin information
        """
        import tempfile
        import zipfile

        try:
            zip_path = os.path.abspath(zip_path)

            if not os.path.exists(zip_path):
                raise FileNotFoundError(f"Plugin ZIP not found: {zip_path}")

            if not zip_path.endswith(".zip"):
                raise ValueError("Plugin file must be a ZIP file (.zip)")

            # Generate plugin name if not provided
            if not plugin_name:
                plugin_name = Path(zip_path).stem

            # Check cache first
            cache_key = f"zip:{zip_path}"
            if cache_key in self._plugin_cache:
                logger.debug(f"Loading plugin from cache: {plugin_name}")
                return self._plugin_cache[cache_key]

            # Extract ZIP to temporary directory
            with tempfile.TemporaryDirectory() as temp_dir:
                with zipfile.ZipFile(zip_path, "r") as zip_ref:
                    zip_ref.extractall(temp_dir)

                # Find the main module in the extracted files
                main_module = None
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if file.endswith(".py") and not file.startswith("_"):
                            main_module = os.path.join(root, file)
                            break
                    if main_module:
                        break

                if not main_module:
                    raise ValueError("No Python modules found in ZIP file")

                # Load the plugin from the extracted file
                plugin_info = self.load_plugin_from_file(main_module, plugin_name)
                plugin_info["type"] = "zip"
                plugin_info["zip_path"] = zip_path

                # Cache the plugin
                self._plugin_cache[cache_key] = plugin_info

                return plugin_info

        except Exception as e:
            logger.error(f"Failed to load plugin from {zip_path}: {e}")
            raise

    def load_plugin_from_url(
        self, url: str, plugin_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Load a provider plugin from a remote URL.

        Args:
            url: URL to the plugin file
            plugin_name: Optional name for the plugin

        Returns:
            Dictionary containing plugin information
        """
        import tempfile
        import urllib.request

        try:
            # Generate plugin name if not provided
            if not plugin_name:
                plugin_name = url.split("/")[-1].replace(".py", "")

            # Check cache first
            cache_key = f"url:{url}"
            if cache_key in self._plugin_cache:
                logger.debug(f"Loading plugin from cache: {plugin_name}")
                return self._plugin_cache[cache_key]

            # Download the plugin file
            with tempfile.NamedTemporaryFile(
                mode="w+b", suffix=".py", delete=False
            ) as temp_file:
                with urllib.request.urlopen(url) as response:
                    temp_file.write(response.read())
                temp_file_path = temp_file.name

            try:
                # Load the plugin from the downloaded file
                plugin_info = self.load_plugin_from_file(temp_file_path, plugin_name)
                plugin_info["type"] = "url"
                plugin_info["url"] = url

                # Cache the plugin
                self._plugin_cache[cache_key] = plugin_info

                return plugin_info

            finally:
                # Clean up temporary file
                os.unlink(temp_file_path)

        except Exception as e:
            logger.error(f"Failed to load plugin from {url}: {e}")
            raise

    def _extract_providers_from_module(
        self, module: Any, plugin_name: str
    ) -> Dict[str, Type[LLMProvider]]:
        """Extract provider classes from a module."""
        import inspect

        providers = {}

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, LLMProvider)
                and obj != LLMProvider
                and not inspect.isabstract(obj)
            ):

                # Extract provider name from class name
                provider_name = self._extract_provider_name(name)
                if provider_name:
                    providers[provider_name] = obj

        return providers

    def _extract_providers_from_package(
        self, package: Any, plugin_name: str
    ) -> Dict[str, Type[LLMProvider]]:
        """Extract provider classes from a package."""
        import inspect

        providers = {}

        # Get all modules in the package
        for name, obj in inspect.getmembers(package, inspect.ismodule):
            if not name.startswith("_"):
                module_providers = self._extract_providers_from_module(
                    obj, f"{plugin_name}.{name}"
                )
                providers.update(module_providers)

        return providers

    def _extract_provider_name(self, class_name: str) -> Optional[str]:
        """Extract provider name from class name."""
        # Remove "Provider" suffix and convert to lowercase
        if class_name.endswith("Provider"):
            name = class_name[:-8].lower()
            return name
        return None

    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin and unregister its providers.

        Args:
            plugin_name: Name of the plugin to unload

        Returns:
            True if unloaded successfully, False otherwise
        """
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_name} is not loaded")
            return False

        try:
            plugin_info = self.loaded_plugins[plugin_name]

            # Unregister providers
            for provider_name in plugin_info["providers"].keys():
                LLMProviderFactory.unregister_provider(provider_name)
                logger.info(
                    f"Unregistered provider {provider_name} from plugin {plugin_name}"
                )

            # Remove from loaded plugins
            del self.loaded_plugins[plugin_name]

            # Remove from cache
            cache_keys_to_remove = []
            for cache_key, cached_info in self._plugin_cache.items():
                if cached_info.get("name") == plugin_name:
                    cache_keys_to_remove.append(cache_key)

            for cache_key in cache_keys_to_remove:
                del self._plugin_cache[cache_key]

            logger.info(f"Unloaded plugin {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to unload plugin {plugin_name}: {e}")
            return False

    def reload_plugin(self, plugin_name: str) -> bool:
        """
        Reload a plugin.

        Args:
            plugin_name: Name of the plugin to reload

        Returns:
            True if reloaded successfully, False otherwise
        """
        if plugin_name not in self.loaded_plugins:
            logger.warning(f"Plugin {plugin_name} is not loaded")
            return False

        try:
            plugin_info = self.loaded_plugins[plugin_name]
            plugin_path = plugin_info["path"]
            plugin_type = plugin_info["type"]

            # Unload the plugin
            self.unload_plugin(plugin_name)

            # Reload based on type
            if plugin_type == "file":
                self.load_plugin_from_file(plugin_path, plugin_name)
            elif plugin_type == "package":
                self.load_plugin_from_package(plugin_path, plugin_name)
            elif plugin_type == "zip":
                self.load_plugin_from_zip(plugin_info["zip_path"], plugin_name)
            elif plugin_type == "url":
                self.load_plugin_from_url(plugin_info["url"], plugin_name)

            logger.info(f"Reloaded plugin {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to reload plugin {plugin_name}: {e}")
            return False

    def list_loaded_plugins(self) -> List[str]:
        """List all loaded plugin names."""
        return list(self.loaded_plugins.keys())

    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a loaded plugin."""
        return self.loaded_plugins.get(plugin_name)

    def discover_plugins(self, search_paths: Optional[List[str]] = None) -> List[str]:
        """
        Discover available plugins in the search paths.

        Args:
            search_paths: Paths to search for plugins

        Returns:
            List of discovered plugin paths
        """
        if search_paths is None:
            search_paths = self.plugin_paths

        discovered_plugins = []

        for search_path in search_paths:
            if not os.path.exists(search_path):
                continue

            # Search for Python files
            for root, dirs, files in os.walk(search_path):
                for file in files:
                    if file.endswith(".py") and not file.startswith("_"):
                        file_path = os.path.join(root, file)
                        discovered_plugins.append(file_path)

                # Search for packages
                for dir_name in dirs:
                    if not dir_name.startswith("_"):
                        package_path = os.path.join(root, dir_name)
                        init_file = os.path.join(package_path, "__init__.py")
                        if os.path.exists(init_file):
                            discovered_plugins.append(package_path)

        return discovered_plugins

    def auto_load_plugins(
        self, search_paths: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Automatically discover and load all available plugins.

        Args:
            search_paths: Paths to search for plugins

        Returns:
            Dictionary containing loading results
        """
        discovered_plugins = self.discover_plugins(search_paths)

        results = {
            "discovered": len(discovered_plugins),
            "loaded": 0,
            "failed": 0,
            "errors": [],
        }

        for plugin_path in discovered_plugins:
            try:
                if os.path.isfile(plugin_path):
                    self.load_plugin_from_file(plugin_path)
                elif os.path.isdir(plugin_path):
                    self.load_plugin_from_package(plugin_path)

                results["loaded"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Failed to load {plugin_path}: {e}")
                logger.warning(f"Failed to auto-load plugin {plugin_path}: {e}")

        logger.info(
            f"Auto-loaded {results['loaded']} plugins, {results['failed']} failed"
        )
        return results


# Global plugin loader instance
_global_plugin_loader = ProviderPluginLoader()


def get_plugin_loader() -> ProviderPluginLoader:
    """Get the global plugin loader instance."""
    return _global_plugin_loader


def load_provider_plugin(
    plugin_path: str, plugin_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    Convenience function to load a provider plugin.

    Args:
        plugin_path: Path to the plugin
        plugin_name: Optional name for the plugin

    Returns:
        Plugin information dictionary
    """
    return _global_plugin_loader.load_plugin_from_file(plugin_path, plugin_name)
