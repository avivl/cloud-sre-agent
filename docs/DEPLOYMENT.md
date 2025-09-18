# Deployment Guide

This guide provides instructions for deploying the Cloud SRE Agent to various cloud platforms and container orchestration systems. While Google Cloud Run is the recommended deployment target for its simplicity and scalability, the provided `Dockerfile` allows for deployment to other platforms like Google Kubernetes Engine (GKE), Amazon ECS, Azure Container Instances, or custom environments.

## Deployment Flow Overview

The deployment process follows a straightforward containerization and Cloud Run deployment pattern:

```mermaid
flowchart TB
    subgraph "Development Environment"
        DEV[Developer Workstation]
        CODE[Application Code]
        CONFIG[config.yaml]
        DOCKER[Dockerfile]
    end
    
    subgraph "Build Process"
        BUILD[Docker Build]
        IMAGE[Docker Image]
        TAG[Tag Image]
    end
    
    subgraph "Cloud Platform"
        GCR[Container Registry]
        CR[Cloud Service]
        SM[Secret Manager]
        LOGS[Cloud Logging]
    end
    
    subgraph "External Services"
        GITHUB[GitHub Repository]
        AI[AI Models]
        MSG[Messaging Service]
    end
    
    DEV --> BUILD
    CODE --> BUILD
    CONFIG --> BUILD
    DOCKER --> BUILD
    
    BUILD --> IMAGE
    IMAGE --> TAG
    TAG --> GCR
    
    GCR --> CR
    SM --> |Secrets| CR
    CR --> LOGS
    
    CR <--> |Pull Requests| GITHUB
    CR <--> |Model Inference| AI
    CR <--> |Log Messages| MSG
    
    classDef dev fill:#e3f2fd,stroke:#1976d2,stroke-width:2px
    classDef build fill:#fff3e0,stroke:#f57c00,stroke-width:2px
    classDef gcp fill:#e8f5e8,stroke:#388e3c,stroke-width:2px
    classDef external fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
    
    class DEV,CODE,CONFIG,DOCKER dev
    class BUILD,IMAGE,TAG build
    class GCR,CR,SM,LOGS gcp
    class GITHUB,AI,MSG external
```

## Containerization with Docker

The agent is packaged as a Docker image, ensuring a consistent and isolated runtime environment. The `Dockerfile` defines the steps to build this image:

```dockerfile
FROM python:3.12-slim-bookworm

WORKDIR /app

# Install uv
RUN pip install uv

# Copy dependency files
COPY pyproject.toml /app/

# Install dependencies
RUN uv sync

# Copy application code
COPY . /app

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "main.py"]
```

**Key aspects of the Dockerfile:**
*   **Base Image:** Uses `python:3.12-slim-bookworm` for a lightweight Python environment.
*   **Dependency Management:** Installs `uv` and then uses `uv sync` to install project dependencies defined in `pyproject.toml`.
*   **Non-Root User:** Creates a dedicated `appuser` and switches to it for security, following best practices for containerized applications.
*   **Entrypoint:** Sets `CMD ["python", "main.py"]` to run the main application script when the container starts.

## Deployment to Cloud Platforms

The Cloud SRE Agent can be deployed to various cloud platforms. Google Cloud Run is recommended for its event-driven nature (triggered by messaging services), automatic scaling (including scaling to zero when idle), and fully managed environment.

The `deploy.sh` script automates the process of building the Docker image, pushing it to a container registry, and deploying it to your chosen cloud platform.

### `deploy.sh` Script

```bash
#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
PROJECT_ID="your-project-id" # Replace with your project ID
SERVICE_NAME="cloud-sre-agent"
REGION="us-central1" # Choose your desired region
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# --- Build Docker Image ---
echo "Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

# --- Push Docker Image to Container Registry ---
echo "Pushing Docker image to container registry..."
docker push "${IMAGE_NAME}"

# --- Deploy to Cloud Platform ---
echo "Deploying to cloud platform..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --region "${REGION}" \
  --platform "managed" \
  --allow-unauthenticated \
  --project "${PROJECT_ID}" \
  --set-env-vars="GITHUB_TOKEN=${GITHUB_TOKEN}" \
  # Add other environment variables as needed, e.g., for specific service configs
  # --set-env-vars="SERVICE_CONFIG_PATH=/app/config/config.yaml" \
  # --update-secrets="GITHUB_TOKEN=GITHUB_TOKEN:latest" # Example for Secret Manager

echo "Deployment to Cloud Run complete!"
echo "Service URL: $(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID} --format='value(status.url)')"
```

### Deployment Steps

1.  **Configure `deploy.sh`:**
    Open `deploy.sh` and replace `"your-project-id"` with your actual project ID. Adjust `REGION` if desired.

2.  **Ensure cloud CLI is configured:**
    Make sure your cloud command-line tool (e.g., `gcloud`, `aws`, `az`) is authenticated and configured for the correct project. You can verify this with the appropriate CLI command.

3.  **Set GitHub Token Environment Variable:**
    Before running the script, ensure your `GITHUB_TOKEN` environment variable is set in your shell. This token is passed to the Cloud Run service as an environment variable.
    ```bash
    export GITHUB_TOKEN="YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    ```

4.  **Execute the deployment script:**
    ```bash
    chmod +x deploy.sh # Make the script executable
    ./deploy.sh
    ```

    The script will perform the following actions:
    *   Build a Docker image locally based on the `Dockerfile`.
    *   Tag the image with your project's container registry path.
    *   Push the built Docker image to the container registry.
    *   Deploy the image to your chosen cloud platform, creating a service or updating an existing one. It configures the service to allow unauthenticated invocations (necessary for messaging service push subscriptions, or if you plan to trigger it via HTTP) and sets the `GITHUB_TOKEN` environment variable within the cloud service instance.

5.  **Verify Deployment:**
    After the script completes, it will output the service URL. You can also check the cloud platform console to verify the deployment status.

## Production Considerations

For production deployments, consider the following:

*   **Secrets Management:** Instead of passing `GITHUB_TOKEN` directly as an environment variable in the `deploy.sh` script, use your cloud platform's secret management service (e.g., Google Secret Manager, AWS Secrets Manager, Azure Key Vault) to securely store and retrieve sensitive credentials at runtime.
*   **Service Account Permissions:** Ensure the cloud service account has only the necessary IAM permissions (e.g., messaging service subscriber, AI model user, cloud logging viewer, and permissions to interact with GitHub if using a GitHub App or fine-grained PAT).
*   **Resource Allocation:** Adjust CPU and memory limits for your cloud service based on expected workload and model inference requirements.
*   **Concurrency:** Configure the maximum number of concurrent requests a single container instance can handle.
*   **Monitoring and Alerting:** Set up cloud monitoring and logging alerts for the service to track its health and performance.
*   **CI/CD Pipeline:** Integrate the build and deployment process into a Continuous Integration/Continuous Deployment (CI/CD) pipeline (e.g., Cloud Build, GitHub Actions, AWS CodePipeline, Azure DevOps) for automated and consistent deployments.
