# SRE Agent Dogfooding Environment

This directory contains a comprehensive testing environment for the SRE agent system, including a mock service that generates various types of errors and test scripts to validate the agent's functionality.

## Overview

The dogfooding environment consists of:

- **Dogfood Service**: A Flask application that generates various types of errors for testing
- **SRE Agent Instances**: Two configured SRE agents that monitor the service and generate patches
- **Test Scripts**: Automated testing and demonstration scripts
- **Configuration Files**: YAML configurations for the SRE agents

## Directory Structure

```
examples/dogfooding/
├── dogfood_service/
│   ├── app.py                 # Flask service with error scenarios
│   └── requirements.txt       # Python dependencies
├── configs/
│   ├── dogfood_instance_1.yaml  # SRE Agent 1 configuration
│   └── dogfood_instance_2.yaml  # SRE Agent 2 configuration
├── quick_test.py              # Quick test script
├── run_dogfood_demo.py        # Comprehensive demo script
└── README.md                  # This file
```

## Quick Start

### 1. Install Dependencies

```bash
# Install dogfood service dependencies
cd examples/dogfooding/dogfood_service
pip install -r requirements.txt

# Install SRE agent dependencies (from project root)
cd ../../..
pip install -r requirements.txt
```

### 2. Start Ollama (if using local models)

```bash
# Start Ollama service
ollama serve

# Pull required models
ollama pull llama3.1:8b
```

### 3. Run Quick Test

```bash
# Run a quick test with both agents
python examples/dogfooding/quick_test.py

# Run a quick test with single agent
python examples/dogfooding/quick_test.py --single-agent
```

### 4. Run Comprehensive Demo

```bash
# Run the full demonstration
python examples/dogfooding/run_dogfood_demo.py
```

## Error Scenarios

The dogfood service generates the following types of errors:

### Mathematical Errors
- **Division by Zero**: `GET /error/division`
- Triggers `ZeroDivisionError` exceptions

### Resource Errors
- **Memory Allocation**: `GET /error/memory`
- Triggers `MemoryError` exceptions

### Network Errors
- **Connection Failures**: `GET /error/connection`
- Triggers connection-related exceptions

### Validation Errors
- **Input Validation**: `GET /error/validation`
- Triggers `ValueError` and `TypeError` exceptions

### Random Errors
- **Mixed Scenarios**: `GET /error/random`
- Randomly selects from available error types

## SRE Agent Configuration

### Agent 1 (Primary Monitor)
- **Log Source**: `/tmp/sre-dogfooding/agent_1.log`
- **Model**: `llama3.1:8b` (Ollama)
- **Patterns**: Mathematical and resource errors
- **Patch Directory**: `/tmp/real_patches`

### Agent 2 (Secondary Monitor)
- **Log Source**: `/tmp/sre-dogfooding/agent_2.log`
- **Model**: `llama3.1:8b` (Ollama)
- **Patterns**: General error patterns
- **Patch Directory**: `/tmp/real_patches`

## Log Analysis

The test scripts automatically analyze generated logs and provide:

- **Log Entry Counts**: Total entries per log file
- **Error Classification**: Errors, warnings, and info messages
- **Pattern Detection**: Specific error types detected
- **Processing Statistics**: Analysis and remediation operations

## Patch Generation

The SRE agents generate patches in JSON format stored in `/tmp/real_patches/`. Each patch includes:

- **Issue Title**: Description of the problem
- **Status**: Current patch status
- **Priority**: Issue priority level
- **Remediation Plan**: Detailed fix instructions
- **Metadata**: Timestamps, flow IDs, and context

## Monitoring and Debugging

### Log Files
- **Agent 1**: `/tmp/sre-dogfooding/agent_1.log`
- **Agent 2**: `/tmp/sre-dogfooding/agent_2.log`
- **Dogfood Service**: Console output

### Real-time Monitoring
```bash
# Monitor agent logs
tail -f /tmp/sre-dogfooding/agent_1.log
tail -f /tmp/sre-dogfooding/agent_2.log

# Monitor patch generation
watch -n 1 'ls -la /tmp/real_patches/'
```

### Debug Mode
All agents run in DEBUG mode by default, providing detailed logging information for troubleshooting.

## Troubleshooting

### Common Issues

1. **Service Won't Start**
   - Check if port 5001 is available
   - Verify Flask dependencies are installed
   - Check service logs for errors

2. **Agents Not Processing Logs**
   - Verify Ollama is running and models are available
   - Check agent configuration files
   - Ensure log directories exist and are writable

3. **No Patches Generated**
   - Verify agents are detecting errors in logs
   - Check patch directory permissions
   - Review agent logs for processing errors

### Debug Commands

```bash
# Check service health
curl http://127.0.0.1:5001/

# Test error endpoints
curl http://127.0.0.1:5001/error/division
curl http://127.0.0.1:5001/error/memory

# Check agent status
ps aux | grep "main.py"

# Verify log generation
ls -la /tmp/sre-dogfooding/
```

## Customization

### Adding New Error Scenarios

1. Add new endpoints to `dogfood_service/app.py`
2. Update agent configuration patterns
3. Test with the provided scripts

### Modifying Agent Behavior

1. Edit configuration files in `configs/`
2. Adjust logging levels, models, or thresholds
3. Restart agents to apply changes

### Extending Test Scripts

1. Modify `quick_test.py` for basic testing
2. Extend `run_dogfood_demo.py` for comprehensive scenarios
3. Add custom analysis functions as needed

## Performance Considerations

- **Log Rotation**: Consider implementing log rotation for long-running tests
- **Resource Usage**: Monitor memory usage during memory error scenarios
- **Model Performance**: Adjust model parameters based on system capabilities
- **Concurrent Processing**: Test with multiple simultaneous error scenarios

## Integration with CI/CD

The dogfooding environment can be integrated into CI/CD pipelines:

```bash
# Run in CI environment
python examples/dogfooding/quick_test.py --single-agent

# Check exit code for success/failure
echo $?
```

## Contributing

When adding new features to the dogfooding environment:

1. Update this README with new functionality
2. Add appropriate test cases
3. Ensure backward compatibility
4. Test with both single and dual agent configurations
