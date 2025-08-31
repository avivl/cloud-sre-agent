# Architecture Overview

The Gemini SRE Agent is designed with a modular and extensible architecture, enabling autonomous log monitoring, analysis, and remediation within Google Cloud environments. The system operates on a continuous, event-driven loop, leveraging Google's Gemini models for intelligent decision-making and the `hyx` library for robust resilience.

## Core Components

The agent's functionality is distributed across several key components, each with a specific role in the incident response workflow:

### 1. Log Ingestion (`LogIngestor`)
*   **Role:** Responsible for retrieving historical logs from Google Cloud Logging.
*   **Functionality:** Primarily used for initial data loading or backfilling purposes. In a real-time scenario, logs are typically streamed via Pub/Sub.

### 2. Log Subscription (`LogSubscriber`)
*   **Role:** Acts as the real-time entry point for log data.
*   **Functionality:** Subscribes to Google Cloud Pub/Sub topics where logs are exported from Cloud Logging. It receives, parses, and dispatches log entries for further processing. Designed to handle asynchronous message processing and acknowledgment.

### 3. Triage Agent (`TriageAgent`)
*   **Role:** Performs rapid, preliminary analysis of incoming log data.
*   **Functionality:** Utilizes a **Gemini Flash model** (e.g., `gemini-1.5-flash-001`) for quick assessment. It identifies potential issues, assigns a preliminary severity score, and summarizes the findings into a structured `TriagePacket`. This acts as a crucial filtering step to prioritize critical events.

### 4. Analysis Agent (`AnalysisAgent`)
*   **Role:** Conducts in-depth root cause analysis and generates comprehensive remediation plans.
*   **Functionality:** Receives `TriagePacket`s from the `TriageAgent`. It employs a more powerful **Gemini Pro model** (e.g., `gemini-1.5-pro-001`) to perform detailed analysis, often incorporating historical logs and relevant configuration data. The output is a `RemediationPlan`, detailing the root cause, proposed fix, and potential code or Infrastructure as Code (IaC) patches.

### 5. Remediation Agent (`RemediationAgent`)
*   **Role:** Automates the implementation of proposed remediation actions.
*   **Functionality:** Receives `RemediationPlan`s. It interacts with GitHub to create new branches, commit the suggested code/IaC changes, and submit Pull Requests for review and approval. This component integrates the AI-driven insights directly into the development workflow, enabling a human-in-the-loop validation step.

## Data Flow and Interaction

The agent operates in a continuous feedback loop:

1.  **Logs to Pub/Sub:** Google Cloud Logging is configured to export relevant log streams to designated Pub/Sub topics.
2.  **Subscriber Activation:** The `LogSubscriber` listens to these topics. Upon receiving a new log message, it triggers an asynchronous processing pipeline.
3.  **Triage & Analysis Pipeline:** The received log data is first sent to the `TriageAgent`. If a significant issue is identified, the resulting `TriagePacket` is then passed to the `AnalysisAgent` for deeper investigation.
4.  **Remediation Trigger:** Once the `AnalysisAgent` generates a `RemediationPlan`, it is forwarded to the `RemediationAgent`.
5.  **GitHub Integration:** The `RemediationAgent` interacts with the configured GitHub repository to create a new branch, commit the proposed changes (code patches, IaC fixes), and open a Pull Request. This PR serves as a critical human-in-the-loop checkpoint for reviewing and approving automated remediation.

## Multi-Service and Multi-Repository Design

The agent is designed to monitor multiple services concurrently. This is achieved through a flexible configuration (`config.yaml`) that allows defining a list of services, each with its own GCP project, location, and Pub/Sub subscription. Furthermore, each service can optionally override the default GitHub repository settings, enabling remediation actions to be directed to different repositories as needed. This modularity ensures scalability and adaptability across diverse microservice architectures.

## Resilience and Observability

*   **Resilience:** Critical operations within the agents are wrapped with resilience patterns (retries, circuit breakers, bulkheads, rate limiting) using the `hyx` library. This ensures the system remains stable and responsive even under adverse conditions like transient network issues, API rate limits, or service outages.
*   **Structured Logging:** All components utilize a centralized structured logging framework. Logs are output in JSON format in production environments, facilitating easy ingestion and analysis by external log aggregation systems (e.g., Google Cloud Logging, Cloud Monitoring). Logs include contextual information (e.g., request IDs, trace IDs) for end-to-end traceability and debugging.
