# gemini_sre_agent/config/source_control_credentials.py

"""
Credential configuration models for source control providers.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator, model_validator
from pydantic.types import SecretStr

from .base import BaseConfig


class CredentialConfig(BaseConfig):
    """Configuration for repository credentials."""

    # Token-based authentication
    token_env: Optional[str] = Field(
        None, description="Environment variable containing the token"
    )
    token_file: Optional[str] = Field(
        None, description="File path containing the token"
    )
    token: Optional[SecretStr] = Field(
        None, description="Direct token value (not recommended for production)"
    )

    # Username/password authentication
    username_env: Optional[str] = Field(
        None, description="Environment variable for username"
    )
    password_env: Optional[str] = Field(
        None, description="Environment variable for password"
    )
    username: Optional[str] = Field(
        None, description="Direct username value (not recommended for production)"
    )
    password: Optional[SecretStr] = Field(
        None, description="Direct password value (not recommended for production)"
    )

    # SSH key authentication
    ssh_key_path: Optional[str] = Field(None, description="Path to SSH private key")
    ssh_key_passphrase_env: Optional[str] = Field(
        None, description="Environment variable for SSH key passphrase"
    )
    ssh_key_passphrase: Optional[SecretStr] = Field(
        None, description="Direct SSH key passphrase (not recommended for production)"
    )

    # OAuth authentication
    client_id_env: Optional[str] = Field(
        None, description="Environment variable for OAuth client ID"
    )
    client_secret_env: Optional[str] = Field(
        None, description="Environment variable for OAuth client secret"
    )
    client_id: Optional[str] = Field(
        None, description="Direct OAuth client ID (not recommended for production)"
    )
    client_secret: Optional[SecretStr] = Field(
        None, description="Direct OAuth client secret (not recommended for production)"
    )

    # Service account authentication (for cloud providers)
    service_account_key_file: Optional[str] = Field(
        None, description="Path to service account key file"
    )
    service_account_key_env: Optional[str] = Field(
        None, description="Environment variable containing service account key JSON"
    )

    @field_validator("ssh_key_path")
    @classmethod
    def validate_ssh_key_path(cls, v):
        """Validate SSH key path exists if provided."""
        if v is not None:
            key_path = Path(v)
            if not key_path.exists():
                raise ValueError(f"SSH key path does not exist: {v}")
            if not key_path.is_file():
                raise ValueError(f"SSH key path is not a file: {v}")
        return v

    @field_validator("service_account_key_file")
    @classmethod
    def validate_service_account_key_file(cls, v):
        """Validate service account key file exists if provided."""
        if v is not None:
            key_path = Path(v)
            if not key_path.exists():
                raise ValueError(f"Service account key file does not exist: {v}")
            if not key_path.is_file():
                raise ValueError(f"Service account key file is not a file: {v}")
        return v

    @model_validator(mode="after")
    def check_auth_method(self):
        """Ensure at least one authentication method is provided."""
        auth_methods = [
            self.token_env,
            self.token_file,
            self.token,
            self.username_env,
            self.username,
            self.ssh_key_path,
            self.client_id_env,
            self.client_id,
            self.service_account_key_file,
            self.service_account_key_env,
        ]

        if not any(method is not None for method in auth_methods):
            raise ValueError(
                "At least one authentication method must be provided. "
                "Use environment variables for production deployments."
            )

        return self

    def get_token(self) -> Optional[str]:
        """Get token from environment variable or file."""
        if self.token:
            return self.token.get_secret_value()

        if self.token_env:
            import os

            return os.getenv(self.token_env)

        if self.token_file:
            try:
                with open(self.token_file, "r") as f:
                    return f.read().strip()
            except (IOError, OSError) as e:
                raise ValueError(
                    f"Failed to read token from file {self.token_file}: {e}"
                ) from e

        return None

    def get_username(self) -> Optional[str]:
        """Get username from environment variable or direct value."""
        if self.username:
            return self.username

        if self.username_env:
            import os

            return os.getenv(self.username_env)

        return None

    def get_password(self) -> Optional[str]:
        """Get password from environment variable or direct value."""
        if self.password:
            return self.password.get_secret_value()

        if self.password_env:
            import os

            return os.getenv(self.password_env)

        return None

    def get_ssh_key_passphrase(self) -> Optional[str]:
        """Get SSH key passphrase from environment variable or direct value."""
        if self.ssh_key_passphrase:
            return self.ssh_key_passphrase.get_secret_value()

        if self.ssh_key_passphrase_env:
            import os

            return os.getenv(self.ssh_key_passphrase_env)

        return None

    def get_client_credentials(self) -> tuple[Optional[str], Optional[str]]:
        """Get OAuth client credentials."""
        client_id = self.client_id
        if self.client_id_env:
            import os

            client_id = os.getenv(self.client_id_env)

        client_secret = None
        if self.client_secret:
            client_secret = self.client_secret.get_secret_value()
        elif self.client_secret_env:
            import os

            client_secret = os.getenv(self.client_secret_env)

        return client_id, client_secret

    def get_service_account_key(self) -> Optional[dict]:
        """Get service account key as dictionary."""
        if self.service_account_key_env:
            import json
            import os

            key_json = os.getenv(self.service_account_key_env)
            if key_json:
                try:
                    return json.loads(key_json)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Invalid JSON in service account key: {e}") from e

        if self.service_account_key_file:
            import json

            try:
                with open(self.service_account_key_file, "r") as f:
                    return json.load(f)
            except (IOError, OSError, json.JSONDecodeError) as e:
                raise ValueError(f"Failed to read service account key: {e}") from e

        return None
