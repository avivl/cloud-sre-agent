from unittest.mock import patch

import pytest


@pytest.fixture(scope="session")
def mock_integration_config():
    """Provide mock config for integration tests when real config is unavailable"""
    return {
        "gemini_cloud_log_monitor": {
            "services": [
                {
                    "project_id": "test-project",
                    "location": "us-central1",
                    "service_name": "test-service",
                    "subscription_id": "test-subscription",
                }
            ],
            "default_model_selection": {
                "triage_model": "gemini-1.5-flash",
                "analysis_model": "gemini-1.5-pro",
                "classification_model": "gemini-2.5-flash-lite",
            },
            "default_github_config": {"repository": "test/repo", "base_branch": "main"},
        }
    }
