# gemini_sre_agent/llm/error_analytics.py

"""
Error analytics and monitoring for the multi-LLM provider system.

This module provides comprehensive error tracking, analytics, and monitoring
capabilities for understanding system health and error patterns.
"""

import asyncio
import time
from collections import Counter, defaultdict, deque
from typing import Any, Dict

from .error_config import ErrorCategory, RequestContext


class ErrorAnalytics:
    """Analytics for error tracking and monitoring."""

    def __init__(self):
        self.error_counts = Counter()
        self.provider_error_counts = defaultdict(Counter)
        self.category_counts = Counter()
        self.recent_errors = deque(maxlen=100)
        self._lock = asyncio.Lock()

    async def record_error(
        self, 
        error: Exception, 
        category: ErrorCategory, 
        context: RequestContext
    ) -> None:
        """Record error for analytics."""
        error_type = type(error).__name__
        async with self._lock:
            self.error_counts[error_type] += 1
            self.provider_error_counts[context.provider_id][error_type] += 1
            self.category_counts[category] += 1
            
            self.recent_errors.append({
                "timestamp": time.time(),
                "error_type": error_type,
                "category": category.name,
                "provider": context.provider_id,
                "message": str(error),
                "request_id": context.request_id
            })

    async def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary statistics."""
        async with self._lock:
            return {
                "total_errors": sum(self.error_counts.values()),
                "error_types": dict(self.error_counts),
                "category_counts": {cat.name: count for cat, count in self.category_counts.items()},
                "recent_errors_count": len(self.recent_errors),
                "provider_errors": {
                    provider: dict(errors) 
                    for provider, errors in self.provider_error_counts.items()
                }
            }

    async def get_provider_health(self, provider_id: str) -> Dict[str, Any]:
        """Get health metrics for a specific provider."""
        async with self._lock:
            provider_errors = self.provider_error_counts.get(provider_id, Counter())
            total_errors = sum(provider_errors.values())
            
            # Calculate health score (0-100, higher is better)
            health_score = max(0, 100 - (total_errors * 10))
            
            return {
                "provider_id": provider_id,
                "total_errors": total_errors,
                "error_types": dict(provider_errors),
                "health_score": health_score,
                "recent_errors": [
                    error for error in self.recent_errors 
                    if error["provider"] == provider_id
                ][-10:]  # Last 10 errors
            }

    async def get_top_error_providers(self, limit: int = 5) -> list[Dict[str, Any]]:
        """Get providers with most errors."""
        async with self._lock:
            provider_totals = [
                {"provider": provider, "total_errors": sum(errors.values())}
                for provider, errors in self.provider_error_counts.items()
            ]
            return sorted(provider_totals, key=lambda x: x["total_errors"], reverse=True)[:limit]

    async def clear_analytics(self) -> None:
        """Clear all analytics data."""
        async with self._lock:
            self.error_counts.clear()
            self.provider_error_counts.clear()
            self.category_counts.clear()
            self.recent_errors.clear()
