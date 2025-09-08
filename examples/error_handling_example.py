# examples/error_handling_example.py

"""
Comprehensive Error Handling Examples for LLM Operations.

This module demonstrates robust error handling patterns for various LLM operations,
including validation errors, timeout handling, circuit breaker patterns, and
graceful degradation strategies.
"""

import asyncio
import logging
from typing import Optional

from gemini_sre_agent.llm.base import LLMRequest
from gemini_sre_agent.llm.common.enums import ModelType
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.mixing import (
    IntelligentCache,
    MixingStrategy,
    ModelConfig,
    ModelMixer,
    TaskType,
)
from gemini_sre_agent.llm.monitoring import CircuitBreakerHealthChecker
from gemini_sre_agent.llm.testing.mock_providers import RealisticMockProvider

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ErrorHandlingExample:
    """Comprehensive error handling examples for LLM operations."""

    def __init__(self):
        """Initialize the error handling example."""
        self.provider_factory = LLMProviderFactory()
        self.model_mixer: Optional[ModelMixer] = None
        self.health_checker: Optional[CircuitBreakerHealthChecker] = None
        self.cache = IntelligentCache(max_size=100, ttl_seconds=300)

    async def setup_mock_environment(self):
        """Set up mock environment for testing error scenarios."""
        # Create realistic mock providers with different failure rates
        providers = [
            RealisticMockProvider(failure_rate=0.1),  # 10% failure rate
            RealisticMockProvider(failure_rate=0.3),  # 30% failure rate
            RealisticMockProvider(failure_rate=0.05),  # 5% failure rate
        ]

        # Create a mock model registry for testing
        from gemini_sre_agent.llm.model_registry import ModelRegistry

        self.model_registry = ModelRegistry()

        # Add providers to factory
        for i, _provider in enumerate(providers):
            self.provider_factory.register_provider(
                f"mock_provider_{i}", RealisticMockProvider
            )

        # Initialize model mixer
        self.model_mixer = ModelMixer(
            provider_factory=self.provider_factory,
            model_registry=self.model_registry,
            max_concurrent_requests=3,
        )

        # Initialize circuit breaker health checker
        self.health_checker = CircuitBreakerHealthChecker(
            provider_factory=self.provider_factory,
            failure_threshold=3,
            recovery_timeout=30,
        )

    async def demonstrate_validation_errors(self):
        """Demonstrate comprehensive validation error handling."""
        logger.info("=== Validation Error Handling Demo ===")

        assert self.model_mixer is not None, "Model mixer not initialized"

        # Test cases for validation errors
        test_cases = [
            {
                "name": "Empty prompt",
                "prompt": "",
                "expected_error": "Prompt cannot be empty",
            },
            {
                "name": "Prompt too long",
                "prompt": "a" * 60000,  # Exceeds MAX_PROMPT_LENGTH
                "expected_error": "Prompt too long",
            },
            {
                "name": "XSS injection attempt",
                "prompt": "<script>alert('xss')</script>",
                "expected_error": "potentially harmful patterns",
            },
            {
                "name": "SQL injection attempt",
                "prompt": "SELECT * FROM users; DROP TABLE users;",
                "expected_error": "potentially harmful patterns",
            },
            {
                "name": "Null bytes and control characters",
                "prompt": "Hello\x00\x01\x02World",
                "expected_error": None,  # Should be sanitized, not rejected
            },
        ]

        for test_case in test_cases:
            try:
                logger.info(f"Testing: {test_case['name']}")

                # This should trigger validation in the model mixer
                result = await self.model_mixer.mix_models(
                    prompt=test_case["prompt"],
                    task_type=TaskType.ANALYSIS,
                    strategy=MixingStrategy.PARALLEL,
                    custom_configs=[
                        ModelConfig(
                            provider="mock_provider_0",
                            model="test-model",
                            model_type=ModelType.SMART,
                            max_tokens=100,
                        )
                    ],
                )

                if test_case["expected_error"]:
                    logger.warning(f"Expected error but got result: {result}")
                else:
                    logger.info(f"Successfully handled: {test_case['name']}")

            except ValueError as e:
                if test_case["expected_error"] and test_case["expected_error"] in str(
                    e
                ):
                    logger.info(f"✅ Correctly caught validation error: {e}")
                else:
                    logger.error(f"❌ Unexpected validation error: {e}")
            except Exception as e:
                logger.error(f"❌ Unexpected error type: {type(e).__name__}: {e}")

    async def demonstrate_timeout_handling(self):
        """Demonstrate timeout error handling."""
        logger.info("=== Timeout Error Handling Demo ===")

        assert self.model_mixer is not None, "Model mixer not initialized"

        try:
            # Create a request that might timeout
            request = LLMRequest(
                prompt="This is a test prompt that might timeout",
                max_tokens=100,
                temperature=0.7,
            )

            # Simulate timeout scenario
            logger.info("Simulating timeout scenario...")

            # Use a provider with high failure rate to increase timeout chances
            provider = self.provider_factory.get_provider("mock_provider_1")
            assert provider is not None, "Provider not found"

            try:
                result = await asyncio.wait_for(
                    provider.generate(request), timeout=1.0  # Very short timeout
                )
                logger.info(f"Request completed: {result.content[:50]}...")

            except asyncio.TimeoutError:
                logger.info("✅ Correctly handled timeout error")

                # Demonstrate graceful degradation
                logger.info("Attempting fallback to another provider...")
                fallback_provider = self.provider_factory.get_provider(
                    "mock_provider_2"
                )
                assert fallback_provider is not None, "Fallback provider not found"

                try:
                    fallback_result = await fallback_provider.generate(request)
                    logger.info(
                        f"✅ Fallback successful: {fallback_result.content[:50]}..."
                    )
                except Exception as e:
                    logger.error(f"❌ Fallback also failed: {e}")

        except Exception as e:
            logger.error(f"❌ Unexpected error in timeout demo: {e}")

    async def demonstrate_circuit_breaker_pattern(self):
        """Demonstrate circuit breaker pattern for health checks."""
        logger.info("=== Circuit Breaker Pattern Demo ===")

        assert self.health_checker is not None, "Health checker not initialized"

        # Check initial health
        logger.info("Checking initial health status...")
        health = await self.health_checker.check_provider_health("mock_provider_1")
        logger.info(f"Initial health: {health.status}")

        # Simulate multiple failures to trigger circuit breaker
        logger.info("Simulating multiple failures to trigger circuit breaker...")

        for i in range(5):
            try:
                health = await self.health_checker.check_provider_health(
                    "mock_provider_1"
                )
                logger.info(f"Health check {i+1}: {health.status}")

                # Check circuit breaker state
                cb_state = self.health_checker.get_circuit_breaker_state(
                    "mock_provider_1"
                )
                logger.info(f"Circuit breaker state: {cb_state['state']}")

                if cb_state["state"] == "open":
                    logger.info("✅ Circuit breaker opened as expected")
                    break

            except Exception as e:
                logger.error(f"Health check failed: {e}")

        # Wait for recovery timeout
        logger.info("Waiting for recovery timeout...")
        await asyncio.sleep(2)  # Short wait for demo

        # Check if circuit breaker moved to half-open
        cb_state = self.health_checker.get_circuit_breaker_state("mock_provider_1")
        logger.info(f"Circuit breaker state after timeout: {cb_state['state']}")

        # Manually reset circuit breaker
        logger.info("Manually resetting circuit breaker...")
        self.health_checker.reset_circuit_breaker("mock_provider_1")

        cb_state = self.health_checker.get_circuit_breaker_state("mock_provider_1")
        logger.info(f"Circuit breaker state after reset: {cb_state['state']}")

    async def demonstrate_graceful_degradation(self):
        """Demonstrate graceful degradation strategies."""
        logger.info("=== Graceful Degradation Demo ===")

        assert self.model_mixer is not None, "Model mixer not initialized"

        # Test with multiple providers
        model_configs = [
            ModelConfig(
                provider="mock_provider_0",
                model="test-model",
                model_type=ModelType.SMART,
                max_tokens=100,
            ),
            ModelConfig(
                provider="mock_provider_1",  # High failure rate
                model="test-model",
                model_type=ModelType.SMART,
                max_tokens=100,
            ),
            ModelConfig(
                provider="mock_provider_2",  # Low failure rate
                model="test-model",
                model_type=ModelType.SMART,
                max_tokens=100,
            ),
        ]

        try:
            result = await self.model_mixer.mix_models(
                prompt="Analyze this complex data and provide insights",
                task_type=TaskType.ANALYSIS,
                strategy=MixingStrategy.PARALLEL,
                custom_configs=model_configs,
            )

            logger.info("✅ Model mixing completed successfully")
            logger.info(
                f"Primary result: {result.primary_result.content[:100] if result.primary_result else 'None'}..."
            )
            logger.info(f"Confidence: {result.confidence_score}")
            logger.info(f"Total cost: ${result.total_cost:.4f}")

            # Check which providers succeeded
            successful_providers = []
            failed_providers = []

            for i, response in enumerate(result.secondary_results):
                if response is not None:
                    successful_providers.append(model_configs[i].provider)
                else:
                    failed_providers.append(model_configs[i].provider)

            logger.info(f"Successful providers: {successful_providers}")
            logger.info(f"Failed providers: {failed_providers}")

        except Exception as e:
            logger.error(f"❌ Model mixing failed: {e}")

            # Demonstrate fallback strategy
            logger.info("Attempting fallback with single reliable provider...")

            try:
                fallback_result = await self.model_mixer.mix_models(
                    prompt="Analyze this complex data and provide insights",
                    task_type=TaskType.ANALYSIS,
                    strategy=MixingStrategy.PARALLEL,
                    custom_configs=[model_configs[2]],  # Use the most reliable provider
                )

                logger.info(
                    f"✅ Fallback successful: {fallback_result.primary_result.content[:100]}..."
                )

            except Exception as fallback_error:
                logger.error(f"❌ Fallback also failed: {fallback_error}")

    async def demonstrate_caching_with_errors(self):
        """Demonstrate intelligent caching with error scenarios."""
        logger.info("=== Intelligent Caching with Errors Demo ===")

        assert self.model_mixer is not None, "Model mixer not initialized"

        # Test caching with successful requests
        logger.info("Testing caching with successful requests...")

        async def compute_expensive_operation(prompt: str) -> str:
            """Simulate an expensive operation."""
            await asyncio.sleep(0.1)  # Simulate processing time
            return f"Processed: {prompt[:50]}..."

        # First request (cache miss)
        start_time = asyncio.get_event_loop().time()
        result1 = await self.cache.get_or_compute(
            key="test_key_1",
            compute_func=compute_expensive_operation,
            prompt="This is a test prompt for caching",
        )
        time1 = asyncio.get_event_loop().time() - start_time
        logger.info(f"First request took {time1:.3f}s: {result1}")

        # Second request (cache hit)
        start_time = asyncio.get_event_loop().time()
        result2 = await self.cache.get_or_compute(
            key="test_key_1",
            compute_func=compute_expensive_operation,
            prompt="This is a test prompt for caching",
        )
        time2 = asyncio.get_event_loop().time() - start_time
        logger.info(f"Second request took {time2:.3f}s: {result2}")

        # Check cache stats
        stats = self.cache.get_stats()
        logger.info(f"Cache stats: {stats}")

        # Test cache invalidation
        logger.info("Testing cache invalidation...")
        invalidated = self.cache.invalidate_pattern("test_key_1")
        logger.info(f"Invalidated {invalidated} items")

        # Test memory usage
        memory_usage = self.cache.get_memory_usage()
        logger.info(f"Cache memory usage: {memory_usage}")

    async def demonstrate_comprehensive_error_handling(self):
        """Demonstrate comprehensive error handling in a real scenario."""
        logger.info("=== Comprehensive Error Handling Demo ===")

        assert self.model_mixer is not None, "Model mixer not initialized"
        assert self.health_checker is not None, "Health checker not initialized"

        # Complex scenario with multiple potential failure points
        try:
            # Step 1: Validate input
            prompt = "Analyze the following data and provide actionable insights"

            # Step 2: Check provider health
            healthy_providers = self.health_checker.get_healthy_providers()
            logger.info(f"Healthy providers: {healthy_providers}")

            if not healthy_providers:
                logger.warning("No healthy providers available, using degraded mode")
                # Use all providers but with lower expectations
                model_configs = [
                    ModelConfig(
                        provider="mock_provider_0",
                        model="test-model",
                        model_type=ModelType.SMART,
                        max_tokens=50,  # Reduced tokens for degraded mode
                    )
                ]
            else:
                # Use healthy providers
                model_configs = [
                    ModelConfig(
                        provider=provider,
                        model="test-model",
                        model_type=ModelType.SMART,
                        max_tokens=100,
                    )
                    for provider in healthy_providers[:2]  # Limit to 2 providers
                ]

            # Step 3: Execute with error handling
            result = await self.model_mixer.mix_models(
                prompt=prompt,
                task_type=TaskType.ANALYSIS,
                strategy=MixingStrategy.PARALLEL,
                custom_configs=model_configs,
            )

            # Step 4: Validate result
            if result.primary_result:
                logger.info("✅ Analysis completed successfully")
                logger.info(f"Result: {result.primary_result.content[:200]}...")
                logger.info(f"Confidence: {result.confidence_score}")
                logger.info(f"Cost: ${result.total_cost:.4f}")
            else:
                logger.warning(
                    "⚠️ No primary result available, checking individual results"
                )

                # Check individual results
                for i, response in enumerate(result.secondary_results):
                    if response:
                        logger.info(f"Provider {model_configs[i].provider} succeeded")
                    else:
                        logger.warning(f"Provider {model_configs[i].provider} failed")

        except ValueError as e:
            logger.error(f"❌ Validation error: {e}")
        except TimeoutError as e:
            logger.error(f"❌ Timeout error: {e}")
        except Exception as e:
            logger.error(f"❌ Unexpected error: {type(e).__name__}: {e}")

            # Log additional context
            logger.error(f"Error details: {str(e)}")

            # Attempt recovery
            logger.info("Attempting error recovery...")
            try:
                # Simple fallback
                simple_result = await self.model_mixer.mix_models(
                    prompt="Simple analysis request",
                    task_type=TaskType.ANALYSIS,
                    strategy=MixingStrategy.SEQUENTIAL,  # More reliable
                    custom_configs=[
                        ModelConfig(
                            provider="mock_provider_2",  # Most reliable
                            model="test-model",
                            model_type=ModelType.SMART,
                            max_tokens=50,
                        )
                    ],
                )
                logger.info(
                    f"✅ Recovery successful: {simple_result.primary_result.content[:100]}..."
                )

            except Exception as recovery_error:
                logger.error(f"❌ Recovery failed: {recovery_error}")

    async def run_all_examples(self):
        """Run all error handling examples."""
        logger.info("🚀 Starting Comprehensive Error Handling Examples")

        try:
            # Setup
            await self.setup_mock_environment()

            # Run examples
            await self.demonstrate_validation_errors()
            await self.demonstrate_timeout_handling()
            await self.demonstrate_circuit_breaker_pattern()
            await self.demonstrate_graceful_degradation()
            await self.demonstrate_caching_with_errors()
            await self.demonstrate_comprehensive_error_handling()

            logger.info("✅ All error handling examples completed successfully")

        except Exception as e:
            logger.error(f"❌ Error in example execution: {e}")
            raise


async def main():
    """Main function to run error handling examples."""
    example = ErrorHandlingExample()
    await example.run_all_examples()


if __name__ == "__main__":
    asyncio.run(main())
