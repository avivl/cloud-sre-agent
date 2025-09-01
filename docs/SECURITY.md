# Security Guide

This guide outlines security best practices and considerations for deploying and operating the Gemini SRE Agent in a production environment. Ensuring the security of your agent and its interactions with GCP and GitHub is paramount.

## 1. Authentication and Authorization

### GCP Authentication

*   **Service Accounts:** Always use dedicated GCP Service Accounts for deploying and running the Gemini SRE Agent in production. Avoid using user credentials.
*   **Least Privilege:** Grant the service account only the minimum necessary IAM roles and permissions. Refer to the [GCP Infrastructure Setup Guide](GCP_SETUP.md) for recommended roles.
*   **Workload Identity (GKE/GKE Autopilot):** If deploying to GKE, leverage Workload Identity to securely bind Kubernetes Service Accounts to GCP Service Accounts, eliminating the need to manage service account keys.
*   **Application Default Credentials (ADC):** The agent uses ADC to authenticate with GCP services. Ensure the environment where the agent runs has access to valid ADC (e.g., via `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to a service account key file, or by running on a GCP compute resource with an attached service account).

### GitHub Authentication

*   **Personal Access Tokens (PATs):** For the `RemediationAgent` to interact with GitHub, a Personal Access Token (PAT) with appropriate scopes (`repo` scope for full repository control) is required.
*   **Fine-Grained PATs:** Prefer using fine-grained PATs with the most restrictive permissions possible, limiting access to specific repositories and actions.
*   **GitHub Apps:** For more robust and scalable integration, consider developing a GitHub App. GitHub Apps offer more granular permissions, better security, and are designed for long-lived integrations.

## 2. Secret Management

Sensitive credentials like GitHub PATs should never be hardcoded or stored directly in version control. Use a secure secret management solution.

*   **Google Secret Manager:** Recommended for managing secrets in GCP. Store your GitHub PAT and any other sensitive configuration values in Secret Manager.
    *   Refer to the [Deployment Guide](DEPLOYMENT.md) for examples on integrating Secret Manager with Cloud Run.
*   **Environment Variables:** While convenient for development, avoid using plain environment variables for secrets in production. If absolutely necessary, ensure they are managed securely by your deployment platform.

## 3. Data Protection and Encryption

### Data in Transit

*   **TLS/SSL:** All communication with GCP APIs (Vertex AI, Pub/Sub, Logging) and GitHub API is encrypted in transit using TLS/SSL.

### Data at Rest

*   **Cloud Logging:** Logs stored in Cloud Logging are encrypted at rest by default.
*   **Pub/Sub:** Messages in Pub/Sub are encrypted at rest by default.

## 4. Compliance Considerations

(This section would discuss any relevant compliance standards or regulations that the agent's operation might need to adhere to, e.g., GDPR, HIPAA, SOC 2. This is a placeholder for future expansion.)

## 5. Threat Model and Mitigations

(This section would outline potential threats to the agent and its operation, and corresponding mitigation strategies. This is a placeholder for future expansion.)

### Example Threats:

*   **Malicious Log Injection:** An attacker injects malicious log entries to trigger unintended remediation actions.
    *   **Mitigation:** Robust input validation in `TriageAgent`, human review of PRs, strict IAM permissions for the agent.
*   **Compromised GitHub Token:** An attacker gains access to the agent's GitHub PAT.
    *   **Mitigation:** Use Secret Manager, fine-grained PATs, regularly rotate tokens, monitor GitHub audit logs.
*   **Model Bias/Hallucination:** Gemini models generate incorrect or harmful remediation plans.
    *   **Mitigation:** Human review of PRs, continuous monitoring of model output, robust testing, prompt engineering best practices.

## 6. Security Best Practices

*   **Regular Audits:** Periodically audit IAM policies, service account permissions, and GitHub PATs.
*   **Logging and Monitoring:** Ensure comprehensive logging and monitoring of the agent's activities to detect suspicious behavior.
*   **Vulnerability Management:** Regularly scan the agent's dependencies for known vulnerabilities.
*   **Network Security:** Implement network security controls (e.g., VPC Service Controls, VPC Access Connector for Cloud Run) to restrict network access.
