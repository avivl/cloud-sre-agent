# gemini_sre_agent/source_control/credential_management/__init__.py

"""
Credential management package.

This package provides secure credential storage, retrieval, and rotation capabilities.
"""

from .backends import (
    CredentialBackend,
    EnvironmentBackend,
    FileBackend,
)
from .cloud_backends import (
    AWSSecretsBackend,
    AzureKeyVaultBackend,
    VaultBackend,
)
from .manager import CredentialManager
from .rotation import CredentialRotationManager

__all__ = [
    "AWSSecretsBackend",
    "AzureKeyVaultBackend",
    "CredentialBackend",
    "CredentialManager",
    "CredentialRotationManager",
    "EnvironmentBackend",
    "FileBackend",
    "VaultBackend",
]
