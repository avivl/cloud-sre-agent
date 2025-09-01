output "logs_topic_name" {
  description = "Name of the Pub/Sub topic for logs."
  value       = google_pubsub_topic.logs_topic.name
}

output "logs_subscription_name" {
  description = "Name of the Pub/Sub subscription for logs."
  value       = google_pubsub_subscription.logs_subscription.name
}

output "agent_service_account_email" {
  description = "Email of the service account used by the Gemini SRE Agent."
  value       = google_service_account.agent_sa.email
}
