import pulumi
import pulumi_gcp as gcp

# Get configuration values
project_id = gcp.config.project or pulumi.Config().require("gcp_project_id")
region = gcp.config.region or pulumi.Config().get("gcp_region") or "us-central1"
service_name_prefix = pulumi.Config().get("service_name_prefix") or "gemini-sre-agent"
log_topic_name = pulumi.Config().get("log_topic_name") or "gemini-sre-logs"
log_subscription_name = pulumi.Config().get("log_subscription_name") or "gemini-sre-logs-sub"
log_sink_name = pulumi.Config().get("log_sink_name") or "gemini-sre-log-sink"
agent_service_account_id = pulumi.Config().get("agent_service_account_id") or "gemini-sre-agent-sa"

# --- Pub/Sub Topic for Logs ---
logs_topic = gcp.pubsub.Topic("logs-topic",
    project=project_id,
    name=log_topic_name
)

# --- Pub/Sub Subscription for Logs ---
logs_subscription = gcp.pubsub.Subscription("logs-subscription",
    project=project_id,
    name=log_subscription_name,
    topic=logs_topic.name,
    ack_deadline_seconds=600,
    message_retention_duration="604800s"
)

# --- Service Account for Gemini SRE Agent ---
agent_sa = gcp.serviceaccount.Account("agent-sa",
    project=project_id,
    account_id=agent_service_account_id,
    display_name="Service Account for Gemini SRE Agent"
)

# --- IAM Permissions for Agent Service Account ---
agent_pubsub_subscriber_binding = gcp.projects.IAMMember("agent-pubsub-subscriber-binding",
    project=project_id,
    role="roles/pubsub.subscriber",
    member=agent_sa.member
)

agent_vertex_ai_user_binding = gcp.projects.IAMMember("agent-vertex-ai-user-binding",
    project=project_id,
    role="roles/aiplatform.user",
    member=agent_sa.member
)

agent_logging_viewer_binding = gcp.projects.IAMMember("agent-logging-viewer-binding",
    project=project_id,
    role="roles/logging.viewer",
    member=agent_sa.member
)

# --- Cloud Logging Sink ---
logs_sink = gcp.logging.ProjectSink("logs-sink",
    project=project_id,
    name=log_sink_name,
    destination=logs_topic.id.apply(lambda id: f"pubsub.googleapis.com/{id}"),
    filter="severity>=ERROR"
)

# --- IAM Permissions for Logging Sink Writer Identity ---
# The writer_identity is created by GCP when the sink is created
# We need to grant Pub/Sub Publisher role to this identity
logs_sink_iam_member = gcp.pubsub.TopicIAMMember("logs-sink-iam-member",
    topic=logs_topic.name,
    role="roles/pubsub.publisher",
    member=logs_sink.writer_identity
)

# --- Outputs ---
pulumi.export("logs_topic_name", logs_topic.name)
pulumi.export("logs_subscription_name", logs_subscription.name)
pulumi.export("agent_service_account_email", agent_sa.email)
