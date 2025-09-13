"""Pytest configuration and shared fixtures for the reorganized test structure."""

import asyncio
from collections.abc import Generator
import os
from pathlib import Path
import tempfile
from typing import Any
from unittest.mock import Mock

import pytest

# Set test environment variables
os.environ["TESTING"] = "true"
os.environ["LOG_LEVEL"] = "DEBUG"


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def mock_config() -> dict[str, Any]:
    """Mock configuration for testing."""
    return {
        "llm": {
            "providers": {
                "openai": {"api_key": "test-key", "model": "gpt-4", "temperature": 0.7},
                "anthropic": {
                    "api_key": "test-key",
                    "model": "claude-3-sonnet",
                    "temperature": 0.7,
                },
            },
            "default_provider": "openai",
            "timeout": 30,
            "max_retries": 3,
        },
        "metrics": {"enabled": True, "collection_interval": 60, "retention_days": 30},
        "resilience": {
            "circuit_breaker": {"failure_threshold": 5, "recovery_timeout": 60},
            "retry": {"max_attempts": 3, "backoff_factor": 2},
        },
        "security": {
            "encryption": {"enabled": True, "algorithm": "AES-256"},
            "access_control": {"enabled": True, "default_permission": "read"},
        },
    }


@pytest.fixture
def mock_llm_response() -> dict[str, Any]:
    """Mock LLM response for testing."""
    return {
        "content": "This is a test response",
        "model": "gpt-4",
        "provider": "openai",
        "tokens_used": 100,
        "cost_usd": 0.01,
        "latency_ms": 500,
        "quality_score": 0.95,
    }


@pytest.fixture
def mock_agent_request() -> dict[str, Any]:
    """Mock agent request for testing."""
    return {
        "agent_id": "test-agent",
        "agent_type": "analysis",
        "prompt": "Test prompt",
        "context": {"test": "data"},
        "max_tokens": 1000,
        "temperature": 0.7,
        "timeout_seconds": 30,
    }


@pytest.fixture
def mock_workflow_context() -> dict[str, Any]:
    """Mock workflow context for testing."""
    return {
        "workflow_id": "test-workflow",
        "repository": "test/repo",
        "branch": "main",
        "commit_sha": "abc123",
        "files_changed": ["test.py"],
        "context_data": {"test": "context"},
    }


@pytest.fixture
def mock_error_data() -> dict[str, Any]:
    """Mock error data for testing."""
    return {
        "error_type": "ValueError",
        "error_message": "Test error message",
        "traceback": "Traceback (most recent call last):\n  File \"test.py\", line 1, in <module>\n    raise ValueError('Test error')\nValueError: Test error",
        "context": {"file": "test.py", "line": 1, "function": "test_function"},
        "timestamp": "2024-01-01T00:00:00Z",
        "severity": "error",
    }


@pytest.fixture
def mock_metrics_data() -> dict[str, Any]:
    """Mock metrics data for testing."""
    return {
        "total_requests": 1000,
        "successful_requests": 950,
        "failed_requests": 50,
        "success_rate": 0.95,
        "avg_latency_ms": 500,
        "p95_latency_ms": 800,
        "p99_latency_ms": 1200,
        "total_cost_usd": 10.50,
        "total_tokens": 50000,
    }


@pytest.fixture
def mock_provider_health() -> dict[str, Any]:
    """Mock provider health data for testing."""
    return {
        "provider": "openai",
        "status": "healthy",
        "last_check": "2024-01-01T00:00:00Z",
        "check_count": 100,
        "success_count": 95,
        "failure_count": 5,
        "success_rate": 0.95,
        "avg_response_time_ms": 500,
        "issues": [],
    }


@pytest.fixture
def mock_pattern_match() -> dict[str, Any]:
    """Mock pattern match data for testing."""
    return {
        "pattern_id": "test-pattern",
        "pattern_type": "regex",
        "confidence": 0.85,
        "matched_text": "test error",
        "start_position": 0,
        "end_position": 10,
        "context": "This is a test error message",
    }


