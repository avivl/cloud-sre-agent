# Setup and Installation Guide

This guide provides comprehensive instructions for setting up and installing the Gemini SRE Agent. Follow these steps to get the project up and running in your environment.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Python 3.12+:** The agent is developed and tested with Python 3.12 and later versions.
    *   [Download Python](https://www.python.org/downloads/)
*   **`uv` (recommended) or `pip`:** For efficient Python package management.
    *   [Install `uv`](https://astral.sh/blog/uv-a-new-python-package-installer)
*   **Google Cloud Platform (GCP) Project:** You need an active GCP project with the following services enabled:
    *   **Cloud Logging API:** To collect and export logs.
    *   **Pub/Sub API:** To stream log data in real-time. Ensure you have Pub/Sub topics and subscriptions configured for your log exports.
    *   **Vertex AI API:** To access Google's Gemini models for AI analysis.
    *   **Service Account:** A GCP Service Account with the necessary permissions:
        *   `Logging Viewer` (roles/logging.viewer): To read log entries.
        *   `Pub/Sub Subscriber` (roles/pubsub.subscriber): To pull messages from Pub/Sub subscriptions.
        *   `Vertex AI User` (roles/aiplatform.user): To interact with Vertex AI models.
*   **GitHub Personal Access Token (PAT):** A GitHub PAT with `repo` scope is required for the `RemediationAgent` to create branches, commit changes, and open pull requests in your repositories.
    *   [Create a GitHub PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

## Local Setup

Follow these steps to set up the Gemini SRE Agent on your local machine:

1.  **Clone the repository:**
    Begin by cloning the project repository to your local machine:
    ```bash
    git clone https://github.com/avivl/gemini-sre-agent.git
    cd gemini-sre-agent
    ```

2.  **Install dependencies:**
    It is highly recommended to use `uv` for faster and more reliable dependency management. Navigate to the project root and run:
    ```bash
    uv sync
    ```
    If you prefer using `pip`, you can install dependencies from `requirements.txt` (which can be generated from `pyproject.toml`):
    ```bash
    pip install -r requirements.txt
    ```

3.  **Authenticate with GCP:**
    The agent needs to authenticate with your GCP project to access Cloud Logging, Pub/Sub, and Vertex AI. Use the `gcloud` CLI to set up Application Default Credentials:
    ```bash
    gcloud auth application-default login
    gcloud config set project YOUR_GCP_PROJECT_ID
    ```
    Replace `YOUR_GCP_PROJECT_ID` with your actual Google Cloud Project ID.

4.  **Set up GitHub Token:**
    The `RemediationAgent` requires a GitHub Personal Access Token to interact with your GitHub repositories. For local development, you can export it as an environment variable:
    ```bash
    export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    ```
    **Important:** Never hardcode sensitive tokens directly into your code. For production deployments, always use a secure secrets management solution like Google Secret Manager.

## Next Steps

Once the local setup is complete, proceed to the [Configuration Guide](CONFIGURATION.md) to tailor the agent's behavior to your specific monitoring needs.
