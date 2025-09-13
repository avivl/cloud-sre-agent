"""Examples demonstrating the comprehensive logging framework usage."""

import random
import time
from typing import Any

from .alerting import AlertRule, AlertSeverity, get_alert_manager
from .flow_tracker import get_flow_tracker
from .logger import LoggingConfig, get_logger


def basic_logging_example():
    """Demonstrate basic logging functionality."""
    print("=== Basic Logging Example ===")

    # Get logger with default configuration
    logger = get_logger()

    # Basic logging
    logger.info("Application started")
    logger.debug("Debug information", extra={"user_id": "12345"})
    logger.warning("This is a warning message")
    logger.error("An error occurred", extra={"error_code": "E001"})

    # Logging with tags
    logger.info("User action", tags=["user", "action"], extra={"action": "login"})

    # Exception logging
    try:
        raise ValueError("Something went wrong")
    except ValueError:
        logger.exception("Caught an exception", extra={"context": "example"})


def flow_tracking_example():
    """Demonstrate flow tracking functionality."""
    print("\n=== Flow Tracking Example ===")

    logger = get_logger()
    get_flow_tracker()

    # Start a flow
    flow_id = logger.start_flow(
        "user_registration", metadata={"user_email": "user@example.com"}
    )
    logger.info("Starting user registration", flow_id=flow_id)

    # Simulate some work
    time.sleep(0.1)

    # Add context
    logger.add_context("registration_step", "email_verification")
    logger.info("Sending verification email", flow_id=flow_id)

    # Simulate more work
    time.sleep(0.1)

    # End flow
    logger.end_flow(flow_id, "completed")
    logger.info("User registration completed", flow_id=flow_id)

    # Show flow history
    flows = logger.get_flow_history(limit=5)
    print(f"Recent flows: {len(flows)}")


def performance_monitoring_example():
    """Demonstrate performance monitoring functionality."""
    print("\n=== Performance Monitoring Example ===")

    logger = get_logger()

    # Record some metrics
    logger.record_metric("api_requests", 1, tags={"endpoint": "/users"})
    logger.record_metric("api_requests", 1, tags={"endpoint": "/posts"})
    logger.record_metric("api_requests", 1, tags={"endpoint": "/users"})

    # Timing operations
    with logger.timing("database_query", tags={"table": "users"}):
        time.sleep(0.05)  # Simulate database query

    with logger.timing("external_api_call", tags={"service": "payment"}):
        time.sleep(0.1)  # Simulate external API call

    # Get performance stats
    stats = logger.get_performance_stats("api_requests", tags={"endpoint": "/users"})
    if stats:
        print(f"API requests to /users: {stats['count']} requests")

    # Export metrics
    metrics = logger.export_metrics("stats")
    print(f"Available metrics: {list(metrics.keys())}")


def alerting_example():
    """Demonstrate alerting functionality."""
    print("\n=== Alerting Example ===")

    logger = get_logger()
    alert_manager = get_alert_manager()

    # Define an alert rule
    def high_error_rate_condition(data: dict[str, Any]) -> bool:
        """Check if error rate is high."""
        level = data.get("level", 0)
        return level >= 40  # ERROR level or higher

    error_rule = AlertRule(
        name="high_error_rate",
        condition=high_error_rate_condition,
        severity=AlertSeverity.HIGH,
        message_template="High error rate detected: {level_name} - {message}",
        cooldown_seconds=60,
    )

    alert_manager.add_rule(error_rule)

    # Trigger some alerts
    logger.error("Database connection failed")
    logger.critical("System overload detected")
    logger.error("Authentication service unavailable")

    # Check alerts
    alerts = logger.get_alerts(limit=5)
    print(f"Active alerts: {len(alerts)}")

    for alert in alerts:
        print(f"Alert: {alert['severity']} - {alert['message']}")

    # Get alert statistics
    stats = logger.get_alert_stats()
    print(f"Alert stats: {stats}")


def context_management_example():
    """Demonstrate context management functionality."""
    print("\n=== Context Management Example ===")

    logger = get_logger()

    # Add context
    logger.add_context("user_id", "12345")
    logger.add_context("session_id", "sess_abc123")
    logger.add_context("request_id", "req_xyz789")

    # Log with context
    logger.info("Processing request")
    logger.debug("User data loaded")

    # Show current context
    context = logger.get_context()
    print(f"Current context: {context}")

    # Remove specific context
    logger.remove_context("request_id")

    # Clear all context
    logger.clear_context()
    logger.info("Context cleared")


def comprehensive_example():
    """Demonstrate comprehensive logging with all features."""
    print("\n=== Comprehensive Example ===")

    # Configure logging
    config = LoggingConfig(
        name="comprehensive_example",
        level=20,  # INFO
        handlers=[{"type": "console", "level": 20, "formatter": "json"}],
        formatters={"json": {"type": "json", "include_extra": True}},
    )

    logger = get_logger(config)

    # Start a complex flow
    with logger.flow("data_processing", tags=["batch", "etl"]) as flow_id:
        logger.add_context("batch_id", "batch_001")
        logger.add_context("source", "database")
        logger.add_context("destination", "warehouse")

        logger.info("Starting data processing batch", flow_id=flow_id)

        # Simulate processing steps
        steps = ["extract", "transform", "load", "validate"]

        for step in steps:
            with logger.timing(f"step_{step}", tags={"step": step}):
                logger.info(f"Executing {step} step", flow_id=flow_id)

                # Simulate work
                time.sleep(random.uniform(0.01, 0.05))

                # Record metrics
                logger.record_metric(
                    "processing_records", random.randint(100, 1000), tags={"step": step}
                )

                # Simulate occasional errors
                if random.random() < 0.1:  # 10% chance of error
                    logger.error(
                        f"Error in {step} step",
                        extra={"error_code": f"E_{step.upper()}"},
                        flow_id=flow_id,
                    )

        logger.info("Data processing batch completed", flow_id=flow_id)

        # Record final metrics
        logger.record_metric("batch_processing_time", 1, tags={"status": "completed"})

    # Show results
    flows = logger.get_flow_history(limit=1)
    if flows:
        flow = flows[0]
        print(f"Flow completed: {flow['operation']} in {flow['duration']:.2f}s")

    metrics = logger.export_metrics("stats")
    print(f"Recorded metrics: {list(metrics.keys())}")

    alerts = logger.get_alerts()
    print(f"Generated alerts: {len(alerts)}")


def main():
    """Run all examples."""
    print("Comprehensive Logging Framework Examples")
    print("=" * 50)

    try:
        basic_logging_example()
        flow_tracking_example()
        performance_monitoring_example()
        alerting_example()
        context_management_example()
        comprehensive_example()

        print("\n" + "=" * 50)
        print("All examples completed successfully!")

    except Exception as e:
        print(f"Example failed: {e}")
        raise


if __name__ == "__main__":
    main()
