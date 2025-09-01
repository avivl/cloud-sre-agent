variable "gcp_project_id" {
  description = "The GCP project ID."
  type        = string
}

variable "gcp_region" {
  description = "The GCP region for resources."
  type        = string
  default     = "us-central1"
}

variable "service_name_prefix" {
  description = "Prefix for resource names to ensure uniqueness."
  type        = string
  default     = "gemini-sre-agent"
}

variable "log_topic_name" {
  description = "Name of the Pub/Sub topic for logs."
  type        = string
  default     = "gemini-sre-logs"
}

variable "log_subscription_name" {
  description = "Name of the Pub/Sub subscription for logs."
  type        = string
  default     = "gemini-sre-logs-sub"
}

variable "log_sink_name" {
  description = "Name of the Cloud Logging sink."
  type        = string
  default     = "gemini-sre-log-sink"
}

variable "agent_service_account_id" {
  description = "ID for the service account used by the Gemini SRE Agent."
  type        = string
  default     = "gemini-sre-agent-sa"
}
