#!/usr/bin/env python3
"""
Advanced LLM Systems Example.

This example demonstrates the enhanced monitoring and model mixing systems,
showing how to use structured logging, metrics collection, health checks,
and advanced model mixing capabilities.
"""

import asyncio
import logging
import time

from gemini_sre_agent.llm.base import ModelType
from gemini_sre_agent.llm.cost_management_integration import create_default_cost_manager
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.mixing import (
    MixingStrategy,
    ModelConfig,
    ModelMixer,
    TaskType,
    context_manager,
)
from gemini_sre_agent.llm.model_registry import ModelRegistry
from gemini_sre_agent.llm.monitoring import (
    LLMDashboardAPI,
    LLMHealthChecker,
    error_logger,
    performance_logger,
    request_logger,
    set_request_context,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def enhanced_monitoring_example():
    """Demonstrate enhanced monitoring capabilities."""
    logger.info("=== Enhanced Monitoring Example ===")

    # Initialize components
    provider_factory = LLMProviderFactory()
    cost_manager = create_default_cost_manager()

    # Initialize health checker
    health_checker = LLMHealthChecker(provider_factory)

    # Initialize dashboard API
    dashboard_api = LLMDashboardAPI(health_checker, cost_manager)

    # Set request context for tracking
    set_request_context(
        request_id="monitoring_example_001",
        session_id="session_001",
        user_id="demo_user",
    )

    # Start continuous health checks
    await health_checker.start_continuous_health_checks()

    # Wait a bit for health checks to run
    await asyncio.sleep(2)

    # Get system overview
    logger.info("\n--- System Overview ---")
    overview = dashboard_api.get_overview()
    logger.info(f"System Status: {overview['status']}")
    logger.info(f"Health: {overview['health']['overall_status']}")
    logger.info(f"Total Requests: {overview['metrics']['total_requests']}")

    # Get detailed health status
    logger.info("\n--- Health Status ---")
    health_status = dashboard_api.get_health_status()
    for provider, health in health_status["providers"].items():
        logger.info(
            f"{provider}: {health['status']} (Success Rate: {health['success_rate']:.1%})"
        )

    # Get metrics
    logger.info("\n--- Metrics ---")
    metrics = dashboard_api.get_metrics()
    logger.info(f"Total Cost: ${metrics['summary']['total_cost']:.2f}")
    logger.info(
        f"Overall Success Rate: {metrics['summary']['overall_success_rate']:.1%}"
    )

    # Get alerts
    logger.info("\n--- Alerts ---")
    alerts = dashboard_api.get_alerts()
    logger.info(f"Total Alerts: {alerts['total_alerts']}")
    logger.info(f"Critical Alerts: {alerts['critical_alerts']}")
    logger.info(f"Warning Alerts: {alerts['warning_alerts']}")

    # Stop health checks
    await health_checker.stop_continuous_health_checks()

    logger.info("Enhanced monitoring example completed")


async def model_mixing_example():
    """Demonstrate advanced model mixing capabilities."""
    logger.info("\n=== Model Mixing Example ===")

    # Initialize components
    provider_factory = LLMProviderFactory()
    model_registry = ModelRegistry()
    cost_manager = create_default_cost_manager()

    # Initialize model mixer
    model_mixer = ModelMixer(provider_factory, model_registry, cost_manager)

    # Create a context session for mixing
    session_id = f"mixing_session_{int(time.time())}"

    # Set request context
    set_request_context(
        request_id="mixing_example_001", session_id=session_id, user_id="demo_user"
    )

    # Example 1: Parallel mixing for code generation
    logger.info("\n--- Parallel Code Generation ---")
    code_prompt = "Write a Python function to calculate the factorial of a number with error handling."

    try:
        result = await model_mixer.mix_models(
            prompt=code_prompt,
            task_type=TaskType.CODE_GENERATION,
            strategy=MixingStrategy.PARALLEL,
            context={"session_id": session_id},
        )

        logger.info(f"Execution Time: {result.execution_time_ms:.2f}ms")
        logger.info(f"Total Cost: ${result.total_cost:.4f}")
        logger.info(f"Confidence Score: {result.confidence_score:.2f}")
        logger.info(f"Models Used: {result.metadata['models_used']}")
        logger.info(f"Successful Models: {result.metadata['successful_models']}")

        if result.aggregated_result:
            logger.info(f"Aggregated Result: {result.aggregated_result[:200]}...")

    except Exception as e:
        logger.error(f"Code generation mixing failed: {e}")

    # Example 2: Sequential mixing for analysis
    logger.info("\n--- Sequential Analysis ---")
    analysis_prompt = "Analyze the pros and cons of microservices architecture for a large e-commerce platform."

    try:
        result = await model_mixer.mix_models(
            prompt=analysis_prompt,
            task_type=TaskType.ANALYSIS,
            strategy=MixingStrategy.SEQUENTIAL,
            context={"session_id": session_id},
        )

        logger.info(f"Execution Time: {result.execution_time_ms:.2f}ms")
        logger.info(f"Total Cost: ${result.total_cost:.4f}")
        logger.info(f"Confidence Score: {result.confidence_score:.2f}")

        if result.aggregated_result:
            logger.info(f"Analysis Result: {result.aggregated_result[:200]}...")

    except Exception as e:
        logger.error(f"Analysis mixing failed: {e}")

    # Example 3: Custom model configuration
    logger.info("\n--- Custom Model Configuration ---")
    custom_configs = [
        ModelConfig(
            provider="openai",
            model="gpt-4o",
            model_type=ModelType.SMART,
            weight=0.6,
            temperature=0.8,
            specialized_for=TaskType.CREATIVE_WRITING,
        ),
        ModelConfig(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            model_type=ModelType.SMART,
            weight=0.4,
            temperature=0.8,
            specialized_for=TaskType.CREATIVE_WRITING,
        ),
    ]

    creative_prompt = "Write a short story about a robot learning to paint."

    try:
        result = await model_mixer.mix_models(
            prompt=creative_prompt,
            task_type=TaskType.CREATIVE_WRITING,
            strategy=MixingStrategy.WEIGHTED,
            custom_configs=custom_configs,
            context={"session_id": session_id},
        )

        logger.info(f"Execution Time: {result.execution_time_ms:.2f}ms")
        logger.info(f"Total Cost: ${result.total_cost:.4f}")
        logger.info(f"Confidence Score: {result.confidence_score:.2f}")

        if result.aggregated_result:
            logger.info(f"Creative Result: {result.aggregated_result[:200]}...")

    except Exception as e:
        logger.error(f"Creative writing mixing failed: {e}")

    # Example 4: Task decomposition and mixing
    logger.info("\n--- Task Decomposition and Mixing ---")
    complex_task = """
    Design a comprehensive system for monitoring a distributed microservices application.
    The system should include:
    1. Metrics collection and aggregation
    2. Distributed tracing
    3. Log aggregation and analysis
    4. Alerting and notification
    5. Performance optimization recommendations
    """

    try:
        results = await model_mixer.decompose_and_mix(
            complex_task=complex_task,
            task_type=TaskType.PROBLEM_SOLVING,
            strategy=MixingStrategy.PARALLEL,
            context={"session_id": session_id},
        )

        logger.info(f"Decomposed into {len(results)} subtasks")
        for i, result in enumerate(results):
            logger.info(
                f"Subtask {i+1}: {result.execution_time_ms:.2f}ms, ${result.total_cost:.4f}, confidence: {result.confidence_score:.2f}"
            )

    except Exception as e:
        logger.error(f"Task decomposition mixing failed: {e}")

    # Get context summary
    logger.info("\n--- Context Summary ---")
    context_summary = context_manager.get_context_summary(session_id)
    logger.info(f"Session: {context_summary['session_id']}")
    logger.info(f"Total Entries: {context_summary['total_entries']}")
    logger.info(f"Unique Models: {context_summary['unique_models']}")
    logger.info(f"Model Interactions: {context_summary['model_interactions']}")

    logger.info("Model mixing example completed")


async def integrated_systems_example():
    """Demonstrate integrated monitoring and mixing systems."""
    logger.info("\n=== Integrated Systems Example ===")

    # Initialize all components
    provider_factory = LLMProviderFactory()
    model_registry = ModelRegistry()
    cost_manager = create_default_cost_manager()

    # Initialize monitoring
    health_checker = LLMHealthChecker(provider_factory)
    dashboard_api = LLMDashboardAPI(health_checker, cost_manager)

    # Initialize mixing
    model_mixer = ModelMixer(provider_factory, model_registry, cost_manager)

    # Start monitoring
    await health_checker.start_continuous_health_checks()

    # Set up request context
    session_id = f"integrated_session_{int(time.time())}"
    set_request_context(
        request_id="integrated_example_001", session_id=session_id, user_id="demo_user"
    )

    # Create context for mixing

    # Perform mixed model operations with monitoring
    tasks = [
        (
            "Write a Python decorator for caching function results.",
            TaskType.CODE_GENERATION,
        ),
        ("Explain the benefits of using async/await in Python.", TaskType.ANALYSIS),
        ("Create a haiku about programming.", TaskType.CREATIVE_WRITING),
    ]

    for i, (prompt, task_type) in enumerate(tasks):
        logger.info(f"\n--- Task {i+1}: {task_type.value} ---")

        try:
            # Record request start
            # request_logger.log_request_start(
            #     request=None,  # Would be actual LLMRequest in real usage
            #     provider="mixed",
            #     model="multiple",
            #     task_type=task_type.value
            # )

            # Execute mixed model operation
            result = await model_mixer.mix_models(
                prompt=prompt,
                task_type=task_type,
                strategy=MixingStrategy.PARALLEL,
                context={"session_id": session_id, "task_index": i},
            )

            # Record performance
            performance_logger.log_latency(
                operation="model_mixing",
                duration_ms=result.execution_time_ms,
                provider="mixed",
                model="multiple",
            )

            # Record cost
            request_logger.log_cost_estimation(
                provider="mixed",
                model="multiple",
                estimated_cost=result.total_cost,
                input_tokens=len(prompt) // 4,  # Rough estimation
                output_tokens=(
                    len(result.aggregated_result) // 4
                    if result.aggregated_result
                    else 0
                ),
            )

            logger.info(
                f"✓ Completed in {result.execution_time_ms:.2f}ms, cost: ${result.total_cost:.4f}"
            )

        except Exception as e:
            error_logger.log_provider_error(
                provider="mixed",
                model="multiple",
                error=e,
                request_context={"prompt": prompt, "task_type": task_type.value},
            )
            logger.error(f"✗ Task failed: {e}")

    # Get final system status
    logger.info("\n--- Final System Status ---")
    system_status = dashboard_api.get_system_status()
    logger.info(f"Overall Status: {system_status['status']}")
    logger.info(f"Total Requests: {system_status['metrics']['total_requests']}")
    logger.info(f"Success Rate: {system_status['metrics']['overall_success_rate']:.1%}")
    logger.info(f"Total Cost: ${system_status['metrics']['total_cost']:.2f}")
    logger.info(
        f"Alerts: {system_status['alerts']['total']} total, {system_status['alerts']['critical']} critical"
    )

    # Stop monitoring
    await health_checker.stop_continuous_health_checks()

    logger.info("Integrated systems example completed")


async def main():
    """Run all examples."""
    logger.info("Starting Advanced LLM Systems Examples")

    try:
        # Run examples
        await enhanced_monitoring_example()
        await model_mixing_example()
        await integrated_systems_example()

        logger.info("\n=== All Examples Completed Successfully ===")

    except Exception as e:
        logger.error(f"Example execution failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
