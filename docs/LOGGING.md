# Logging and Flow Tracking System

The Gemini SRE Agent implements comprehensive flow tracking with structured logging to enable complete end-to-end traceability from log ingestion through remediation.

## Overview

Every log entry processed by the system can be traced through the entire pipeline using two key identifiers:

- **`flow_id`**: Extracted from the original log's `insertId`, tracks the processing of a single log entry
- **`issue_id`**: Generated during triage, identifies a specific issue/incident across the pipeline

## Flow Tracking Architecture

```
Log Entry (insertId) → flow_id → [TRIAGE] → issue_id → [ANALYSIS] → [REMEDIATION] → PR
```

## Log Flow Prefixes

The system uses standardized prefixes to categorize all log messages:

### 1. `[LOG_INGESTION]` - Message Processing
- **Purpose**: Tracks Pub/Sub message reception and processing
- **Components**: `LogSubscriber` class
- **Key Events**: Message received, acknowledged, processing errors

### 2. `[TRIAGE]` - Issue Detection
- **Purpose**: Tracks log analysis and issue identification
- **Components**: `TriageAgent` class
- **Key Events**: Analysis start, completion, model responses, validation errors

### 3. `[ANALYSIS]` - Root Cause Analysis
- **Purpose**: Tracks deep analysis and remediation plan generation
- **Components**: `AnalysisAgent` class
- **Key Events**: Analysis start, completion, model responses, plan generation

### 4. `[REMEDIATION]` - GitHub Integration
- **Purpose**: Tracks pull request creation and code fixes
- **Components**: `RemediationAgent` class
- **Key Events**: Branch creation, file updates, PR creation, GitHub API calls

### 5. `[STARTUP]` - System Initialization
- **Purpose**: Tracks system startup and configuration
- **Components**: `main.py` initialization
- **Key Events**: Agent initialization, service setup, configuration loading

### 6. `[ERROR_HANDLING]` - Error Processing
- **Purpose**: Tracks all error conditions across the system
- **Components**: All agents and main pipeline
- **Key Events**: API errors, validation failures, processing errors

## Log Message Format

All log messages follow this standardized format:

```
[FLOW_PREFIX] Message description: flow_id={flow_id}, issue_id={issue_id}, additional_context=value
```

### Examples

**Log Ingestion:**
```
[LOG_INGESTION] Received message: flow_id=abc-123
[LOG_INGESTION] Message acknowledged: flow_id=abc-123, message_id=msg-456
```

**Triage Phase:**
```
[TRIAGE] Analyzing 1 log entries for triage: flow_id=abc-123
[TRIAGE] Triage analysis complete: flow_id=abc-123, issue_id=issue-xyz-789, severity=8
```

**Analysis Phase:**
```
[ANALYSIS] Analyzing issue: flow_id=abc-123, issue_id=issue-xyz-789, historical_logs=1, configs=0
[ANALYSIS] Analysis complete: flow_id=abc-123, issue_id=issue-xyz-789
```

**Remediation Phase:**
```
[REMEDIATION] Attempting to create pull request: flow_id=abc-123, issue_id=issue-xyz-789, branch=fix/issue-xyz-789, target=main
[REMEDIATION] Branch created successfully: flow_id=abc-123, issue_id=issue-xyz-789, branch=fix/issue-xyz-789
[REMEDIATION] Updated service code file: flow_id=abc-123, issue_id=issue-xyz-789, file=service.py
[REMEDIATION] Pull request created successfully: flow_id=abc-123, issue_id=issue-xyz-789, pr_url=https://github.com/...
```

**Error Handling:**
```
[ERROR_HANDLING] Failed to validate TriagePacket schema: flow_id=abc-123, error=ValidationError(...)
[ERROR_HANDLING] GitHub API error during PR creation: flow_id=abc-123, issue_id=issue-xyz-789, status=422, data={...}
```

## Tracing Execution Paths

### Complete Flow Example

Here's a complete execution trace for a single log entry:

