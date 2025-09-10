# gemini_sre_agent/source_control/credential_manager.py

"""
Credential manager module.

This module provides backward compatibility imports for the refactored credential management system.
"""

# Import all classes from the new credential_management package
from .credential_management import (
    AWSSecretsBackend,
    AzureKeyVaultBackend,
    CredentialBackend,
    CredentialManager,
    CredentialRotationManager,
    EnvironmentBackend,
    FileBackend,
    VaultBackend,
)

# Re-export all classes for backward compatibility
__all__ = [
    "CredentialManager",
    "CredentialRotationManager",
    "CredentialBackend",
    "EnvironmentBackend",
    "FileBackend",
    "VaultBackend",
    "AWSSecretsBackend",
    "AzureKeyVaultBackend",
]
