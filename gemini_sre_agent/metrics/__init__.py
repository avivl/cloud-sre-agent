from typing import Optional

from gemini_sre_agent.llm.config_manager import get_config_manager

from .metrics_manager import MetricsManager

_metrics_manager: Optional[MetricsManager] = None


def get_metrics_manager() -> MetricsManager:
    """Get the global MetricsManager instance."""
    global _metrics_manager
    if _metrics_manager is None:
        config_manager = get_config_manager()
        _metrics_manager = MetricsManager(config_manager)
    return _metrics_manager
