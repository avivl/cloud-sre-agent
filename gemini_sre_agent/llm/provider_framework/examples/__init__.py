# gemini_sre_agent/llm/provider_framework/examples/__init__.py

"""
Provider Framework Examples.

This package contains example implementations demonstrating how to use
the provider addition framework to create new providers with minimal code.
"""

from .custom_provider import CustomProvider
from .simple_provider import SimpleProvider

__all__ = [
    "CustomProvider",
    "SimpleProvider",
]
