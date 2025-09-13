# gemini_sre_agent/ml/schemas.py

"""
Common schemas and data models for the ML module.

This module provides shared data structures and schemas used across
the enhanced code generation system.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class BaseSchema:
    """Base schema class with common functionality."""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BaseSchema":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class RequestSchema(BaseSchema):
    """Schema for API requests."""

    model: str
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int | None = None


@dataclass
class ResponseSchema(BaseSchema):
    """Schema for API responses."""

    content: str
    model: str
    success: bool = True
    error: str | None = None


@dataclass
class UsageSchema(BaseSchema):
    """Schema for usage tracking."""

    input_tokens: int
    output_tokens: int
    cost_usd: float
    timestamp: str
