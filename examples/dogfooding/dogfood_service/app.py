#!/usr/bin/env python3
"""
Dogfooding Problem Service - Flask-based error-producing service for testing SRE Agent.

This service provides 4 MVP error endpoints to test the SRE Agent's ability to:
1. Detect errors from structured logs
2. Analyze root causes
3. Generate fixes via PRs

All files must be under 250 LOC for maintainability.
"""

import json
import logging
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from flask import Flask, jsonify, request

# Configure structured JSON logging
log_file = "/tmp/sre-dogfooding/dogfood_service.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[logging.FileHandler(log_file), logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Service metadata
SERVICE_VERSION = "1.0.0"
SERVICE_NAME = "dogfood_service"


def log_error(
    error_type: str,
    endpoint: str,
    error: Exception,
    context: Dict[str, Any] | None = None,
) -> None:
    """Log errors in structured JSON format for SRE Agent ingestion."""
    try:
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": SERVICE_NAME,
            "error_type": error_type,
            "category": _get_error_category(error_type),
            "endpoint": endpoint,
            "request_id": f"req_{int(time.time() * 1000)}",
            "traceback": traceback.format_exc(),
            "context": context if context is not None else {},
            "metadata": {
                "error_count": 1,
                "service_version": SERVICE_VERSION,
                "environment": "dogfood",
            },
        }
        logger.error(json.dumps(error_data))
    except Exception as log_error:
        # Fallback logging if JSON serialization fails
        logger.error(f"Failed to log error: {log_error}")


def _get_error_category(error_type: str) -> str:
    """Map error types to categories for better classification."""
    category_map = {
        "ZeroDivisionError": "mathematical",
        "MemoryError": "resource",
        "TimeoutError": "network",
        "JSONDecodeError": "data",
    }
    return category_map.get(error_type, "unknown")


@app.route("/")
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


@app.route("/error/division")
def division_error():
    """Trigger ZeroDivisionError - Mathematical error."""
    try:
        # Intentional division by zero
        result = 10 / 0
        return jsonify({"result": result})
    except ZeroDivisionError as e:
        log_error(
            "ZeroDivisionError",
            "/error/division",
            e,
            {
                "user_agent": request.headers.get("User-Agent", "unknown"),
                "ip_address": request.remote_addr,
            },
        )
        return jsonify({"error": "Division by zero occurred"}), 500


@app.route("/error/memory")
def memory_error():
    """Trigger MemoryError - Resource error with safety limits."""
    allocated_chunks = []
    try:
        # Simulate memory exhaustion with safety limit (1GB max)
        max_memory_mb = 1024
        chunk_size = 10 * 1024 * 1024  # 10MB chunks

        for _i in range(max_memory_mb // 10):  # Safety limit
            chunk = bytearray(chunk_size)
            allocated_chunks.append(chunk)
            time.sleep(0.001)  # Small delay to prevent system lockup

        # If we get here, we've hit our safety limit
        raise MemoryError("Simulated memory exhaustion (safety limit reached)")

    except MemoryError as e:
        log_error(
            "MemoryError",
            "/error/memory",
            e,
            {
                "allocated_chunks": len(allocated_chunks),
                "total_memory_mb": len(allocated_chunks) * 10,
            },
        )
        return jsonify({"error": "Memory allocation failed"}), 500


@app.route("/error/timeout")
def timeout_error():
    """Trigger TimeoutError - Network error simulation."""
    try:
        # Simulate network timeout
        time.sleep(30)  # This will be interrupted by client timeout
        return jsonify({"result": "should_not_reach_here"})
    except Exception:
        # Simulate timeout error
        timeout_error = TimeoutError("Connection timeout after 30 seconds")
        log_error(
            "TimeoutError",
            "/error/timeout",
            timeout_error,
            {
                "timeout_seconds": 30,
                "user_agent": request.headers.get("User-Agent", "unknown"),
            },
        )
        return jsonify({"error": "Request timeout"}), 408


@app.route("/error/json")
def json_error():
    """Trigger JSONDecodeError - Data serialization error."""
    try:
        # Intentional JSON parsing error
        invalid_json = '{"invalid": json, "missing": quotes}'
        data = json.loads(invalid_json)
        return jsonify(data)
    except json.JSONDecodeError as e:
        log_error(
            "JSONDecodeError",
            "/error/json",
            e,
            {
                "invalid_json": '{"invalid": json, "missing": quotes}',
                "error_position": e.pos,
            },
        )
        return jsonify({"error": "JSON parsing failed"}), 400


@app.route("/status")
def status():
    """Service status endpoint for monitoring."""
    return jsonify(
        {
            "service": SERVICE_NAME,
            "version": SERVICE_VERSION,
            "status": "running",
            "endpoints": [
                "/",
                "/error/division",
                "/error/memory",
                "/error/timeout",
                "/error/json",
                "/status",
            ],
            "log_file": log_file,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
    )


if __name__ == "__main__":
    # Ensure log directory exists and log file is writable
    log_dir = Path("/tmp/sre-dogfooding")
    log_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(log_file, "a") as f:
            f.write("")
    except Exception as e:
        print(f"Warning: Could not create log file {log_file}: {e}")

    print(f"Starting {SERVICE_NAME} v{SERVICE_VERSION}")
    print(f"Log file: {log_file}")
    print("Available endpoints:")
    print("  GET / - Health check")
    print("  GET /error/division - ZeroDivisionError")
    print("  GET /error/memory - MemoryError (with safety limits)")
    print("  GET /error/timeout - TimeoutError")
    print("  GET /error/json - JSONDecodeError")
    print("  GET /status - Service status")

    app.run(host="0.0.0.0", port=5001, debug=False)
