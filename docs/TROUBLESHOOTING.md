# Troubleshooting Guide

This guide provides solutions to common issues you might encounter while setting up, deploying, or running the Gemini SRE Agent.

## 1. Authentication and Permission Issues

### Issue: `google.api_core.exceptions.ServiceUnavailable: 503 Getting metadata from plugin failed with error: Reauthentication is needed.`

**Cause:** Your `gcloud` application default credentials have expired or are invalid.

**Solution:** Reauthenticate your `gcloud` CLI by running:
```bash
gcloud auth application-default login
```
Follow the prompts in your browser to complete the authentication process.

### Issue: `google.api_core.exceptions.NotFound: 404 Publisher Model ... was not found or your project does not have access to it.`

**Cause:** The specified Gemini model is not available in your project/location, or your service account lacks the necessary permissions.

**Solution:**
1.  **Verify Project ID and Location:** Ensure the `project_id` and `location` in your `config/config.yaml` (or service-specific overrides) are correct for your GCP project.
2.  **Check Model Availability:** In the GCP Console, navigate to **Vertex AI > Language models** or **Vertex AI > Model Garden** for your project. Verify that the specified Gemini models (e.g., `gemini-1.5-flash-001`, `gemini-1.5-pro-001`) are available in the region you are using (`us-central1` by default).
3.  **Enable Vertex AI API:** Ensure the Vertex AI API is enabled in your GCP project.
4.  **Check Service Account Permissions:** Confirm that the service account running the agent has the `Vertex AI User` role (`roles/aiplatform.user`) in that project.

### Issue: `github.GithubException: 401 Unauthorized` or `403 Forbidden`

**Cause:** Your GitHub Personal Access Token (PAT) is invalid, has expired, or lacks the necessary `repo` scope.

**Solution:**
1.  **Verify PAT:** Go to your GitHub settings > Developer settings > Personal access tokens and ensure your PAT is still valid.
2.  **Check Scopes:** Confirm that your PAT has the `repo` scope enabled.
3.  **Environment Variable:** Ensure the `GITHUB_TOKEN` environment variable is correctly set in your environment where the agent is running.

## 2. Pub/Sub Configuration Problems

### Issue: Agent not receiving messages from Pub/Sub

**Cause:** The Pub/Sub topic or subscription is misconfigured, or the Cloud Logging sink is not correctly exporting logs.

**Solution:**
1.  **Verify Pub/Sub Topic and Subscription:**
    *   Ensure the Pub/Sub topic and subscription exist and their names match those in your `config/config.yaml`.
    *   Use `gcloud pubsub topics describe YOUR_TOPIC_NAME` and `gcloud pubsub subscriptions describe YOUR_SUBSCRIPTION_NAME` to verify.
2.  **Check Cloud Logging Sink:**
    *   Verify that the Cloud Logging sink exists and is correctly configured to export logs to your Pub/Sub topic.
    *   Ensure the sink's filter matches the logs you expect to be exported.
    *   Check the sink's writer identity has the `roles/pubsub.publisher` role on the Pub/Sub topic.
3.  **Log Volume:** Confirm that logs are actually being generated and sent to Cloud Logging for the services you are monitoring.

## 3. Deployment Errors

### Issue: Docker image build fails

**Cause:** Missing dependencies, incorrect `Dockerfile` path, or issues with `uv` installation.

**Solution:**
1.  **Check `Dockerfile`:** Ensure the `Dockerfile` is in the project root and is correctly written.
2.  **Verify `uv` installation:** Run `uv --version` to confirm `uv` is installed and accessible.
3.  **Dependency Issues:** Ensure `pyproject.toml` is correctly formatted and all dependencies are resolvable.

### Issue: Cloud Run deployment fails

**Cause:** Incorrect `gcloud` command, insufficient permissions for the deploying user/service account, or issues with the Docker image.

**Solution:**
1.  **`gcloud` CLI Configuration:** Ensure your `gcloud` CLI is authenticated and configured for the correct project and region.
2.  **IAM Permissions:** The user or service account deploying to Cloud Run needs the `Cloud Run Developer` role (`roles/run.developer`) and `Service Account User` role (`roles/iam.serviceAccountUser`) on the service account used by the Cloud Run service.
3.  **Docker Image:** Verify that the Docker image was successfully built and pushed to GCR.
4.  **Cloud Run Logs:** Check the Cloud Run service logs in GCP Console for more detailed error messages.

## 4. Model API and Billing Troubleshooting

### Issue: Gemini model calls are slow or fail frequently

**Cause:** API rate limits, network latency, or model capacity issues.

**Solution:**
1.  **Check Quotas:** Review your Vertex AI API quotas in the GCP Console. You might be hitting rate limits.
2.  **Monitor Latency:** Use Cloud Monitoring to observe latency metrics for Vertex AI API calls.
3.  **Resilience Configuration:** Adjust the resilience parameters in `config/config.yaml` (e.g., `retry` attempts, `wait` times, `bulkhead` limits) to better handle transient issues.

### Issue: Unexpected billing charges for Vertex AI

**Cause:** High volume of model calls, using expensive models, or inefficient prompt design.

**Solution:**
1.  **Monitor Usage:** Regularly review your Vertex AI usage in the GCP Billing console.
2.  **Model Selection:** Ensure you are using the most cost-effective models for each task (e.g., Flash models for triage, Pro models for analysis only when necessary).
3.  **Prompt Optimization:** Optimize your prompts to reduce token usage and unnecessary model calls.
4.  **Logging:** Use the agent's structured logging to track model call frequency and associated costs.

## 5. GitHub Integration Issues

### Issue: Agent fails to create branches or Pull Requests

**Cause:** Incorrect GitHub PAT, insufficient PAT scopes, or repository access issues.

**Solution:**
1.  **Verify PAT:** Double-check your `GITHUB_TOKEN` environment variable and ensure the PAT is valid and not expired.
2.  **Check PAT Scopes:** Confirm that the PAT has the `repo` scope enabled, which grants full control over private repositories.
3.  **Repository Access:** Ensure the GitHub user associated with the PAT has write access to the target repository.
4.  **GitHub API Rate Limits:** Check if you are hitting GitHub API rate limits. The `RemediationAgent` does not currently implement specific rate limiting for GitHub API calls, which could be a future enhancement.
