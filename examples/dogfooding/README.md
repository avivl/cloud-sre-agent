# Dogfooding Testing Environment

A streamlined testing environment for the Gemini SRE Agent that demonstrates the agent's ability to monitor, analyze, and fix both external services and itself.

## Overview

This dogfooding environment consists of three main components:

1. **Problem Service** - A Flask-based service that intentionally produces various error types
2. **SRE Agent Instance #1** - Monitors the Problem Service and creates patches to fix detected issues
3. **SRE Agent Instance #2** - Monitors Instance #1 and creates patches to fix agent crashes and logic errors

## Quick Start

The environment provides two main scripts for testing:

- **`quick_test.py`** - Fast test to verify the system is working
- **`run_dogfood_demo.py`** - Full orchestration of the dogfooding environment

### Prerequisites

- Python 3.12+
- Git repository with GitHub integration configured
- SRE Agent dependencies installed
- **Ollama installed and running locally**

### Installation

1. **Install and start Ollama:**

   ```bash
   # Install Ollama (if not already installed)
   curl -fsSL https://ollama.ai/install.sh | sh

   # Start Ollama service
   ollama serve

   # Pull required models (in a separate terminal)
   ollama pull llama3.1:8b
   ollama pull llama3.1:70b
   ollama pull codellama:7b
   ollama pull codellama:13b
   ```

2. **Install Problem Service dependencies:**

   ```bash
   cd examples/dogfooding/dogfood_service
   uv pip install -r requirements.txt
   ```

3. **Verify configuration files exist:**

   ```bash
   ls examples/dogfooding/configs/
   # Should show: dogfood_instance_1.yaml, dogfood_instance_2.yaml
   ```

4. **Set up GitHub credentials:**

   ```bash
   export GITHUB_TOKEN="your_github_token_here"
   ```

5. **Verify Ollama is running:**
   ```bash
   curl http://localhost:11434/api/tags
   # Should return a list of available models
   ```

### Running the Tests

#### Quick Test (Recommended for first run)

```bash
cd examples/dogfooding
python quick_test.py
```

This will:

- Start the Problem Service
- Start SRE Agent Instance #1
- Trigger 4 error scenarios in sequence
- Generate patches automatically
- Show test results and cleanup

#### Single Agent Mode

```bash
python quick_test.py --single-agent
```

Runs with only the first agent (Fixer), skips the second agent (Meta-Monitor).

#### Full Demo Mode

```bash
python run_dogfood_demo.py
```

This will:

- Start the Problem Service
- Start both SRE Agent instances
- Trigger 4 error scenarios in sequence
- Generate patches automatically
- Run for calculated duration then stop

#### Single Agent Demo

```bash
python run_dogfood_demo.py --single-agent
```

Runs the demo with only the first agent.

### Monitoring

#### Manual Log Monitoring

```bash
# Monitor Problem Service logs
tail -f /tmp/sre-dogfooding/dogfood_service.log

# Monitor SRE Agent Instance #1 logs
tail -f /tmp/sre-dogfooding/sre_agent_1.log

# Monitor SRE Agent Instance #2 logs
tail -f /tmp/sre-dogfooding/sre_agent_2.log
```

#### Check Generated Patches

```bash
# List generated patches
ls -la /tmp/real_patches/

# View a specific patch
cat /tmp/real_patches/patch_*.patch
```

## Architecture

### Problem Service

**Location:** `examples/dogfooding/dogfood_service/`

**Error Endpoints:**

- `GET /error/division` - Triggers ZeroDivisionError
- `GET /error/memory` - Simulates memory exhaustion (with safety limits)
- `GET /error/timeout` - Simulates connection timeouts
- `GET /error/json` - Triggers JSON parsing errors

**Features:**

- Structured JSON logging to `/tmp/sre-dogfooding/dogfood_service.log`
- Health check endpoint at `/`
- Status endpoint at `/status`
- Resource safety limits to prevent system issues

### SRE Agent Instance #1 (Fixer)

