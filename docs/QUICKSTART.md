# Quick Start Guide

This guide provides a rapid, 15-minute walkthrough to get the Cloud SRE Agent up and running with minimal effort. It's designed for users who want to quickly see the agent in action.

## 1. Prerequisites (Quick Check)

Ensure you have the following installed:

*   **Python 3.12+**
*   **`uv`** (recommended) or `pip`
*   **Cloud CLI tools** (authenticated to your cloud platform, e.g., `gcloud`, `aws`, `az`)
*   **GitHub Personal Access Token (PAT)** with `repo` scope

## 2. Clone the Repository

```bash
git clone https://github.com/avivl/cloud-sre-agent.git
cd cloud-sre-agent
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
    *   `cloud_sre_agent.services[0].project_id`: Your cloud platform project ID.
    *   `cloud_sre_agent.services[0].location`: Your cloud platform region (e.g., `us-central1`).
    *   `cloud_sre_agent.services[0].subscription_id`: The name of a messaging service subscription you will create (e.g., `my-test-logs-sub`).
    *   `cloud_sre_agent.default_github_config.repository`: Your GitHub test repository (e.g., `your-username/your-test-repo`).

    **Example `config/config.yaml` snippet:**
    ```yaml
    cloud_sre_agent:
      # ... other defaults ...
      services:
        - service_name: "quickstart-service"
          project_id: "your-actual-project-id"
          location: "us-central1"
          subscription_id: "my-test-logs-sub"
      default_github_config:
        repository: "your-github-username/your-test-repo"
        base_branch: "main"
    ```

## 5. Set Environment Variables

```bash
export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
# If you use a service account key file for cloud platform auth, you might also need:
# export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

## 6. Set up Cloud Infrastructure (Quick Setup)

Use the provided cloud setup scripts to quickly provision the necessary cloud platform resources. **Remember to update the variables inside the script before running it.**

1.  **Edit `infra/gcloud_setup.sh`:** Update `PROJECT_ID`, `LOG_TOPIC_NAME`, `LOG_SUBSCRIPTION_NAME`, etc., to match your `config.yaml` and desired names.
2.  **Make executable and run:**
    ```bash
    chmod +x infra/gcloud_setup.sh
    ./infra/gcloud_setup.sh
    ```
    This script will create a messaging service topic, subscription, service account, and a cloud logging sink that exports `ERROR` level logs to your messaging service topic.

## 7. Run the Agent Locally

```bash
python main.py
```

The agent will start listening for logs. To test it, generate some `ERROR` level logs in your configured cloud platform project (e.g., from a cloud function or a simple logging command).

```bash
gcloud logging write --severity=ERROR --project=YOUR_PROJECT_ID --payload-type=json quickstart-log '{"message": "This is a test error from quickstart!"}'
```

## 8. Verify Functionality

*   **Check Agent Logs:** Observe the agent's console output for messages indicating log processing, triage, and analysis.
*   **Check GitHub:** If the agent detects a remediable issue, it will create a branch and a Pull Request in your configured GitHub repository.

## 9. Cleanup (Optional)

To clean up the cloud platform resources created by the setup script:

```bash
# Delete messaging service subscription
gcloud pubsub subscriptions delete projects/YOUR_PROJECT_ID/subscriptions/YOUR_LOGS_SUBSCRIPTION_NAME
# Delete messaging service topic
gcloud pubsub topics delete projects/YOUR_PROJECT_ID/topics/YOUR_LOGS_TOPIC_NAME
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
*   [Cloud Platform Setup Guide](CLOUD_SETUP.md)
*   [Operations Runbook](OPERATIONS.md)
*   [Troubleshooting Guide](TROUBLESHOOTING.md)
