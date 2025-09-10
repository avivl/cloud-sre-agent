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

    def __init__(
        self, encryption_key: Optional[str] = None, enable_rotation: bool = True
    ):
        self.backends: Dict[str, CredentialBackend] = {}
        self.default_backend: Optional[str] = None
        self.logger = logging.getLogger(__name__)
        self.credential_cache: Dict[str, Dict[str, Any]] = {}
        self.cache_expiry: Dict[str, datetime] = {}
        self.rotation_manager = (
            CredentialRotationManager(self) if enable_rotation else None
        )

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

    def add_vault_backend(
        self,
        name: str,
        vault_url: str,
        vault_token: Optional[str] = None,
        mount_point: str = "secret",
        set_as_default: bool = False,
    ):
        """Add a HashiCorp Vault backend."""
        backend = VaultBackend(vault_url, vault_token, mount_point)
        self.register_backend(name, backend, set_as_default)

    def add_aws_secrets_backend(
        self,
        name: str,
        region_name: Optional[str] = None,
        profile_name: Optional[str] = None,
        set_as_default: bool = False,
    ):
        """Add an AWS Secrets Manager backend."""
        backend = AWSSecretsBackend(region_name, profile_name)
        self.register_backend(name, backend, set_as_default)

    def add_azure_keyvault_backend(
        self,
        name: str,
        vault_url: str,
        credential: Optional[Any] = None,
        set_as_default: bool = False,
    ):
        """Add an Azure Key Vault backend."""
        backend = AzureKeyVaultBackend(vault_url, credential)
        self.register_backend(name, backend, set_as_default)

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

    async def schedule_credential_rotation(
        self, credential_id: str, rotation_interval_days: int = 90
    ):
        """Schedule credential rotation."""
        if self.rotation_manager:
            await self.rotation_manager.schedule_rotation(
                credential_id, rotation_interval_days
            )
        else:
            self.logger.warning("Rotation manager not enabled")

    async def check_rotation_needed(self, credential_id: str) -> bool:
        """Check if credential rotation is needed."""
        if self.rotation_manager:
            return await self.rotation_manager.check_rotation_needed(credential_id)
        return False

    async def validate_credential(self, credential_id: str, provider_type: str) -> bool:
        """Validate that a credential is working."""
        if self.rotation_manager:
            return await self.rotation_manager.validate_credential(
                credential_id, provider_type
            )
        return True  # If no rotation manager, assume valid

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


class VaultBackend(CredentialBackend):
    """Credential backend using HashiCorp Vault."""

    def __init__(
        self,
        vault_url: str,
        vault_token: Optional[str] = None,
        mount_point: str = "secret",
    ):
        self.vault_url = vault_url.rstrip("/")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.mount_point = mount_point
        self.logger = logging.getLogger("VaultBackend")

        if not self.vault_token:
            raise ValueError(
                "Vault token is required. Set VAULT_TOKEN environment variable or pass vault_token parameter."
            )

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a credential from Vault."""
        try:
            import hvac
        except ImportError:
            self.logger.error(
                "hvac library not installed. Install with: pip install hvac"
            )
            return None

        try:
            client = hvac.Client(url=self.vault_url, token=self.vault_token)
            if not client.is_authenticated():
                self.logger.error("Vault authentication failed")
                return None

            secret_path = f"{self.mount_point}/data/{key}"
            response = client.secrets.kv.v2.read_secret_version(path=secret_path)

            if response and "data" in response and "data" in response["data"]:
                return json.dumps(response["data"]["data"])
            return None
        except Exception as e:
            self.logger.error(f"Failed to retrieve secret from Vault: {e}")
            return None

    async def set(self, key: str, value: str) -> None:
        """Store a credential in Vault."""
        try:
            import hvac
        except ImportError:
            self.logger.error(
                "hvac library not installed. Install with: pip install hvac"
            )
            raise

        try:
            client = hvac.Client(url=self.vault_url, token=self.vault_token)
            if not client.is_authenticated():
                raise RuntimeError("Vault authentication failed")

            secret_path = f"{self.mount_point}/data/{key}"
            secret_data = json.loads(value) if isinstance(value, str) else value

            client.secrets.kv.v2.create_or_update_secret(
                path=secret_path, secret=secret_data
            )
        except Exception as e:
            raise RuntimeError(f"Failed to store secret in Vault: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a credential from Vault."""
        try:
            import hvac
        except ImportError:
            self.logger.error(
                "hvac library not installed. Install with: pip install hvac"
            )
            return

        try:
            client = hvac.Client(url=self.vault_url, token=self.vault_token)
            if not client.is_authenticated():
                self.logger.error("Vault authentication failed")
                return

            secret_path = f"{self.mount_point}/data/{key}"
            client.secrets.kv.v2.delete_metadata_and_all_versions(path=secret_path)
        except Exception as e:
            self.logger.error(f"Failed to delete secret from Vault: {e}")