**Configuration:** `examples/dogfooding/configs/dogfood_instance_1.yaml`

**Purpose:** Monitors the Problem Service and creates PRs to fix detected issues

**Features:**

- File-based log ingestion using modern ingestion system
- Error detection and categorization
- Automated patch creation with proper labeling
- Fix validation through automated testing

### SRE Agent Instance #2 (Meta-Monitor)

**Configuration:** `examples/dogfooding/configs/dogfood_instance_2.yaml`

**Purpose:** Monitors Instance #1 and creates patches to fix agent crashes and logic errors

**Features:**

- Self-healing capabilities
- Agent crash detection
- Simple logic error fixes
- Conservative fix generation

## Configuration

### Agent Configuration

The dogfooding environment uses the modern ingestion system for both instances:

#### Instance 1 (Dogfood Fixer)

- **Configuration:** `configs/dogfood_instance_1.yaml`
- **Features:** Modern ingestion system with advanced monitoring
- **Log Ingestion:** Monitors dogfood service logs
- **Health Monitoring:** Real-time health checks and metrics
- **Backpressure Management:** Automatic load balancing

#### Instance 2 (Meta-Monitor)

- **Configuration:** `configs/dogfood_instance_2.yaml`
- **Features:** Modern ingestion system for self-healing
- **Log Ingestion:** Monitors SRE Agent 1 logs for self-healing
- **Model Selection:** Configurable primary and fallback models
- **GitHub Integration:** Automated patch creation and labeling

### Environment Variables

```bash
# Required for SRE Agent instances
export USE_NEW_INGESTION_SYSTEM=true
export GITHUB_TOKEN="your_token_here"  # Optional - will use patch files if not provided

# Ollama configuration
export OLLAMA_BASE_URL="http://localhost:11434"
export OLLAMA_MODEL="llama3.1:8b"

# Optional: Custom model selection (overrides config files)
export PRIMARY_MODEL="llama3.1:8b"
export FALLBACK_MODEL="llama3.1:70b"
```

**Note:** If `GITHUB_TOKEN` is not provided or invalid, the SRE Agent will automatically create local patch files instead of GitHub PRs. This allows the dogfooding environment to work without GitHub authentication. Patches are stored in `/tmp/real_patches/`.

## Patch File Management

When GitHub authentication is not available, the SRE Agent automatically creates local patch files instead of PRs. These patch files contain all the information needed to apply fixes.

### Patch File Structure

Patch files are stored in `/tmp/real_patches/` and include:

- **Git patch files** - Standard Git unified diff format
- **JSON metadata files** - Contains structured data about the fix
- **Markdown summary files** - Human-readable description of the fix

### Managing Patch Files

```bash
# List all patch files
ls -la /tmp/real_patches/

# View a specific patch
cat /tmp/real_patches/patch_*.patch

# View patch metadata
cat /tmp/real_patches/patch_*.json
```

### Patch File Contents

Each patch file includes:

- **Root Cause Analysis** - Detailed analysis of the problem
- **Proposed Fix** - The suggested solution
- **Target File** - Which file needs to be modified
- **Patch Content** - The actual code changes (if available)
- **Metadata** - Flow ID, Issue ID, timestamps, status

## Testing

### Running Tests

#### Quick Test (Recommended)

```bash
# Run quick test to verify everything works
python quick_test.py

# Run with single agent only
python quick_test.py --single-agent
```

#### Full Demo Test

```bash
# Run full demo with both agents
python run_dogfood_demo.py

# Run with single agent only
python run_dogfood_demo.py --single-agent
```

#### Unit Tests (Problem Service)

```bash
# Test Problem Service
cd examples/dogfooding/dogfood_service
python -m pytest tests/ -v

# Test specific error scenarios
python -m pytest tests/test_errors.py::TestErrorEndpoints::test_division_error -v

# Test fix validation
python -m pytest tests/test_validation.py -v
```

### Test Coverage

The test suite covers:

