#!/usr/bin/env bash
#
# gcloud_setup.sh — one-time (idempotent-ish) GCP infrastructure for the
# Cloud SRE Agent.
#
# Flow it provisions:
#   Cloud Logging sink (severity>=ERROR)
#     -> Pub/Sub topic
#       -> Pub/Sub PULL subscription (the agent pulls from this)
#   + a dedicated least-privilege service account for the agent
#   + an Artifact Registry repo to hold the agent image
#
# Everything is parameterized via env vars — there is NO hardcoded project.
# Re-running is safe: each create is guarded so an "already exists" is treated
# as success.
#
# Usage:
#   PROJECT_ID=my-proj REGION=us-central1 ./infra/gcloud_setup.sh

set -euo pipefail

# --- Configuration (override via environment) --------------------------------
PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required (no default)}"
REGION="${REGION:-us-central1}"

# Artifact Registry (Docker) repo for the agent image.
AR_REPO="${AR_REPO:-sre-agent}"

# Pub/Sub topic + pull subscription the error logs flow through.
LOG_TOPIC_NAME="${LOG_TOPIC_NAME:-sre-agent-logs}"
LOG_SUBSCRIPTION_NAME="${LOG_SUBSCRIPTION_NAME:-sre-agent-logs-sub}"

# Cloud Logging sink that routes severity>=ERROR to the topic.
LOG_SINK_NAME="${LOG_SINK_NAME:-sre-agent-error-sink}"
LOG_SINK_FILTER="${LOG_SINK_FILTER:-severity>=ERROR}"

# Subscription tuning.
ACK_DEADLINE="${ACK_DEADLINE:-600}"
MESSAGE_RETENTION="${MESSAGE_RETENTION:-7d}"

# Dedicated agent service account.
AGENT_SA_ID="${AGENT_SA_ID:-sre-agent-sa}"
AGENT_SA_EMAIL="${AGENT_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

echo "Project:        ${PROJECT_ID}"
echo "Region:         ${REGION}"
echo "Artifact repo:  ${AR_REPO}"
echo "Topic:          ${LOG_TOPIC_NAME}"
echo "Subscription:   ${LOG_SUBSCRIPTION_NAME}"
echo "Sink:           ${LOG_SINK_NAME} (${LOG_SINK_FILTER})"
echo "Service account:${AGENT_SA_EMAIL}"
echo

# --- 0. Enable required APIs --------------------------------------------------
# logging + pubsub for the ingest path; aiplatform for Vertex AI (Gemini under
# Google's BAA); artifactregistry + run for the image and worker pool deploy;
# cloudtrace for the agent's OpenTelemetry export.
echo "Enabling required APIs..."
gcloud services enable \
  logging.googleapis.com \
  pubsub.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  cloudtrace.googleapis.com \
  --project="${PROJECT_ID}"

# --- 1. Artifact Registry repo ------------------------------------------------
# Holds the agent container image. (Alternative: classic GCR at gcr.io/<proj>,
# now backed by Artifact Registry — but a dedicated AR Docker repo is the
# recommended, granular-IAM option, so we create one here.)
echo "Ensuring Artifact Registry repo '${AR_REPO}'..."
if ! gcloud artifacts repositories describe "${AR_REPO}" \
      --location="${REGION}" --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Cloud SRE Agent container images" \
    --project="${PROJECT_ID}"
else
  echo "  already exists, skipping."
fi

# --- 2. Pub/Sub topic ---------------------------------------------------------
echo "Ensuring Pub/Sub topic '${LOG_TOPIC_NAME}'..."
if ! gcloud pubsub topics describe "${LOG_TOPIC_NAME}" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub topics create "${LOG_TOPIC_NAME}" --project="${PROJECT_ID}"
else
  echo "  already exists, skipping."
fi

