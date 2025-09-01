# Performance Tuning Guide

This guide provides recommendations and strategies for optimizing the performance and cost-efficiency of the Gemini SRE Agent. Effective performance tuning ensures the agent operates efficiently, especially under high log volumes, and minimizes operational costs.

## 1. Model Selection Optimization

Choosing the right Gemini model for each task is crucial for balancing performance, accuracy, and cost.

*   **Triage Agent:** Prioritize **Gemini Flash models** (e.g., `gemini-1.5-flash-001`). These models are designed for speed and cost-efficiency, making them ideal for rapid, high-volume log triage where a quick, preliminary assessment is sufficient.
*   **Analysis Agent:** Utilize **Gemini Pro models** (e.g., `gemini-1.5-pro-001`) for deep root cause analysis and complex remediation plan generation. These models offer superior reasoning capabilities, which are necessary for intricate problem-solving, even if they come with higher latency and cost.
*   **Experimentation:** Continuously evaluate new model versions and fine-tuned models as they become available to identify further optimization opportunities.

## 2. Resource Allocation Tuning (Cloud Run)

For Cloud Run deployments, optimizing CPU and memory allocation directly impacts performance and cost.

*   **CPU Allocation:**
    *   **Initial:** Start with 1 CPU for most workloads.
    *   **Scaling:** Increase CPU if you observe high CPU utilization or latency during peak processing times. Gemini model inference can be CPU-intensive.
*   **Memory Allocation:**
    *   **Initial:** Start with 512MiB to 1GiB.
    *   **Scaling:** Increase memory if you encounter out-of-memory errors or observe high memory utilization. Larger models or complex log processing might require more memory.
*   **Concurrency:**
    *   **Definition:** The number of requests a single container instance can process simultaneously.
    *   **Tuning:** Start with a lower concurrency (e.g., 1-10) and gradually increase it while monitoring CPU/memory utilization and latency. Higher concurrency can improve resource utilization but might lead to resource contention if not properly tuned.

## 3. Scaling Considerations

Cloud Run automatically scales the number of container instances based on incoming request volume. Proper configuration ensures responsiveness and cost efficiency.

*   **`min-instances`:** Set to 0 for cost optimization when idle. If you require very low latency for initial log processing, you might set `min-instances` to 1 to keep an instance warm.
*   **`max-instances`:** Configure based on your expected peak load and budget. A higher `max-instances` allows the agent to handle sudden spikes in log volume.
*   **Cold Starts:** Be aware of cold starts when scaling from zero instances. Optimize your Docker image and application startup time to minimize cold start latency.

## 4. Cost Optimization Strategies

Minimizing operational costs is a key aspect of performance tuning.

*   **Optimize Log Filters:** In your Cloud Logging sinks, use precise filters to export only the necessary logs to Pub/Sub. This reduces Pub/Sub message volume and subsequent processing costs.
*   **Pub/Sub Message Retention:** Adjust the `message_retention_duration` for your Pub/Sub subscriptions to the minimum required (e.g., 1-3 days) to reduce storage costs.
*   **Model Usage:** Be mindful of the number of calls to Gemini models. Optimize prompts to be concise and effective, reducing token usage.
*   **Cloud Run Resource Allocation:** Continuously monitor and adjust CPU, memory, and concurrency settings to match actual workload demands, avoiding over-provisioning.
*   **Serverless First:** Cloud Run's pay-per-use model is inherently cost-efficient for event-driven workloads. Leverage this by allowing instances to scale to zero when idle.

## 5. Performance Monitoring

Regularly monitor the agent's performance to identify bottlenecks and areas for optimization.

*   **Google Cloud Monitoring:** Create custom dashboards to track key metrics:
    *   **End-to-End Latency:** From log ingestion to PR creation.
    *   **Agent Processing Time:** Time taken by `TriageAgent` and `AnalysisAgent` to process a log entry.
    *   **Model Inference Latency:** Latency of Gemini API calls.
    *   **GitHub API Latency:** Latency of GitHub API calls.
*   **Structured Logging Analysis:** Use your structured logs to analyze processing times, error rates, and resource utilization at a granular level.
*   **Tracing:** Implement distributed tracing (e.g., using OpenTelemetry with Cloud Trace) to visualize the flow of a single log entry through the entire agent pipeline and identify latency hotspots.
