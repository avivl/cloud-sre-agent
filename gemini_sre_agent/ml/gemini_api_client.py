"""
Gemini API client for pattern classification and confidence assessment.

This module provides a robust API client for Google's Gemini models with
structured output, error handling, and performance monitoring.
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from .adaptive_rate_limiter import AdaptiveRateLimiter
from .cost_tracker import CostTracker
from .rate_limiter_config import UrgencyLevel

try:
    import google.generativeai as genai  # type: ignore

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None


class GeminiRequest(BaseModel):
    """Request structure for Gemini API calls."""

    model: str = Field(..., description="Gemini model name")
    messages: List[Dict[str, str]] = Field(..., description="Chat messages")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=None, gt=0, le=8192)
    response_schema: Optional[Dict[str, Any]] = Field(default=None)
    generation_config: Optional[Dict[str, Any]] = Field(default=None)


class GeminiResponse(BaseModel):
    """Response structure from Gemini API calls."""

    success: bool
    content: str = Field(default="")
    parsed_json: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = Field(default=None)
    tokens_used: int = Field(default=0)
    latency_ms: float = Field(default=0.0)
    model_used: str = Field(default="")


class GeminiAPIClient:
    """High-performance Gemini API client with structured output support."""

    def __init__(
        self,
        api_key: str,
        cost_tracker: Optional[CostTracker] = None,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
    ) -> None:
        """Initialize the Gemini API client."""
        self.logger = logging.getLogger(__name__)

        if not GENAI_AVAILABLE:
            raise ImportError("google-generativeai package is required")

        # Configure the Gemini API
        if genai is not None:
            genai.configure(api_key=api_key)  # type: ignore

        # Monitoring components
        self.cost_tracker = cost_tracker
        self.rate_limiter = rate_limiter

        # Performance tracking
        self._request_count = 0
        self._total_tokens = 0
        self._total_latency = 0.0

    async def generate_response(self, request: GeminiRequest) -> GeminiResponse:
        """Generate response using Gemini model with structured output."""
        start_time = datetime.now()

        try:
            # Rate limiting
            if self.rate_limiter and self.cost_tracker:
                allowed = await self.rate_limiter.should_allow_request(
                    UrgencyLevel.MEDIUM, self.cost_tracker
                )
                if not allowed:
                    response = GeminiResponse(
                        success=False,
                        error_message="Request blocked by rate limiter",
                        model_used=request.model,
                        metadata={"timestamp": start_time.isoformat()},
                    )
                    return response

            # Initialize response object
            response = GeminiResponse(
                success=False,
                model_used=request.model,
                metadata={"timestamp": start_time.isoformat()},
            )

            # Configure generation parameters
            generation_config = self._build_generation_config(request)

            # Get the model
            model = genai.GenerativeModel(model_name=request.model)  # type: ignore

            # Convert messages to chat format
            chat_content = self._format_messages(request.messages)

            # Generate response
            api_response = await asyncio.to_thread(
                model.generate_content,
                chat_content,
                generation_config=genai.types.GenerationConfig(**generation_config),  # type: ignore
            )

            # Calculate latency
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Process successful response
            if api_response.candidates:
                content = api_response.candidates[0].content.parts[0].text
                tokens_used = self._estimate_tokens(content)

                response.success = True
                response.content = content
                response.tokens_used = tokens_used
                response.latency_ms = latency_ms

                # Parse JSON if structured output requested
                if request.response_schema:
                    response.parsed_json = self._parse_structured_output(
                        content, request.response_schema
                    )

                # Track metrics
                await self._track_success_metrics(request, response)

            else:
                response.error_message = "No candidates in API response"
                await self._track_error_metrics(request, response)

            return response

        except Exception as e:
            error_msg = f"Gemini API error: {str(e)}"
            self.logger.error(f"[GEMINI_CLIENT] {error_msg}")

            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            response = GeminiResponse(
                success=False,
                error_message=error_msg,
                latency_ms=latency_ms,
                model_used=request.model,
                metadata={"timestamp": start_time.isoformat()},
            )

            await self._track_error_metrics(request, response)
            return response

    def _build_generation_config(self, request: GeminiRequest) -> Dict[str, Any]:
        """Build generation configuration for API call."""
        config = {
            "temperature": request.temperature,
            "candidate_count": 1,
        }

        if request.max_tokens:
            config["max_output_tokens"] = request.max_tokens

        # Add structured output configuration if schema provided
        if request.response_schema:
            config["response_mime_type"] = "application/json"
            config["response_schema"] = request.response_schema

        # Merge custom generation config
        if request.generation_config:
            config.update(request.generation_config)

        return config

    def _format_messages(self, messages: List[Dict[str, str]]) -> str:
        """Format chat messages into single content string."""
        formatted_parts = []

        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role == "system":
                formatted_parts.append(f"SYSTEM: {content}")
            elif role == "user":
                formatted_parts.append(f"USER: {content}")
            elif role == "assistant":
                formatted_parts.append(f"ASSISTANT: {content}")
            else:
                formatted_parts.append(content)

        return "\n\n".join(formatted_parts)

    def _parse_structured_output(
        self, content: str, schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse structured JSON output from response content."""
        try:
            # Try to extract JSON from content
            content = content.strip()

            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            if content.startswith("```"):
                content = content[3:]

            content = content.strip()

            # Parse JSON
            parsed = json.loads(content)

            # Basic schema validation (required fields)
            if "required" in schema:
                required_fields = schema["required"]
                for field in required_fields:
                    if field not in parsed:
                        self.logger.warning(
                            f"[GEMINI_CLIENT] Missing required field: {field}"
                        )

            return parsed

        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(
                f"[GEMINI_CLIENT] Failed to parse structured output: {e}"
            )
            return {}

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text (rough approximation)."""
        # Rough estimation: ~4 characters per token for English
        return max(1, len(text) // 4)

    async def _track_success_metrics(
        self, request: GeminiRequest, response: GeminiResponse
    ) -> None:
        """Track successful API call metrics."""
        self._request_count += 1
        self._total_tokens += response.tokens_used
        self._total_latency += response.latency_ms

        # Cost tracking
        if self.cost_tracker:
            await self.cost_tracker.record_actual_cost(
                model_name=request.model,
                input_tokens=self._estimate_tokens(
                    self._format_messages(request.messages)
                ),
                output_tokens=response.tokens_used,
                operation_type="pattern_classification",
            )

    async def _track_error_metrics(
        self, request: GeminiRequest, response: GeminiResponse
    ) -> None:
        """Track failed API call metrics."""
        self._request_count += 1
        self._total_latency += response.latency_ms

        # Cost tracking for errors
        if self.cost_tracker:
            await self.cost_tracker.record_actual_cost(
                model_name=request.model,
                input_tokens=self._estimate_tokens(
                    self._format_messages(request.messages)
                ),
                output_tokens=0,
                operation_type="pattern_classification_error",
            )

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get client performance statistics."""
        avg_latency = self._total_latency / max(1, self._request_count)
        avg_tokens = self._total_tokens / max(1, self._request_count)

        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "total_latency_ms": self._total_latency,
            "average_latency_ms": avg_latency,
            "average_tokens_per_request": avg_tokens,
        }