@pytest.fixture
def mock_classification_result() -> dict[str, Any]:
    """Mock classification result for testing."""
    return {
        "error_type": "ValueError",
        "category": "validation",
        "confidence": 0.90,
        "suggested_actions": [
            "Check input validation",
            "Verify data types",
            "Add error handling",
        ],
        "severity": "medium",
        "patterns_matched": ["test-pattern-1", "test-pattern-2"],
    }


@pytest.fixture
def mock_cost_data() -> dict[str, Any]:
    """Mock cost data for testing."""
    return {
        "total_cost_usd": 150.75,
        "daily_average": 5.02,
        "cost_trend": "stable",
        "breakdown": {"input_tokens": 120.50, "output_tokens": 30.25},
        "by_provider": {"openai": 100.00, "anthropic": 50.75},
        "by_model": {"gpt-4": 80.00, "claude-3-sonnet": 50.75},
    }


@pytest.fixture
def mock_alert() -> dict[str, Any]:
    """Mock alert data for testing."""
    return {
        "alert_id": "test-alert-1",
        "type": "performance",
        "severity": "warning",
        "provider": "openai",
        "message": "High error rate detected",
        "details": {"error_rate": 0.15, "threshold": 0.10},
        "timestamp": "2024-01-01T00:00:00Z",
        "status": "active",
    }


@pytest.fixture
def mock_file_system(temp_dir: Path) -> Generator[Path, None, None]:
    """Create a mock file system for testing."""
    # Create test files
    (temp_dir / "test_file.py").write_text("print('Hello, World!')")
    (temp_dir / "test_config.json").write_text('{"test": "config"}')
    (temp_dir / "test_log.txt").write_text("2024-01-01 INFO: Test log message")

    # Create subdirectories
    (temp_dir / "subdir").mkdir()
    (temp_dir / "subdir" / "nested_file.py").write_text("def test(): pass")

    yield temp_dir


@pytest.fixture
def mock_github_repo() -> Mock:
    """Mock GitHub repository for testing."""
    repo = Mock()
    repo.name = "test-repo"
    repo.full_name = "test-org/test-repo"
    repo.owner.login = "test-org"
    repo.default_branch = "main"
    repo.html_url = "https://github.com/test-org/test-repo"
    repo.clone_url = "https://github.com/test-org/test-repo.git"
    return repo


@pytest.fixture
def mock_gitlab_project() -> Mock:
    """Mock GitLab project for testing."""
    project = Mock()
    project.name = "test-project"
    project.path_with_namespace = "test-group/test-project"
    project.namespace.name = "test-group"
    project.default_branch = "main"
    project.web_url = "https://gitlab.com/test-group/test-project"
    project.ssh_url_to_repo = "git@gitlab.com:test-group/test-project.git"
    return project


@pytest.fixture
def mock_llm_provider() -> Mock:
    """Mock LLM provider for testing."""
    provider = Mock()
    provider.name = "test-provider"
    provider.model = "test-model"
    provider.generate.return_value = "Test response"
    provider.stream_generate.return_value = ["Test", " response"]
    provider.estimate_cost.return_value = 0.01
    provider.get_health.return_value = {"status": "healthy"}
    return provider


@pytest.fixture
def mock_agent() -> Mock:
    """Mock agent for testing."""
    agent = Mock()
    agent.agent_id = "test-agent"
    agent.agent_type = "analysis"
    agent.process.return_value = {"result": "test result"}
    agent.get_status.return_value = "ready"
    agent.get_metrics.return_value = {"requests": 100, "success_rate": 0.95}
    return agent


@pytest.fixture
def mock_workflow() -> Mock:
    """Mock workflow for testing."""
    workflow = Mock()
    workflow.workflow_id = "test-workflow"
    workflow.status = "running"
    workflow.execute.return_value = {"result": "workflow completed"}
    workflow.get_progress.return_value = 0.75
    workflow.get_metrics.return_value = {"duration_ms": 5000}
    return workflow


@pytest.fixture
def mock_pattern_classifier() -> Mock:
    """Mock pattern classifier for testing."""
    classifier = Mock()
    classifier.classify.return_value = {
        "error_type": "ValueError",
        "confidence": 0.85,
        "category": "validation",
    }
    classifier.get_patterns.return_value = ["pattern1", "pattern2"]
    classifier.get_confidence.return_value = 0.85
    return classifier


