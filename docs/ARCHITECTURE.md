# Architecture Overview

The Gemini SRE Agent is designed with a modular and extensible architecture, enabling autonomous log monitoring, analysis, and remediation within Google Cloud environments. The system operates on a continuous, event-driven loop, leveraging Google's Gemini models for intelligent decision-making and the `hyx` library for robust resilience.

## Core Components

The agent's functionality is distributed across several key components, each with a specific role in the incident response workflow:

### 1. Log Ingestion (`LogIngestor`)
*   **Role:** Responsible for retrieving historical logs from Google Cloud Logging.
*   **Functionality:** Primarily used for initial data loading or backfilling purposes. In a real-time scenario, logs are typically streamed via Pub/Sub.

### 2. Log Subscription (`LogSubscriber`)
*   **Role:** Acts as the real-time entry point for log data.
*   **Functionality:** Subscribes to Google Cloud Pub/Sub topics where logs are exported from Cloud Logging. It receives, parses, and dispatches log entries for further processing via a configurable callback. Extracts `flow_id` from log `insertId` for complete pipeline traceability. Designed for continuous processing without fixed timeouts and includes comprehensive error handling with message acknowledgment patterns.

### 3. Triage Agent (`TriageAgent`)
*   **Role:** Performs rapid, preliminary analysis of incoming log data.
*   **Functionality:** Utilizes a **Gemini Flash model** for quick assessment. It identifies potential issues, assigns a preliminary severity score, and summarizes the findings into a structured `TriagePacket`. This acts as a crucial filtering step to prioritize critical events. Includes built-in retry mechanisms for model calls to enhance robustness. All operations include `flow_id` tracking for complete traceability.

### 4. Analysis Agent (`AnalysisAgent`)
*   **Role:** Conducts in-depth root cause analysis and generates comprehensive remediation plans focused on service code fixes.
*   **Functionality:** Receives `TriagePacket`s from the `TriageAgent`. It employs a more powerful **Gemini Pro model** to perform detailed analysis, incorporating the current log as context along with historical data and relevant configuration. The output is a `RemediationPlan` detailing root cause, proposed service code fix, and code patches with file path instructions. Includes built-in retry mechanisms and comprehensive flow tracking with both `flow_id` and `issue_id`.

### 5. Remediation Agent (`RemediationAgent`)
*   **Role:** Automates the implementation of proposed service code remediation actions.
*   **Functionality:** Receives `RemediationPlan`s and interacts with GitHub to create branches, commit service code changes, and submit Pull Requests. Features idempotent branch creation for retry scenarios and extracts file paths from code patch comments. Integrates AI-driven insights into the development workflow with human-in-the-loop validation. All GitHub operations include comprehensive flow tracking.

### 6. Quantitative Verification Agent (`QuantitativeAnalyzer`)
*   **Role:** Provides empirical validation of analysis findings through automated code execution.
*   **Implementation:** Uses Gemini API's Code Execution capability to:
    *   Generate Python code for precise error rate calculations
    *   Validate hypotheses with statistical analysis
    *   Perform quantitative verification of findings
*   **Integration:** Works in conjunction with AnalysisAgent to provide data-driven validation of AI analysis results.

## Flow Tracking System

The system implements comprehensive end-to-end traceability using standardized identifiers:

*   **`flow_id`**: Extracted from the original log's `insertId`, tracks a single log entry through the entire pipeline
*   **`issue_id`**: Generated during triage analysis, identifies a specific issue/incident across all components

Every log message uses standardized prefixes (`[LOG_INGESTION]`, `[TRIAGE]`, `[ANALYSIS]`, `[REMEDIATION]`, `[ERROR_HANDLING]`) with both identifiers for complete operational visibility. For detailed information on using this system for troubleshooting and monitoring, see [LOGGING.md](LOGGING.md) and [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

## Data Flow and Interaction

The agent operates in a continuous feedback loop with complete flow tracking:

```mermaid
sequenceDiagram
    participant CL as Cloud Logging
    participant PS as Pub/Sub
    participant LS as LogSubscriber
    participant TA as TriageAgent<br/>(Flash)
    participant AA as AnalysisAgent<br/>(Pro)
    participant QA as QuantitativeAnalyzer<br/>(Code Execution)
    participant RA as RemediationAgent
    participant GH as GitHub

    CL->>PS: Export logs (severity>=ERROR)
    PS->>LS: Push log message
    LS->>TA: process_log_data(log_entry)
    
    Note over TA: Quick classification<br/>Gemini Flash
    TA->>TA: Generate TriagePacket
    
    alt Issue Severity >= HIGH
        TA->>AA: analyze_issue(triage_packet)
        
        Note over AA: Deep root cause analysis<br/>Gemini Pro
        AA->>AA: Analyze historical logs<br/>+ configuration context
        
        AA->>QA: validate_hypothesis(analysis_result)
        Note over QA: Generate & execute<br/>Python validation code
        QA->>AA: empirical_data
        
        AA->>RA: create_pull_request(remediation_plan)
        Note over RA: Generate code patches<br/>& PR description
        RA->>GH: Create branch & PR
        GH-->>RA: PR URL
        
        RA-->>LS: Success notification
    else Issue Severity < HIGH
        TA-->>LS: Log and continue
    end
```

### Detailed Process Flow

1.  **Logs to Pub/Sub:** Google Cloud Logging is configured to export relevant log streams to designated Pub/Sub topics.
2.  **Subscriber Activation:** The `main.py` orchestrator launches an asynchronous task for each configured service. The `LogSubscriber` within each task listens to its respective Pub/Sub topic. Upon receiving a new log message, it triggers an asynchronous processing pipeline via a callback.
3.  **Triage & Analysis Pipeline:** The received log data is first sent to the `TriageAgent`. If a significant issue is identified, the resulting `TriagePacket` is then passed to the `AnalysisAgent` for deeper investigation. Both agents incorporate retry logic for their Gemini model interactions. The `AnalysisAgent` may also interact with the `QuantitativeAnalyzer` for empirical validation of its findings.
4.  **Remediation Trigger:** Once the `AnalysisAgent` generates a `RemediationPlan`, it is forwarded to the `RemediationAgent`.
5.  **GitHub Integration:** The `RemediationAgent` interacts with the configured GitHub repository to create a new branch, commit the proposed changes (code patches, IaC fixes), and open a Pull Request. This PR serves as a critical human-in-the-loop checkpoint for reviewing and approving automated remediation.

## Multi-Service and Multi-Repository Design

The agent is designed to monitor multiple services concurrently. This is achieved through a flexible configuration (`config.yaml`) that allows defining a list of services, each with its own GCP project, location, and Pub/Sub subscription. Furthermore, each service can optionally override the default GitHub repository settings, enabling remediation actions to be directed to different repositories as needed. This modularity ensures scalability and adaptability across diverse microservice architectures.

## Resilience and Observability

*   **Resilience:** Critical operations within the agents are wrapped with resilience patterns (retries, circuit breakers, bulkheads, rate limiting) using the `hyx` library. Additionally, `asyncio.wait_for()` is used to enforce timeouts on asynchronous operations, ensuring the system remains stable and responsive even under adverse conditions like transient network issues, API rate limits, or service outages.
*   **Structured Logging:** All components utilize a centralized structured logging framework with comprehensive flow tracking. The system implements complete end-to-end traceability using `flow_id` (from log `insertId`) and `issue_id` parameters that flow through all subsystems. For detailed information on the logging format and flow tracking system, see [LOGGING.md](LOGGING.md).
