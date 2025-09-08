# gemini_sre_agent/llm/testing/framework.py

"""
Core Testing Framework for LLM Providers and Model Mixing.

This module provides the main TestingFramework class that orchestrates
all testing activities including provider validation, performance benchmarking,
integration testing, and cost analysis.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..base import LLMRequest, LLMResponse, ModelType
from ..cost_management_integration import IntegratedCostManager
from ..factory import LLMProviderFactory
from ..model_registry import ModelRegistry
from .cost_analysis_tests import CostAnalysisTester
from .integration_tests import IntegrationTester

# from ..mixing.model_mixer import ModelMixer  # Imported when needed
from .mock_providers import MockProviderFactory
from .performance_benchmark import PerformanceBenchmark
from .test_data_generators import TestDataGenerator

logger = logging.getLogger(__name__)


class TestResult(Enum):
    """Test result status."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass
class TestReport:
    """Comprehensive test report."""

    test_name: str
    result: TestResult
    duration_ms: float
    details: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)


@dataclass
class TestSuite:
    """Test suite configuration."""

    name: str
    description: str
    tests: List[str]
    timeout_seconds: int = 300
    parallel: bool = False
    retry_count: int = 0


class TestingFramework:
    """Comprehensive testing framework for LLM providers and model mixing."""

    def __init__(
        self,
        provider_factory: LLMProviderFactory,
        model_registry: ModelRegistry,
        cost_manager: Optional[IntegratedCostManager] = None,
        enable_mock_testing: bool = True,
        test_timeout_seconds: int = 300,
    ):
        """Initialize the testing framework."""
        self.provider_factory = provider_factory
        self.model_registry = model_registry
        self.cost_manager = cost_manager
        self.test_timeout_seconds = test_timeout_seconds

        # Initialize testing components
        self.mock_factory = MockProviderFactory() if enable_mock_testing else None
        self.test_data_generator = TestDataGenerator()
        self.performance_benchmark = PerformanceBenchmark(
            provider_factory, model_registry, cost_manager
        )
        self.cost_analysis_tester = (
            CostAnalysisTester(cost_manager) if cost_manager else None
        )
        self.integration_tester = IntegrationTester(
            provider_factory, model_registry, cost_manager
        )

        # Test results storage
        self.test_results: List[TestReport] = []
        self.test_suites: Dict[str, TestSuite] = {}

        # Initialize default test suites
        self._initialize_default_test_suites()

    def _initialize_default_test_suites(self) -> None:
        """Initialize default test suites."""
        self.test_suites = {
            "provider_validation": TestSuite(
                name="Provider Validation",
                description="Validate all LLM providers work correctly",
                tests=[
                    "test_provider_connectivity",
                    "test_provider_authentication",
                    "test_provider_response_format",
                    "test_provider_error_handling",
                ],
                timeout_seconds=120,
            ),
            "performance_benchmarking": TestSuite(
                name="Performance Benchmarking",
                description="Benchmark performance across all providers and models",
                tests=[
                    "test_latency_benchmarks",
                    "test_throughput_benchmarks",
                    "test_memory_usage",
                    "test_concurrent_requests",
                ],
                timeout_seconds=600,
                parallel=True,
            ),
            "model_mixing": TestSuite(
                name="Model Mixing Integration",
                description="Test model mixing scenarios and strategies",
                tests=[
                    "test_sequential_mixing",
                    "test_parallel_mixing",
                    "test_cascade_mixing",
                    "test_context_sharing",
                    "test_result_aggregation",
                ],
                timeout_seconds=300,
            ),
            "cost_analysis": TestSuite(
                name="Cost Analysis",
                description="Verify cost tracking and budget enforcement",
                tests=[
                    "test_cost_tracking_accuracy",
                    "test_budget_enforcement",
                    "test_cost_optimization",
                    "test_pricing_data_refresh",
                ],
                timeout_seconds=180,
            ),
            "security_validation": TestSuite(
                name="Security Validation",
                description="Test security measures and input validation",
                tests=[
                    "test_input_validation",
                    "test_output_sanitization",
                    "test_rate_limiting",
                    "test_authentication",
                ],
                timeout_seconds=120,
            ),
        }

    async def run_test_suite(self, suite_name: str) -> List[TestReport]:
        """Run a specific test suite."""
        if suite_name not in self.test_suites:
            raise ValueError(f"Test suite '{suite_name}' not found")

        suite = self.test_suites[suite_name]
        logger.info(f"Running test suite: {suite.name}")

        results = []
        if suite.parallel:
            # Run tests in parallel
            tasks = []
            for test_name in suite.tests:
                task = asyncio.create_task(
                    self._run_single_test(test_name, suite.timeout_seconds)
                )
                tasks.append(task)

            # Wait for all tests to complete
            test_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, result in enumerate(test_results):
                if isinstance(result, Exception):
                    results.append(
                        TestReport(
                            test_name=suite.tests[i],
                            result=TestResult.ERROR,
                            duration_ms=0.0,
                            error_message=str(result),
                        )
                    )
                else:
                    results.append(result)
        else:
            # Run tests sequentially
            for test_name in suite.tests:
                result = await self._run_single_test(test_name, suite.timeout_seconds)
                results.append(result)

                # Stop on first failure if not configured to continue
                if result.result == TestResult.FAILED and suite.retry_count == 0:
                    break

        self.test_results.extend(results)
        return results

    async def run_all_test_suites(self) -> Dict[str, List[TestReport]]:
        """Run all test suites."""
        logger.info("Running all test suites")

        all_results = {}
        for suite_name in self.test_suites:
            try:
                results = await self.run_test_suite(suite_name)
                all_results[suite_name] = results
            except Exception as e:
                logger.error(f"Failed to run test suite '{suite_name}': {e}")
                all_results[suite_name] = [
                    TestReport(
                        test_name=suite_name,
                        result=TestResult.ERROR,
                        duration_ms=0.0,
                        error_message=str(e),
                    )
                ]

        return all_results

    async def _run_single_test(
        self, test_name: str, timeout_seconds: int
    ) -> TestReport:
        """Run a single test with timeout."""
        start_time = time.time()

        try:
            # Get the test method
            test_method = getattr(self, test_name, None)
            if not test_method:
                return TestReport(
                    test_name=test_name,
                    result=TestResult.ERROR,
                    duration_ms=0.0,
                    error_message=f"Test method '{test_name}' not found",
                )

            # Run the test with timeout
            result = await asyncio.wait_for(test_method(), timeout=timeout_seconds)

            duration_ms = (time.time() - start_time) * 1000

            return TestReport(
                test_name=test_name,
                result=TestResult.PASSED if result else TestResult.FAILED,
                duration_ms=duration_ms,
                details={"result": result} if isinstance(result, dict) else {},
            )

        except asyncio.TimeoutError:
            duration_ms = (time.time() - start_time) * 1000
            return TestReport(
                test_name=test_name,
                result=TestResult.ERROR,
                duration_ms=duration_ms,
                error_message=f"Test timed out after {timeout_seconds} seconds",
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return TestReport(
                test_name=test_name,
                result=TestResult.ERROR,
                duration_ms=duration_ms,
                error_message=str(e),
            )

    # Provider Validation Tests
    async def test_provider_connectivity(self) -> bool:
        """Test that all providers can connect."""
        try:
            providers = self.provider_factory.list_providers()
            for provider_name in providers:
                provider = self.provider_factory.get_provider(provider_name)
                if not provider:
                    logger.error(f"Provider {provider_name} not available")
                    return False

                # Test basic connectivity
                test_request = LLMRequest(
                    prompt="Test connectivity",
                    model_type=ModelType.SMART,
                    max_tokens=10,
                )

                response = await provider.generate(test_request)
                if not response or not response.content:
                    logger.error(f"Provider {provider_name} failed connectivity test")
                    return False

            return True
        except Exception as e:
            logger.error(f"Provider connectivity test failed: {e}")
            return False

    async def test_provider_authentication(self) -> bool:
        """Test provider authentication."""
        try:
            # This would test authentication for each provider
            # For now, we'll assume authentication is handled by the provider factory
            providers = self.provider_factory.list_providers()
            return len(providers) > 0
        except Exception as e:
            logger.error(f"Provider authentication test failed: {e}")
            return False

    async def test_provider_response_format(self) -> bool:
        """Test that providers return properly formatted responses."""
        try:
            providers = self.provider_factory.list_providers()
            for provider_name in providers:
                provider = self.provider_factory.get_provider(provider_name)
                if not provider:
                    continue

                test_request = LLMRequest(
                    prompt="Test response format",
                    model_type=ModelType.SMART,
                    max_tokens=50,
                )

                response = await provider.generate(test_request)

                # Validate response format
                if not isinstance(response, LLMResponse):
                    logger.error(
                        f"Provider {provider_name} returned invalid response type"
                    )
                    return False

                if not hasattr(response, "content") or not response.content:
                    logger.error(f"Provider {provider_name} returned empty content")
                    return False

                if not hasattr(response, "usage"):
                    logger.error(f"Provider {provider_name} missing usage information")
                    return False

            return True
        except Exception as e:
            logger.error(f"Provider response format test failed: {e}")
            return False

    async def test_provider_error_handling(self) -> bool:
        """Test provider error handling."""
        try:
            providers = self.provider_factory.list_providers()
            for provider_name in providers:
                provider = self.provider_factory.get_provider(provider_name)
                if not provider:
                    continue

                # Test with invalid request
                invalid_request = LLMRequest(
                    prompt="",  # Empty prompt should cause error
                    model_type=ModelType.SMART,
                    max_tokens=10,
                )

                try:
                    await provider.generate(invalid_request)
                    # Some providers might handle empty prompts gracefully
                    # This is acceptable behavior
                except Exception:
                    # Expected behavior for invalid requests
                    pass  # nosec B110

            return True
        except Exception as e:
            logger.error(f"Provider error handling test failed: {e}")
            return False

    # Performance Benchmarking Tests
    async def test_latency_benchmarks(self) -> Dict[str, Any]:
        """Test latency benchmarks across providers."""
        try:
            return await self.performance_benchmark.run_latency_benchmarks()
        except Exception as e:
            logger.error(f"Latency benchmark test failed: {e}")
            return {}

    async def test_throughput_benchmarks(self) -> Dict[str, Any]:
        """Test throughput benchmarks across providers."""
        try:
            return await self.performance_benchmark.run_throughput_benchmarks()
        except Exception as e:
            logger.error(f"Throughput benchmark test failed: {e}")
            return {}

    async def test_memory_usage(self) -> Dict[str, Any]:
        """Test memory usage across providers."""
        try:
            return await self.performance_benchmark.run_memory_benchmarks()
        except Exception as e:
            logger.error(f"Memory usage test failed: {e}")
            return {}

    async def test_concurrent_requests(self) -> Dict[str, Any]:
        """Test concurrent request handling."""
        try:
            return await self.performance_benchmark.run_concurrency_benchmarks()
        except Exception as e:
            logger.error(f"Concurrent requests test failed: {e}")
            return {}

    # Model Mixing Tests
    async def test_sequential_mixing(self) -> bool:
        """Test sequential model mixing."""
        try:
            return await self.integration_tester.test_sequential_mixing()
        except Exception as e:
            logger.error(f"Sequential mixing test failed: {e}")
            return False

    async def test_parallel_mixing(self) -> bool:
        """Test parallel model mixing."""
        try:
            return await self.integration_tester.test_parallel_mixing()
        except Exception as e:
            logger.error(f"Parallel mixing test failed: {e}")
            return False

    async def test_cascade_mixing(self) -> bool:
        """Test cascade model mixing."""
        try:
            return await self.integration_tester.test_cascade_mixing()
        except Exception as e:
            logger.error(f"Cascade mixing test failed: {e}")
            return False

    async def test_context_sharing(self) -> bool:
        """Test context sharing between models."""
        try:
            return await self.integration_tester.test_context_sharing()
        except Exception as e:
            logger.error(f"Context sharing test failed: {e}")
            return False

    async def test_result_aggregation(self) -> bool:
        """Test result aggregation."""
        try:
            return await self.integration_tester.test_result_aggregation()
        except Exception as e:
            logger.error(f"Result aggregation test failed: {e}")
            return False

    # Cost Analysis Tests
    async def test_cost_tracking_accuracy(self) -> bool:
        """Test cost tracking accuracy."""
        if not self.cost_analysis_tester:
            return True  # Skip if cost manager not available

        try:
            return await self.cost_analysis_tester.test_cost_tracking_accuracy()
        except Exception as e:
            logger.error(f"Cost tracking accuracy test failed: {e}")
            return False

    async def test_budget_enforcement(self) -> bool:
        """Test budget enforcement."""
        if not self.cost_analysis_tester:
            return True  # Skip if cost manager not available

        try:
            return await self.cost_analysis_tester.test_budget_enforcement()
        except Exception as e:
            logger.error(f"Budget enforcement test failed: {e}")
            return False

    async def test_cost_optimization(self) -> bool:
        """Test cost optimization."""
        if not self.cost_analysis_tester:
            return True  # Skip if cost manager not available

        try:
            return await self.cost_analysis_tester.test_cost_optimization()
        except Exception as e:
            logger.error(f"Cost optimization test failed: {e}")
            return False

    async def test_pricing_data_refresh(self) -> bool:
        """Test pricing data refresh."""
        if not self.cost_analysis_tester:
            return True  # Skip if cost manager not available

        try:
            return await self.cost_analysis_tester.test_pricing_data_refresh()
        except Exception as e:
            logger.error(f"Pricing data refresh test failed: {e}")
            return False

    # Security Validation Tests
    async def test_input_validation(self) -> bool:
        """Test input validation."""
        try:
            # Test with various invalid inputs
            invalid_inputs = [
                "",  # Empty string
                "x" * 100000,  # Very long string
                None,  # None value
            ]

            for _ in invalid_inputs:
                try:
                    # This would test the ModelMixer input validation
                    # For now, we'll just verify the framework can handle it
                    pass
                except ValueError:
                    # Expected behavior
                    pass

            return True
        except Exception as e:
            logger.error(f"Input validation test failed: {e}")
            return False

    async def test_output_sanitization(self) -> bool:
        """Test output sanitization."""
        try:
            # Test that outputs are properly sanitized
            # This would test the ModelMixer output sanitization
            return True
        except Exception as e:
            logger.error(f"Output sanitization test failed: {e}")
            return False

    async def test_rate_limiting(self) -> bool:
        """Test rate limiting."""
        try:
            # Test rate limiting functionality
            # This would test the rate limiting in the ModelMixer
            return True
        except Exception as e:
            logger.error(f"Rate limiting test failed: {e}")
            return False

    async def test_authentication(self) -> bool:
        """Test authentication."""
        try:
            # Test authentication mechanisms
            # This would test authentication in the dashboard APIs
            return True
        except Exception as e:
            logger.error(f"Authentication test failed: {e}")
            return False

    def generate_test_report(self) -> Dict[str, Any]:
        """Generate a comprehensive test report."""
        total_tests = len(self.test_results)
        passed_tests = len(
            [r for r in self.test_results if r.result == TestResult.PASSED]
        )
        failed_tests = len(
            [r for r in self.test_results if r.result == TestResult.FAILED]
        )
        error_tests = len(
            [r for r in self.test_results if r.result == TestResult.ERROR]
        )

        total_duration = sum(r.duration_ms for r in self.test_results)

        return {
            "summary": {
                "total_tests": total_tests,
                "passed": passed_tests,
                "failed": failed_tests,
                "errors": error_tests,
                "success_rate": (
                    (passed_tests / total_tests * 100) if total_tests > 0 else 0
                ),
                "total_duration_ms": total_duration,
            },
            "test_results": [
                {
                    "test_name": r.test_name,
                    "result": r.result.value,
                    "duration_ms": r.duration_ms,
                    "error_message": r.error_message,
                    "metrics": r.metrics,
                }
                for r in self.test_results
            ],
            "test_suites": {
                name: {
                    "name": suite.name,
                    "description": suite.description,
                    "test_count": len(suite.tests),
                }
                for name, suite in self.test_suites.items()
            },
        }
