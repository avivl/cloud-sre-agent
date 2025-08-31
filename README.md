# Gemini SRE Agent for Cloud Log Monitoring
[![GitHub Stars](https://img.shields.io/github/stars/avivl/claude-007-agents?style=for-the-badge&logo=github&color=gold)](https://github.com/avivl/gemini-sre-agent/stargazers)
[![Last Commit](https://img.shields.io/github/last-commit/avivl/gemini-sre-agent?style=for-the-badge&logo=github)](https://github.com/avivl/gemini-sre-agent/commits/main)
[![License](https://img.shields.io/badge/License-MIT-blue?style=for-the-badge)](LICENSE)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-886FBF?logo=googlegemini&logoColor=fff)](#)
The Gemini SRE Agent is an autonomous system designed to monitor Google Cloud logs, detect anomalies, perform root cause analysis, and automate remediation actions by creating GitHub Pull Requests. It leverages Google's Gemini models for intelligent triage and analysis, and is built with resilience patterns using the `hyx` library.

## Features

*   **Multi-Service Monitoring:** Configure the agent to monitor logs from multiple Google Cloud services, each with its own Pub/Sub subscription.
*   **Intelligent Triage:** Uses Gemini Flash models for rapid, preliminary analysis of log entries, identifying issues and assigning severity.
*   **Deep Analysis & Remediation Planning:** Employs Gemini Pro models for in-depth root cause analysis and generates detailed remediation plans, including code and Infrastructure as Code (IaC) patches.
*   **Automated Pull Request Generation:** Integrates with GitHub to automatically create pull requests for proposed fixes, enabling a human-in-the-loop review process.
*   **Resilience & Fault Tolerance:** Implements circuit breakers, retries, bulkheads, and rate limiting using the `hyx` library to ensure stability and reliability.
*   **Structured Logging:** Produces machine-readable JSON logs in production for easy integration with log aggregation and analysis systems.
*   **Configurable:** Flexible configuration via YAML files for project details, model selection, GitHub integration, and logging.

## Architecture Overview

The agent operates in a continuous loop:

1.  **Log Ingestion:** Google Cloud Logging exports relevant logs to Pub/Sub topics.
2.  **Log Subscription:** The agent subscribes to these Pub/Sub topics, receiving log entries in real-time.
3.  **Triage:** Incoming logs are fed to a Gemini Flash model for quick assessment and `TriagePacket` generation.
4.  **Analysis:** The `TriagePacket` is passed to a Gemini Pro model for deep root cause analysis and `RemediationPlan` creation.
5.  **Remediation:** The `RemediationPlan` is used to generate and submit a GitHub Pull Request with the proposed fix.

## Setup and Installation

### Prerequisites

*   Python 3.12+
*   `uv` (or `pip`) for package management
*   Google Cloud Platform (GCP) project with:
    *   Cloud Logging enabled
    *   Pub/Sub enabled (with subscriptions configured for log exports)
    *   Vertex AI API enabled
    *   Service Account with necessary permissions (Logging Viewer, Pub/Sub Subscriber, Vertex AI User)
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
    (Alternatively, using `pip`: `pip install -r requirements.txt`)

3.  **Authenticate with GCP:**
    Ensure your `gcloud` CLI is authenticated and configured for your project.
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_GCP_PROJECT_ID
    ```

4.  **Set up GitHub Token:**
    Export your GitHub Personal Access Token as an environment variable:
    ```bash
    export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    ```
    **Note:** For production, use a secure secrets management solution like Google Secret Manager.

## Configuration

The agent's behavior is controlled by the `config/config.yaml` file.

```yaml
# config/config.yaml
gemini_cloud_log_monitor:
  default_model_selection:
    triage_model: "gemini-1.5-flash-001"
    analysis_model: "gemini-1.5-pro-001"
    classification_model: "gemini-2.5-flash-lite"

  default_github_config:
    repository: "owner/repo"
    base_branch: "main"

  logging:
    log_level: "INFO"
    json_format: false
    log_file: null # e.g., "/var/log/gemini-sre-agent.log"

  services:
    - service_name: "billing-service"
      project_id: "your-gcp-project"
      location: "us-central1"
      subscription_id: "billing-logs-subscription"
      # Optional: Override default model_selection or github for this service
      # model_selection:
      #   triage_model: "gemini-1.5-flash-special"
      # github:
      #   repository: "owner/billing-repo" # Can be a different repo for this service

    - service_name: "auth-service"
      project_id: "your-gcp-project"
      location: "us-central1"
      subscription_id: "auth-logs-subscription"
      # This service will use default_model_selection and default_github_config
```

*   **`default_model_selection`**: Global default Gemini models for triage, analysis, and classification.
*   **`default_github_config`**: Global default GitHub repository and base branch for PRs.
*   **`logging`**: Global logging settings.
    *   `log_level`: Minimum level to log (DEBUG, INFO, WARN, ERROR, FATAL).
    *   `json_format`: Set to `true` for JSON output (recommended for production).
    *   `log_file`: Path to a log file. If `null`, logs go to console.
*   **`services`**: A list of service configurations to monitor.
    *   `service_name`: A unique name for the service being monitored.
    *   `project_id`: The GCP project ID where the service's logs reside.
    *   `location`: The GCP region for Vertex AI model interactions.
    *   `subscription_id`: The Pub/Sub subscription ID from which to pull logs for this service.
    *   `model_selection` (optional): Override global model settings for this specific service.
    *   `github` (optional): Override global GitHub settings for this specific service (e.g., if a service's fixes go to a different repository).

## Running the Agent

### Locally

```bash
python main.py
```

### Deployment to Google Cloud Run (Example)

The `deploy.sh` script provides an example of how to containerize and deploy the agent to Google Cloud Run.

1.  **Ensure `gcloud` CLI is configured for your project.**
2.  **Set `PROJECT_ID` and `REGION` in `deploy.sh`.**
3.  **Run the deployment script:**
    ```bash
    ./deploy.sh
    ```
    This script will:
    *   Build a Docker image of the application.
    *   Push the image to Google Container Registry (GCR).
    *   Deploy the image to Cloud Run, setting the `GITHUB_TOKEN` environment variable.

## Development

### Running Tests

```bash
uv run pytest
# or
pytest
```

### Code Style and Linting

(Add instructions for linting and code formatting tools if used, e.g., `ruff check .`, `black .`)

## Contributing

(Standard contributing guidelines)

## License

(License information)
