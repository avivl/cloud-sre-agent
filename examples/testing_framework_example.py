# examples/testing_framework_example.py

"""
Example usage of the Comprehensive Testing Framework.

This example demonstrates how to use the testing framework to run various
types of tests including provider validation, performance benchmarking,
integration testing, and cost analysis.
"""

import asyncio
import logging

from gemini_sre_agent.llm.cost_management_integration import IntegratedCostManager
from gemini_sre_agent.llm.testing.framework import TestingFramework
from gemini_sre_agent.llm.testing.mock_providers import (
    MockModelRegistry,
    MockProviderFactory,
)

# from typing import Dict, Any  # Imported when needed


# from gemini_sre_agent.llm.factory import LLMProviderFactory  # Imported when needed
# from gemini_sre_agent.llm.model_registry import ModelRegistry  # Imported when needed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def basic_testing_example():
    """Basic example of using the testing framework."""
    logger.info("=== Basic Testing Framework Example ===")

    # Initialize mock components for testing
    mock_provider_factory = MockProviderFactory()
    mock_model_registry = MockModelRegistry()

    # Create testing framework
    testing_framework = TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        enable_mock_testing=True,
    )

    # Run a single test suite
    logger.info("Running provider validation tests...")
    results = await testing_framework.run_test_suite("provider_validation")

    # Display results
    for result in results:
        status = "✅ PASSED" if result.result.value == "passed" else "❌ FAILED"
        logger.info(f"  {result.test_name}: {status} ({result.duration_ms:.2f}ms)")

    # Generate and display test report
    report = testing_framework.generate_test_report()
    logger.info("\nTest Summary:")
    logger.info(f"  Total Tests: {report['summary']['total_tests']}")
    logger.info(f"  Passed: {report['summary']['passed']}")
    logger.info(f"  Failed: {report['summary']['failed']}")
    logger.info(f"  Success Rate: {report['summary']['success_rate']:.1f}%")


async def performance_benchmarking_example():
    """Example of performance benchmarking."""
    logger.info("\n=== Performance Benchmarking Example ===")

    # Initialize components
    mock_provider_factory = MockProviderFactory()
    mock_model_registry = MockModelRegistry()

    testing_framework = TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        enable_mock_testing=True,
    )

    # Run performance benchmarks
    logger.info("Running performance benchmarks...")
    results = await testing_framework.run_test_suite("performance_benchmarking")

    # Display performance results
    for result in results:
        if result.result.value == "passed" and result.metrics:
            logger.info(f"  {result.test_name}:")
            for metric, value in result.metrics.items():
                logger.info(f"    {metric}: {value:.2f}")


async def integration_testing_example():
    """Example of integration testing."""
    logger.info("\n=== Integration Testing Example ===")

    # Initialize components
    mock_provider_factory = MockProviderFactory()
    mock_model_registry = MockModelRegistry()

    testing_framework = TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        enable_mock_testing=True,
    )

    # Run integration tests
    logger.info("Running model mixing integration tests...")
    results = await testing_framework.run_test_suite("model_mixing")

    # Display integration test results
    for result in results:
        status = "✅ PASSED" if result.result.value == "passed" else "❌ FAILED"
        logger.info(f"  {result.test_name}: {status}")
        if result.error_message:
            logger.info(f"    Error: {result.error_message}")


async def cost_analysis_example():
    """Example of cost analysis testing."""
    logger.info("\n=== Cost Analysis Example ===")

    # Initialize components with cost manager
    mock_provider_factory = MockProviderFactory()
    mock_model_registry = MockModelRegistry()

    # Create a mock cost manager for testing
    # from gemini_sre_agent.llm.testing.mock_providers import MockCostManager
    # mock_cost_manager = MockCostManager()

    from gemini_sre_agent.llm.budget_manager import BudgetConfig
    from gemini_sre_agent.llm.cost_analytics import AnalyticsConfig
    from gemini_sre_agent.llm.cost_management import CostManagementConfig

    cost_manager = IntegratedCostManager(
        cost_config=CostManagementConfig(
            budget_limit=100.0, refresh_interval=3600, max_records=10000
        ),
        budget_config=BudgetConfig(
            budget_limit=100.0,
            auto_reset=True,
            rollover_unused=False,
            max_rollover=50.0,
        ),
        optimization_config={},  # Empty dict for now
        analytics_config=AnalyticsConfig(
            retention_days=90,
            cost_optimization_threshold=0.1,
            performance_weight=0.3,
            quality_weight=0.4,
            cost_weight=0.3,
        ),
    )

    testing_framework = TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        cost_manager=cost_manager,
        enable_mock_testing=True,
    )

    # Run cost analysis tests
    logger.info("Running cost analysis tests...")
    results = await testing_framework.run_test_suite("cost_analysis")

    # Display cost analysis results
    for result in results:
        status = "✅ PASSED" if result.result.value == "passed" else "❌ FAILED"
        logger.info(f"  {result.test_name}: {status}")


