# Setup and Installation Guide

This guide provides comprehensive instructions for setting up and installing the Cloud SRE Agent. Follow these steps to get the project up and running in your environment across multiple cloud platforms and AI providers.

## Prerequisites

Before you begin, ensure you have the following installed and configured:

*   **Python 3.12+:** The agent is developed and tested with Python 3.12 and later versions.
    *   [Download Python](https://www.python.org/downloads/)
*   **`uv` (recommended) or `pip`:** For efficient Python package management.
    *   [Install `uv`](https://astral.sh/blog/uv-a-new-python-package-installer)
    *   **Note:** Core dependencies including `pyyaml`, `pydantic`, `hyx`, `tenacity`, `PyGithub`, `litellm`, and cloud-specific packages will be installed automatically by `uv sync`.
*   **Cloud Platform Access:** You need access to one or more cloud platforms with the following services enabled:
    *   **Google Cloud Platform (GCP):**
        *   **Cloud Logging API:** To collect and export logs.
        *   **Pub/Sub API:** To stream log data in real-time.
        *   **Vertex AI API:** To access Google's AI models.
        *   **Service Account:** A GCP Service Account with the necessary permissions.
    *   **Amazon Web Services (AWS):**
        *   **CloudWatch Logs:** To collect and export logs.
        *   **Kinesis Data Streams:** To stream log data in real-time.
        *   **IAM Role:** An AWS IAM role with the necessary permissions.
    *   **Microsoft Azure:**
        *   **Azure Monitor:** To collect and export logs.
        *   **Event Hubs:** To stream log data in real-time.
        *   **Service Principal:** An Azure service principal with the necessary permissions.
    *   **Kubernetes:**
        *   **Cluster Access:** Access to Kubernetes cluster for log collection.
        *   **RBAC Permissions:** Appropriate RBAC permissions for log access.
*   **AI Provider API Keys:** You need API keys for one or more AI providers:
    *   **OpenAI:** [Get OpenAI API Key](https://platform.openai.com/api-keys)
    *   **Anthropic:** [Get Anthropic API Key](https://console.anthropic.com/)
    *   **Google AI:** [Get Google AI API Key](https://makersuite.google.com/app/apikey)
    *   **Cohere:** [Get Cohere API Key](https://dashboard.cohere.ai/api-keys)
    *   **Ollama:** [Install Ollama](https://ollama.ai/) for local models
*   **GitHub Personal Access Token (PAT):** A GitHub PAT with `repo` scope is required for the `RemediationAgent` to create branches, commit changes, and open pull requests in your repositories.
    *   [Create a GitHub PAT](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)

## Cloud Infrastructure Setup

Before running the agent, you need to set up the necessary cloud infrastructure for your chosen platforms. Refer to the following guides for detailed instructions:

*   **Google Cloud Platform:** [GCP Infrastructure Setup Guide](GCP_SETUP.md)
*   **Amazon Web Services:** [AWS Infrastructure Setup Guide](AWS_SETUP.md) (coming soon)
*   **Microsoft Azure:** [Azure Infrastructure Setup Guide](AZURE_SETUP.md) (coming soon)
*   **Kubernetes:** [Kubernetes Setup Guide](K8S_SETUP.md) (coming soon)

## Local Setup

Follow these steps to set up the Cloud SRE Agent on your local machine:

1.  **Clone the repository:**
    Begin by cloning the project repository to your local machine:
    ```bash
    git clone https://github.com/avivl/cloud-sre-agent.git
    cd cloud-sre-agent
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
