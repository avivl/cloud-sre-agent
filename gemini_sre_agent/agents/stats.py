# gemini_sre_agent/agents/stats.py

"""
Statistics collection for agent execution.

This module provides the AgentStats class for collecting and analyzing
agent performance metrics, including success rates, latencies, and error tracking.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class AgentStats:
    """Statistics collector for agent execution."""
    agent_name: str
    request_count: int = 0
    success_count: int = 0
    error_count: int = 0
    
    # Detailed metrics
    latencies_ms: Dict[str, List[int]] = field(default_factory=lambda: defaultdict(list))
    errors: Dict[str, List[str]] = field(default_factory=lambda: defaultdict(list))
    prompt_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    model_usage: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    
    def record_success(self, model: str, latency_ms: int, prompt_name: Optional[str] = None):
        """Record a successful agent execution."""
        self.request_count += 1
        self.success_count += 1
        self.latencies_ms[model].append(latency_ms)
        self.model_usage[model] += 1
        if prompt_name:
            self.prompt_usage[prompt_name] += 1
    
    def record_error(self, model: str, error: str, prompt_name: Optional[str] = None):
        """Record a failed agent execution."""
        self.request_count += 1
        self.error_count += 1
        self.errors[model].append(error)
        self.model_usage[model] += 1
        if prompt_name:
            self.prompt_usage[prompt_name] += 1
    
    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of agent statistics."""
        return {
            "agent_name": self.agent_name,
            "request_count": self.request_count,
            "success_rate": self.success_count / max(1, self.request_count),
            "avg_latency_ms": {
                model: sum(latencies) / max(1, len(latencies)) 
                for model, latencies in self.latencies_ms.items()
            },
            "model_usage": dict(self.model_usage),
            "prompt_usage": dict(self.prompt_usage),
            "error_count_by_model": {
                model: len(errors) for model, errors in self.errors.items()
            }
        }
    
    def reset(self):
        """Reset all statistics."""
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.latencies_ms.clear()
        self.errors.clear()
        self.prompt_usage.clear()
        self.model_usage.clear()
