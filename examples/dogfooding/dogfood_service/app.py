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
        "FileNotFoundError": "filesystem",
        "PermissionError": "security",
        "ConnectionError": "network",
        "ValueError": "validation",
        "KeyError": "data",
        "AttributeError": "code",
        "ImportError": "dependency",
        "OSError": "system",
        "TypeError": "code",
        "IndexError": "data",
        "RecursionError": "code",
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


@app.route("/error/file")
def file_error():
    """Trigger FileNotFoundError - Filesystem error."""
    try:
        # Try to read a non-existent file
        with open("/tmp/non_existent_file.txt", "r") as f:
            content = f.read()
        return jsonify({"content": content})
    except FileNotFoundError as e:
        log_error(
            "FileNotFoundError",
            "/error/file",
            e,
            {
                "file_path": "/tmp/non_existent_file.txt",
                "operation": "read",
            },
        )
        return jsonify({"error": "File not found"}), 404


@app.route("/error/permission")
def permission_error():
    """Trigger PermissionError - Security error."""
    try:
        # Try to write to a protected directory
        with open("/root/protected_file.txt", "w") as f:
            f.write("test")
        return jsonify({"message": "File written successfully"})
    except PermissionError as e:
        log_error(
            "PermissionError",
            "/error/permission",
            e,
            {
                "file_path": "/root/protected_file.txt",
                "operation": "write",
            },
        )
        return jsonify({"error": "Permission denied"}), 403


@app.route("/error/connection")
def connection_error():
    """Trigger ConnectionError - Network connectivity error."""
    try:
        import socket

        # Try to connect to a non-existent service
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("192.168.1.999", 9999))  # Invalid IP and port
        sock.close()
        return jsonify({"message": "Connection successful"})
    except (ConnectionError, OSError) as e:
        log_error(
            "ConnectionError",
            "/error/connection",
            e,
            {
                "target_host": "192.168.1.999",
                "target_port": 9999,
                "timeout": 1,
            },
        )
        return jsonify({"error": "Connection failed"}), 503


@app.route("/error/validation")
def validation_error():
    """Trigger ValueError - Data validation error."""
    try:
        # Try to convert invalid string to int
        invalid_number = "not_a_number"
        result = int(invalid_number)
        return jsonify({"result": result})
    except ValueError as e:
        log_error(
            "ValueError",
            "/error/validation",
            e,
            {
                "invalid_input": "not_a_number",
                "expected_type": "int",
            },
        )
        return jsonify({"error": "Invalid input format"}), 400


@app.route("/error/key")
def key_error():
    """Trigger KeyError - Missing dictionary key error."""
    try:
        data = {"name": "test", "version": "1.0"}
        # Try to access non-existent key
        result = data["missing_key"]
        return jsonify({"result": result})
    except KeyError as e:
        log_error(
            "KeyError",
            "/error/key",
            e,
            {
                "missing_key": "missing_key",
                "available_keys": list(data.keys()),
            },
        )
        return jsonify({"error": "Key not found"}), 400


@app.route("/error/attribute")
def attribute_error():
    """Trigger AttributeError - Code structure error."""
    try:
        # Try to call non-existent method
        data = {"name": "test"}
        result = data.non_existent_method()
        return jsonify({"result": result})
    except AttributeError as e:
        log_error(
            "AttributeError",
            "/error/attribute",
            e,
            {
                "object_type": "dict",
                "missing_attribute": "non_existent_method",
            },
        )
        return jsonify({"error": "Attribute not found"}), 500


@app.route("/error/import")
def import_error():
    """Trigger ImportError - Dependency error."""
    try:
        # Try to import non-existent module
        import non_existent_module

        return jsonify({"message": "Module imported successfully"})
    except ImportError as e:
        log_error(
            "ImportError",
            "/error/import",
            e,
            {
                "module_name": "non_existent_module",
                "error_type": "module_not_found",
            },
        )
        return jsonify({"error": "Module not found"}), 500


@app.route("/error/type")
def type_error():
    """Trigger TypeError - Type mismatch error."""
    try:
        # Try to add string and integer
        result = "hello" + 123
        return jsonify({"result": result})
    except TypeError as e:
        log_error(
            "TypeError",
            "/error/type",
            e,
            {
                "left_type": "str",
                "right_type": "int",
                "operation": "addition",
            },
        )
        return jsonify({"error": "Type mismatch"}), 400


@app.route("/error/index")
def index_error():
    """Trigger IndexError - Array access error."""
    try:
        # Try to access non-existent array index
        data = [1, 2, 3]
        result = data[10]
        return jsonify({"result": result})
    except IndexError as e:
        log_error(
            "IndexError",
            "/error/index",
            e,
            {
                "list_length": len(data),
                "requested_index": 10,
            },
        )
        return jsonify({"error": "Index out of range"}), 400


@app.route("/error/recursion")
def recursion_error():
    """Trigger RecursionError - Infinite recursion error."""
    try:

        def infinite_recursion(n):
            return infinite_recursion(n + 1)

        result = infinite_recursion(0)
        return jsonify({"result": result})
    except RecursionError as e:
        log_error(
            "RecursionError",
            "/error/recursion",
            e,
            {
                "function_name": "infinite_recursion",
                "recursion_depth": "exceeded_limit",
            },
        )
        return jsonify({"error": "Maximum recursion depth exceeded"}), 500


@app.route("/error/database")
def database_error():
    """Trigger database-like error simulation."""
    try:
        # Simulate database connection failure
        raise OSError("Database connection failed: Connection refused")
    except OSError as e:
        log_error(
            "OSError",
            "/error/database",
            e,
            {
                "error_type": "database_connection",
                "database_host": "localhost",
                "database_port": 5432,
            },
        )
        return jsonify({"error": "Database connection failed"}), 503


@app.route("/error/rate_limit")
def rate_limit_error():
    """Trigger rate limiting error simulation."""
    try:
        # Simulate rate limiting
        raise Exception("Rate limit exceeded: 100 requests per minute")
    except Exception as e:
        log_error(
            "RateLimitError",
            "/error/rate_limit",
            e,
            {
                "error_type": "rate_limit",
                "limit": "100 requests per minute",
                "retry_after": 60,
            },
        )
        return jsonify({"error": "Rate limit exceeded", "retry_after": 60}), 429


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
                "/error/file",
                "/error/permission",
                "/error/connection",
                "/error/validation",
                "/error/key",
                "/error/attribute",
                "/error/import",
                "/error/type",
                "/error/index",
                "/error/recursion",
                "/error/database",
                "/error/rate_limit",
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
    print("  GET /error/file - FileNotFoundError")
    print("  GET /error/permission - PermissionError")
    print("  GET /error/connection - ConnectionError")
    print("  GET /error/validation - ValueError")
    print("  GET /error/key - KeyError")
    print("  GET /error/attribute - AttributeError")
    print("  GET /error/import - ImportError")
    print("  GET /error/type - TypeError")
    print("  GET /error/index - IndexError")
    print("  GET /error/recursion - RecursionError")
    print("  GET /error/database - Database connection error")
    print("  GET /error/rate_limit - Rate limiting error")
    print("  GET /status - Service status")

    app.run(host="0.0.0.0", port=5001, debug=False)
