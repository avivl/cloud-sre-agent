provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# --- Pub/Sub Topic for Logs ---
resource "google_pubsub_topic" "logs_topic" {
  project = var.gcp_project_id
  name    = var.log_topic_name
}

# --- Pub/Sub Subscription for Logs ---
resource "google_pubsub_subscription" "logs_subscription" {
  project = var.gcp_project_id
  name    = var.log_subscription_name
  topic   = google_pubsub_topic.logs_topic.id

  ack_deadline_seconds = 600 # 10 minutes
  message_retention_duration = "604800s" # 7 days
}

# --- Service Account for Gemini SRE Agent ---
resource "google_service_account" "agent_sa" {
  project      = var.gcp_project_id
  account_id   = var.agent_service_account_id
  display_name = "Service Account for Gemini SRE Agent"
}

# --- IAM Permissions for Agent Service Account ---
resource "google_project_iam_member" "agent_pubsub_subscriber" {
  project = var.gcp_project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_vertex_ai_user" {
  project = var.gcp_project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

resource "google_project_iam_member" "agent_logging_viewer" {
  project = var.gcp_project_id
  role    = "roles/logging.viewer"
  member  = "serviceAccount:${google_service_account.agent_sa.email}"
}

# --- Cloud Logging Sink ---
resource "google_logging_project_sink" "logs_sink" {
  project = var.gcp_project_id
  name    = var.log_sink_name
  destination = "pubsub.googleapis.com/${google_pubsub_topic.logs_topic.id}"
  filter      = "severity>=ERROR"

  # Grant Pub/Sub Publisher role to the Logging Sink's writer identity
  # The writer_identity is created by GCP when the sink is created
  # We need to parse it from the sink's attributes
  # This requires the 'roles/logging.viewer' on the project for the user running Terraform
  # and 'roles/editor' or 'roles/owner' for the project to grant permissions
  depends_on = [google_pubsub_topic.logs_topic]
}

resource "google_pubsub_topic_iam_member" "logs_topic_iam" {
  topic   = google_pubsub_topic.logs_topic.name
  role    = "roles/pubsub.publisher"
  member  = google_logging_project_sink.logs_sink.writer_identity
}
