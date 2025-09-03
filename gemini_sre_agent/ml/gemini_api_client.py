# gemini_sre_agent/ml/gemini_api_client.py

"""
Gemini API client for enhanced code generation.

This module provides a client for interacting with the Gemini API,
including structured output support, error handling, cost tracking,
and rate limiting.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .adaptive_rate_limiter import AdaptiveRateLimiter
from .cost_tracker import CostTracker
from .rate_limiter_config import UrgencyLevel


@dataclass
class GeminiRequest:
    """
    Request model for Gemini API calls.

    This class represents a request to the Gemini API with all necessary
    parameters and configuration options.
    """

    model: str
    messages: List[Dict[str, str]]
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: float = 0.9
    top_k: int = 40
    stop_sequences: Optional[List[str]] = None
    safety_settings: Optional[Dict[str, Any]] = None
    generation_config: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert request to dictionary for API call."""
        config = {
            "model": self.model,
            "messages": self.messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        if self.max_tokens:
            config["max_tokens"] = self.max_tokens
        if self.stop_sequences:
            config["stop_sequences"] = self.stop_sequences
        if self.safety_settings:
            config["safety_settings"] = self.safety_settings
        if self.generation_config:
            config["generation_config"] = self.generation_config

        return config

    def validate(self) -> bool:
        """Validate request parameters."""
        if not self.model:
            return False
        if not self.messages:
            return False
        if not 0 <= self.temperature <= 2:
            return False
        if not 0 <= self.top_p <= 1:
            return False
        if self.top_k < 0:
            return False
        return True


@dataclass
class GeminiResponse:
    """
    Response model for Gemini API calls.

    This class represents the response from the Gemini API with
    content, metadata, and usage information.
    """

    content: str
    model: str
    finish_reason: str
    usage: Dict[str, int]
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    success: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert response to dictionary."""
        return {
            "content": self.content,
            "model": self.model,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
            "metadata": self.metadata,
            "error": self.error,
            "success": self.success,
        }

    @property
    def input_tokens(self) -> int:
        """Get number of input tokens."""
        return self.usage.get("input_tokens", 0)

    @property
    def output_tokens(self) -> int:
        """Get number of output tokens."""
        return self.usage.get("output_tokens", 0)

    @property
    def total_tokens(self) -> int:
        """Get total number of tokens."""
        return self.input_tokens + self.output_tokens


class GeminiAPIClient:
    """
    Client for interacting with the Gemini API.

    This class provides a comprehensive interface for making requests to the
    Gemini API with built-in rate limiting, cost tracking, and error handling.
    """

    def __init__(
        self,
        api_key: str,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
        cost_tracker: Optional[CostTracker] = None,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    ):
        """
        Initialize the Gemini API client.

        Args:
            api_key: API key for Gemini API
            rate_limiter: Optional rate limiter instance
            cost_tracker: Optional cost tracker instance
            base_url: Base URL for the API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.rate_limiter = rate_limiter
        self.cost_tracker = cost_tracker
        self.logger = logging.getLogger(__name__)

        # Request/response tracking
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0

    async def generate_content(
        self,
        request: GeminiRequest,
        urgency: UrgencyLevel = UrgencyLevel.MEDIUM,
    ) -> GeminiResponse:
        """
        Generate content using the Gemini API.

        Args:
            request: Gemini request object
            urgency: Urgency level for rate limiting

        Returns:
            Gemini response object

        Raises:
            ValueError: If request is invalid
            RuntimeError: If API call fails
        """
        # Validate request
        if not request.validate():
            raise ValueError("Invalid request parameters")

        # Check rate limits
        if self.rate_limiter:
            can_make_request = await self.rate_limiter.can_make_request(urgency)
            if not can_make_request:
                delay = await self.rate_limiter.get_delay_seconds(urgency)
                raise RuntimeError(
                    f"Rate limit exceeded. Retry after {delay:.2f} seconds"
                )

        # Estimate cost
        estimated_cost = 0.0
        if self.cost_tracker:
            # Estimate input tokens from messages
            estimated_input_tokens = (
                sum(len(msg.get("content", "")) for msg in request.messages) // 4
            )
            estimated_cost = self.cost_tracker.estimate_cost(
                request.model, estimated_input_tokens, 0
            )
            budget_ok = await self.cost_tracker.check_budget(estimated_cost)
            if not budget_ok:
                raise RuntimeError("Operation would exceed budget limits")

        # Make API call
        try:
            self.total_requests += 1
            response = await self._make_api_call(request)
            self.successful_requests += 1

            # Record successful usage
            if self.cost_tracker:
                await self.cost_tracker.record_usage(
                    operation="generate_content",
                    model=request.model,
                    input_tokens=response.input_tokens,
                    output_tokens=response.output_tokens,
                    cost_usd=estimated_cost,
                    success=True,
                )

            # Record success in rate limiter
            if self.rate_limiter:
                await self.rate_limiter.record_request_success(estimated_cost)

            return response

        except Exception as e:
            self.failed_requests += 1
            error_msg = str(e)

            # Record failed usage
            if self.cost_tracker:
                await self.cost_tracker.record_usage(
                    operation="generate_content",
                    model=request.model,
                    input_tokens=0,
                    output_tokens=0,
                    cost_usd=estimated_cost,
                    success=False,
                    error_message=error_msg,
                )

            # Record error in rate limiter
            if self.rate_limiter:
                await self.rate_limiter.record_request_error(
                    "api_error", estimated_cost
                )

            # Return error response
            return GeminiResponse(
                content="",
                model=request.model,
                finish_reason="error",
                usage={"input_tokens": 0, "output_tokens": 0},
                error=error_msg,
                success=False,
            )

    async def _make_api_call(self, request: GeminiRequest) -> GeminiResponse:
        """
        Make the actual API call to Gemini.

        Args:
            request: Gemini request object

        Returns:
            Gemini response object

        Raises:
            RuntimeError: If API call fails
        """
        # This is a simplified implementation
        # In a real implementation, this would make an HTTP request to the Gemini API

        # Simulate API response
        estimated_input_tokens = (
            sum(len(msg.get("content", "")) for msg in request.messages) // 4
        )
        response_data = {
            "content": "This is a simulated response from Gemini API",
            "model": request.model,
            "finish_reason": "stop",
            "usage": {
                "input_tokens": estimated_input_tokens or 100,
                "output_tokens": 50,
            },
        }

        return GeminiResponse(
            content=response_data["content"],
            model=response_data["model"],
            finish_reason=response_data["finish_reason"],
            usage=response_data["usage"],
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get client statistics."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate": (
                self.successful_requests / self.total_requests
                if self.total_requests > 0
                else 0.0
            ),
        }

    def reset_stats(self):
        """Reset client statistics."""
        self.total_requests = 0
        self.successful_requests = 0
        self.failed_requests = 0
