"""
Provider Addition Framework for Multi-LLM Provider Support.

This package provides a comprehensive framework for easily adding new LLM providers
with minimal code, automatic registration, validation, and plugin support.
"""

from .auto_registry import ProviderAutoRegistry
from .base_template import BaseProviderTemplate
from .capability_discovery import ProviderCapabilityDiscovery
from .plugin_loader import ProviderPluginLoader
from .templates import (
    HTTPAPITemplate,
    OpenAICompatibleTemplate,
    RESTAPITemplate,
    StreamingTemplate,
)
from .validator import ProviderValidator

__all__ = [
    "ProviderAutoRegistry",
    "BaseProviderTemplate",
    "ProviderCapabilityDiscovery",
    "ProviderPluginLoader",
    "HTTPAPITemplate",
    "OpenAICompatibleTemplate",
    "RESTAPITemplate",
    "StreamingTemplate",
    "ProviderValidator",
]
