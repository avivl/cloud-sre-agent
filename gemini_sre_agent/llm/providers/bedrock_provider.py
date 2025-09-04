# gemini_sre_agent/llm/providers/bedrock_provider.py

"""
Bedrock provider implementation.

This module contains the concrete implementation of the LLMProvider interface
for AWS Bedrock models.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List

import boto3

from ..base import LLMProvider, LLMRequest, LLMResponse, ModelType
from ..config import LLMProviderConfig

logger = logging.getLogger(__name__)


class BedrockProvider(LLMProvider):
    """AWS Bedrock provider implementation."""

    def __init__(self, config: LLMProviderConfig):
        super().__init__(config)
        self.region = (
            config.provider_specific.get("aws_region", "us-east-1")
            if config.provider_specific
            else "us-east-1"
        )
        self.profile = (
            config.provider_specific.get("aws_profile")
            if config.provider_specific
            else None
        )

        # Initialize boto3 clients
        try:
            session_kwargs = {"region_name": self.region}
            if self.profile:
                session_kwargs["profile_name"] = self.profile

            session = boto3.Session(**session_kwargs)
            self.runtime_client = session.client("bedrock-runtime")
            self.bedrock_client = session.client("bedrock")
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock clients: {e}")
            raise

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate non-streaming response using Bedrock API."""
        logger.info(f"Generating response with Bedrock model: {self.model}")

        try:
            messages = self._convert_messages_to_bedrock_format(request.messages or [])
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            body = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
            }

            response = await asyncio.to_thread(
                self.runtime_client.invoke_model,
                modelId=self.model,
                body=json.dumps(body),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            content = self._extract_content_from_response(response_body)
            usage = self._extract_usage_from_response(response_body)

            return LLMResponse(
                content=content,
                model=self.model,
                provider=self.provider_name,
                usage=usage,
            )

        except Exception as e:
            logger.error(f"Bedrock generation error: {e}")
            raise

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response using Bedrock API."""
        logger.info(f"Generating streaming response with Bedrock model: {self.model}")

        try:
            messages = self._convert_messages_to_bedrock_format(request.messages or [])
            temperature = self.config.provider_specific.get("temperature", 0.7)
            max_tokens = self.config.provider_specific.get("max_tokens", 1000)
            top_p = self.config.provider_specific.get("top_p", 1.0)

            body = {
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
                "top_p": top_p,
                "stream": True,
            }

            response = await asyncio.to_thread(
                self.runtime_client.invoke_model_with_response_stream,
                modelId=self.model,
                body=json.dumps(body),
                contentType="application/json",
            )

            # Process streaming response
            for event in response["body"]:
                if "chunk" in event:
                    chunk_data = json.loads(event["chunk"]["bytes"])
                    if "delta" in chunk_data and "text" in chunk_data["delta"]:
                        yield LLMResponse(
                            content=chunk_data["delta"]["text"],
                            model=self.model,
                            provider=self.provider_name,
                            usage=None,
                        )

        except Exception as e:
            logger.error(f"Bedrock streaming error: {e}")
            raise

    async def health_check(self) -> bool:
        """Check if Bedrock API is accessible."""
        logger.debug("Performing Bedrock health check")

        try:
            # Use bedrock client (not runtime) for listing models
            await asyncio.to_thread(self.bedrock_client.list_foundation_models)
            return True
        except Exception as e:
            logger.error(f"Bedrock health check failed: {e}")
            return False

    def supports_streaming(self) -> bool:
        """Check if Bedrock supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if Bedrock supports tool calling."""
        return True

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available Bedrock models mapped to semantic types."""
        default_mappings = {
            ModelType.FAST: "anthropic.claude-3-5-haiku-20241022-v1:0",
            ModelType.SMART: "anthropic.claude-3-5-sonnet-20241022-v1:0",
            ModelType.DEEP_THINKING: "anthropic.claude-3-5-sonnet-20241022-v2:0",
            ModelType.CODE: "anthropic.claude-3-5-sonnet-20241022-v1:0",
            ModelType.ANALYSIS: "anthropic.claude-3-5-sonnet-20241022-v1:0",
        }

        if self.config.model_type_mappings:
            default_mappings.update(self.config.model_type_mappings)

        return default_mappings

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings using Bedrock API."""
        logger.info(f"Generating embeddings for text of length: {len(text)}")

        try:
            body = {"inputText": text}

            response = await asyncio.to_thread(
                self.runtime_client.invoke_model,
                modelId="amazon.titan-embed-text-v1",
                body=json.dumps(body),
                contentType="application/json",
            )

            response_body = json.loads(response["body"].read())
            return response_body["embedding"]

        except Exception as e:
            logger.error(f"Bedrock embeddings error: {e}")
            raise

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        return int(len(text.split()) * 1.3)

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        if "claude-3-5-sonnet" in self.model:
            input_cost_per_1k = 0.003
            output_cost_per_1k = 0.015
        elif "claude-3-5-haiku" in self.model:
            input_cost_per_1k = 0.0008
            output_cost_per_1k = 0.004
        else:
            input_cost_per_1k = 0.003
            output_cost_per_1k = 0.015

        input_cost = (input_tokens / 1000) * input_cost_per_1k
        output_cost = (output_tokens / 1000) * output_cost_per_1k
        return input_cost + output_cost

    def _convert_messages_to_bedrock_format(self, messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Convert generic message format to Bedrock format."""
        bedrock_messages = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")

            if role not in ["user", "assistant"]:
                role = "user"

            bedrock_messages.append({"role": role, "content": content})

        return bedrock_messages

    def _extract_content_from_response(self, response_body: Dict[str, Any]) -> str:
        """Extract content from Bedrock response."""
        if "content" in response_body and response_body["content"]:
            return response_body["content"][0]["text"]
        return ""

    def _extract_usage_from_response(self, response_body: Dict[str, Any]) -> Dict[str, int]:
        """Extract usage information from Bedrock response."""
        usage = response_body.get("usage", {})
        return {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
        }

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate Bedrock-specific configuration."""
        provider_specific = (
            config.provider_specific if hasattr(config, "provider_specific") else {}
        )
        if not provider_specific.get("aws_region"):
            raise ValueError("AWS region is required for Bedrock")