@pytest.fixture
def mock_metrics_collector() -> Mock:
    """Mock metrics collector for testing."""
    collector = Mock()
    collector.collect_metrics.return_value = {"requests": 100, "success_rate": 0.95}
    collector.get_summary.return_value = {"total_requests": 1000}
    collector.get_provider_metrics.return_value = {"openai": {"requests": 500}}
    collector.get_model_metrics.return_value = {"gpt-4": {"requests": 300}}
    return collector


@pytest.fixture
def mock_cost_manager() -> Mock:
    """Mock cost manager for testing."""
    manager = Mock()
    manager.estimate_cost.return_value = 0.01
    manager.get_total_cost.return_value = 150.75
    manager.get_cost_breakdown.return_value = {"input": 100.0, "output": 50.75}
    manager.get_cost_analytics.return_value = {"trend": "stable", "daily_avg": 5.02}
    return manager


@pytest.fixture
def mock_resilience_manager() -> Mock:
    """Mock resilience manager for testing."""
    manager = Mock()
    manager.circuit_breaker.is_open.return_value = False
    manager.retry_handler.should_retry.return_value = True
    manager.fallback_manager.get_fallback.return_value = "fallback_response"
    manager.get_health.return_value = {"status": "healthy"}
    return manager


@pytest.fixture
def mock_security_manager() -> Mock:
    """Mock security manager for testing."""
    manager = Mock()
    manager.encrypt.return_value = "encrypted_data"
    manager.decrypt.return_value = "decrypted_data"
    manager.check_permission.return_value = True
    manager.audit_log.return_value = True
    manager.get_compliance_status.return_value = {"status": "compliant"}
    return manager


# Async fixtures
@pytest.fixture
async def async_mock_llm_provider() -> Mock:
    """Async mock LLM provider for testing."""
    provider = Mock()
    provider.name = "test-provider"
    provider.model = "test-model"
    provider.generate = Mock(return_value="Test response")
    provider.stream_generate = Mock(return_value=["Test", " response"])
    provider.estimate_cost = Mock(return_value=0.01)
    provider.get_health = Mock(return_value={"status": "healthy"})
    return provider


@pytest.fixture
async def async_mock_agent() -> Mock:
    """Async mock agent for testing."""
    agent = Mock()
    agent.agent_id = "test-agent"
    agent.agent_type = "analysis"
    agent.process = Mock(return_value={"result": "test result"})
    agent.get_status = Mock(return_value="ready")
    agent.get_metrics = Mock(return_value={"requests": 100, "success_rate": 0.95})
    return agent


# Test data fixtures
@pytest.fixture
def sample_log_entries() -> list[dict[str, Any]]:
    """Sample log entries for testing."""
    return [
        {
            "timestamp": "2024-01-01T00:00:00Z",
            "level": "ERROR",
            "message": "ValueError: Invalid input",
            "service": "test-service",
            "traceback": "Traceback...",
            "context": {"user_id": "123"},
        },
        {
            "timestamp": "2024-01-01T00:01:00Z",
            "level": "INFO",
            "message": "Request processed successfully",
            "service": "test-service",
            "context": {"request_id": "req-123"},
        },
    ]


@pytest.fixture
def sample_error_patterns() -> list[dict[str, Any]]:
    """Sample error patterns for testing."""
    return [
        {
            "pattern_id": "value-error-1",
            "pattern_type": "regex",
            "pattern": r"ValueError: (.+)",
            "error_type": "ValueError",
            "category": "validation",
            "confidence": 0.9,
        },
        {
            "pattern_id": "connection-error-1",
            "pattern_type": "keyword",
            "pattern": "ConnectionError",
            "error_type": "ConnectionError",
            "category": "network",
            "confidence": 0.8,
        },
    ]


# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_files():
    """Clean up test files after each test."""
    yield
    # Add cleanup logic here if needed
    pass


# Skip slow tests by default
def pytest_collection_modifyitems(config, items):
    """Modify test collection to skip slow tests by default."""
    if not config.getoption("--runslow", default=False):
        skip_slow = pytest.mark.skip(reason="need --runslow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
