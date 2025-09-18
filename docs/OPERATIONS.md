# Operations Runbook

This runbook provides guidelines and procedures for operating, monitoring, and maintaining the Cloud SRE Agent in a production environment. It covers system monitoring, incident response, maintenance, and cost optimization.

## 1. System Monitoring Procedures

Effective monitoring is crucial for ensuring the continuous and reliable operation of the Cloud SRE Agent. Leverage cloud platform monitoring services (e.g., Google Cloud Monitoring, AWS CloudWatch, Azure Monitor) for comprehensive observability.

### Key Metrics to Monitor

*   **Cloud Service Metrics:**
    *   **Request Count:** Total number of requests processed by the agent.
    *   **Request Latency:** Time taken to process requests (e.g., messaging service messages).
    *   **CPU Utilization:** Average CPU usage of the agent instances.
    *   **Memory Utilization:** Average memory usage of the agent instances.
    *   **Container Instance Count:** Number of running instances.
    *   **Container Instance Startup Latency:** Time taken for instances to start.
*   **Messaging Service Metrics:**
    *   **Unacked Message Count:** Number of messages waiting to be acknowledged in the subscription (should be low).
    *   **Oldest Unacked Message Age:** Age of the oldest unacknowledged message (should be low).
    *   **Subscription Throughput:** Rate of messages being pulled/pushed.
*   **AI Model Metrics:**
    *   **Model Prediction Count:** Number of calls to AI models.
    *   **Model Prediction Latency:** Latency of AI model responses.
    *   **Model Error Rate:** Errors returned by AI models.
*   **GitHub API Metrics:**
    *   Monitor GitHub API rate limits (if exposed by PyGithub or through custom logging).

### Monitoring Tools

*   **Cloud Platform Monitoring:** Create custom dashboards to visualize the key metrics listed above (e.g., Google Cloud Monitoring, AWS CloudWatch, Azure Monitor).
*   **Cloud Logging:** Use advanced log filters to analyze agent logs, especially for `ERROR` and `FATAL` severity levels.

### Alerting

Configure alerts in your cloud platform monitoring service for critical thresholds:

*   **High Unacked Message Count:** Alert if `Unacked Message Count` for a messaging service subscription exceeds a threshold for a sustained period.
*   **High Error Rates:** Alert if `Model Error Rate` or agent's internal `failed_operations` (from `get_health_stats()`) exceed a threshold.
*   **High Latency:** Alert if `Request Latency` for cloud service or AI model calls exceeds acceptable limits.
*   **Resource Exhaustion:** Alert on high CPU/Memory utilization or if `max_instances` is frequently hit.

## 2. Incident Response Playbook

This section outlines procedures for responding to incidents detected or caused by the Cloud SRE Agent.

### Common Incident Scenarios

*   **Agent Not Processing Logs:**
    *   **Symptoms:** No PRs, messaging service unacked messages increasing, no recent agent logs.
    *   **Troubleshooting:** Check cloud service status, review cloud service logs for errors, verify messaging service subscription health, check cloud platform authentication.
*   **Agent Generating Incorrect Fixes/PRs:**
    *   **Symptoms:** PRs with illogical code, frequent PR rejections.
    *   **Troubleshooting:** Review agent logs (DEBUG level), inspect AI model prompts and responses, refine prompt engineering, consider model fine-tuning.
*   **GitHub API Rate Limit Exceeded:**
    *   **Symptoms:** PR creation failures with 403 errors.
    *   **Troubleshooting:** Check GitHub API rate limit status, review agent's `rate_limit_hits` metric, adjust `rate_limit` configuration in `config.yaml`.

### Escalation Procedures

(Define who to contact and when for different severity levels of incidents.)

## 3. Maintenance and Update Procedures

### Agent Updates

*   **Code Changes:** Follow the [Development Guide](DEVELOPMENT.md) for making code changes, running tests, and submitting PRs.
*   **Deployment:** Use the [Deployment Guide](DEPLOYMENT.md) for deploying versions of the agent.

### Model Updates

*   Monitor AI model versions from your chosen providers and evaluate their performance and cost implications.
*   Update `config.yaml` to use model versions as appropriate.

### Infrastructure Updates

*   Use the [Infrastructure as Code Guide](INFRASTRUCTURE.md) to manage changes to cloud platform resources.

## 4. Backup and Disaster Recovery

(This section would cover strategies for backing up critical configurations, data, and procedures for recovering from major outages. This is a placeholder for future expansion.)

## 5. Performance Monitoring and Cost Optimization

### Performance Monitoring

*   Regularly review Cloud Monitoring dashboards for performance trends.
*   Analyze log processing latency and model inference times.

### Cost Optimization

*   **Model Selection:** Continuously evaluate the cost-effectiveness of the AI models used. Use fast models for triage and advanced models only when deep analysis is strictly required.
*   **Log Filtering:** Optimize cloud logging sink filters to export only necessary logs to messaging services, reducing messaging service and processing costs.
*   **Cloud Service Scaling:** Configure cloud service `min-instances` and `max-instances` appropriately to balance cost and responsiveness.
*   **Messaging Service Message Retention:** Adjust `message_retention_duration` for messaging service subscriptions to minimize storage costs.
