# Infrastructure as Code Guide

This guide provides comprehensive instructions and examples for provisioning the necessary Google Cloud Platform (GCP) infrastructure for the Cloud SRE Agent using Infrastructure as Code (IaC) tools. Consistent and automated infrastructure deployment is crucial for operational readiness.

## Prerequisites

Before deploying the infrastructure, ensure you have:

*   **Google Cloud Project:** An active GCP project with billing enabled.
*   **`gcloud` CLI:** Authenticated and configured for your project.
*   **Terraform CLI (v1.0+):** If you choose to use Terraform.
    *   [Install Terraform](https://developer.hashicorp.com/terraform/downloads)
*   **Pulumi CLI (v3.0+):** If you choose to use Pulumi.
    *   [Install Pulumi](https://www.pulumi.com/docs/get-started/install/)
*   **Python 3.12+ and `uv`:** For Pulumi Python environment setup.

## Terraform Configuration

Terraform configurations are located in the `infra/terraform/` directory. These files define the GCP resources required for the Cloud SRE Agent.

### Files Overview

*   `versions.tf`: Specifies the required Terraform and Google Cloud provider requirements.
*   `variables.tf`: Defines input variables for the configuration (e.g., `gcp_project_id`, `gcp_region`).
*   `main.tf`: Contains the core resource definitions for Pub/Sub, Cloud Logging Sinks, Service Accounts, and IAM policies.
*   `outputs.tf`: Defines output values that can be used by other configurations or for quick reference.

### Resources Provisioned

*   **Pub/Sub Topic (`google_pubsub_topic.logs_topic`):** A dedicated topic for receiving log exports from Cloud Logging.
*   **Pub/Sub Subscription (`google_pubsub_subscription.logs_subscription`):** A subscription to the `logs_topic` that the Cloud SRE Agent will consume messages from.
*   **Service Account for Agent (`google_service_account.agent_sa`):** A dedicated service account for the Cloud SRE Agent application.
*   **IAM Permissions for Agent Service Account:** Grants the agent's service account necessary roles:
    *   `roles/pubsub.subscriber`
    *   `roles/aiplatform.user`
    *   `roles/logging.viewer`
*   **Cloud Logging Sink (`google_logging_project_sink.logs_sink`):** Configures a sink to export logs matching a specified filter (default: `severity>=ERROR`) to the `logs_topic`.
*   **IAM Permissions for Logging Sink Writer Identity:** Grants the automatically created Logging Sink writer identity the `roles/pubsub.publisher` role on the `logs_topic`.

### Deployment Steps (Terraform)

1.  **Navigate to the Terraform directory:**
    ```bash
    cd infra/terraform
    ```
2.  **Initialize Terraform:**
    ```bash
    terraform init
    ```
3.  **Review the plan:**
    ```bash
    terraform plan -var="gcp_project_id=YOUR_GCP_PROJECT_ID"
    ```
    Replace `YOUR_GCP_PROJECT_ID` with your actual GCP project ID. Review the proposed changes carefully.
4.  **Apply the changes:**
    ```bash
    terraform apply -var="gcp_project_id=YOUR_GCP_PROJECT_ID"
    ```
    Confirm with `yes` when prompted.

## Pulumi Configuration

Pulumi configurations are located in the `infra/pulumi/` directory. These Python-based programs define the same GCP resources as the Terraform setup.

### Files Overview

*   `Pulumi.yaml`: Pulumi project definition file.
*   `requirements.txt`: Python dependencies for the Pulumi program.
*   `__main__.py`: The main Pulumi program defining the resources.

### Resources Provisioned

(Same as Terraform section, as they provision identical resources)

### Deployment Steps (Pulumi)

1.  **Navigate to the Pulumi directory:**
    ```bash
    cd infra/pulumi
    ```
2.  **Install Python dependencies:**
    ```bash
    uv sync # or pip install -r requirements.txt
    ```
3.  **Initialize Pulumi stack:**
    ```bash
    pulumi stack init dev # or a suitable stack name
    ```
4.  **Configure Pulumi:**
    ```bash
    pulumi config set gcp:project YOUR_GCP_PROJECT_ID
    pulumi config set gcp:region us-central1 # or your desired region
    ```
5.  **Review the plan:**
    ```bash
    pulumi preview
    ```
6.  **Deploy the infrastructure:**
    ```bash
    pulumi up
    ```
    Confirm with `yes` when prompted.

## Resource Validation

After deploying the infrastructure, you can verify the resources using the `gcloud` CLI or the GCP Console:

*   **Pub/Sub Topic:**
    ```bash
    gcloud pubsub topics describe gemini-sre-logs --project=YOUR_GCP_PROJECT_ID
    ```
*   **Pub/Sub Subscription:**
    ```bash
    gcloud pubsub subscriptions describe gemini-sre-logs-sub --project=YOUR_GCP_PROJECT_ID
    ```
*   **Service Account:**
    ```bash
    gcloud iam service-accounts describe gemini-sre-agent-sa@YOUR_GCP_PROJECT_ID.iam.gserviceaccount.com
    ```
*   **Logging Sink:**
    ```bash
    gcloud logging sinks describe gemini-sre-log-sink --project=YOUR_GCP_PROJECT_ID
    ```

## Cost Estimation and Resource Optimization

(This section would discuss how to estimate costs for the provisioned resources and strategies for optimizing them, e.g., Pub/Sub message retention, log filter granularity. This is a placeholder for future expansion.)

## Automated Deployment Scripts with Validation

(This section would detail how to integrate these IaC deployments into CI/CD pipelines, including validation steps. This is a placeholder for future expansion.)
