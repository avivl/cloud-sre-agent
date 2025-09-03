# gemini_sre_agent/config/base.py

"""
Base configuration classes with environment support and schema versioning.
"""

import hashlib
import json
from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    """Supported environments."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TESTING = "testing"


class BaseConfig(BaseSettings):
    """Base configuration class with common settings and schema versioning."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="forbid",
    )

    # Schema versioning and metadata
    schema_version: str = Field(
        default="1.0.0", description="Configuration schema version"
    )
    last_validated: Optional[str] = Field(
        default=None, description="Last validation timestamp"
    )
    validation_checksum: Optional[str] = Field(
        default=None, description="Configuration validation checksum"
    )

    # Environment settings
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False
    log_level: str = "INFO"

    # Application settings
    app_name: str = "gemini-sre-agent"
    app_version: str = "0.1.0"

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, v):
        """Validate configuration schema version."""
        supported_versions = ["1.0.0"]
        if v not in supported_versions:
            raise ValueError(
                f"Unsupported schema version {v}. Supported: {supported_versions}"
            )
        return v

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v):
        """Validate log level."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of {valid_levels}")
        return v.upper()

    def calculate_checksum(self) -> str:
        """Calculate configuration checksum for drift detection."""
        # Create a serializable representation
        config_dict = self.model_dump(exclude={"validation_checksum", "last_validated"})
        config_str = json.dumps(config_dict, sort_keys=True)

        return hashlib.sha256(config_str.encode()).hexdigest()

    def validate_checksum(self) -> bool:
        """Validate configuration checksum."""
        if not self.validation_checksum:
            return True  # No checksum to validate

        return self.calculate_checksum() == self.validation_checksum
