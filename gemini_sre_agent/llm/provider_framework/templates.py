"""
Pre-built Provider Templates for Common Patterns.

This module provides ready-to-use templates for common provider patterns,
making it even easier to implement new providers.
"""

import json
import logging
from typing import Any, Dict

import httpx

from ..base import LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig
from .base_template import BaseProviderTemplate

logger = logging.getLogger(__name__)


class HTTPAPITemplate(BaseProviderTemplate):
    """
    Template for providers that use simple HTTP API calls.

    Perfect for REST APIs that follow standard patterns.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make HTTP API request."""
        payload = self._get_request_payload(request)

        response = await self.client.post(
            "/chat/completions",  # Override in subclasses
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse HTTP API response."""
        return self._parse_openai_response(response_data)

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get model mapping. Override in subclasses."""
        return {
            ModelType.FAST: "fast-model",
            ModelType.SMART: "smart-model",
        }

    async def health_check(self) -> bool:
        """Check health via HTTP endpoint."""
        try:
            response = await self.client.get("/health", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False


class OpenAICompatibleTemplate(BaseProviderTemplate):
    """
    Template for OpenAI-compatible providers.

    Perfect for providers that follow OpenAI's API format exactly.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make OpenAI-compatible API request."""
        payload = self._get_request_payload(request)

        response = await self.client.post(
            "/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse OpenAI-compatible response."""
        return self._parse_openai_response(response_data)

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get model mapping. Override in subclasses."""
        return {
            ModelType.FAST: "gpt-3.5-turbo",
            ModelType.SMART: "gpt-4",
        }

    def supports_streaming(self) -> bool:
        """OpenAI-compatible providers typically support streaming."""
        return True

    def supports_tools(self) -> bool:
        """OpenAI-compatible providers typically support tools."""
        return True


class RESTAPITemplate(BaseProviderTemplate):
    """
    Template for custom REST API providers.

    Provides flexibility for non-standard API formats.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

        # Customizable endpoints
        self.chat_endpoint = self._get_provider_specific_config(
            "chat_endpoint", "/chat"
        )
        self.health_endpoint = self._get_provider_specific_config(
            "health_endpoint", "/health"
        )

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make custom REST API request."""
        payload = self._customize_payload(request)

        response = await self.client.post(
            self.chat_endpoint,
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse custom REST API response."""
        # Override in subclasses for custom response formats
        return self._parse_openai_response(response_data)

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get model mapping. Override in subclasses."""
        return {
            ModelType.FAST: "fast",
            ModelType.SMART: "smart",
        }

    def _customize_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Customize the request payload. Override in subclasses."""
        return self._get_request_payload(request)

    async def health_check(self) -> bool:
        """Check health via custom endpoint."""
        try:
            response = await self.client.get(self.health_endpoint, timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False


class StreamingTemplate(BaseProviderTemplate):
    """
    Template for providers that support streaming responses.

    Extends base template with streaming capabilities.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make streaming API request."""
        payload = self._get_request_payload(request)
        payload["stream"] = True

        response = await self.client.post(
            "/v1/chat/completions",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse streaming response."""
        return self._parse_openai_response(response_data)

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get model mapping. Override in subclasses."""
        return {
            ModelType.FAST: "streaming-fast",
            ModelType.SMART: "streaming-smart",
        }

    def supports_streaming(self) -> bool:
        """This template supports streaming."""
        return True

    async def generate_stream(self, request: LLMRequest):
        """Generate streaming response."""
        payload = self._get_request_payload(request)
        payload["stream"] = True

        async with self.client.stream(
            "POST",
            "/v1/chat/completions",
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]  # Remove "data: " prefix
                    if data.strip() == "[DONE]":
                        break

                    try:
                        chunk_data = json.loads(data)
                        if "choices" in chunk_data:
                            choice = chunk_data["choices"][0]
                            if "delta" in choice and "content" in choice["delta"]:
                                yield LLMResponse(
                                    content=choice["delta"]["content"],
                                    model=chunk_data.get("model", ""),
                                    usage={},
                                    finish_reason=choice.get("finish_reason"),
                                )
                    except json.JSONDecodeError:
                        continue


class AnthropicCompatibleTemplate(BaseProviderTemplate):
    """
    Template for Anthropic-compatible providers.

    Follows Anthropic's API format and patterns.
    """

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
            headers=self._get_headers(),
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get Anthropic-compatible headers."""
        return {
            "x-api-key": self.api_key or "",
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def _get_request_payload(self, request: LLMRequest) -> Dict[str, Any]:
        """Convert to Anthropic format."""
        # Convert OpenAI format to Anthropic format
        messages = []
        system_message = None

        for msg in request.messages or []:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        payload = {
            "model": "anthropic-model",
            "max_tokens": request.max_tokens,
            "messages": messages,
        }

        if system_message:
            payload["system"] = system_message

        return payload

    async def _make_api_request(self, request: LLMRequest) -> Dict[str, Any]:
        """Make Anthropic-compatible API request."""
        payload = self._get_request_payload(request)

        response = await self.client.post(
            "/v1/messages",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def _parse_response(self, response_data: Dict[str, Any]) -> LLMResponse:
        """Parse Anthropic-compatible response."""
        content = ""
        for block in response_data.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return LLMResponse(
            content=content,
            model=response_data.get("model", ""),
            usage=response_data.get("usage", {}),
            finish_reason=response_data.get("stop_reason", "end_turn"),
        )

    def _get_model_mapping(self) -> Dict[ModelType, str]:
        """Get Anthropic model mapping."""
        return {
            ModelType.FAST: "claude-3-haiku-20240307",
            ModelType.SMART: "claude-3-5-sonnet-20241022",
        }

    def supports_tools(self) -> bool:
        """Anthropic supports tools."""
        return True
