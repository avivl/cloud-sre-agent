# Troubleshooting Guide

This guide provides systematic approaches for troubleshooting the Cloud SRE Agent using the flow tracking system described in [LOGGING.md](LOGGING.md).

## Overview

The Cloud SRE Agent uses structured logging with flow tracking to enable complete traceability from log ingestion through remediation. Every issue can be traced using:

- **`flow_id`**: Tracks a single log entry through the entire pipeline
- **`issue_id`**: Identifies a specific issue/incident across components

## Common Issues and Solutions

### 1. Log Processing Failures

#### Symptom: Messages are received but not processed
```bash
# Look for LOG_INGESTION messages without corresponding TRIAGE messages
grep "[LOG_INGESTION] Received message" /path/to/logs | head -5
grep "[TRIAGE] Starting triage analysis" /path/to/logs | head -5
```

**Root Cause Analysis:**
```bash
# Find specific flow_id that failed
FLOW_ID="log-20250127-100000"
grep "flow_id=$FLOW_ID" /path/to/logs

# Look for error patterns
grep -E "(flow_id=$FLOW_ID.*ERROR_HANDLING|ERROR_HANDLING.*flow_id=$FLOW_ID)" /path/to/logs
```

**Common Solutions:**
- **JSON Decode Errors**: Check messaging service message format
- **Model API Errors**: Verify cloud platform credentials and quotas
- **Network Issues**: Check connectivity to AI services

#### Symptom: Triage completes but analysis never starts
```bash
# Find triage completion without analysis start
ISSUE_ID="database-connection-failure-001"
grep "issue_id=$ISSUE_ID" /path/to/logs | grep -E "(TRIAGE.*complete|ANALYSIS.*Starting)"
```

**Troubleshooting Steps:**
1. Check if severity threshold is met (default: severity >= 7)
2. Verify AnalysisAgent initialization
3. Check for validation errors in triage output

### 2. GitHub Integration Issues

#### Symptom: Analysis completes but no pull request is created
```bash
# Trace remediation flow
ISSUE_ID="database-connection-failure-001"
grep "issue_id=$ISSUE_ID" /path/to/logs | grep "REMEDIATION"
```

**Common Issues:**
- **Branch Creation Failures**: Look for GitHub API 422 errors
- **File Path Extraction**: Check for "FILE:" comment in code patches
- **Permission Errors**: Verify GitHub token permissions

#### Symptom: "Reference already exists" errors
```bash
# This should be handled idempotently - look for the handling
grep "Branch already exists (idempotent)" /path/to/logs
```

**Expected Behavior:**
The system should gracefully handle existing branches and continue processing.

### 3. Performance Issues

#### Symptom: Processing takes too long
```bash
# Analyze processing times for a specific flow
FLOW_ID="log-20250127-100000"

echo "=== Triage Timing ==="
grep -E "\[TRIAGE\] (Starting|complete)" /path/to/logs | grep "flow_id=$FLOW_ID"

echo "=== Analysis Timing ==="
grep -E "\[ANALYSIS\] (Starting|complete)" /path/to/logs | grep "flow_id=$FLOW_ID"

echo "=== Remediation Timing ==="
grep -E "\[REMEDIATION\] (Creating|created successfully)" /path/to/logs | grep "flow_id=$FLOW_ID"
```

**Performance Benchmarks:**
- Triage: < 10 seconds
- Analysis: < 30 seconds  
- Remediation: < 20 seconds

## Execution Path Tracing Scripts

### Complete Flow Analysis
```bash
#!/bin/bash
# trace_flow.sh - Trace a complete flow from start to finish

FLOW_ID="$1"
if [ -z "$FLOW_ID" ]; then
    echo "Usage: $0 <flow_id>"
    exit 1
fi

echo "=== Tracing Flow: $FLOW_ID ==="
echo

echo "1. LOG INGESTION:"
grep "\[LOG_INGESTION\].*flow_id=$FLOW_ID" /path/to/logs

echo
echo "2. TRIAGE:"
grep "\[TRIAGE\].*flow_id=$FLOW_ID" /path/to/logs

echo
echo "3. ANALYSIS:"
grep "\[ANALYSIS\].*flow_id=$FLOW_ID" /path/to/logs

echo
echo "4. REMEDIATION:"
grep "\[REMEDIATION\].*flow_id=$FLOW_ID" /path/to/logs

echo
echo "5. ERRORS:"
grep "\[ERROR_HANDLING\].*flow_id=$FLOW_ID" /path/to/logs
```

### Issue Impact Analysis
```bash
#!/bin/bash
# issue_analysis.sh - Analyze all flows for a specific issue

ISSUE_ID="$1"
if [ -z "$ISSUE_ID" ]; then
    echo "Usage: $0 <issue_id>"
    exit 1
fi

echo "=== Issue Analysis: $ISSUE_ID ==="

echo
echo "All flows for this issue:"
grep "issue_id=$ISSUE_ID" /path/to/logs | cut -d' ' -f1-3 | sort -u

echo
echo "Success/Failure summary:"
echo "Successful remediations:"
grep "issue_id=$ISSUE_ID.*Pull request created successfully" /path/to/logs | wc -l

echo "Failed attempts:"
grep "issue_id=$ISSUE_ID.*ERROR_HANDLING" /path/to/logs | wc -l
```

### Recent Activity Monitor
```bash
#!/bin/bash
# recent_activity.sh - Monitor recent system activity

TIME_WINDOW="${1:-10m}"  # Default to last 10 minutes

echo "=== Recent Activity (last $TIME_WINDOW) ==="

echo
echo "Flows started:"
grep "\[LOG_INGESTION\] Received message" /path/to/logs | tail -10

echo
echo "Issues triaged:"
grep "\[TRIAGE\] Triage analysis complete" /path/to/logs | tail -5

echo
echo "Pull requests created:"
grep "\[REMEDIATION\] Pull request created successfully" /path/to/logs | tail -5

echo
echo "Recent errors:"
grep "\[ERROR_HANDLING\]" /path/to/logs | tail -10
```

