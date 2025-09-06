#!/usr/bin/env python3
"""
Test suite for Dogfooding Problem Service error endpoints.

Tests all 4 MVP error scenarios to ensure they produce the expected errors
and generate proper structured logs for SRE Agent ingestion.

All files must be under 250 LOC for maintainability.
"""

import json
import os

# Add the parent directory to the path to import the app
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import _get_error_category, app, log_error


class TestErrorEndpoints(unittest.TestCase):
    """Test error endpoint functionality."""

    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True

        # Create a temporary log file for testing
        self.temp_log = tempfile.NamedTemporaryFile(mode="w+", delete=False)
        self.temp_log.close()

        # Patch the log file path
        self.log_patcher = patch("app.log_file", self.temp_log.name)
        self.log_patcher.start()

    def tearDown(self):
        """Clean up test environment."""
        self.log_patcher.stop()
        if os.path.exists(self.temp_log.name):
            os.unlink(self.temp_log.name)

    def test_health_check(self):
        """Test the health check endpoint."""
        response = self.app.get("/")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "dogfood_service")
        self.assertEqual(data["version"], "1.0.0")

    def test_status_endpoint(self):
        """Test the status endpoint."""
        response = self.app.get("/status")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.data)
        self.assertEqual(data["service"], "dogfood_service")
        self.assertEqual(data["status"], "running")
        self.assertIn("endpoints", data)
        self.assertIn("log_file", data)

    def test_division_error(self):
        """Test division by zero error endpoint."""
        response = self.app.get("/error/division")
        self.assertEqual(response.status_code, 500)

        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("Division by zero", data["error"])

        # Check that error was logged
        self._verify_error_logged("ZeroDivisionError", "/error/division")

    def test_memory_error(self):
        """Test memory error endpoint."""
        response = self.app.get("/error/memory")
        self.assertEqual(response.status_code, 500)

        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("Memory allocation failed", data["error"])

        # Check that error was logged
        self._verify_error_logged("MemoryError", "/error/memory")

    def test_timeout_error(self):
        """Test timeout error endpoint."""
        # Use a short timeout for testing
        with patch("app.time.sleep", side_effect=Exception("Timeout simulation")):
            response = self.app.get("/error/timeout")
            self.assertEqual(response.status_code, 408)

        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("Request timeout", data["error"])

        # Check that error was logged
        self._verify_error_logged("TimeoutError", "/error/timeout")

    def test_json_error(self):
        """Test JSON parsing error endpoint."""
        response = self.app.get("/error/json")
        self.assertEqual(response.status_code, 400)

        data = json.loads(response.data)
        self.assertIn("error", data)
        self.assertIn("JSON parsing failed", data["error"])

        # Check that error was logged
        self._verify_error_logged("JSONDecodeError", "/error/json")

    def _verify_error_logged(self, expected_error_type: str, expected_endpoint: str):
        """Verify that an error was logged with correct structure."""
        with open(self.temp_log.name, "r") as f:
            log_content = f.read()

        # Find the last log entry
        log_lines = [line.strip() for line in log_content.split("\n") if line.strip()]
        if not log_lines:
            self.fail("No log entries found")

        last_entry = log_lines[-1]

        try:
            log_data = json.loads(last_entry)
        except json.JSONDecodeError:
            self.fail(f"Invalid JSON in log entry: {last_entry}")

        # Verify log structure
        self.assertEqual(log_data["level"], "ERROR")
        self.assertEqual(log_data["service"], "dogfood_service")
        self.assertEqual(log_data["error_type"], expected_error_type)
        self.assertEqual(log_data["endpoint"], expected_endpoint)
        self.assertIn("timestamp", log_data)
        self.assertIn("traceback", log_data)
        self.assertIn("context", log_data)
        self.assertIn("metadata", log_data)

        # Verify metadata
        metadata = log_data["metadata"]
        self.assertEqual(metadata["service_version"], "1.0.0")
        self.assertEqual(metadata["environment"], "dogfood")
        self.assertEqual(metadata["error_count"], 1)


class TestUtilityFunctions(unittest.TestCase):
    """Test utility functions."""

    def test_get_error_category(self):
        """Test error category mapping."""
        self.assertEqual(_get_error_category("ZeroDivisionError"), "mathematical")
        self.assertEqual(_get_error_category("MemoryError"), "resource")
        self.assertEqual(_get_error_category("TimeoutError"), "network")
        self.assertEqual(_get_error_category("JSONDecodeError"), "data")
        self.assertEqual(_get_error_category("UnknownError"), "unknown")

    def test_log_error_function(self):
        """Test the log_error function."""
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as temp_log:
            temp_log.close()

            with patch("app.log_file", temp_log.name):
                test_error = ValueError("Test error")
                log_error("ValueError", "/test", test_error, {"test": "context"})

                with open(temp_log.name, "r") as f:
                    log_content = f.read()

                log_data = json.loads(log_content.strip())
                self.assertEqual(log_data["error_type"], "ValueError")
                self.assertEqual(log_data["endpoint"], "/test")
                self.assertEqual(log_data["context"]["test"], "context")

            os.unlink(temp_log.name)


class TestErrorScenarios(unittest.TestCase):
    """Test complete error scenarios."""

    def setUp(self):
        """Set up test environment."""
        self.app = app.test_client()
        self.app.testing = True

    def test_all_error_endpoints_exist(self):
        """Test that all expected error endpoints exist."""
        endpoints = [
            "/error/division",
            "/error/memory",
            "/error/timeout",
            "/error/json",
        ]

        for endpoint in endpoints:
            response = self.app.get(endpoint)
            # Should return an error status (4xx or 5xx)
            self.assertGreaterEqual(response.status_code, 400)

    def test_error_endpoints_return_json(self):
        """Test that error endpoints return valid JSON."""
        endpoints = [
            "/error/division",
            "/error/memory",
            "/error/timeout",
            "/error/json",
        ]

        for endpoint in endpoints:
            response = self.app.get(endpoint)
            # Should be able to parse as JSON
            data = json.loads(response.data)
            self.assertIn("error", data)


if __name__ == "__main__":
    unittest.main()
