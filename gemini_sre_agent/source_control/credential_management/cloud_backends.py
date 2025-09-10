# gemini_sre_agent/source_control/credential_management/cloud_backends.py

"""
Cloud credential storage backends module.

This module contains cloud-based credential storage backend implementations.
"""

import json
import logging
import os
from typing import Any, Optional

from .backends import CredentialBackend


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
