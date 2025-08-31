# GEMINI.md - Gemini SRE Agent for Cloud Log Monitoring

This document provides a comprehensive overview of the Gemini SRE Agent project, intended as a reference for future development and interaction.

## Project Overview

**Project Name:** Gemini SRE Agent for Cloud Log Monitoring

**Purpose:** The Gemini SRE Agent is an autonomous system designed to monitor Google Cloud logs, detect anomalies, perform root cause analysis, and automate remediation actions by creating GitHub Pull Requests. It aims to enhance site reliability engineering by providing intelligent, automated responses to operational issues.

**Main Technologies:**
*   **Python:** The primary programming language.
*   **Google Cloud Platform (GCP):** Leverages various GCP services including Cloud Logging, Pub/Sub, and Vertex AI (for Gemini models).
*   **GitHub:** Integrates for automated Pull Request generation as part of remediation.
*   **`uv`:** A fast Python package installer and resolver, used for dependency management.
*   **`hyx`:** A Python library for implementing resilience patterns (circuit breakers, retries, bulkheads, rate limiting).
*   **`pytest`:** A testing framework for Python, used for unit and integration tests.
*   **Pydantic:** Used for defining and validating configuration models.

**Architecture:** The agent operates in a continuous, event-driven loop:
1.  **Log Ingestion:** Relevant logs from GCP services are exported to Pub/Sub topics.
2.  **Log Subscription:** The agent subscribes to these Pub/Sub topics, receiving log entries in real-time.
3.  **Triage Agent:** Incoming logs are processed by a `TriageAgent` (leveraging a Gemini Flash model) for rapid, preliminary analysis, identifying issues and generating `TriagePacket`s.
4.  **Analysis Agent:** The `TriagePacket` is then passed to an `AnalysisAgent` (employing a Gemini Pro model) for deep root cause analysis and the creation of detailed `RemediationPlan`s.
5.  **Remediation Agent:** The `RemediationAgent` automates the remediation process by interacting with GitHub to create new branches, commit proposed fixes, and submit Pull Requests for review and approval.

**Key Features:**
*   **Multi-Service Monitoring:** Configurable to monitor logs from multiple Google Cloud services, each potentially with its own Pub/Sub subscription and specific overrides for models or GitHub repositories.
*   **Intelligent Triage:** Utilizes Gemini Flash models for efficient initial assessment of log data.
*   **Deep Analysis & Remediation Planning:** Employs Gemini Pro models for comprehensive root cause analysis and actionable remediation strategies.
*   **Automated Pull Request Generation:** Streamlines the fix deployment process through direct GitHub integration.
*   **Resilience & Fault Tolerance:** Ensures system stability and reliability through integrated `hyx` patterns.
*   **Structured Logging:** Provides machine-readable JSON logs for enhanced observability and integration with log aggregation systems.
*   **Configurable:** Highly flexible configuration via YAML files, allowing customization of project details, model selection, GitHub integration, and logging settings.

## Building and Running

### Prerequisites
*   Python 3.12+
*   `uv` (recommended for package management)
*   Google Cloud Platform (GCP) project with Cloud Logging, Pub/Sub, and Vertex AI API enabled.
*   GCP Service Account with permissions for Logging Viewer, Pub/Sub Subscriber, and Vertex AI User.
*   GitHub Personal Access Token with `repo` scope for creating pull requests.

### Local Setup
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/avivl/gemini-sre-agent.git
    cd gemini-sre-agent
    ```
2.  **Install dependencies using `uv`:**
    ```bash
    uv sync
    ```
3.  **Authenticate with GCP:**
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_GCP_PROJECT_ID
    ```
4.  **Set up GitHub Token:**
    ```bash
    export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    ```
    *(For production, use Google Secret Manager or similar secure solution.)*

### Running Locally
To start the agent locally:
```bash
python main.py
```

### Deployment to Google Cloud Run (Example)

The `deploy.sh` script automates the containerization and deployment to Google Cloud Run.
1.  **Update `deploy.sh`:** Set `PROJECT_ID` and `REGION` variables within the script.
2.  **Execute the deployment script:**
    ```bash
    ./deploy.sh
    ```
    This script will:
    *   Build a Docker image (`Dockerfile`) of the application.
    *   Push the image to Google Container Registry (GCR).
    *   Deploy the image to Cloud Run, passing the `GITHUB_TOKEN` as an environment variable.

## Development Conventions

*   **Package Management:** Dependencies are managed using `uv` (specified in `pyproject.toml`).
*   **Testing:** Unit tests are written using `pytest` and `pytest-asyncio` (configured in `pyproject.toml` and demonstrated in `tests/`).
*   **Configuration:** Application settings are defined in `config/config.yaml` and loaded/validated using Pydantic models (`src/gemini_sre_agent/config.py`). The configuration supports global defaults and service-specific overrides for multi-service monitoring.
*   **Logging:** Structured logging is implemented using Python's `logging` module with a custom JSON formatter (`src/gemini_sre_agent/logger.py`), ensuring machine-readable logs in production and human-readable logs in development.
*   **Resilience:** The `hyx` library (`src/gemini_sre_agent/resilience.py`) is used to apply various resilience patterns to critical operations, enhancing the agent's robustness.
*   **Code Structure:** The codebase follows a modular design, separating concerns into distinct agent classes (e.g., `LogSubscriber`, `TriageAgent`, `AnalysisAgent`, `RemediationAgent`).