# --- 3. Pub/Sub PULL subscription --------------------------------------------
# The agent (worker pool, no ingress) PULLS from this subscription — a push
# subscription would require an HTTP endpoint, which a worker pool does not have.
echo "Ensuring PULL subscription '${LOG_SUBSCRIPTION_NAME}'..."
if ! gcloud pubsub subscriptions describe "${LOG_SUBSCRIPTION_NAME}" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud pubsub subscriptions create "${LOG_SUBSCRIPTION_NAME}" \
    --topic="${LOG_TOPIC_NAME}" \
    --ack-deadline="${ACK_DEADLINE}" \
    --message-retention-duration="${MESSAGE_RETENTION}" \
    --project="${PROJECT_ID}"
else
  echo "  already exists, skipping."
fi

# --- 4. Dedicated service account --------------------------------------------
echo "Ensuring service account '${AGENT_SA_EMAIL}'..."
if ! gcloud iam service-accounts describe "${AGENT_SA_EMAIL}" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${AGENT_SA_ID}" \
    --display-name="Cloud SRE Agent" \
    --project="${PROJECT_ID}"
else
  echo "  already exists, skipping."
fi

# --- 5. Least-privilege IAM for the agent service account --------------------
# add-iam-policy-binding is idempotent (re-adding an existing binding is a no-op).
#   pubsub.subscriber  — pull error logs from the subscription
#   logging.logWriter  — emit the agent's own structured logs
#   cloudtrace.agent   — export OpenTelemetry traces
#   aiplatform.user    — call Vertex AI (Gemini) under Google's BAA
echo "Granting least-privilege roles to ${AGENT_SA_EMAIL}..."
for ROLE in \
  roles/pubsub.subscriber \
  roles/logging.logWriter \
  roles/cloudtrace.agent \
  roles/aiplatform.user; do
  echo "  + ${ROLE}"
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${AGENT_SA_EMAIL}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done

# --- 6. Cloud Logging sink (severity>=ERROR -> topic) ------------------------
# Create-or-update so re-runs converge. After (re)creating, capture the sink's
# writer identity and grant it pub/sub publisher on the topic so log routing can
# actually deliver.
echo "Ensuring Cloud Logging sink '${LOG_SINK_NAME}'..."
SINK_DEST="pubsub.googleapis.com/projects/${PROJECT_ID}/topics/${LOG_TOPIC_NAME}"
if ! gcloud logging sinks describe "${LOG_SINK_NAME}" \
      --project="${PROJECT_ID}" >/dev/null 2>&1; then
  gcloud logging sinks create "${LOG_SINK_NAME}" \
    "${SINK_DEST}" \
    --log-filter="${LOG_SINK_FILTER}" \
    --project="${PROJECT_ID}"
else
  echo "  exists — updating filter/destination."
  gcloud logging sinks update "${LOG_SINK_NAME}" \
    "${SINK_DEST}" \
    --log-filter="${LOG_SINK_FILTER}" \
    --project="${PROJECT_ID}"
fi

# Grant the sink's auto-provisioned writer identity publish rights on the topic.
echo "Granting Pub/Sub Publisher to the sink writer identity..."
SINK_WRITER_IDENTITY="$(gcloud logging sinks describe "${LOG_SINK_NAME}" \
  --project="${PROJECT_ID}" --format='value(writerIdentity)')"
gcloud pubsub topics add-iam-policy-binding "${LOG_TOPIC_NAME}" \
  --member="${SINK_WRITER_IDENTITY}" \
  --role="roles/pubsub.publisher" \
  --project="${PROJECT_ID}" \
  --quiet >/dev/null

# --- Done ---------------------------------------------------------------------
echo
echo "Infrastructure ready."
echo "  Image registry: ${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}"
echo "  Topic:          ${LOG_TOPIC_NAME}"
echo "  Subscription:   ${LOG_SUBSCRIPTION_NAME}  (agent pulls from this)"
echo "  Sink writer:    ${SINK_WRITER_IDENTITY}"
echo "  Agent SA:       ${AGENT_SA_EMAIL}"
echo
echo "Next: run ./deploy.sh (same PROJECT_ID/REGION) to build, push, and deploy"
echo "the worker pool."