async def comprehensive_testing_example():
    """Comprehensive example running all test suites."""
    logger.info("\n=== Comprehensive Testing Example ===")

    # Initialize components
    mock_provider_factory = MockProviderFactory()
    mock_model_registry = MockModelRegistry()

    # Create mock cost manager
    # from gemini_sre_agent.llm.testing.mock_providers import MockCostManager
    # mock_cost_manager = MockCostManager()

    from gemini_sre_agent.llm.budget_manager import BudgetConfig
    from gemini_sre_agent.llm.cost_analytics import AnalyticsConfig
    from gemini_sre_agent.llm.cost_management import CostManagementConfig

    cost_manager = IntegratedCostManager(
        cost_config=CostManagementConfig(
            budget_limit=100.0, refresh_interval=3600, max_records=10000
        ),
        budget_config=BudgetConfig(
            budget_limit=100.0,
            auto_reset=True,
            rollover_unused=False,
            max_rollover=50.0,
        ),
        optimization_config={},  # Empty dict for now
        analytics_config=AnalyticsConfig(
            retention_days=90,
            cost_optimization_threshold=0.1,
            performance_weight=0.3,
            quality_weight=0.4,
            cost_weight=0.3,
        ),
    )

    testing_framework = TestingFramework(
        provider_factory=mock_provider_factory,
        model_registry=mock_model_registry,
        cost_manager=cost_manager,
        enable_mock_testing=True,
    )

    # Run all test suites
    logger.info("Running all test suites...")
    all_results = await testing_framework.run_all_test_suites()

    # Display comprehensive results
    total_tests = 0
    total_passed = 0

    for suite_name, results in all_results.items():
        suite_passed = sum(1 for r in results if r.result.value == "passed")
        suite_total = len(results)

        logger.info(f"\n{suite_name.upper()}:")
        logger.info(f"  Tests: {suite_passed}/{suite_total} passed")

        total_tests += suite_total
        total_passed += suite_passed

        # Show individual test results
        for result in results:
            status = "✅" if result.result.value == "passed" else "❌"
            logger.info(f"    {status} {result.test_name} ({result.duration_ms:.1f}ms)")
            if result.error_message:
                logger.info(f"      Error: {result.error_message}")

    # Final summary
    success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
    logger.info("\n=== FINAL SUMMARY ===")
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"Passed: {total_passed}")
    logger.info(f"Failed: {total_tests - total_passed}")
    logger.info(f"Success Rate: {success_rate:.1f}%")

    # Generate detailed report
    report = testing_framework.generate_test_report()
    logger.info("\nDetailed Report Generated:")
    logger.info(f"  Total Duration: {report['summary']['total_duration_ms']:.2f}ms")
    logger.info(f"  Test Suites: {len(report['test_suites'])}")


async def custom_test_example():
    """Example of creating and running custom tests."""
    logger.info("\n=== Custom Test Example ===")

    # Initialize components
    # mock_provider_factory = MockProviderFactory()
    # mock_model_registry = MockModelRegistry()

    # testing_framework = TestingFramework(
    #     provider_factory=mock_provider_factory,
    #     model_registry=mock_model_registry,
    #     enable_mock_testing=True,
    # )

    # Add a custom test method
    async def custom_test_method():
        """Custom test method."""
        logger.info("Running custom test...")
        # Simulate some test logic
        await asyncio.sleep(0.1)
        return True

    # Add the custom test to the framework
    # Run the custom test directly
    result = await custom_test_method()

    logger.info(f"Custom test result: {'PASSED' if result else 'FAILED'}")


async def main():
    """Main function to run all examples."""
    try:
        await basic_testing_example()
        await performance_benchmarking_example()
        await integration_testing_example()
        await cost_analysis_example()
        await custom_test_example()
        await comprehensive_testing_example()

        logger.info("\n=== All Examples Completed Successfully ===")

    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
