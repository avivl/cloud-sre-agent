# tests/source_control/test_error_handling_health_checks.py

"""
Unit tests for HealthCheckManager in error handling system.
"""

from unittest.mock import MagicMock

import pytest

from gemini_sre_agent.source_control.error_handling.core import CircuitState
from gemini_sre_agent.source_control.error_handling.health_checks import (
    HealthCheckManager,
)


class TestHealthCheckManager:
    """Test cases for HealthCheckManager."""

    @pytest.fixture
    def mock_resilient_manager(self):
        """Create a mock ResilientOperationManager."""
        manager = MagicMock()
        manager.circuit_breakers = {}
        manager._determine_operation_type = MagicMock(return_value="file_operation")
        return manager

    @pytest.fixture
    def health_check_manager(self, mock_resilient_manager):
        """Create a HealthCheckManager instance for testing."""
        return HealthCheckManager(mock_resilient_manager)

    @pytest.fixture
    def mock_circuit_breaker(self):
        """Create a mock circuit breaker."""
        cb = MagicMock()
        cb.name = "test_circuit"
        cb.state = CircuitState.CLOSED
        cb.get_stats.return_value = {
            "failure_rate": 0.1,
            "total_requests": 100,
            "total_failures": 10,
            "state": "closed",
        }
        return cb

    def test_health_check_manager_initialization(
        self, health_check_manager, mock_resilient_manager
    ):
        """Test HealthCheckManager initialization."""
        assert health_check_manager.resilient_manager == mock_resilient_manager
        assert health_check_manager.logger is not None

    def test_get_circuit_breaker_health_specific_circuit(
        self, health_check_manager, mock_circuit_breaker
    ):
        """Test getting health status for a specific circuit breaker."""
        health_check_manager.resilient_manager.circuit_breakers["test_circuit"] = (
            mock_circuit_breaker
        )

        result = health_check_manager.get_circuit_breaker_health("test_circuit")

        assert result["status"] == "healthy"
        assert result["circuit_name"] == "test_circuit"
        assert result["state"] == "closed"
        assert "stats" in result
        assert "message" in result

    def test_get_circuit_breaker_health_nonexistent_circuit(self, health_check_manager):
        """Test getting health status for a non-existent circuit breaker."""
        result = health_check_manager.get_circuit_breaker_health("nonexistent")

        assert result["status"] == "error"
        assert "not found" in result["message"]
        assert result["circuit_name"] == "nonexistent"

    def test_get_circuit_breaker_health_open_circuit(
        self, health_check_manager, mock_circuit_breaker
    ):
        """Test getting health status for an open circuit breaker."""
        mock_circuit_breaker.state = CircuitState.OPEN
        health_check_manager.resilient_manager.circuit_breakers["test_circuit"] = (
            mock_circuit_breaker
        )

        result = health_check_manager.get_circuit_breaker_health("test_circuit")

        assert result["status"] == "unhealthy"
        assert result["state"] == "open"

    def test_get_circuit_breaker_health_all_circuits(self, health_check_manager):
        """Test getting health status for all circuit breakers."""
        cb1 = MagicMock()
        cb1.state = CircuitState.CLOSED
        cb1.get_stats.return_value = {
            "failure_rate": 0.1,
            "total_requests": 100,
            "total_failures": 10,
        }

        cb2 = MagicMock()
        cb2.state = CircuitState.OPEN
        cb2.get_stats.return_value = {
            "failure_rate": 0.8,
            "total_requests": 100,
            "total_failures": 80,
        }

        health_check_manager.resilient_manager.circuit_breakers = {
            "circuit1": cb1,
            "circuit2": cb2,
        }

        result = health_check_manager.get_circuit_breaker_health()

        assert result["status"] == "unhealthy"
        assert result["total_circuits"] == 2
        assert result["healthy_circuits"] == 1
        assert len(result["circuits"]) == 2

    def test_get_operation_type_health_specific_type(
        self, health_check_manager, mock_circuit_breaker
    ):
        """Test getting health status for a specific operation type."""
        health_check_manager.resilient_manager._determine_operation_type.return_value = (
            "file_operation"
        )
        health_check_manager.resilient_manager.circuit_breakers["test_circuit"] = (
            mock_circuit_breaker
        )

        result = health_check_manager.get_operation_type_health("file_operation")

        assert result["status"] == "healthy"
        assert result["operation_type"] == "file_operation"
        assert result["total_circuits"] == 1
        assert result["healthy_circuits"] == 1
        assert result["open_circuits"] == 0

    def test_get_operation_type_health_nonexistent_type(self, health_check_manager):
        """Test getting health status for a non-existent operation type."""
        result = health_check_manager.get_operation_type_health("nonexistent_type")

        assert result["status"] == "error"
        assert "not found" in result["message"]
        assert result["operation_type"] == "nonexistent_type"

    def test_get_overall_health(self, health_check_manager, mock_circuit_breaker):
        """Test getting overall health status."""
        health_check_manager.resilient_manager.circuit_breakers["test_circuit"] = (
            mock_circuit_breaker
        )

        result = health_check_manager.get_overall_health()

        assert "status" in result
        assert "circuit_breakers" in result
        assert "operation_types" in result
        assert "message" in result

    def test_circuit_state_enum(self):
        """Test CircuitState enum values."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"
