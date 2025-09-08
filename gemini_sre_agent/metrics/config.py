from typing import Any, Dict

from pydantic import BaseModel, Field


class MetricsConfig(BaseModel):
    """Configuration for the metrics system."""

    alert_thresholds: Dict[str, Any] = Field(
        default_factory=dict, description="Thresholds for triggering alerts."
    )
