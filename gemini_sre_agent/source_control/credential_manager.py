# gemini_sre_agent/source_control/credential_manager.py

import base64
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class CredentialBackend(ABC):
    """Abstract base class for credential storage backends."""

    @abstractmethod
    async def get(self, key: str) -> Optional[str]:
        """Retrieve a credential value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: str) -> None:
        """Store a credential value by key."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a credential by key."""
        pass


class EnvironmentBackend(CredentialBackend):
    """Credential backend using environment variables."""

    async def get(self, key: str) -> Optional[str]:
        return os.environ.get(key)

    async def set(self, key: str, value: str) -> None:
        os.environ[key] = value

    async def delete(self, key: str) -> None:
        if key in os.environ:
            del os.environ[key]


class FileBackend(CredentialBackend):
    """Credential backend using file storage."""

    def __init__(self, base_path: str = "/tmp/credentials"):
        self.base_path = base_path
        os.makedirs(base_path, exist_ok=True)

    def _get_file_path(self, key: str) -> str:
        """Get the file path for a given key."""
        # Sanitize the key to prevent directory traversal
        safe_key = "".join(c for c in key if c.isalnum() or c in "._-")
        return os.path.join(self.base_path, f"{safe_key}.json")

    async def get(self, key: str) -> Optional[str]:
        file_path = self._get_file_path(key)
        if not os.path.exists(file_path):
            return None

        try:
            with open(file_path, "r") as f:
                return f.read()
        except (IOError, OSError):
            return None

    async def set(self, key: str, value: str) -> None:
        file_path = self._get_file_path(key)
        try:
            with open(file_path, "w") as f:
                f.write(value)
        except (IOError, OSError) as e:
            raise RuntimeError(
                f"Failed to write credential file {file_path}: {e}"
            ) from e

    async def delete(self, key: str) -> None:
        file_path = self._get_file_path(key)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except (IOError, OSError):
                pass


class CredentialManager:
    """Manages secure credential storage and retrieval."""

    def __init__(self, encryption_key: Optional[str] = None):
        self.backends: Dict[str, CredentialBackend] = {}
        self.default_backend: Optional[str] = None
        self.logger = logging.getLogger(__name__)
        self.credential_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry: Dict[str, datetime] = {}

        # Setup encryption
        if encryption_key:
            salt = b"static_salt_for_key_derivation"  # In production, use a secure random salt
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(encryption_key.encode()))
            self.cipher = Fernet(key)
        else:
            self.cipher = None
            self.logger.warning(
                "No encryption key provided. Credentials will not be encrypted in memory."
            )

    def register_backend(
        self, name: str, backend: CredentialBackend, default: bool = False
    ) -> None:
        """Register a credential storage backend."""
        self.backends[name] = backend
        if default or self.default_backend is None:
            self.default_backend = name

    async def get_credentials(
        self, credential_id: str, provider_type: str
    ) -> Dict[str, Any]:
        """Retrieve credentials for a specific provider."""
        # Check cache first
        cache_key = f"{credential_id}:{provider_type}"
        if (
            cache_key in self.credential_cache
            and datetime.now() < self.cache_expiry.get(cache_key, datetime.min)
        ):
            return self.credential_cache[cache_key]

        # Determine backend and key format
        backend_name, actual_key = self._parse_credential_id(credential_id)
        if backend_name not in self.backends:
            raise ValueError(f"Unknown credential backend: {backend_name}")

        backend = self.backends[backend_name]

        # Retrieve raw credential data
        raw_data = await backend.get(actual_key)
        if not raw_data:
            raise ValueError(f"Credential not found: {credential_id}")

        # Parse and validate credential data
        try:
            credential_data = json.loads(raw_data)

            # Decrypt credentials if encryption is available
            if self.cipher:
                credential_data = self._decrypt(credential_data)

            # Validate credential type matches provider
            if credential_data.get("provider_type") != provider_type:
                self.logger.warning(
                    f"Credential provider type mismatch: expected {provider_type}, got {credential_data.get('provider_type')}"
                )

            # Cache the credentials with expiry
            self.credential_cache[cache_key] = credential_data
            self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=15)

            return credential_data
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid credential format for {credential_id}") from e

    async def store_credentials(
        self, credential_id: str, credential_data: Dict[str, Any]
    ) -> None:
        """Store credentials in the specified backend."""
        backend_name, actual_key = self._parse_credential_id(credential_id)
        if backend_name not in self.backends:
            raise ValueError(f"Unknown credential backend: {backend_name}")

        backend = self.backends[backend_name]

        # Add metadata
        credential_data["last_updated"] = datetime.now().isoformat()

        # Encrypt credentials if encryption is available
        if self.cipher:
            credential_data = self._encrypt(credential_data)

        # Store the credentials
        await backend.set(actual_key, json.dumps(credential_data))

        # Update cache
        provider_type = credential_data.get("provider_type")
        if provider_type:
            cache_key = f"{credential_id}:{provider_type}"
            self.credential_cache[cache_key] = credential_data
            self.cache_expiry[cache_key] = datetime.now() + timedelta(minutes=15)

    async def rotate_credentials(
        self, credential_id: str, new_value: Dict[str, Any]
    ) -> None:
        """Rotate credentials with a new value."""
        # Store new credentials
        await self.store_credentials(credential_id, new_value)

        # Log the rotation for audit purposes
        self.logger.info(f"Credentials rotated for {credential_id}")

        # Clear any cached values
        for cache_key in list(self.credential_cache.keys()):
            if cache_key.startswith(f"{credential_id}:"):
                del self.credential_cache[cache_key]
                if cache_key in self.cache_expiry:
                    del self.cache_expiry[cache_key]

    def _parse_credential_id(self, credential_id: str) -> tuple:
        """Parse a credential ID into backend name and actual key."""
        if ":" in credential_id:
            backend_name, actual_key = credential_id.split(":", 1)
            return backend_name, actual_key
        else:
            return self.default_backend, credential_id

    def _encrypt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Encrypt sensitive data if encryption is enabled."""
        if self.cipher:
            # Convert dict to JSON string, encrypt, then convert back to dict
            json_str = json.dumps(data)
            encrypted_str = self.cipher.encrypt(json_str.encode()).decode()
            return {"encrypted": encrypted_str}
        return data

    def _decrypt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decrypt sensitive data if encryption is enabled."""
        if self.cipher and "encrypted" in data:
            # Decrypt the encrypted string and parse back to dict
            encrypted_str = data["encrypted"]
            decrypted_str = self.cipher.decrypt(encrypted_str.encode()).decode()
            return json.loads(decrypted_str)
        return data
