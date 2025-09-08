from typing import Literal

from pydantic import BaseModel, Field


class Alert(BaseModel):
    """A class to represent an alert."""

    severity: Literal["high", "medium", "low"] = Field(
        ..., description="The severity of the alert."
    )
    provider_id: str = Field(
        ..., description="The ID of the provider that triggered the alert."
    )
    message: str = Field(..., description="A human-readable message for the alert.")
    metric: str = Field(..., description="The metric that triggered the alert.")
    value: float = Field(
        ..., description="The value of the metric that triggered the alert."
    )
    threshold: float = Field(..., description="The threshold for the metric.")
