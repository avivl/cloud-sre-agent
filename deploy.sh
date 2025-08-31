#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration ---
PROJECT_ID="your-gcp-project-id" # Replace with your GCP Project ID
SERVICE_NAME="gemini-sre-agent"
REGION="us-central1" # Choose your desired GCP region
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# --- Build Docker Image ---
echo "Building Docker image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" .

# --- Push Docker Image to Google Container Registry ---
echo "Pushing Docker image to GCR..."
docker push "${IMAGE_NAME}"

# --- Deploy to Google Cloud Run ---
echo "Deploying to Google Cloud Run..."
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
