# tests/test_framework.py

"""
Unit tests for the TestingFramework class.

This module contains comprehensive unit tests for the core testing framework
functionality including test execution, reporting, and test suite management.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.llm.testing.framework import (
    TestingFramework,
    TestReport,
    TestResult,
)
from gemini_sre_agent.llm.testing.mock_providers import (
    MockModelRegistry,
    MockProviderFactory,
)


class TestTestingFramework:
    """Test cases for the TestingFramework class."""

    @pytest.fixture
    def mock_provider_factory(self):
        """Create a mock provider factory."""
        factory = MockProviderFactory()
        return factory

    @pytest.fixture
    def mock_model_registry(self):
        """Create a mock model registry."""
        registry = MockModelRegistry()
        return registry

    @pytest.fixture
    def testing_framework(self, mock_provider_factory, mock_model_registry):
        """Create a testing framework instance."""
        return TestingFramework(
            provider_factory=mock_provider_factory,
            model_registry=mock_model_registry,
            enable_mock_testing=True,
        )

    def test_initialization(self, testing_framework):
        """Test framework initialization."""
        assert testing_framework.provider_factory is not None
        assert testing_framework.model_registry is not None
        assert testing_framework.mock_factory is not None
        assert testing_framework.test_data_generator is not None
        assert testing_framework.performance_benchmark is not None
        assert testing_framework.integration_tester is not None
        assert len(testing_framework.test_suites) > 0

    def test_default_test_suites(self, testing_framework):
        """Test that default test suites are created."""
        expected_suites = [
            "provider_validation",
            "performance_benchmarking",
            "model_mixing",
            "cost_analysis",
            "security_validation",
        ]

        for suite_name in expected_suites:
            assert suite_name in testing_framework.test_suites
            suite = testing_framework.test_suites[suite_name]
            assert suite.name is not None
            assert suite.description is not None
            assert len(suite.tests) > 0

    @pytest.mark.asyncio
    async def test_run_single_test(self, testing_framework):
        """Test running a single test."""
        # Mock the test method
        with patch.object(
            testing_framework, "test_provider_connectivity", new_callable=AsyncMock
        ) as mock_test:
            mock_test.return_value = True

            result = await testing_framework._run_single_test(
                "test_provider_connectivity", 30
            )

            assert result.test_name == "test_provider_connectivity"
            assert result.result == TestResult.PASSED
            assert result.duration_ms > 0
            mock_test.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_single_test_failure(self, testing_framework):
        """Test running a single test that fails."""
        # Mock the test method to return False
        with patch.object(
            testing_framework, "test_provider_connectivity", new_callable=AsyncMock
        ) as mock_test:
            mock_test.return_value = False

            result = await testing_framework._run_single_test(
                "test_provider_connectivity", 30
            )

            assert result.test_name == "test_provider_connectivity"
            assert result.result == TestResult.FAILED
            assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_run_single_test_exception(self, testing_framework):
        """Test running a single test that raises an exception."""
        # Mock the test method to raise an exception
        with patch.object(
            testing_framework, "test_provider_connectivity", new_callable=AsyncMock
        ) as mock_test:
            mock_test.side_effect = Exception("Test failed")

            result = await testing_framework._run_single_test(
                "test_provider_connectivity", 30
            )

            assert result.test_name == "test_provider_connectivity"
            assert result.result == TestResult.ERROR
            assert result.error_message == "Test failed"

    @pytest.mark.asyncio
    async def test_run_single_test_timeout(self, testing_framework):
        """Test running a single test that times out."""

        # Mock the test method to take too long
        async def slow_test():
            await asyncio.sleep(2)
            return True

        with patch.object(
            testing_framework, "test_provider_connectivity", side_effect=slow_test
        ):
            result = await testing_framework._run_single_test(
                "test_provider_connectivity", 1
            )

            assert result.test_name == "test_provider_connectivity"
            assert result.result == TestResult.ERROR
            assert "timed out" in result.error_message

    @pytest.mark.asyncio
    async def test_run_single_test_not_found(self, testing_framework):
        """Test running a test method that doesn't exist."""
        result = await testing_framework._run_single_test("nonexistent_test", 30)

        assert result.test_name == "nonexistent_test"
        assert result.result == TestResult.ERROR
        assert "not found" in result.error_message

    @pytest.mark.asyncio
    async def test_run_test_suite(self, testing_framework):
        """Test running a test suite."""
        # Mock the test methods
        with patch.object(
            testing_framework, "test_provider_connectivity", new_callable=AsyncMock
        ) as mock_connectivity, patch.object(
            testing_framework, "test_provider_authentication", new_callable=AsyncMock
        ) as mock_auth:

            mock_connectivity.return_value = True
            mock_auth.return_value = True

            results = await testing_framework.run_test_suite("provider_validation")

            assert len(results) > 0
            for result in results:
                assert result.result in [
                    TestResult.PASSED,
                    TestResult.FAILED,
                    TestResult.ERROR,
                ]

    @pytest.mark.asyncio
    async def test_run_test_suite_parallel(self, testing_framework):
        """Test running a test suite in parallel."""
        # Mock the test methods
        with patch.object(
            testing_framework, "test_latency_benchmarks", new_callable=AsyncMock
        ) as mock_latency, patch.object(
            testing_framework, "test_throughput_benchmarks", new_callable=AsyncMock
        ) as mock_throughput:

            mock_latency.return_value = {"test": 100.0}
            mock_throughput.return_value = {"test": 10.0}

            results = await testing_framework.run_test_suite("performance_benchmarking")

            assert len(results) > 0
            # Verify both tests were called
            mock_latency.assert_called_once()
            mock_throughput.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_test_suite_not_found(self, testing_framework):
        """Test running a test suite that doesn't exist."""
        with pytest.raises(ValueError, match="Test suite 'nonexistent' not found"):
            await testing_framework.run_test_suite("nonexistent")

    @pytest.mark.asyncio
    async def test_run_all_test_suites(self, testing_framework):
        """Test running all test suites."""
        # Mock all test methods to return True
        test_methods = [
            "test_provider_connectivity",
            "test_provider_authentication",
            "test_provider_response_format",
            "test_provider_error_handling",
            "test_latency_benchmarks",
            "test_throughput_benchmarks",
            "test_memory_usage",
            "test_concurrent_requests",
        ]

        for method_name in test_methods:
            if hasattr(testing_framework, method_name):
                with patch.object(
                    testing_framework, method_name, new_callable=AsyncMock
                ) as mock_method:
                    mock_method.return_value = True

        all_results = await testing_framework.run_all_test_suites()

        assert isinstance(all_results, dict)
        assert len(all_results) > 0

        for results in all_results.values():
            assert isinstance(results, list)
            assert len(results) > 0

    def test_generate_test_report(self, testing_framework):
        """Test generating a test report."""
        # Add some mock test results
        testing_framework.test_results = [
            TestReport(
                test_name="test1",
                result=TestResult.PASSED,
                duration_ms=100.0,
            ),
            TestReport(
                test_name="test2",
                result=TestResult.FAILED,
                duration_ms=200.0,
            ),
            TestReport(
                test_name="test3",
                result=TestResult.ERROR,
                duration_ms=50.0,
                error_message="Test error",
            ),
        ]

        report = testing_framework.generate_test_report()

        assert "summary" in report
        assert "test_results" in report
        assert "test_suites" in report

        summary = report["summary"]
        assert summary["total_tests"] == 3
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["errors"] == 1
        assert summary["success_rate"] == 100 / 3  # 1/3 * 100
        assert summary["total_duration_ms"] == 350.0

    @pytest.mark.asyncio
    async def test_provider_connectivity_test(self, testing_framework):
        """Test the provider connectivity test method."""
        # Mock the provider factory
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = Mock(content="test response")

        with patch.object(
            testing_framework.provider_factory,
            "list_providers",
            return_value=["test_provider"],
        ), patch.object(
            testing_framework.provider_factory,
            "get_provider",
            return_value=mock_provider,
        ):

            result = await testing_framework.test_provider_connectivity()
            assert result is True

    @pytest.mark.asyncio
    async def test_provider_connectivity_test_failure(self, testing_framework):
        """Test the provider connectivity test method with failure."""
        # Mock the provider factory to return no providers
        with patch.object(
            testing_framework.provider_factory, "list_providers", return_value=[]
        ):
            result = await testing_framework.test_provider_connectivity()
            assert result is False

    @pytest.mark.asyncio
    async def test_provider_authentication_test(self, testing_framework):
        """Test the provider authentication test method."""
        with patch.object(
            testing_framework.provider_factory,
            "list_providers",
            return_value=["test_provider"],
        ):
            result = await testing_framework.test_provider_authentication()
            assert result is True

    @pytest.mark.asyncio
    async def test_provider_response_format_test(self, testing_framework):
        """Test the provider response format test method."""
        # Mock response
        mock_response = Mock()
        mock_response.content = "test content"
        mock_response.usage = {"input_tokens": 10, "output_tokens": 5}

        mock_provider = AsyncMock()
        mock_provider.generate.return_value = mock_response

        with patch.object(
            testing_framework.provider_factory,
            "list_providers",
            return_value=["test_provider"],
        ), patch.object(
            testing_framework.provider_factory,
            "get_provider",
            return_value=mock_provider,
        ):

            result = await testing_framework.test_provider_response_format()
            assert result is True

    @pytest.mark.asyncio
    async def test_provider_error_handling_test(self, testing_framework):
        """Test the provider error handling test method."""
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = Exception("Test error")

        with patch.object(
            testing_framework.provider_factory,
            "list_providers",
            return_value=["test_provider"],
        ), patch.object(
            testing_framework.provider_factory,
            "get_provider",
            return_value=mock_provider,
        ):

            result = await testing_framework.test_provider_error_handling()
            assert result is True  # Should handle errors gracefully

    @pytest.mark.asyncio
    async def test_input_validation_test(self, testing_framework):
        """Test the input validation test method."""
        result = await testing_framework.test_input_validation()
        assert result is True

    @pytest.mark.asyncio
    async def test_output_sanitization_test(self, testing_framework):
        """Test the output sanitization test method."""
        result = await testing_framework.test_output_sanitization()
        assert result is True

    @pytest.mark.asyncio
    async def test_rate_limiting_test(self, testing_framework):
        """Test the rate limiting test method."""
        result = await testing_framework.test_rate_limiting()
        assert result is True

    @pytest.mark.asyncio
    async def test_authentication_test(self, testing_framework):
        """Test the authentication test method."""
        result = await testing_framework.test_authentication()
        assert result is True


class TestTestReport:
    """Test cases for the TestReport dataclass."""

    def test_test_report_creation(self):
        """Test creating a test report."""
        report = TestReport(
            test_name="test_example",
            result=TestResult.PASSED,
            duration_ms=150.0,
            details={"key": "value"},
            error_message=None,
            metrics={"latency": 100.0},
        )

        assert report.test_name == "test_example"
        assert report.result == TestResult.PASSED
        assert report.duration_ms == 150.0
        assert report.details == {"key": "value"}
        assert report.error_message is None
        assert report.metrics == {"latency": 100.0}

    def test_test_report_defaults(self):
        """Test test report with default values."""
        report = TestReport(
            test_name="test_default",
            result=TestResult.FAILED,
            duration_ms=200.0,
        )

        assert report.details == {}
        assert report.error_message is None
        assert report.metrics == {}


class TestTestResult:
    """Test cases for the TestResult enum."""

    def test_test_result_values(self):
        """Test TestResult enum values."""
        assert TestResult.PASSED.value == "passed"
        assert TestResult.FAILED.value == "failed"
        assert TestResult.SKIPPED.value == "skipped"
        assert TestResult.ERROR.value == "error"