- All 4 MVP error endpoints
- Structured logging validation
- Error categorization
- Patch generation and validation
- Performance characteristics
- Integration testing

## Troubleshooting

### Common Issues

1. **Ollama not running:**

   ```bash
   # Check if Ollama is running
   curl http://localhost:11434/api/tags

   # Start Ollama if not running
   ollama serve

   # Check if models are available
   ollama list
   ```

2. **Ollama models not found:**

   ```bash
   # Pull required models
   ollama pull llama3.1:8b
   ollama pull llama3.1:70b
   ollama pull codellama:7b
   ollama pull codellama:13b

   # Verify models are available
   ollama list
   ```

3. **Service won't start:**

   ```bash
   # Check if port 5001 is available
   lsof -i :5001

   # Check Flask installation
   uv pip install Flask==3.0.0

   # If port 5001 is in use, try a different port
   # Edit dogfood_service/app.py and change port=5001 to port=5002
   ```

4. **Agent instances fail to start:**

   ```bash
   # Verify configuration files
   python -c "import yaml; yaml.safe_load(open('configs/dogfood_instance_1.yaml'))"

   # Check GitHub token
   echo $GITHUB_TOKEN

   # Check Ollama connectivity
   curl http://localhost:11434/api/tags
   ```

5. **No patches created:**

   ```bash
   # Check agent logs for errors
   tail -f /tmp/sre-dogfooding/sre_agent_1.log

   # Check if patches directory exists
   ls -la /tmp/real_patches/

   # Verify GitHub permissions (if using GitHub mode)
   curl -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user

   # Check Ollama model responses
   curl -X POST http://localhost:11434/api/generate -d '{"model": "llama3.1:8b", "prompt": "Hello"}'
   ```

6. **Log files not created:**

   ```bash
   # Check /tmp directory permissions
   ls -la /tmp/

   # Create log files manually
   mkdir -p /tmp/sre-dogfooding
   touch /tmp/sre-dogfooding/dogfood_service.log /tmp/sre-dogfooding/sre_agent_1.log /tmp/sre-dogfooding/sre_agent_2.log
   ```

### Debug Mode

Run with debug logging:

```bash
export LOG_LEVEL=DEBUG
python quick_test.py
```

## File Structure

```
examples/dogfooding/
├── dogfood_service/
│   ├── app.py                    # Flask service with 4 MVP error endpoints
│   ├── requirements.txt          # Service dependencies
│   └── tests/                    # Test suite for validation
│       ├── test_errors.py        # Error endpoint tests
│       └── test_validation.py    # Fix validation tests
├── configs/
│   ├── dogfood_instance_1.yaml   # Agent Instance #1 config
│   └── dogfood_instance_2.yaml   # Agent Instance #2 config
├── quick_test.py                 # Quick test script
├── run_dogfood_demo.py           # Full orchestration script
└── README.md                     # This file
```

## Contributing

When adding new error scenarios or features:

1. **Keep files under 250 LOC** for maintainability
2. **Add comprehensive tests** for new functionality
3. **Update configuration files** as needed
4. **Test with both quick_test and run_dogfood_demo**
5. **Verify patch generation** works correctly

## Security Notes

- **GitHub Token:** Use limited-scope tokens for each agent instance
- **Resource Limits:** Built-in safeguards prevent system resource exhaustion
- **Code Review:** All generated patches require manual review before applying
- **Rollback:** Implement rollback mechanisms for failed fixes

## Performance

- **Memory Usage:** Service limited to 1GB per request
- **CPU Usage:** Throttled to prevent system lockup
- **Network Timeouts:** Controlled timeout values
- **Log Rotation:** Automatic log file rotation and cleanup

## Future Enhancements

- **Web Dashboard:** Add web-based monitoring interface
- **Advanced Scenarios:** Add more complex error types
- **Containerization:** Docker Compose for isolated environments
- **Multi-Repository:** Support for multiple repositories
- **ML Integration:** Machine learning for better error classification
- **GitHub Integration:** Direct PR creation when GitHub token is available