class AWSSecretsBackend(CredentialBackend):
    """Credential backend using AWS Secrets Manager."""

    def __init__(
        self, region_name: Optional[str] = None, profile_name: Optional[str] = None
    ):
        self.region_name = region_name or os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        self.profile_name = profile_name
        self.logger = logging.getLogger("AWSSecretsBackend")

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a credential from AWS Secrets Manager."""
        try:
            import boto3
        except ImportError:
            self.logger.error(
                "boto3 library not installed. Install with: pip install boto3"
            )
            return None

        try:
            session = boto3.Session(profile_name=self.profile_name)
            client = session.client("secretsmanager", region_name=self.region_name)

            response = client.get_secret_value(SecretId=key)
            return response["SecretString"]
        except Exception as e:
            self.logger.error(
                f"Failed to retrieve secret from AWS Secrets Manager: {e}"
            )
            return None

    async def set(self, key: str, value: str) -> None:
        """Store a credential in AWS Secrets Manager."""
        try:
            import boto3
        except ImportError:
            self.logger.error(
                "boto3 library not installed. Install with: pip install boto3"
            )
            raise

        try:
            session = boto3.Session(profile_name=self.profile_name)
            client = session.client("secretsmanager", region_name=self.region_name)

            try:
                # Try to update existing secret
                client.update_secret(SecretId=key, SecretString=value)
            except client.exceptions.ResourceNotFoundException:
                # Create new secret if it doesn't exist
                client.create_secret(Name=key, SecretString=value)
        except Exception as e:
            raise RuntimeError(
                f"Failed to store secret in AWS Secrets Manager: {e}"
            ) from e

    async def delete(self, key: str) -> None:
        """Delete a credential from AWS Secrets Manager."""
        try:
            import boto3
        except ImportError:
            self.logger.error(
                "boto3 library not installed. Install with: pip install boto3"
            )
            return

        try:
            session = boto3.Session(profile_name=self.profile_name)
            client = session.client("secretsmanager", region_name=self.region_name)

            client.delete_secret(SecretId=key, ForceDeleteWithoutRecovery=True)
        except Exception as e:
            self.logger.error(f"Failed to delete secret from AWS Secrets Manager: {e}")


class AzureKeyVaultBackend(CredentialBackend):
    """Credential backend using Azure Key Vault."""

    def __init__(self, vault_url: str, credential: Optional[Any] = None):
        self.vault_url = vault_url
        self.credential = credential
        self.logger = logging.getLogger("AzureKeyVaultBackend")

    async def get(self, key: str) -> Optional[str]:
        """Retrieve a credential from Azure Key Vault."""
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except ImportError:
            self.logger.error(
                "azure-keyvault-secrets library not installed. Install with: pip install azure-keyvault-secrets azure-identity"
            )
            return None

        try:
            credential = self.credential or DefaultAzureCredential()
            client = SecretClient(vault_url=self.vault_url, credential=credential)

            secret = client.get_secret(key)
            return secret.value
        except Exception as e:
            self.logger.error(f"Failed to retrieve secret from Azure Key Vault: {e}")
            return None

    async def set(self, key: str, value: str) -> None:
        """Store a credential in Azure Key Vault."""
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except ImportError:
            self.logger.error(
                "azure-keyvault-secrets library not installed. Install with: pip install azure-keyvault-secrets azure-identity"
            )
            raise

        try:
            credential = self.credential or DefaultAzureCredential()
            client = SecretClient(vault_url=self.vault_url, credential=credential)

            client.set_secret(key, value)
        except Exception as e:
            raise RuntimeError(f"Failed to store secret in Azure Key Vault: {e}") from e

    async def delete(self, key: str) -> None:
        """Delete a credential from Azure Key Vault."""
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore
            from azure.keyvault.secrets import SecretClient  # type: ignore
        except ImportError:
            self.logger.error(
                "azure-keyvault-secrets library not installed. Install with: pip install azure-keyvault-secrets azure-identity"
            )
            return

        try:
            credential = self.credential or DefaultAzureCredential()
            client = SecretClient(vault_url=self.vault_url, credential=credential)

            client.begin_delete_secret(key)
        except Exception as e:
            self.logger.error(f"Failed to delete secret from Azure Key Vault: {e}")


class CredentialRotationManager:
    """Manages credential rotation and validation."""

    def __init__(self, credential_manager: "CredentialManager"):
        self.credential_manager = credential_manager
        self.logger = logging.getLogger("CredentialRotationManager")
        self.rotation_schedule: Dict[str, datetime] = {}

    async def schedule_rotation(
        self, credential_id: str, rotation_interval_days: int = 90
    ):
        """Schedule credential rotation."""
        next_rotation = datetime.now() + timedelta(days=rotation_interval_days)
        self.rotation_schedule[credential_id] = next_rotation
        self.logger.info(f"Scheduled rotation for {credential_id} on {next_rotation}")

    async def check_rotation_needed(self, credential_id: str) -> bool:
        """Check if credential rotation is needed."""
        if credential_id not in self.rotation_schedule:
            return False

        return datetime.now() >= self.rotation_schedule[credential_id]

    async def rotate_credential(
        self, credential_id: str, new_credential_data: Dict[str, Any]
    ) -> bool:
        """Rotate a credential with new data."""
        # Add validation before rotation
        if not await self._validate_new_credentials(new_credential_data):
            self.logger.error(f"New credentials for {credential_id} failed validation")
            return False

        # Store old credentials as backup
        old_credentials = None
        try:
            old_credentials = await self.credential_manager.get_credentials(
                credential_id, "backup"
            )
        except Exception:
            # No backup exists, try to get current credentials
            try:
                old_credentials = await self.credential_manager.get_credentials(
                    credential_id, "current"
                )
            except Exception:
                self.logger.warning(
                    f"No existing credentials found for {credential_id}"
                )

        try:
            # Attempt rotation
            await self.credential_manager.store_credentials(
                credential_id, new_credential_data
            )

            # Test new credentials
            if not await self._test_new_credentials(credential_id, new_credential_data):
                # Rollback on failure
                if old_credentials:
                    await self.credential_manager.store_credentials(
                        credential_id, old_credentials
                    )
                    self.logger.error(
                        f"New credentials failed test, rolled back to old credentials for {credential_id}"
                    )
                return False

            # Update rotation schedule only after successful test
            await self.schedule_rotation(credential_id)

            self.logger.info(f"Successfully rotated credentials for {credential_id}")
            return True

        except Exception as e:
            # Rollback on error
            if old_credentials:
                try:
                    await self.credential_manager.store_credentials(
                        credential_id, old_credentials
                    )
                    self.logger.error(
                        f"Credential rotation failed, rolled back to old credentials for {credential_id}"
                    )
                except Exception as rollback_error:
                    self.logger.error(
                        f"Failed to rollback credentials for {credential_id}: {rollback_error}"
                    )
            self.logger.error(f"Failed to rotate credentials for {credential_id}: {e}")
            return False

    async def validate_credential(self, credential_id: str, provider_type: str) -> bool:
        """Validate that a credential is working."""
        try:
            credentials = await self.credential_manager.get_credentials(
                credential_id, provider_type
            )

            # Basic validation - check if required fields are present
            if provider_type == "github":
                return "token" in credentials
            elif provider_type == "gitlab":
                return "token" in credentials
            elif provider_type == "aws":
                return (
                    "access_key_id" in credentials
                    and "secret_access_key" in credentials
                )
            else:
                return len(credentials) > 0
        except Exception as e:
            self.logger.error(f"Credential validation failed for {credential_id}: {e}")
            return False

    async def _validate_new_credentials(self, credential_data: Dict[str, Any]) -> bool:
        """Validate new credentials before rotation."""
        try:
            # Check if credential data is not empty
            if not credential_data or len(credential_data) == 0:
                self.logger.error("Credential data is empty")
                return False

            # Check for required fields based on provider type
            if "provider_type" in credential_data:
                provider_type = credential_data["provider_type"]
                if provider_type == "github":
                    if "token" not in credential_data or not credential_data["token"]:
                        self.logger.error("GitHub credentials missing or empty token")
                        return False
                elif provider_type == "gitlab":
                    if "token" not in credential_data or not credential_data["token"]:
                        self.logger.error("GitLab credentials missing or empty token")
                        return False
                elif provider_type == "aws":
                    if (
                        "access_key_id" not in credential_data
                        or not credential_data["access_key_id"]
                        or "secret_access_key" not in credential_data
                        or not credential_data["secret_access_key"]
                    ):
                        self.logger.error("AWS credentials missing required fields")
                        return False

            # Check for sensitive data patterns (basic validation)
            for key, value in credential_data.items():
                if isinstance(value, str) and len(value) < 8:
                    self.logger.warning(
                        f"Credential field {key} seems too short for a secure credential"
                    )

            return True
        except Exception as e:
            self.logger.error(f"Credential validation error: {e}")
            return False

    async def _test_new_credentials(
        self, credential_id: str, credential_data: Dict[str, Any]
    ) -> bool:
        """Test new credentials by attempting to use them."""
        try:
            # Store credentials temporarily for testing
            test_credential_id = f"{credential_id}_test"
            await self.credential_manager.store_credentials(
                test_credential_id, credential_data
            )

            # Test based on provider type
            provider_type = credential_data.get("provider_type", "unknown")

            if provider_type == "github":
                return await self._test_github_credentials(test_credential_id)
            elif provider_type == "gitlab":
                return await self._test_gitlab_credentials(test_credential_id)
            elif provider_type == "aws":
                return await self._test_aws_credentials(test_credential_id)
            else:
                # For unknown types, just check if we can retrieve the credentials
                test_creds = await self.credential_manager.get_credentials(
                    test_credential_id, provider_type
                )
                return test_creds is not None

        except Exception as e:
            self.logger.error(f"Credential testing failed: {e}")
            return False
        finally:
            # Clean up test credentials
            try:
                # Note: delete_credentials method needs to be implemented in CredentialManager
                # For now, we'll just log that cleanup was attempted
                self.logger.debug(
                    f"Would clean up test credentials for {credential_id}_test"
                )
            except Exception:
                pass

    async def _test_github_credentials(self, credential_id: str) -> bool:
        """Test GitHub credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual GitHub API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "github"
            )
            return "token" in credentials and len(credentials["token"]) > 0
        except Exception as e:
            self.logger.error(f"GitHub credential test failed: {e}")
            return False

    async def _test_gitlab_credentials(self, credential_id: str) -> bool:
        """Test GitLab credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual GitLab API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "gitlab"
            )
            return "token" in credentials and len(credentials["token"]) > 0
        except Exception as e:
            self.logger.error(f"GitLab credential test failed: {e}")
            return False

    async def _test_aws_credentials(self, credential_id: str) -> bool:
        """Test AWS credentials by making a simple API call."""
        try:
            # This would need to be implemented with actual AWS API call
            # For now, just validate the credential structure
            credentials = await self.credential_manager.get_credentials(
                credential_id, "aws"
            )
            return (
                "access_key_id" in credentials
                and "secret_access_key" in credentials
                and len(credentials["access_key_id"]) > 0
                and len(credentials["secret_access_key"]) > 0
            )
        except Exception as e:
            self.logger.error(f"AWS credential test failed: {e}")
            return False
