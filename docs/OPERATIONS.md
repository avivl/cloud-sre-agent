# Operations Runbook

This runbook provides guidelines and procedures for operating, monitoring, and maintaining the Gemini SRE Agent in a production environment. It covers system monitoring, incident response, maintenance, and cost optimization.

## 1. System Monitoring Procedures

Effective monitoring is crucial for ensuring the continuous and reliable operation of the Gemini SRE Agent. Leverage Google Cloud Monitoring (formerly Stackdriver) for comprehensive observability.

### Key Metrics to Monitor

*   **Cloud Run Service Metrics:**
    *   **Request Count:** Total number of requests processed by the agent.
    *   **Request Latency:** Time taken to process requests (e.g., Pub/Sub messages).
    *   **CPU Utilization:** Average CPU usage of the agent instances.
    *   **Memory Utilization:** Average memory usage of the agent instances.
    *   **Container Instance Count:** Number of running instances.
    *   **Container Instance Startup Latency:** Time taken for new instances to start.
*   **Pub/Sub Metrics:**
    *   **Unacked Message Count:** Number of messages waiting to be acknowledged in the subscription (should be low).
    *   **Oldest Unacked Message Age:** Age of the oldest unacknowledged message (should be low).
    *   **Subscription Throughput:** Rate of messages being pulled/pushed.
*   **Vertex AI Metrics:**
    *   **Model Prediction Count:** Number of calls to Gemini models.
    *   **Model Prediction Latency:** Latency of Gemini model responses.
    *   **Model Error Rate:** Errors returned by Gemini models.
*   **GitHub API Metrics:**
    *   Monitor GitHub API rate limits (if exposed by PyGithub or through custom logging).

### Monitoring Tools

*   **Google Cloud Monitoring:** Create custom dashboards to visualize the key metrics listed above.
*   **Cloud Logging:** Use advanced log filters to analyze agent logs, especially for `ERROR` and `FATAL` severity levels.

### Alerting

Configure alerts in Google Cloud Monitoring for critical thresholds:

*   **High Unacked Message Count:** Alert if `Unacked Message Count` for a Pub/Sub subscription exceeds a threshold for a sustained period.
*   **High Error Rates:** Alert if `Model Error Rate` or agent's internal `failed_operations` (from `get_health_stats()`) exceed a threshold.
*   **High Latency:** Alert if `Request Latency` for Cloud Run or Gemini model calls exceeds acceptable limits.
*   **Resource Exhaustion:** Alert on high CPU/Memory utilization or if `max_instances` is frequently hit.

## 2. Incident Response Playbook

This section outlines procedures for responding to incidents detected or caused by the Gemini SRE Agent.

### Common Incident Scenarios

*   **Agent Not Processing Logs:**
    *   **Symptoms:** No new PRs, Pub/Sub unacked messages increasing, no recent agent logs.
    *   **Troubleshooting:** Check Cloud Run service status, review Cloud Run logs for errors, verify Pub/Sub subscription health, check GCP authentication.
*   **Agent Generating Incorrect Fixes/PRs:**
    *   **Symptoms:** PRs with illogical code, frequent PR rejections.
    *   **Troubleshooting:** Review agent logs (DEBUG level), inspect Gemini model prompts and responses, refine prompt engineering, consider model fine-tuning.
*   **GitHub API Rate Limit Exceeded:**
    *   **Symptoms:** PR creation failures with 403 errors.
    *   **Troubleshooting:** Check GitHub API rate limit status, review agent's `rate_limit_hits` metric, adjust `rate_limit` configuration in `config.yaml`.

### Escalation Procedures

(Define who to contact and when for different severity levels of incidents.)

## 3. Maintenance and Update Procedures

### Agent Updates

*   **Code Changes:** Follow the [Development Guide](DEVELOPMENT.md) for making code changes, running tests, and submitting PRs.
*   **Deployment:** Use the [Deployment Guide](DEPLOYMENT.md) for deploying new versions of the agent.

### Model Updates

*   Monitor new Gemini model versions and evaluate their performance and cost implications.
*   Update `config.yaml` to use new model versions as appropriate.

### Infrastructure Updates

*   Use the [Infrastructure as Code Guide](INFRASTRUCTURE.md) to manage changes to GCP resources.

## 4. Backup and Disaster Recovery

(This section would cover strategies for backing up critical configurations, data, and procedures for recovering from major outages. This is a placeholder for future expansion.)

## 5. Performance Monitoring and Cost Optimization

### Performance Monitoring

*   Regularly review Cloud Monitoring dashboards for performance trends.
*   Analyze log processing latency and model inference times.

### Cost Optimization

*   **Model Selection:** Continuously evaluate the cost-effectiveness of the Gemini models used. Use Flash models for triage and Pro models only when deep analysis is strictly required.
*   **Log Filtering:** Optimize Cloud Logging sink filters to export only necessary logs to Pub/Sub, reducing Pub/Sub and processing costs.
*   **Cloud Run Scaling:** Configure Cloud Run `min-instances` and `max-instances` appropriately to balance cost and responsiveness.
*   **Pub/Sub Message Retention:** Adjust `message_retention_duration` for Pub/Sub subscriptions to minimize storage costs.
