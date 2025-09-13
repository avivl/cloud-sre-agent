"""Validation schemas for the configuration validation system."""

from abc import abstractmethod
from typing import Any

from pydantic import BaseModel, Field, model_validator, validator

from .result import ValidationResult


class BaseValidationSchema(BaseModel):
    """Base class for validation schemas."""

    @abstractmethod
    def validate_data(self, data: Any) -> ValidationResult:
        """Validate data against the schema.

        Args:
            data: Data to validate

        Returns:
            Validation result
        """
        pass

    def get_schema_info(self) -> dict[str, Any]:
        """Get schema information.

        Returns:
            Dictionary with schema information
        """
        return {
            "schema_name": self.__class__.__name__,
            "fields": list(self.model_fields.keys()),
            "required_fields": [
                name for name, field in self.model_fields.items() if field.is_required()
            ],
        }


class ConfigValidationSchema(BaseValidationSchema):
    """Schema for general configuration validation."""

    environment: str = Field(..., description="Environment name")
    schema_version: str = Field(..., description="Schema version")
    services: list[str] = Field(
        default_factory=list, description="List of configured services"
    )
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Log level")

    @validator("environment")
    def validate_environment(cls, v: str) -> str:
        """Validate environment value.

        Args:
            v: Environment value

        Returns:
            Validated environment value
        """
        valid_environments = ["development", "staging", "production", "test"]
        if v not in valid_environments:
            raise ValueError(f"Environment must be one of: {valid_environments}")
        return v

    @validator("log_level")
    def validate_log_level(cls, v: str) -> str:
        """Validate log level.

        Args:
            v: Log level value

        Returns:
            Validated log level value
        """
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        return v.upper()

    @model_validator(mode="after")
    def validate_config_consistency(self) -> "ConfigValidationSchema":
        """Validate configuration consistency.

        Returns:
            Self for chaining
        """
        # Check if debug mode is appropriate for environment
        if self.environment == "production" and self.debug:
            raise ValueError("Debug mode should not be enabled in production")

        # Check if log level is appropriate for environment
        if self.environment == "production" and self.log_level in ["DEBUG", "INFO"]:
            raise ValueError(
                "Production environment should use WARNING or higher log level"
            )

        return self

    def validate_data(self, data: Any) -> ValidationResult:
        """Validate data against the configuration schema.

        Args:
            data: Data to validate

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate using Pydantic
            self.model_validate(data)
        except Exception as e:
            result.is_valid = False
            result.add_error(
                message=f"Configuration validation failed: {e!s}",
                rule_name="ConfigValidationSchema",
                context={"exception": str(e)},
            )

        return result


class ServiceValidationSchema(BaseValidationSchema):
    """Schema for service configuration validation."""

    name: str = Field(..., description="Service name")
    enabled: bool = Field(default=True, description="Whether service is enabled")
    timeout: float = Field(default=30.0, description="Service timeout in seconds")
    retries: int = Field(default=3, description="Number of retries")
    health_check_interval: float = Field(
        default=60.0, description="Health check interval in seconds"
    )
    dependencies: list[str] = Field(
        default_factory=list, description="Service dependencies"
    )

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate service name.

        Args:
            v: Service name

        Returns:
            Validated service name
        """
        if not v or not v.strip():
            raise ValueError("Service name cannot be empty")
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError(
                "Service name must contain only alphanumeric characters, hyphens, and underscores"
            )
        return v.strip()

    @validator("timeout")
    def validate_timeout(cls, v: float) -> float:
        """Validate timeout value.

        Args:
            v: Timeout value

        Returns:
            Validated timeout value
        """
        if v <= 0:
            raise ValueError("Timeout must be positive")
        if v > 3600:  # 1 hour
            raise ValueError("Timeout should not exceed 3600 seconds")
        return v

    @validator("retries")
    def validate_retries(cls, v: int) -> int:
        """Validate retries value.

        Args:
            v: Retries value

        Returns:
            Validated retries value
        """
        if v < 0:
            raise ValueError("Retries cannot be negative")
        if v > 10:
            raise ValueError("Retries should not exceed 10")
        return v

    @validator("health_check_interval")
    def validate_health_check_interval(cls, v: float) -> float:
        """Validate health check interval.

        Args:
            v: Health check interval value

        Returns:
            Validated health check interval value
        """
        if v <= 0:
            raise ValueError("Health check interval must be positive")
        if v < 10:  # 10 seconds minimum
            raise ValueError("Health check interval should be at least 10 seconds")
        return v

    def validate_data(self, data: Any) -> ValidationResult:
        """Validate data against the service schema.

        Args:
            data: Data to validate

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate using Pydantic
            self.model_validate(data)
        except Exception as e:
            result.is_valid = False
            result.add_error(
                message=f"Service validation failed: {e!s}",
                rule_name="ServiceValidationSchema",
                context={"exception": str(e)},
            )

        return result


class LLMValidationSchema(BaseValidationSchema):
    """Schema for LLM configuration validation."""

    provider: str = Field(..., description="LLM provider name")
    model: str = Field(..., description="Model name")
    api_key: str | None = Field(None, description="API key")
    max_tokens: int = Field(default=1000, description="Maximum tokens")
    temperature: float = Field(default=0.7, description="Temperature")
    timeout: float = Field(default=30.0, description="Request timeout")
    retries: int = Field(default=3, description="Number of retries")

    @validator("provider")
    def validate_provider(cls, v: str) -> str:
        """Validate provider name.

        Args:
            v: Provider name

        Returns:
            Validated provider name
        """
        valid_providers = ["openai", "anthropic", "google", "azure", "ollama"]
        if v.lower() not in valid_providers:
            raise ValueError(f"Provider must be one of: {valid_providers}")
        return v.lower()

    @validator("max_tokens")
    def validate_max_tokens(cls, v: int) -> int:
        """Validate max tokens.

        Args:
            v: Max tokens value

        Returns:
            Validated max tokens value
        """
        if v <= 0:
            raise ValueError("Max tokens must be positive")
        if v > 100000:  # 100k tokens max
            raise ValueError("Max tokens should not exceed 100000")
        return v

    @validator("temperature")
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature.

        Args:
            v: Temperature value

        Returns:
            Validated temperature value
        """
        if v < 0 or v > 2:
            raise ValueError("Temperature must be between 0 and 2")
        return v

    @model_validator(mode="after")
    def validate_llm_consistency(self) -> "LLMValidationSchema":
        """Validate LLM configuration consistency.

        Returns:
            Self for chaining
        """
        # Check if API key is required for non-local providers
        local_providers = ["ollama"]
        if self.provider not in local_providers and not self.api_key:
            raise ValueError(f"API key is required for provider '{self.provider}'")

        return self

    def validate_data(self, data: Any) -> ValidationResult:
        """Validate data against the LLM schema.

        Args:
            data: Data to validate

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate using Pydantic
            self.model_validate(data)
        except Exception as e:
            result.is_valid = False
            result.add_error(
                message=f"LLM validation failed: {e!s}",
                rule_name="LLMValidationSchema",
                context={"exception": str(e)},
            )

        return result


class DatabaseValidationSchema(BaseValidationSchema):
    """Schema for database configuration validation."""

    host: str = Field(..., description="Database host")
    port: int = Field(default=5432, description="Database port")
    database: str = Field(..., description="Database name")
    username: str = Field(..., description="Database username")
    password: str | None = Field(None, description="Database password")
    ssl_mode: str = Field(default="prefer", description="SSL mode")
    connection_pool_size: int = Field(default=10, description="Connection pool size")

    @validator("port")
    def validate_port(cls, v: int) -> int:
        """Validate port number.

        Args:
            v: Port number

        Returns:
            Validated port number
        """
        if v <= 0 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v

    @validator("ssl_mode")
    def validate_ssl_mode(cls, v: str) -> str:
        """Validate SSL mode.

        Args:
            v: SSL mode

        Returns:
            Validated SSL mode
        """
        valid_modes = [
            "disable",
            "allow",
            "prefer",
            "require",
            "verify-ca",
            "verify-full",
        ]
        if v.lower() not in valid_modes:
            raise ValueError(f"SSL mode must be one of: {valid_modes}")
        return v.lower()

    @validator("connection_pool_size")
    def validate_connection_pool_size(cls, v: int) -> int:
        """Validate connection pool size.

        Args:
            v: Connection pool size

        Returns:
            Validated connection pool size
        """
        if v <= 0:
            raise ValueError("Connection pool size must be positive")
        if v > 100:
            raise ValueError("Connection pool size should not exceed 100")
        return v

    def validate_data(self, data: Any) -> ValidationResult:
        """Validate data against the database schema.

        Args:
            data: Data to validate

        Returns:
            Validation result
        """
        result = ValidationResult(is_valid=True)

        try:
            # Validate using Pydantic
            self.model_validate(data)
        except Exception as e:
            result.is_valid = False
            result.add_error(
                message=f"Database validation failed: {e!s}",
                rule_name="DatabaseValidationSchema",
                context={"exception": str(e)},
            )

        return result
