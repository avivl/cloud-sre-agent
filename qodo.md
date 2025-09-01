# Repository Tour

## 🎯 What This Repository Does

**Gemini SRE Agent** is an autonomous system designed to monitor Google Cloud logs, detect anomalies, perform root cause analysis, and automate remediation actions by creating GitHub Pull Requests. It leverages Google's Gemini models for intelligent triage and analysis, and is built with resilience patterns using the `hyx` library.

**Key responsibilities:**
- Monitor logs from multiple Google Cloud services via Pub/Sub subscriptions
- Perform intelligent triage using Gemini Flash models for rapid analysis
- Conduct deep root cause analysis using Gemini Pro models
- Generate automated remediation plans and create GitHub Pull Requests
- Maintain system resilience with circuit breakers, retries, and rate limiting

---

## 🏗️ Architecture Overview

### System Context
```
[Google Cloud Logging] → [Pub/Sub Topics] → [Gemini SRE Agent] → [GitHub PRs]
                                                    ↓
                                            [Gemini AI Models]
                                                    ↓
                                            [Vertex AI Platform]
```

### Key Components
- **LogSubscriber** - Subscribes to Google Cloud Pub/Sub for real-time log ingestion
- **TriageAgent** - Uses Gemini Flash models for rapid log analysis and issue identification
- **AnalysisAgent** - Employs Gemini Pro models for deep root cause analysis and remediation planning
- **RemediationAgent** - Creates GitHub Pull Requests with proposed fixes
- **HyxResilientClient** - Provides circuit breakers, retries, bulkheads, and rate limiting for system resilience

### Data Flow
1. **Log Export**: Google Cloud Logging exports relevant logs to Pub/Sub topics
2. **Real-time Ingestion**: LogSubscriber receives log entries from Pub/Sub subscriptions
3. **Intelligent Triage**: TriageAgent analyzes logs using Gemini Flash for quick assessment
4. **Deep Analysis**: AnalysisAgent performs root cause analysis using Gemini Pro models
5. **Automated Remediation**: RemediationAgent creates GitHub PRs with proposed fixes

---

## 📁 Project Structure [Partial Directory Tree]

```
gemini-sre-agent/
├── gemini_sre_agent/         # Core agent modules
│   ├── config.py             # Configuration management with Pydantic models
│   ├── triage_agent.py       # Gemini Flash-based log triage
│   ├── analysis_agent.py     # Gemini Pro-based deep analysis
│   ├── remediation_agent.py  # GitHub PR creation and management
│   ├── log_subscriber.py     # Google Cloud Pub/Sub integration
│   ├── log_ingestion.py      # Direct Cloud Logging API access
│   ├── resilience.py         # Hyx-based resilience patterns
│   └── logger.py             # Structured logging with JSON support
├── tests/                        # Comprehensive test suite
├── config/                       # Configuration files
│   └── config.yaml              # Multi-service monitoring configuration
├── main.py                      # Application entry point
├── pyproject.toml              # Python dependencies and project metadata
├── Dockerfile                  # Container configuration for deployment
└── deploy.sh                   # Google Cloud Run deployment script
```

### Key Files to Know

| File | Purpose | When You'd Touch It |
|------|---------|---------------------|
| `main.py` | Application entry point and service orchestration | Adding new services to monitor |
| `config/config.yaml` | Multi-service configuration with model selection | Configuring new services or changing AI models |
| `gemini_sre_agent/config.py` | Pydantic configuration models | Modifying configuration schema |
| `gemini_sre_agent/triage_agent.py` | Gemini Flash triage logic | Adjusting triage prompts or logic |
| `gemini_sre_agent/analysis_agent.py` | Gemini Pro analysis logic | Modifying root cause analysis approach |
| `gemini_sre_agent/resilience.py` | Hyx resilience patterns | Tuning circuit breakers or retry policies |
| `pyproject.toml` | Dependencies and Python configuration | Adding new libraries or updating versions |

---

## 🔧 Technology Stack

### Core Technologies
- **Language:** Python (3.12+) - Chosen for AI/ML ecosystem compatibility and async support
- **Framework:** FastAPI - For potential API endpoints and async request handling
- **AI Platform:** Google Vertex AI - Integration with Gemini models for intelligent analysis
- **Message Queue:** Google Cloud Pub/Sub - Real-time log streaming and event-driven architecture

