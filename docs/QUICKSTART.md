# Quick Start Guide

This guide provides a rapid, 15-minute walkthrough to get the Gemini SRE Agent up and running with minimal effort. It's designed for users who want to quickly see the agent in action.

## 1. Prerequisites (Quick Check)

Ensure you have the following installed:

*   **Python 3.12+**
*   **`uv`** (recommended) or `pip`
*   **`gcloud` CLI** (authenticated to your GCP project)
*   **GitHub Personal Access Token (PAT)** with `repo` scope

## 2. Clone the Repository

```bash
git clone https://github.com/avivl/gemini-sre-agent.git
cd gemini-sre-agent
```

## 3. Install Dependencies

```bash
uv sync
```

## 4. Prepare Configuration

1.  **Copy the example configuration:**
    ```bash
    cp config/example.config.yaml config/config.yaml
    ```
2.  **Edit `config/config.yaml`:**
    Open `config/config.yaml` and update the following placeholders with your actual values:
    *   `gemini_cloud_log_monitor.services[0].project_id`: Your GCP Project ID.
    *   `gemini_cloud_log_monitor.services[0].location`: Your GCP region (e.g., `us-central1`).
    *   `gemini_cloud_log_monitor.services[0].subscription_id`: The name of a Pub/Sub subscription you will create (e.g., `my-test-logs-sub`).
    *   `gemini_cloud_log_monitor.default_github_config.repository`: Your GitHub test repository (e.g., `your-username/your-test-repo`).

    **Example `config/config.yaml` snippet:**
    ```yaml
    gemini_cloud_log_monitor:
      # ... other defaults ...
      services:
        - service_name: "quickstart-service"
          project_id: "your-actual-gcp-project-id"
          location: "us-central1"
          subscription_id: "my-test-logs-sub"
      default_github_config:
        repository: "your-github-username/your-test-repo"
        base_branch: "main"
    ```

## 5. Set Environment Variables

```bash
export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
# If you use a service account key file for gcloud auth, you might also need:
# export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

## 6. Set up GCP Infrastructure (Quick Setup)

Use the provided `gcloud_setup.sh` script to quickly provision the necessary GCP resources. **Remember to update the variables inside the script before running it.**

1.  **Edit `infra/gcloud_setup.sh`:** Update `PROJECT_ID`, `LOG_TOPIC_NAME`, `LOG_SUBSCRIPTION_NAME`, etc., to match your `config.yaml` and desired names.
2.  **Make executable and run:**
    ```bash
    chmod +x infra/gcloud_setup.sh
    ./infra/gcloud_setup.sh
    ```
    This script will create a Pub/Sub topic, subscription, service account, and a Cloud Logging sink that exports `ERROR` level logs to your Pub/Sub topic.

## 7. Run the Agent Locally

```bash
python main.py
```

The agent will start listening for logs. To test it, generate some `ERROR` level logs in your configured GCP project (e.g., from a Cloud Function or a simple `gcloud logging write` command).

```bash
gcloud logging write --severity=ERROR --project=YOUR_GCP_PROJECT_ID --payload-type=json quickstart-log '{"message": "This is a test error from quickstart!"}'
```

## 8. Verify Functionality

*   **Check Agent Logs:** Observe the agent's console output for messages indicating log processing, triage, and analysis.
*   **Check GitHub:** If the agent detects a remediable issue, it will create a new branch and a Pull Request in your configured GitHub repository.

## 9. Cleanup (Optional)

To clean up the GCP resources created by the `gcloud_setup.sh` script:

```bash
# Delete Pub/Sub subscription
gcloud pubsub subscriptions delete projects/YOUR_GCP_PROJECT_ID/subscriptions/YOUR_LOGS_SUBSCRIPTION_NAME
# Delete Pub/Sub topic
gcloud pubsub topics delete projects/YOUR_GCP_PROJECT_ID/topics/YOUR_LOGS_TOPIC_NAME
# Delete Logging Sink
gcloud logging sinks delete YOUR_SINK_NAME
# Delete Service Account (be careful with this!)
gcloud iam service-accounts delete YOUR_AGENT_SERVICE_ACCOUNT_EMAIL
```

This completes the quick start. For more detailed information, refer to the full documentation:

*   [Architecture Overview](ARCHITECTURE.md)
*   [Setup and Installation Guide](SETUP_INSTALLATION.md)
*   [Configuration Guide](CONFIGURATION.md)
*   [Deployment Guide](DEPLOYMENT.md)
*   [Development Guide](DEVELOPMENT.md)
*   [GCP Infrastructure Setup Guide](GCP_SETUP.md)
*   [Operations Runbook](OPERATIONS.md)
*   [Troubleshooting Guide](TROUBLESHOOTING.md)
