#!/bin/bash

# Exit immediately if a command exits with a non-zero status.
set -e

# --- Configuration Variables (REPLACE THESE) ---
# Your Google Cloud Project ID
PROJECT_ID="your-gcp-project-id"
# The GCP region for your resources (e.g., us-central1)
REGION="us-central1"
# Name for the Pub/Sub topic for logs
LOG_TOPIC_NAME="gemini-sre-logs"
# Name for the Pub/Sub subscription for logs
LOG_SUBSCRIPTION_NAME="gemini-sre-logs-sub"
# Name for the Cloud Logging sink
LOG_SINK_NAME="gemini-sre-log-sink"
# ID for the service account used by the Gemini SRE Agent
AGENT_SERVICE_ACCOUNT_ID="gemini-sre-agent-sa"

# --- Prerequisites ---
echo "Ensuring gcloud CLI is authenticated and configured..."
gcloud auth list
gcloud config list

# --- 1. Enable Required APIs ---
echo "Enabling required GCP APIs..."
gcloud services enable logging.googleapis.com --project=${PROJECT_ID}
gcloud services enable pubsub.googleapis.com --project=${PROJECT_ID}
gcloud services enable aiplatform.googleapis.com --project=${PROJECT_ID}

# --- 2. Create Pub/Sub Topic and Subscription ---
echo "Creating Pub/Sub topic: ${LOG_TOPIC_NAME}..."
gcloud pubsub topics create projects/${PROJECT_ID}/topics/${LOG_TOPIC_NAME} --project=${PROJECT_ID}

echo "Creating Pub/Sub subscription: ${LOG_SUBSCRIPTION_NAME}..."
gcloud pubsub subscriptions create projects/${PROJECT_ID}/subscriptions/${LOG_SUBSCRIPTION_NAME} \
    --topic=projects/${PROJECT_ID}/topics/${LOG_TOPIC_NAME} \
    --ack-deadline=600 \
    --message-retention-duration=7d \
    --project=${PROJECT_ID}

# --- 3. Create Service Account for Gemini SRE Agent ---
echo "Creating Service Account: ${AGENT_SERVICE_ACCOUNT_ID}..."
AGENT_SA_EMAIL="${AGENT_SERVICE_ACCOUNT_ID}@${PROJECT_ID}.iam.gserviceaccount.com"
gcloud iam service-accounts create ${AGENT_SERVICE_ACCOUNT_ID} \
    --display-name="Service Account for Gemini SRE Agent" \
    --project=${PROJECT_ID}

# --- 4. Grant IAM Permissions for Agent Service Account ---
echo "Granting IAM permissions to agent service account..."
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${AGENT_SA_EMAIL}" \
    --role="roles/pubsub.subscriber" \
    --project=${PROJECT_ID}

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${AGENT_SA_EMAIL}" \
    --role="roles/aiplatform.user" \
    --project=${PROJECT_ID}

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
    --member="serviceAccount:${AGENT_SA_EMAIL}" \
    --role="roles/logging.viewer" \
    --project=${PROJECT_ID}

# --- 5. Configure Cloud Logging Sink ---
echo "Creating Cloud Logging sink: ${LOG_SINK_NAME}..."

# Get the project number for the sink writer identity
PROJECT_NUMBER=$(gcloud projects describe ${PROJECT_ID} --format="value(projectNumber)")
SINK_WRITER_IDENTITY="service-${PROJECT_NUMBER}@gcp-sa-logging.iam.gserviceaccount.com"

# Grant Pub/Sub Publisher role to the Logging Sink's writer identity
echo "Granting Pub/Sub Publisher role to sink writer identity..."
gcloud pubsub topics add-iam-policy-binding projects/${PROJECT_ID}/topics/${LOG_TOPIC_NAME} \
    --member="serviceAccount:${SINK_WRITER_IDENTITY}" \
    --role="roles/pubsub.publisher" \
    --project=${PROJECT_ID}

# Create the sink
gcloud logging sinks create ${LOG_SINK_NAME} \
    pubsub.googleapis.com/projects/${PROJECT_ID}/topics/${LOG_TOPIC_NAME} \
    --log-filter='severity>=ERROR' \
    --project=${PROJECT_ID}

echo "Infrastructure setup complete!"
echo "Pub/Sub Topic: ${LOG_TOPIC_NAME}"
echo "Pub/Sub Subscription: ${LOG_SUBSCRIPTION_NAME}"
echo "Agent Service Account Email: ${AGENT_SA_EMAIL}"