```
2025-01-27T10:00:00Z [LOG_INGESTION] Received message: flow_id=log-20250127-100000
2025-01-27T10:00:01Z [LOG_INGESTION] Processing log data for my-service: flow_id=log-20250127-100000
2025-01-27T10:00:01Z [TRIAGE] Starting triage analysis: flow_id=log-20250127-100000
2025-01-27T10:00:02Z [TRIAGE] Analyzing 1 log entries for triage: flow_id=log-20250127-100000
2025-01-27T10:00:05Z [TRIAGE] Triage analysis complete: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, severity=9
2025-01-27T10:00:05Z [TRIAGE] Triage completed for service=my-service: flow_id=log-20250127-100000, issue_id=database-connection-failure-001
2025-01-27T10:00:05Z [ANALYSIS] Starting deep analysis: flow_id=log-20250127-100000, issue_id=database-connection-failure-001
2025-01-27T10:00:06Z [ANALYSIS] Analyzing issue: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, historical_logs=1, configs=0
2025-01-27T10:00:12Z [ANALYSIS] Analysis complete: flow_id=log-20250127-100000, issue_id=database-connection-failure-001
2025-01-27T10:00:12Z [ANALYSIS] Analysis completed for service=my-service: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, proposed_fix=Add connection retry logic with exponential backoff...
2025-01-27T10:00:12Z [REMEDIATION] Creating pull request: flow_id=log-20250127-100000, issue_id=database-connection-failure-001
2025-01-27T10:00:13Z [REMEDIATION] Attempting to create pull request: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, branch=fix/database-connection-failure-001, target=main
2025-01-27T10:00:14Z [REMEDIATION] Branch created successfully: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, branch=fix/database-connection-failure-001
2025-01-27T10:00:15Z [REMEDIATION] Updated service code file: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, file=database.py
2025-01-27T10:00:16Z [REMEDIATION] Pull request created successfully: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, pr_url=https://github.com/myorg/myrepo/pull/123
2025-01-27T10:00:16Z [REMEDIATION] Pull request created successfully: flow_id=log-20250127-100000, issue_id=database-connection-failure-001, pr_url=https://github.com/myorg/myrepo/pull/123
2025-01-27T10:00:16Z [LOG_INGESTION] Message acknowledged: flow_id=log-20250127-100000, message_id=projects/my-project/subscriptions/my-sub-456
```

## Debugging and Monitoring

### Finding Issues by Flow ID

To trace a specific log entry through the entire pipeline:

```bash
# Find all events for a specific flow_id
grep "flow_id=log-20250127-100000" /path/to/logs

# Find all events for a specific issue_id
grep "issue_id=database-connection-failure-001" /path/to/logs

# Find errors in a specific flow
grep -E "(flow_id=log-20250127-100000.*ERROR_HANDLING|ERROR_HANDLING.*flow_id=log-20250127-100000)" /path/to/logs
```

### Performance Analysis

Track processing times by analyzing timestamps:

```bash
# Extract processing start/end times for performance analysis
grep -E "\[TRIAGE\] (Starting|complete)" /path/to/logs | grep "flow_id=log-20250127-100000"
grep -E "\[ANALYSIS\] (Starting|complete)" /path/to/logs | grep "flow_id=log-20250127-100000"
grep -E "\[REMEDIATION\] (Creating|created successfully)" /path/to/logs | grep "flow_id=log-20250127-100000"
```

### Common Patterns

**Successful Processing:**
```
LOG_INGESTION → TRIAGE → ANALYSIS → REMEDIATION → Success
```

**Triage Failure:**
```
LOG_INGESTION → TRIAGE → ERROR_HANDLING (stops here)
```

**Analysis Failure:**
```
LOG_INGESTION → TRIAGE → ANALYSIS → ERROR_HANDLING (stops here)
```

**Remediation Failure:**
```
LOG_INGESTION → TRIAGE → ANALYSIS → REMEDIATION → ERROR_HANDLING (stops here)
```

## Log Levels

The system uses Python's standard logging levels:

- **DEBUG**: Detailed diagnostic information (model prompts, raw responses)
- **INFO**: General information about processing flow
- **WARNING**: Non-critical issues (missing file paths, idempotent operations)
- **ERROR**: Error conditions that stop processing

## Configuration

Log levels and formats can be configured in `config.yaml`:

```yaml
gemini_cloud_log_monitor:
  logging:
    log_level: "INFO"      # DEBUG, INFO, WARNING, ERROR
    json_format: false     # true for structured JSON logging
    log_file: null         # null for console, or path for file logging
```

## Monitoring Integration

The structured logging format is designed to integrate with monitoring systems:

### Prometheus Metrics (Future Enhancement)
```
sre_agent_flows_total{flow_prefix="TRIAGE", status="success"}
sre_agent_processing_duration_seconds{flow_prefix="ANALYSIS"}
sre_agent_errors_total{flow_prefix="REMEDIATION", error_type="github_api"}
```

### Log Aggregation (Splunk/ELK)
```
flow_id="*" AND [REMEDIATION] AND "Pull request created successfully"
issue_id="*" AND [ERROR_HANDLING]
[TRIAGE] AND severity>=8
```

## Troubleshooting Guide

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed troubleshooting procedures using the logging system.