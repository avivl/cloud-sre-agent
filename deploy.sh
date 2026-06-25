#!/usr/bin/env bash
#
# deploy.sh — build, push, and deploy the Cloud SRE Agent as a Cloud Run
# *worker pool*.
#
# A worker pool has NO HTTP ingress — it pulls work (error logs via the Pub/Sub
# subscription created by infra/gcloud_setup.sh) and runs the agent loop. That
# is why this uses `gcloud beta run worker-pools deploy` and not `run deploy`.
#
# Fully parameterized via env vars — no hardcoded project. Run infra/gcloud_setup.sh
# first (it creates the Artifact Registry repo, topic, subscription, sink, and SA).
#
# Usage:
#   PROJECT_ID=my-proj REGION=us-central1 ./deploy.sh

set -euo pipefail

# --- Configuration (override via environment) --------------------------------
PROJECT_ID="${PROJECT_ID:?PROJECT_ID is required (no default)}"
REGION="${REGION:-us-central1}"

# Must match infra/gcloud_setup.sh.
AR_REPO="${AR_REPO:-sre-agent}"
WORKER_POOL_NAME="${WORKER_POOL_NAME:-sre-agent}"
AGENT_SA_ID="${AGENT_SA_ID:-sre-agent-sa}"
AGENT_SA_EMAIL="${AGENT_SA_ID}@${PROJECT_ID}.iam.gserviceaccount.com"

# Image coordinates. Tag defaults to the short git SHA when available, else "latest".
IMAGE_TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo latest)}"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPO}/${WORKER_POOL_NAME}:${IMAGE_TAG}"

# LLM / Vertex wiring. The agent reads SRE_-prefixed env vars as config overrides
# (double underscore => nested key: SRE_LLM__PROJECT -> llm.project). We force the
# BAA-eligible Vertex backend and point it at this project/region.
LLM_LOCATION="${LLM_LOCATION:-${REGION}}"

echo "Project:      ${PROJECT_ID}"
echo "Region:       ${REGION}"
echo "Worker pool:  ${WORKER_POOL_NAME}"
echo "Image:        ${IMAGE}"
echo "Service acct: ${AGENT_SA_EMAIL}"
echo

# --- 1. Authenticate Docker to Artifact Registry -----------------------------
echo "Configuring Docker auth for ${REGION}-docker.pkg.dev..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# --- 2. Build the image -------------------------------------------------------
echo "Building image ${IMAGE}..."
docker build -t "${IMAGE}" .

# --- 3. Push to Artifact Registry --------------------------------------------
echo "Pushing image..."
docker push "${IMAGE}"

# --- 4. Deploy the Cloud Run worker pool -------------------------------------
# Worker pools have no ingress and no --port/--allow-unauthenticated flags.
# Env wiring sets the LLM backend to Vertex AI and points it at this project.
echo "Deploying worker pool ${WORKER_POOL_NAME}..."
gcloud beta run worker-pools deploy "${WORKER_POOL_NAME}" \
  --image="${IMAGE}" \
  --region="${REGION}" \
  --project="${PROJECT_ID}" \
  --service-account="${AGENT_SA_EMAIL}" \
  --set-env-vars="SRE_LLM__BACKEND=vertex,SRE_LLM__PROJECT=${PROJECT_ID},SRE_LLM__LOCATION=${LLM_LOCATION}"

echo
echo "Worker pool '${WORKER_POOL_NAME}' deployed in ${REGION}."
echo "It pulls error logs from the Pub/Sub subscription and runs the agent loop."
