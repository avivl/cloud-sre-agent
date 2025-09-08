# gemini_sre_agent/llm/testing/mock_providers.py

"""
Mock LLM Providers for Testing.

This module provides mock implementations of LLM providers that can be used
for testing without incurring API costs or requiring actual provider connections.
"""

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..base import LLMRequest, LLMResponse
from ..common.enums import ModelType, ProviderType
from ..factory import LLMProvider, LLMProviderFactory
from ..model_registry import ModelInfo, ModelRegistry


@dataclass
class MockResponseConfig:
    """Configuration for mock responses."""

    response_time_ms: int = 100
    success_rate: float = 1.0
    error_rate: float = 0.0
    timeout_rate: float = 0.0
    custom_responses: Optional[Dict[str, str]] = None


class MockLLMProvider(LLMProvider):
    """Mock LLM provider for testing purposes."""

    def __init__(
        self,
        provider_type: ProviderType,
        config: Optional[MockResponseConfig] = None,
    ):
        """Initialize the mock provider."""
        # Create a mock config object
        mock_config = type(
            "MockConfig",
            (),
            {"provider": provider_type, "model": "mock-model", "max_retries": 3},
        )()
        super().__init__(mock_config)
        self.provider_type = provider_type
        self.config = config or MockResponseConfig()
        self.request_count = 0
        self.total_tokens = 0

        # Predefined responses for common test scenarios
        self.default_responses = {
            "hello": "Hello! How can I help you today?",
            "test": "This is a test response from the mock provider.",
            "error": "This is an error response for testing.",
            "timeout": "This response will timeout for testing.",
            "long": "This is a longer response that contains more content to test token counting and response handling. "
            * 10,
        }

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate a mock response."""
        self.request_count += 1

        # Simulate response time
        await asyncio.sleep(self.config.response_time_ms / 1000.0)

        # Determine response type based on configuration
        response_type = self._determine_response_type()

        if response_type == "error":
            raise Exception("Mock provider error for testing")
        elif response_type == "timeout":
            raise asyncio.TimeoutError("Mock provider timeout for testing")

        # Generate response content
        content = self._generate_response_content(request.prompt or "")

        # Calculate token usage (rough estimation)
        input_tokens = len(request.prompt.split()) if request.prompt else 0
        output_tokens = len(content.split())
        total_tokens = input_tokens + output_tokens

        self.total_tokens += total_tokens

        return LLMResponse(
            content=content,
            usage={
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
            model_type=request.model_type,
            provider=self.provider_type.value,
        )

    def _determine_response_type(self) -> str:
        """Determine the type of response based on configuration."""
        rand = random.random()  # nosec B311

        if rand < self.config.error_rate:
            return "error"
        elif rand < self.config.error_rate + self.config.timeout_rate:
            return "timeout"
        else:
            return "success"

    def _generate_response_content(self, prompt: str) -> str:
        """Generate response content based on the prompt."""
        if not prompt:
            return self.default_responses["test"]

        prompt_lower = prompt.lower().strip()

        # Check for custom responses first
        if self.config.custom_responses:
            for key, response in self.config.custom_responses.items():
                if key.lower() in prompt_lower:
                    return response

        # Check for predefined responses
        for key, response in self.default_responses.items():
            if key in prompt_lower:
                return response

        # Generate contextual response
        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! How can I assist you today?"
        elif "question" in prompt_lower:
            return "That's an interesting question. Here's my response based on the mock provider's capabilities."
        elif "code" in prompt_lower:
            return "Here's some mock code:\n\n```python\ndef mock_function():\n    return 'This is mock code for testing'\n```"
        elif "explain" in prompt_lower:
            return "I'll explain this concept using the mock provider's knowledge base. This is a simulated explanation for testing purposes."
        else:
            return (
                f"Mock response to: {prompt[:100]}{'...' if len(prompt) > 100 else ''}"
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get provider statistics."""
        return {
            "provider_type": self.provider_type.value,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
            "average_tokens_per_request": (
                self.total_tokens / self.request_count if self.request_count > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset provider statistics."""
        self.request_count = 0
        self.total_tokens = 0

    async def _generate(self, request: LLMRequest) -> LLMResponse:
        """Internal generate method - delegates to public generate method."""
        return await self.generate(request)

    async def generate_stream(self, request: LLMRequest):  # type: ignore
        """Generate streaming response (not implemented for mock)."""
        # For mock, just return the regular response
        response = await self.generate(request)
        yield response

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information."""
        return {
            "provider_type": self.provider_type.value,
            "is_available": True,
            "request_count": self.request_count,
            "total_tokens": self.total_tokens,
        }

    async def health_check(self) -> bool:
        """Check if provider is healthy."""
        return True

    def get_capabilities(self) -> List[str]:
        """Get provider capabilities."""
        return ["text_generation", "streaming"]

    def get_supported_models(self) -> List[str]:
        """Get supported models."""
        return ["mock-model-1", "mock-model-2"]

    def get_model_info(self, model: str) -> Optional[Dict[str, Any]]:
        """Get model information."""
        return {
            "name": model,
            "provider": self.provider_type.value,
            "max_tokens": 4096,
            "supports_streaming": True,
        }

    async def validate_request(self, request: LLMRequest) -> bool:
        """Validate request."""
        return request.prompt is not None and len(request.prompt) > 0

    def estimate_cost(self, request: LLMRequest) -> float:
        """Estimate cost for request."""
        # Simple cost estimation
        estimated_tokens = len(request.prompt.split()) * 2 if request.prompt else 0
        return estimated_tokens * 0.0001  # $0.0001 per token

    def supports_streaming(self) -> bool:
        """Check if provider supports streaming."""
        return True

    def supports_tools(self) -> bool:
        """Check if provider supports tool calling."""
        return False

    def get_available_models(self) -> Dict[ModelType, str]:
        """Get available models mapped to semantic types."""
        from ..common.enums import ModelType

        return {
            ModelType.SMART: "mock-smart-model",
            ModelType.FAST: "mock-fast-model",
            ModelType.DEEP_THINKING: "mock-deep-model",
        }

    async def embeddings(self, text: str) -> List[float]:
        """Generate embeddings for the given text."""
        # Return mock embeddings
        return [0.1, 0.2, 0.3, 0.4, 0.5] * 100  # 500-dimensional mock embedding

    def token_count(self, text: str) -> int:
        """Count tokens in the given text."""
        # Simple word-based token counting for mock
        return int(len(text.split()) * 1.3)  # Rough approximation

    def cost_estimate(self, input_tokens: int, output_tokens: int) -> float:
        """Estimate cost for the given token usage."""
        # Mock pricing: $0.001 per 1K tokens
        return (input_tokens + output_tokens) * 0.001 / 1000

    @classmethod
    def validate_config(cls, config: Any) -> None:
        """Validate provider-specific configuration."""
        pass

    def get_custom_capabilities(self) -> List[Any]:
        """Get provider-specific custom capabilities."""
        return []


class MockProviderFactory(LLMProviderFactory):
    """Factory for creating mock providers."""

    def __init__(self):
        """Initialize the mock provider factory."""
        self.providers: Dict[str, MockLLMProvider] = {}
        self._initialize_mock_providers()

    def _initialize_mock_providers(self) -> None:
        """Initialize mock providers for all supported types."""
        # Fast provider - quick responses
        self.providers["mock_openai_fast"] = MockLLMProvider(
            ProviderType.OPENAI,
            MockResponseConfig(
                response_time_ms=50,
                success_rate=0.95,
                error_rate=0.05,
            ),
        )

        # Slow provider - slower responses
        self.providers["mock_openai_slow"] = MockLLMProvider(
            ProviderType.OPENAI,
            MockResponseConfig(
                response_time_ms=500,
                success_rate=0.90,
                error_rate=0.10,
            ),
        )

        # Reliable provider - high success rate
        self.providers["mock_anthropic_reliable"] = MockLLMProvider(
            ProviderType.CLAUDE,
            MockResponseConfig(
                response_time_ms=200,
                success_rate=0.99,
                error_rate=0.01,
            ),
        )

        # Unreliable provider - high error rate
        self.providers["mock_anthropic_unreliable"] = MockLLMProvider(
            ProviderType.CLAUDE,
            MockResponseConfig(
                response_time_ms=150,
                success_rate=0.70,
                error_rate=0.30,
            ),
        )

        # Google provider
        self.providers["mock_google"] = MockLLMProvider(
            ProviderType.GEMINI,
            MockResponseConfig(
                response_time_ms=300,
                success_rate=0.95,
                error_rate=0.05,
            ),
        )

    @classmethod
    def get_provider(cls, provider_name: str) -> Optional[MockLLMProvider]:
        """Get a mock provider by name."""
        instance = cls()
        return instance.providers.get(provider_name)

    @classmethod
    def list_providers(cls) -> List[str]:
        """List all available mock providers."""
        instance = cls()
        return list(instance.providers.keys())

    def create_custom_provider(
        self,
        name: str,
        provider_type: ProviderType,
        config: MockResponseConfig,
    ) -> MockLLMProvider:
        """Create a custom mock provider."""
        provider = MockLLMProvider(provider_type, config)
        self.providers[name] = provider
        return provider

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all mock providers."""
        return {name: provider.get_stats() for name, provider in self.providers.items()}

    def reset_all_stats(self) -> None:
        """Reset statistics for all mock providers."""
        for provider in self.providers.values():
            provider.reset_stats()


class MockModelRegistry(ModelRegistry):
    """Mock model registry for testing."""

    def __init__(self):
        """Initialize the mock model registry."""
        super().__init__()
        self.models = {
            "gpt-3.5-turbo": {
                "name": "gpt-3.5-turbo",
                "provider": "openai",
                "cost_per_1k_tokens": 0.002,
                "max_tokens": 4096,
                "semantic_type": "smart",
            },
            "gpt-4": {
                "name": "gpt-4",
                "provider": "openai",
                "cost_per_1k_tokens": 0.03,
                "max_tokens": 8192,
                "semantic_type": "smart",
            },
            "claude-3-sonnet": {
                "name": "claude-3-sonnet",
                "provider": "anthropic",
                "cost_per_1k_tokens": 0.015,
                "max_tokens": 4096,
                "semantic_type": "smart",
            },
            "claude-3-haiku": {
                "name": "claude-3-haiku",
                "provider": "anthropic",
                "cost_per_1k_tokens": 0.00025,
                "max_tokens": 4096,
                "semantic_type": "fast",
            },
            "gemini-pro": {
                "name": "gemini-pro",
                "provider": "google",
                "cost_per_1k_tokens": 0.0005,
                "max_tokens": 4096,
                "semantic_type": "smart",
            },
        }

    def get_model(self, model_name: str) -> Optional[ModelInfo]:
        """Get model information."""
        model_data = self.models.get(model_name)
        if not model_data:
            return None

        return ModelInfo(
            name=model_data["name"],
            provider=ProviderType(model_data["provider"]),
            semantic_type=ModelType(model_data["semantic_type"]),
            cost_per_1k_tokens=model_data["cost_per_1k_tokens"],
            max_tokens=model_data["max_tokens"],
        )

    def get_all_models(self) -> List[ModelInfo]:
        """Get all models."""
        return [
            ModelInfo(
                name=model_data["name"],
                provider=ProviderType(model_data["provider"]),
                semantic_type=ModelType(model_data["semantic_type"]),
                cost_per_1k_tokens=model_data["cost_per_1k_tokens"],
                max_tokens=model_data["max_tokens"],
            )
            for model_data in self.models.values()
        ]

    def get_models_by_provider(self, provider: str) -> List[ModelInfo]:
        """Get models by provider."""
        return [
            ModelInfo(
                name=model_data["name"],
                provider=ProviderType(model_data["provider"]),
                semantic_type=ModelType(model_data["semantic_type"]),
                cost_per_1k_tokens=model_data["cost_per_1k_tokens"],
                max_tokens=model_data["max_tokens"],
            )
            for model_data in self.models.values()
            if model_data["provider"] == provider
        ]

    def get_models_by_type(self, semantic_type: str) -> List[Dict[str, Any]]:
        """Get models by semantic type."""
        return [
            model
            for model in self.models.values()
            if model["semantic_type"] == semantic_type
        ]


class MockCostManager:
    """Mock cost manager for testing."""

    def __init__(self):
        """Initialize the mock cost manager."""
        self.total_cost = 0.0
        self.request_count = 0
        self.cost_history = []

    def estimate_cost(
        self,
        provider: ProviderType,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """Estimate cost for a request."""
        # Simple cost estimation based on token count
        cost_per_1k = 0.002  # Default cost
        total_tokens = input_tokens + output_tokens
        cost = (total_tokens / 1000) * cost_per_1k

        return cost

    def record_cost(self, cost: float) -> None:
        """Record a cost."""
        self.total_cost += cost
        self.request_count += 1
        self.cost_history.append(
            {
                "cost": cost,
                "timestamp": time.time(),
                "request_count": self.request_count,
            }
        )

    def get_total_cost(self) -> float:
        """Get total cost."""
        return self.total_cost

    def get_average_cost(self) -> float:
        """Get average cost per request."""
        return self.total_cost / self.request_count if self.request_count > 0 else 0.0

    def get_cost_history(self) -> List[Dict[str, Any]]:
        """Get cost history."""
        return self.cost_history.copy()

    def reset(self) -> None:
        """Reset cost tracking."""
        self.total_cost = 0.0
        self.request_count = 0
        self.cost_history = []


class RealisticMockProvider(MockLLMProvider):
    """Mock provider with realistic failure patterns."""

    def __init__(
        self,
        failure_rate: float = 0.05,
        provider_type: ProviderType = ProviderType.OPENAI,
    ):
        super().__init__(provider_type)
        self.failure_rate = failure_rate
        self.consecutive_failures = 0
        self.base_failure_rate = failure_rate
        self.failure_scenarios = [
            "network_timeout",
            "rate_limit_exceeded",
            "authentication_failed",
            "quota_exceeded",
            "model_unavailable",
        ]

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate with realistic failure patterns."""
        # Simulate cascading failures
        if self.consecutive_failures > 3:
            self.failure_rate = min(self.failure_rate * 1.5, 0.5)  # Cap at 50%

        if random.random() < self.failure_rate:  # nosec B311
            self.consecutive_failures += 1
            scenario = random.choice(self.failure_scenarios)  # nosec B311

            if scenario == "network_timeout":
                raise TimeoutError("Request timed out after 30 seconds")
            elif scenario == "rate_limit_exceeded":
                raise Exception("Rate limit exceeded. Try again in 60 seconds")
            elif scenario == "authentication_failed":
                raise Exception("Invalid API key")
            elif scenario == "quota_exceeded":
                raise Exception("Monthly quota exceeded")
            elif scenario == "model_unavailable":
                raise Exception("Model temporarily unavailable")
            else:
                raise Exception("Simulated provider failure")

        self.consecutive_failures = 0
        # Gradually recover failure rate
        self.failure_rate = max(self.failure_rate * 0.9, self.base_failure_rate)

        return await super().generate(request)

    def get_failure_stats(self) -> Dict[str, Any]:
        """Get failure statistics."""
        return {
            "consecutive_failures": self.consecutive_failures,
            "current_failure_rate": self.failure_rate,
            "base_failure_rate": self.base_failure_rate,
        }

    def reset_failure_state(self) -> None:
        """Reset failure state for testing."""
        self.consecutive_failures = 0
        self.failure_rate = self.base_failure_rate
