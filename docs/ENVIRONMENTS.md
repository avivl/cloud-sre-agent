# Multi-Environment Guide

This guide outlines strategies for managing the Gemini SRE Agent across different environments, such as development, staging, and production. Proper environment management ensures consistency, reduces risks, and streamlines promotion workflows.

## 1. Environment Definitions

### Development Environment

*   **Purpose:** Local development, feature testing, and rapid iteration.
*   **Configuration:** Typically uses `DEBUG` level logging, local or test GCP projects, and potentially mocked external services (e.g., GitHub).
*   **Deployment:** Local execution (`python main.py`) or deployment to a personal Cloud Run instance.
*   **Key Considerations:** Focus on developer productivity, quick feedback loops, and isolated testing.

### Staging Environment

*   **Purpose:** Integration testing, user acceptance testing (UAT), and pre-production validation.
*   **Configuration:** Mirrors production as closely as possible in terms of GCP resources, model versions, and GitHub repositories. Uses `INFO` level logging.
*   **Deployment:** Automated deployment via CI/CD pipelines (e.g., GitHub Actions) to a dedicated staging GCP project.
*   **Key Considerations:** Data realism, performance testing, and verifying end-to-end workflows before production.

### Production Environment

*   **Purpose:** Live operation, monitoring, and automated remediation of critical services.
*   **Configuration:** Uses `INFO` or `WARN` level logging, production GCP projects, and real GitHub repositories.
*   **Deployment:** Automated, robust, and highly controlled deployment via CI/CD pipelines to a dedicated production GCP project.
*   **Key Considerations:** Stability, security, scalability, cost optimization, and comprehensive monitoring.

## 2. Environment-Specific Configurations

The `config/config.yaml` file is central to managing environment-specific settings. You can define different `services` blocks or override `default_model_selection` and `default_github_config` based on the environment.

### Example: `config.yaml` for Multiple Environments

While the primary `config.yaml` structure supports multiple services, you might manage different versions of this file for different environments or use environment variables to select configurations.

```yaml
# config/config.yaml (example for production)
# This file would be managed by your CI/CD or configuration management system
gemini_cloud_log_monitor:
  default_model_selection:
    triage_model: "gemini-1.5-flash-001"
    analysis_model: "gemini-1.5-pro-001"
    classification_model: "gemini-2.5-flash-lite"

  default_github_config:
    repository: "your-prod-org/your-prod-repo"
    base_branch: "main"

  logging:
    log_level: "INFO"
    json_format: true
    log_file: "/var/log/gemini-sre-agent.log"

  services:
    - service_name: "prod-billing-service"
      project_id: "your-prod-gcp-project"
      location: "us-central1"
      subscription_id: "prod-billing-logs-sub"
      # ...
```

### Using Environment Variables for Configuration Overrides

For Cloud Run deployments, you can use environment variables to override specific configuration values without modifying the `config.yaml` file within the container image. This is particularly useful for sensitive data or environment-specific settings.

```bash
gcloud run deploy gemini-sre-agent \
  --set-env-vars="LOG_LEVEL=DEBUG,GITHUB_TOKEN=${GITHUB_TOKEN}" \
  # ... other configurations
```

## 3. Promotion Workflows

Promotion workflows define the process of moving code and configurations from one environment to the next (e.g., Development -> Staging -> Production).

### CI/CD Pipeline Integration

Your CI/CD pipeline (e.g., GitHub Actions) should automate the promotion process:

1.  **Development to Staging:**
    *   Merge feature branches to `develop` (or similar) branch.
    *   CI/CD pipeline builds, tests, and deploys to the staging environment.
2.  **Staging to Production:**
    *   Merge `develop` to `main` (or similar) branch after successful UAT.
    *   CI/CD pipeline builds, tests, and deploys to the production environment.

### Configuration Management per Environment

*   **Version Control:** Store environment-specific `config.yaml` files (or templates) in version control, ensuring proper access controls.
*   **Secrets Management:** Use Google Secret Manager (or similar) to manage sensitive environment-specific secrets.
*   **IaC for Environments:** Use Terraform or Pulumi to define and manage environment-specific GCP resources.

## 4. Resource Naming Conventions

Adopt clear and consistent naming conventions for your GCP resources across environments to easily distinguish them (e.g., `prod-gemini-sre-agent-topic`, `dev-gemini-sre-agent-sub`).

## 5. Monitoring and Alerting per Environment

Tailor your monitoring and alerting configurations to the specific needs and criticality of each environment. Production environments will typically have more aggressive alerting thresholds and broader coverage.

```