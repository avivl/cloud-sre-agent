# gemini_sre_agent/config/secrets.py

"""
Enhanced secrets management with validation and secure handling.
"""

import os
from typing import Dict, Optional

from pydantic import Field, SecretStr, field_validator

from .base import BaseConfig


class SecretsConfig(BaseConfig):
    """Secrets and sensitive configuration with enhanced validation."""

    # API Keys
    gemini_api_key: SecretStr = Field(..., description="Gemini API key")
    github_token: Optional[SecretStr] = None
    gcp_service_account_key: Optional[SecretStr] = None

    # Database credentials
    database_password: Optional[SecretStr] = None

    # External service credentials
    external_api_keys: Dict[str, SecretStr] = Field(default_factory=dict)

    @field_validator("gemini_api_key")
    @classmethod
    def validate_gemini_api_key_format(cls, v):
        """Validate Gemini API key format."""
        key_value = v.get_secret_value()
        if not key_value:
            raise ValueError("Gemini API key cannot be empty")

        # Basic format validation for Gemini API keys
        if not key_value.startswith("AIza"):
            raise ValueError("Invalid Gemini API key format - should start with 'AIza'")

        if len(key_value) < 39:  # Minimum expected length
            raise ValueError("Gemini API key appears to be too short")

        return v

    @field_validator("github_token")
    @classmethod
    def validate_github_token_format(cls, v):
        """Validate GitHub token format if provided."""
        if v is None:
            return v

        token_value = v.get_secret_value()
        if not token_value:
            return v

        # GitHub personal access tokens start with 'ghp_' or 'github_pat_'
        if not (
            token_value.startswith("ghp_") or token_value.startswith("github_pat_")
        ):
            raise ValueError("Invalid GitHub token format")

        return v

    @field_validator("gcp_service_account_key")
    @classmethod
    def validate_gcp_service_account_key(cls, v):
        """Validate GCP service account key format if provided."""
        if v is None:
            return v

        key_value = v.get_secret_value()
        if not key_value:
            return v

        # Basic JSON structure validation
        import json

        try:
            json.loads(key_value)
        except json.JSONDecodeError as e:
            raise ValueError("GCP service account key must be valid JSON") from e

        return v

    @classmethod
    def from_env(cls) -> "SecretsConfig":
        """Load secrets from environment variables with validation."""
        from pydantic import SecretStr

        github_token = os.getenv("GITHUB_TOKEN")
        gcp_key = os.getenv("GCP_SERVICE_ACCOUNT_KEY")
        db_password = os.getenv("DATABASE_PASSWORD")

        return cls(
            gemini_api_key=SecretStr(os.getenv("GEMINI_API_KEY", "")),
            github_token=SecretStr(github_token) if github_token else None,
            gcp_service_account_key=SecretStr(gcp_key) if gcp_key else None,
            database_password=SecretStr(db_password) if db_password else None,
        )

    def mask_for_logging(self) -> Dict[str, str]:
        """Return masked versions of secrets for safe logging."""
        return {
            "gemini_api_key": f"{self.gemini_api_key.get_secret_value()[:8]}...",
            "github_token": (
                f"{self.github_token.get_secret_value()[:8]}..."
                if self.github_token
                else "***NOT_SET***"
            ),
            "gcp_service_account_key": (
                "***MASKED***" if self.gcp_service_account_key else "***NOT_SET***"
            ),
            "database_password": (
                "***MASKED***" if self.database_password else "***NOT_SET***"
            ),
        }