### Key Libraries
- **google-cloud-aiplatform** - Vertex AI integration for Gemini model access
- **google-cloud-pubsub** - Real-time log ingestion from Google Cloud
- **google-cloud-logging** - Direct access to Cloud Logging API
- **hyx** - Resilience patterns (circuit breakers, retries, bulkheads, rate limiting)
- **pydantic** - Configuration validation and data modeling
- **PyGithub** - GitHub API integration for automated PR creation

### Development Tools
- **pytest** - Testing framework with async support
- **uvicorn** - ASGI server for FastAPI applications
- **pyyaml** - YAML configuration file parsing
- **tenacity** - Additional retry mechanisms

---

## 🌐 External Dependencies

### Required Services
- **Google Cloud Vertex AI** - Hosts Gemini models for triage and analysis (critical for core functionality)
- **Google Cloud Pub/Sub** - Real-time log message delivery (critical for log ingestion)
- **Google Cloud Logging** - Source of log data and historical log access
- **GitHub API** - Pull request creation and repository management (critical for remediation)

### Optional Integrations
- **Google Cloud Run** - Containerized deployment platform (fallback: local deployment)
- **Google Container Registry** - Docker image storage for Cloud Run deployment

### Environment Variables

```bash
# Required
GITHUB_TOKEN=              # GitHub Personal Access Token for PR creation
GOOGLE_APPLICATION_CREDENTIALS=  # Path to GCP service account key (or use gcloud auth)

# Optional
LOG_LEVEL=                 # Logging verbosity (default: INFO)
CONFIG_PATH=               # Custom config file path (default: config/config.yaml)
```

---

## 🔄 Common Workflows

### **Workflow 1: Automated Incident Response**
1. **Log Detection**: Google Cloud service generates error logs
2. **Real-time Ingestion**: Pub/Sub delivers logs to LogSubscriber
3. **Intelligent Triage**: TriageAgent analyzes logs using Gemini Flash, creates TriagePacket
4. **Deep Analysis**: AnalysisAgent performs root cause analysis using Gemini Pro
5. **Automated Remediation**: RemediationAgent creates GitHub PR with proposed fix

**Code path:** `LogSubscriber` → `TriageAgent` → `AnalysisAgent` → `RemediationAgent` → `GitHub API`

### **Workflow 2: Multi-Service Monitoring Setup**
1. **Configuration**: Define services in `config/config.yaml` with Pub/Sub subscriptions
2. **Service Initialization**: Main application creates agent instances per service
3. **Parallel Monitoring**: Each service runs independent monitoring loops
4. **Centralized Logging**: All services use shared logging configuration

**Code path:** `load_config()` → `main()` → `service_config` → `agent_initialization`

---

## 📈 Performance & Scale

### Performance Considerations
- **Resilience Patterns**: Circuit breakers prevent cascade failures, rate limiting manages API usage
- **Async Processing**: Non-blocking I/O for concurrent log processing across multiple services
- **Model Selection**: Gemini Flash for fast triage, Gemini Pro for detailed analysis

### Monitoring
- **Metrics**: Resilience client tracks operation success/failure rates, circuit breaker states
- **Alerts**: Built-in logging for circuit breaker opens, rate limit hits, and retry exhaustion
- **Health Stats**: Comprehensive health monitoring via `get_health_stats()` method

---

## 🚨 Things to Be Careful About

### 🔒 Security Considerations
- **Authentication**: Uses Google Cloud service accounts for Vertex AI access
- **API Keys**: GitHub token should be stored securely (use Google Secret Manager in production)
- **Permissions**: Service account needs Logging Viewer, Pub/Sub Subscriber, and Vertex AI User roles

### ⚠️ Operational Warnings
- **Rate Limits**: Gemini API has usage quotas - monitor via resilience client statistics
- **Cost Management**: Gemini Pro models are more expensive than Flash - configure usage carefully
- **GitHub PR Limits**: Avoid creating duplicate PRs for the same issue (implement deduplication)
- **Pub/Sub Acknowledgment**: Ensure proper message acknowledgment to prevent message loss

*Updated at: 2025-01-27 22:47:00 UTC*