## Debugging Specific Components

### TriageAgent Debugging
```bash
# Check triage model responses
grep "\[TRIAGE\] Raw model response" /path/to/logs | tail -5

# Validation errors
grep "Failed to validate TriagePacket schema" /path/to/logs

# Model call failures  
grep "Error calling AI Triage model" /path/to/logs
```

### AnalysisAgent Debugging
```bash
# Check analysis model responses
grep "\[ANALYSIS\] Raw model response" /path/to/logs | tail -5

# Validation errors
grep "Failed to validate RemediationPlan schema" /path/to/logs

# Model call failures
grep "Error calling AI Analysis model" /path/to/logs
```

### RemediationAgent Debugging
```bash
# GitHub API errors
grep "GitHub API error during PR creation" /path/to/logs

# File path extraction issues
grep "Invalid file path extracted" /path/to/logs

# Branch creation issues
grep "Branch.*already exists\|Branch created successfully" /path/to/logs | tail -10
```

## System Health Checks

### Daily Health Check Script
```bash
#!/bin/bash
# health_check.sh - Daily system health verification

echo "=== Cloud SRE Agent Health Check ==="
echo "Date: $(date)"
echo

# Check for recent activity (last 24 hours)
echo "Messages processed (last 24h):"
grep "\[LOG_INGESTION\] Received message" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l

echo "Issues triaged (last 24h):"
grep "\[TRIAGE\] Triage analysis complete" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l

echo "Pull requests created (last 24h):"
grep "\[REMEDIATION\] Pull request created successfully" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l

echo
echo "Error summary (last 24h):"
echo "Triage errors:"
grep "\[ERROR_HANDLING\].*TRIAGE" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l

echo "Analysis errors:"
grep "\[ERROR_HANDLING\].*ANALYSIS" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l

echo "Remediation errors:"
grep "\[ERROR_HANDLING\].*REMEDIATION" /path/to/logs | grep "$(date +%Y-%m-%d)" | wc -l
```

### Performance Monitoring
```bash
#!/bin/bash
# performance_monitor.sh - Track processing performance

echo "=== Performance Analysis ==="

# Average processing times (requires more sophisticated parsing)
echo "Recent triage completion times:"
grep "\[TRIAGE\] Triage analysis complete" /path/to/logs | tail -10 | while read line; do
    FLOW_ID=$(echo "$line" | grep -o "flow_id=[^,]*" | cut -d= -f2)
    START_TIME=$(grep "\[TRIAGE\] Starting triage analysis.*flow_id=$FLOW_ID" /path/to/logs | head -1 | cut -d' ' -f1)
    END_TIME=$(echo "$line" | cut -d' ' -f1)
    echo "Flow $FLOW_ID: $START_TIME -> $END_TIME"
done
```

## Recovery Procedures

### Stuck Processing Recovery
If a flow appears stuck in processing:

1. **Identify the stuck flow:**
   ```bash
   # Find flows that started but never completed
   grep "\[TRIAGE\] Starting triage analysis" /path/to/logs | tail -10
   grep "\[TRIAGE\] Triage analysis complete" /path/to/logs | tail -10
   ```

2. **Check for errors:**
   ```bash
   FLOW_ID="stuck-flow-id"
   grep "flow_id=$FLOW_ID" /path/to/logs | grep "ERROR_HANDLING"
   ```

3. **Manual retry (if needed):**
   The system has built-in retry mechanisms, but manual intervention may be needed for persistent issues.

### System Restart Recovery
After system restart:

1. **Verify all agents initialize:**
   ```bash
   grep "\[STARTUP\]" /path/to/logs | tail -20
   ```

2. **Check subscription resumption:**
   ```bash
   grep "\[LOG_INGESTION\] Listening for messages" /path/to/logs | tail -1
   ```

3. **Monitor first few messages:**
   ```bash
   grep "\[LOG_INGESTION\] Received message" /path/to/logs | tail -5
   ```

## Alerting Recommendations

### Critical Alerts
- No messages received for > 1 hour
- Error rate > 10% for any component
- No pull requests created for > 4 hours (during business hours)

### Warning Alerts  
- Processing time > 2 minutes for any flow
- Model API errors > 5% rate
- GitHub API errors

### Monitoring Queries
```bash
# Error rate calculation (last hour)
TOTAL=$(grep "\[LOG_INGESTION\] Received message" /path/to/logs | tail -100 | wc -l)
ERRORS=$(grep "\[ERROR_HANDLING\]" /path/to/logs | tail -100 | wc -l)
ERROR_RATE=$(echo "scale=2; $ERRORS * 100 / $TOTAL" | bc)
echo "Error rate: $ERROR_RATE%"
```

## Contact and Escalation

### Log Collection for Support
When reporting issues, collect:

1. **Flow trace:** Complete log output for affected flow_id
2. **Error context:** All ERROR_HANDLING messages with timestamps
3. **Configuration:** Current config.yaml (redacted)
4. **System info:** Configuration, deployment environment

### Support Information
- **Documentation:** [LOGGING.md](LOGGING.md) for log format reference  
- **Architecture:** [ARCHITECTURE.md](../ARCHITECTURE.md) for system design
- **Configuration:** [README.md](../README.md) for setup instructions

---

**Note:** Replace `/path/to/logs` with your actual log file path or use journalctl/kubectl logs as appropriate for your deployment environment.