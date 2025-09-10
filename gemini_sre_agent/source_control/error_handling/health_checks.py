# gemini_sre_agent/source_control/error_handling/health_checks.py

"""
Health check endpoints for circuit breaker status and error handling system.

This module provides health check functionality to monitor the status of
circuit breakers and the overall error handling system.
"""

import logging
from typing import Any, Dict, Optional

from .core import CircuitState
from .resilient_operations import ResilientOperationManager


class HealthCheckManager:
    """Manages health checks for the error handling system."""

    def __init__(self, resilient_manager: ResilientOperationManager):
        self.resilient_manager = resilient_manager
        self.logger = logging.getLogger("HealthCheckManager")

    def get_circuit_breaker_health(self, circuit_name: Optional[str] = None) -> Dict[str, Any]:
        """Get health status for circuit breakers."""
        if circuit_name:
            if circuit_name not in self.resilient_manager.circuit_breakers:
                return {
                    "status": "error",
                    "message": f"Circuit breaker '{circuit_name}' not found",
                    "circuit_name": circuit_name,
                }
            
            circuit = self.resilient_manager.circuit_breakers[circuit_name]
            stats = circuit.get_stats()
            
            return {
                "status": "healthy" if circuit.state != CircuitState.OPEN else "unhealthy",
                "circuit_name": circuit_name,
                "state": circuit.state.value,
                "stats": stats,
                "message": self._get_circuit_health_message(circuit.state, stats),
            }
        
        # Get health for all circuit breakers
        all_circuits_healthy = True
        circuit_health = []
        
        for name, circuit in self.resilient_manager.circuit_breakers.items():
            stats = circuit.get_stats()
            is_healthy = circuit.state != CircuitState.OPEN and stats["failure_rate"] <= 0.5
            
            if not is_healthy:
                all_circuits_healthy = False
            
            circuit_health.append({
                "circuit_name": name,
                "status": "healthy" if is_healthy else "unhealthy",
                "state": circuit.state.value,
                "stats": stats,
                "message": self._get_circuit_health_message(circuit.state, stats),
            })
        
        return {
            "status": "healthy" if all_circuits_healthy else "unhealthy",
            "total_circuits": len(self.resilient_manager.circuit_breakers),
            "healthy_circuits": sum(1 for ch in circuit_health if ch["status"] == "healthy"),
            "circuits": circuit_health,
            "message": "All circuit breakers are healthy" if all_circuits_healthy else "Some circuit breakers are unhealthy",
        }

    def get_operation_type_health(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """Get health status for operation types."""
        operation_type_stats = {}
        
        for name, circuit in self.resilient_manager.circuit_breakers.items():
            op_type = self.resilient_manager._determine_operation_type(name)
            
            if operation_type and op_type != operation_type:
                continue
            
            if op_type not in operation_type_stats:
                operation_type_stats[op_type] = {
                    "total": 0,
                    "healthy": 0,
                    "open_circuits": 0,
                    "circuits": [],
                }
            
            stats = circuit.get_stats()
            is_healthy = circuit.state != CircuitState.OPEN and stats["failure_rate"] <= 0.5
            
            operation_type_stats[op_type]["total"] += 1
            if is_healthy:
                operation_type_stats[op_type]["healthy"] += 1
            else:
                if circuit.state == CircuitState.OPEN:
                    operation_type_stats[op_type]["open_circuits"] += 1
            
            operation_type_stats[op_type]["circuits"].append({
                "circuit_name": name,
                "status": "healthy" if is_healthy else "unhealthy",
                "state": circuit.state.value,
                "stats": stats,
            })
        
        if operation_type:
            if operation_type not in operation_type_stats:
                return {
                    "status": "error",
                    "message": f"Operation type '{operation_type}' not found",
                    "operation_type": operation_type,
                }
            
            stats = operation_type_stats[operation_type]
            is_healthy = stats["open_circuits"] == 0 and stats["healthy"] == stats["total"]
            
            return {
                "status": "healthy" if is_healthy else "unhealthy",
                "operation_type": operation_type,
                "total_circuits": stats["total"],
                "healthy_circuits": stats["healthy"],
                "open_circuits": stats["open_circuits"],
                "circuits": stats["circuits"],
                "message": self._get_operation_type_health_message(stats),
            }
        
        # Get health for all operation types
        all_types_healthy = True
        type_health = []
        
        for op_type, stats in operation_type_stats.items():
            is_healthy = stats["open_circuits"] == 0 and stats["healthy"] == stats["total"]
            
            if not is_healthy:
                all_types_healthy = False
            
            type_health.append({
                "operation_type": op_type,
                "status": "healthy" if is_healthy else "unhealthy",
                "total_circuits": stats["total"],
                "healthy_circuits": stats["healthy"],
                "open_circuits": stats["open_circuits"],
                "message": self._get_operation_type_health_message(stats),
            })
        
        return {
            "status": "healthy" if all_types_healthy else "unhealthy",
            "total_operation_types": len(operation_type_stats),
            "healthy_operation_types": sum(1 for th in type_health if th["status"] == "healthy"),
            "operation_types": type_health,
            "message": "All operation types are healthy" if all_types_healthy else "Some operation types are unhealthy",
        }

    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall health status of the error handling system."""
        circuit_health = self.get_circuit_breaker_health()
        operation_type_health = self.get_operation_type_health()
        
        overall_healthy = (
            circuit_health["status"] == "healthy" and
            operation_type_health["status"] == "healthy"
        )
        
        return {
            "status": "healthy" if overall_healthy else "unhealthy",
            "circuit_breakers": circuit_health,
            "operation_types": operation_type_health,
            "message": "Error handling system is healthy" if overall_healthy else "Error handling system has issues",
        }

    def _get_circuit_health_message(self, state: CircuitState, stats: Dict[str, Any]) -> str:
        """Get a descriptive message for circuit health."""
        if state == CircuitState.OPEN:
            return f"Circuit is open (failure rate: {stats['failure_rate']:.2%})"
        elif state == CircuitState.HALF_OPEN:
            return "Circuit is half-open (testing recovery)"
        else:  # CLOSED
            if stats["failure_rate"] > 0.5:
                return f"Circuit is closed but has high failure rate: {stats['failure_rate']:.2%}"
            else:
                return f"Circuit is closed and healthy (failure rate: {stats['failure_rate']:.2%})"

    def _get_operation_type_health_message(self, stats: Dict[str, Any]) -> str:
        """Get a descriptive message for operation type health."""
        if stats["open_circuits"] > 0:
            return f"Operation type has {stats['open_circuits']} open circuits"
        elif stats["healthy"] < stats["total"]:
            return f"Operation type has {stats['total'] - stats['healthy']} unhealthy circuits"
        else:
            return f"Operation type is healthy ({stats['healthy']}/{stats['total']} circuits)"


def create_health_check_endpoints(resilient_manager: ResilientOperationManager) -> Dict[str, Any]:
    """Create health check endpoints for the error handling system."""
    health_manager = HealthCheckManager(resilient_manager)
    
    return {
        "circuit_breaker_health": health_manager.get_circuit_breaker_health,
        "operation_type_health": health_manager.get_operation_type_health,
        "overall_health": health_manager.get_overall_health,
    }
