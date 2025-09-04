# Secure Credential Management for Multi-Provider LLM Configuration

This guide provides best practices for securely managing API keys, credentials, and sensitive configuration data in the multi-provider LLM system.

## Overview

The multi-provider LLM system requires API keys and credentials for various providers. This document outlines secure practices for:

- **API key management** across multiple providers
- **Environment variable security**
- **Secret rotation** and lifecycle management
- **Access control** and audit logging
- **Compliance** with security standards

## Security Principles

### 1. Least Privilege

- Grant only necessary permissions to API keys
- Use separate keys for different environments
- Implement role-based access control

### 2. Defense in Depth

- Multiple layers of security controls
- Encryption at rest and in transit
- Regular security audits and monitoring

### 3. Zero Trust

- Never trust, always verify
- Continuous authentication and authorization
- Assume breach mentality

## API Key Management

### Provider-Specific API Keys

#### OpenAI

```bash
# Environment variable
export OPENAI_API_KEY="sk-proj-..."

# Optional: Organization and Project IDs
export OPENAI_ORG_ID="org-..."
export OPENAI_PROJECT_ID="proj-..."
```

**Security Considerations:**

- Use project-specific keys when possible
- Set usage limits and alerts
- Monitor usage patterns for anomalies
- Rotate keys regularly (every 90 days)

#### Anthropic

```bash
# Environment variable
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Security Considerations:**

- Use organization-specific keys
- Set rate limits and usage caps
- Monitor for unusual activity
- Implement key rotation schedule

#### xAI (Grok)

```bash
# Environment variable
export XAI_API_KEY="xai-..."
```

**Security Considerations:**

- Monitor usage and costs
- Set appropriate rate limits
- Rotate keys regularly
- Track access patterns

#### Amazon Bedrock

```bash
# AWS credentials
export AWS_ACCESS_KEY_ID="AKIA..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_DEFAULT_REGION="us-east-1"

# Optional: AWS Profile
export AWS_PROFILE="production"
```

**Security Considerations:**

- Use IAM roles when possible
- Implement least privilege policies
- Enable CloudTrail logging
- Use AWS Secrets Manager for key storage

#### Ollama (Local)

```bash
# No API key required for local Ollama
# Optional: Custom endpoint
export OLLAMA_BASE_URL="http://localhost:11434"
```

**Security Considerations:**

- Secure local network access
- Use TLS for remote connections
- Implement access controls
- Monitor local model usage

### Environment Variable Security

#### .env File Management

```bash
# .env file (DO NOT commit to version control)
# Add to .gitignore
echo ".env" >> .gitignore
echo ".env.*" >> .gitignore
```

**Secure .env file structure:**

```bash
# .env file
# API Keys
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
XAI_API_KEY=xai-...
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...

# Optional: Organization/Project IDs
OPENAI_ORG_ID=org-...
OPENAI_PROJECT_ID=proj-...

# Configuration overrides
LLM_DEFAULT_PROVIDER=openai
LLM_ENABLE_MONITORING=true
LLM_MONTHLY_BUDGET=1000.0
```

#### Environment Variable Best Practices

1. **Never commit .env files to version control**
2. **Use different .env files for different environments**
3. **Set appropriate file permissions (600)**
4. **Use environment-specific variable names**

```bash
# Set secure file permissions
chmod 600 .env

# Environment-specific files
.env.development
.env.staging
.env.production
```

### Secret Management Systems

#### AWS Secrets Manager

```python
import boto3
import json
from botocore.exceptions import ClientError

def get_secret(secret_name: str, region_name: str = "us-east-1") -> dict:
    """Retrieve secret from AWS Secrets Manager."""
    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=region_name
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        raise e

    secret = get_secret_value_response['SecretString']
    return json.loads(secret)

# Usage
secrets = get_secret("llm-api-keys")
openai_key = secrets["openai_api_key"]
anthropic_key = secrets["anthropic_api_key"]
```

#### HashiCorp Vault

```python
import hvac

def get_vault_secret(secret_path: str, key: str) -> str:
    """Retrieve secret from HashiCorp Vault."""
    client = hvac.Client(url='https://vault.company.com')
    client.token = os.environ['VAULT_TOKEN']

    response = client.secrets.kv.v2.read_secret_version(
        path=secret_path
    )

    return response['data']['data'][key]

# Usage
openai_key = get_vault_secret("llm/keys", "openai_api_key")
anthropic_key = get_vault_secret("llm/keys", "anthropic_api_key")
```

#### Azure Key Vault

```python
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential

def get_azure_secret(vault_url: str, secret_name: str) -> str:
    """Retrieve secret from Azure Key Vault."""
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url=vault_url, credential=credential)

    secret = client.get_secret(secret_name)
    return secret.value

# Usage
vault_url = "https://your-vault.vault.azure.net/"
openai_key = get_azure_secret(vault_url, "openai-api-key")
anthropic_key = get_azure_secret(vault_url, "anthropic-api-key")
```

## Configuration Security

### Secure Configuration Loading

```python
import os
from pathlib import Path
from gemini_sre_agent.llm.config_manager import ConfigManager

def load_secure_config(config_path: Path) -> ConfigManager:
    """Load configuration with secure credential handling."""

    # Check for required environment variables
    required_vars = [
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
        'XAI_API_KEY'
    ]

    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {missing_vars}")

    # Load configuration
    config_manager = ConfigManager(config_path)

    # Validate API keys
    config = config_manager.get_config()
    for provider_name, provider_config in config.providers.items():
        if provider_config.api_key and not provider_config.api_key.startswith('${'):
            # API key is hardcoded - this is a security risk
            raise ValueError(f"Hardcoded API key detected for provider: {provider_name}")

    return config_manager
```

### Credential Validation

```python
def validate_api_keys(config: LLMConfig) -> Dict[str, bool]:
    """Validate all API keys in the configuration."""
    results = {}

    for provider_name, provider_config in config.providers.items():
        try:
            # Test API key validity
            handler = ProviderHandlerFactory.create_handler(provider_config)
            is_valid, message = handler.validate_credentials()
            results[provider_name] = is_valid

            if not is_valid:
                logger.warning(f"Invalid API key for provider {provider_name}: {message}")

        except Exception as e:
            logger.error(f"Error validating API key for provider {provider_name}: {e}")
            results[provider_name] = False

    return results
```

## Access Control

### Role-Based Access Control (RBAC)

```yaml
# RBAC configuration
access_control:
  roles:
    admin:
      permissions:
        - "llm:read"
        - "llm:write"
        - "llm:admin"
        - "secrets:read"
        - "secrets:write"
    developer:
      permissions:
        - "llm:read"
        - "llm:write"
    viewer:
      permissions:
        - "llm:read"

  users:
    admin@company.com:
      roles: ["admin"]
    developer@company.com:
      roles: ["developer"]
    viewer@company.com:
      roles: ["viewer"]
```

### API Key Permissions

#### OpenAI API Key Permissions

```bash
# Create API key with specific permissions
curl -X POST "https://api.openai.com/v1/api_keys" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "gemini-sre-agent-production",
    "permissions": {
      "chat": true,
      "completions": true,
      "embeddings": false,
      "fine_tuning": false,
      "models": true
    },
    "usage_limit": 1000000
  }'
```

#### Anthropic API Key Permissions

```bash
# Anthropic API keys are organization-scoped
# Set usage limits and monitoring through Anthropic console
```

#### AWS IAM Policy for Bedrock

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": [
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0",
        "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-haiku-20241022-v1:0"
      ]
    }
  ]
}
```

## Monitoring and Auditing

### API Key Usage Monitoring

```python
import logging
from datetime import datetime
from typing import Dict, Any

class APIKeyMonitor:
    """Monitor API key usage and detect anomalies."""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.usage_stats = {}

    def log_api_usage(self, provider: str, model: str, tokens: int, cost: float):
        """Log API usage for monitoring."""
        timestamp = datetime.utcnow()

        # Log usage
        self.logger.info(
            f"API usage - Provider: {provider}, Model: {model}, "
            f"Tokens: {tokens}, Cost: ${cost:.4f}, Time: {timestamp}"
        )

        # Track usage statistics
        key = f"{provider}:{model}"
        if key not in self.usage_stats:
            self.usage_stats[key] = {
                'total_tokens': 0,
                'total_cost': 0.0,
                'request_count': 0
            }

        self.usage_stats[key]['total_tokens'] += tokens
        self.usage_stats[key]['total_cost'] += cost
        self.usage_stats[key]['request_count'] += 1

        # Check for anomalies
        self._check_anomalies(provider, model, tokens, cost)

    def _check_anomalies(self, provider: str, model: str, tokens: int, cost: float):
        """Check for usage anomalies."""
        # Implement anomaly detection logic
        # - Unusual token usage patterns
        # - Unexpected cost spikes
        # - Abnormal request frequencies
        pass
```

### Audit Logging

```python
import json
from datetime import datetime
from typing import Dict, Any

class AuditLogger:
    """Log security-relevant events for audit purposes."""

    def __init__(self, log_file: str = "audit.log"):
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log_api_key_access(self, provider: str, user: str, action: str):
        """Log API key access events."""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'api_key_access',
            'provider': provider,
            'user': user,
            'action': action
        }
        self.logger.info(json.dumps(event))

    def log_configuration_change(self, user: str, change_type: str, details: Dict[str, Any]):
        """Log configuration changes."""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'configuration_change',
            'user': user,
            'change_type': change_type,
            'details': details
        }
        self.logger.info(json.dumps(event))

    def log_security_event(self, event_type: str, severity: str, details: Dict[str, Any]):
        """Log security events."""
        event = {
            'timestamp': datetime.utcnow().isoformat(),
            'event_type': 'security_event',
            'severity': severity,
            'details': details
        }
        self.logger.info(json.dumps(event))
```

## Key Rotation

### Automated Key Rotation

```python
import os
import requests
from datetime import datetime, timedelta
from typing import Dict, List

class KeyRotationManager:
    """Manage API key rotation for security."""

    def __init__(self):
        self.rotation_schedule = {
            'openai': 90,  # days
            'anthropic': 90,
            'xai': 90,
            'aws': 90
        }
        self.last_rotation = {}

    def check_rotation_needed(self, provider: str) -> bool:
        """Check if key rotation is needed."""
        if provider not in self.last_rotation:
            return True

        days_since_rotation = (datetime.now() - self.last_rotation[provider]).days
        return days_since_rotation >= self.rotation_schedule.get(provider, 90)

    def rotate_key(self, provider: str, new_key: str) -> bool:
        """Rotate API key for a provider."""
        try:
            # Update environment variable
            env_var = f"{provider.upper()}_API_KEY"
            os.environ[env_var] = new_key

            # Update configuration
            # This would typically involve updating the secret management system

            # Log rotation
            self.last_rotation[provider] = datetime.now()

            return True

        except Exception as e:
            logger.error(f"Failed to rotate key for {provider}: {e}")
            return False

    def schedule_rotation(self, provider: str, new_key: str, rotation_time: datetime):
        """Schedule key rotation for a specific time."""
        # Implement scheduled rotation logic
        pass
```

### Rotation Script

```bash
#!/bin/bash
# rotate_api_keys.sh

# Rotate OpenAI API key
echo "Rotating OpenAI API key..."
NEW_OPENAI_KEY=$(curl -X POST "https://api.openai.com/v1/api_keys" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "gemini-sre-agent-rotated-'$(date +%Y%m%d)'"}' \
  | jq -r '.id')

# Update environment variable
export OPENAI_API_KEY="$NEW_OPENAI_KEY"

# Update secret management system
aws secretsmanager update-secret \
  --secret-id "llm-api-keys" \
  --secret-string "{\"openai_api_key\":\"$NEW_OPENAI_KEY\"}"

# Revoke old key
curl -X DELETE "https://api.openai.com/v1/api_keys/$OLD_OPENAI_KEY" \
  -H "Authorization: Bearer $NEW_OPENAI_KEY"

echo "OpenAI API key rotated successfully"
```

## Compliance and Standards

### SOC 2 Compliance

```python
class SOC2Compliance:
    """Ensure SOC 2 compliance for credential management."""

    def __init__(self):
        self.audit_logger = AuditLogger()

    def validate_access_controls(self) -> bool:
        """Validate access control implementation."""
        # Check for proper access controls
        # - Role-based access
        # - Principle of least privilege
        # - Regular access reviews
        pass

    def validate_encryption(self) -> bool:
        """Validate encryption implementation."""
        # Check for encryption at rest and in transit
        # - API keys encrypted in storage
        # - TLS for all communications
        # - Proper key management
        pass

    def validate_monitoring(self) -> bool:
        """Validate monitoring and logging."""
        # Check for comprehensive monitoring
        # - Access logging
        # - Usage monitoring
        # - Anomaly detection
        pass
```

### GDPR Compliance

```python
class GDPRCompliance:
    """Ensure GDPR compliance for data handling."""

    def __init__(self):
        self.data_retention_policy = {
            'logs': 30,  # days
            'metrics': 90,
            'audit_logs': 2555  # 7 years
        }

    def anonymize_logs(self, logs: List[Dict]) -> List[Dict]:
        """Anonymize logs to remove PII."""
        # Implement PII removal logic
        pass

    def handle_data_deletion_request(self, user_id: str):
        """Handle GDPR data deletion requests."""
        # Implement data deletion logic
        pass
```

## Security Checklist

### Pre-Deployment Security Checklist

- [ ] All API keys stored in secure secret management system
- [ ] No hardcoded credentials in configuration files
- [ ] Environment variables properly secured
- [ ] Access controls implemented and tested
- [ ] Monitoring and alerting configured
- [ ] Audit logging enabled
- [ ] Key rotation schedule established
- [ ] Security policies documented
- [ ] Team trained on security procedures
- [ ] Incident response plan in place

### Regular Security Reviews

- [ ] Monthly API key usage review
- [ ] Quarterly access control audit
- [ ] Semi-annual security assessment
- [ ] Annual penetration testing
- [ ] Continuous monitoring and alerting
- [ ] Regular security training updates

## Incident Response

### Security Incident Response Plan

1. **Detection**: Monitor for security events
2. **Assessment**: Evaluate severity and impact
3. **Containment**: Isolate affected systems
4. **Eradication**: Remove threats and vulnerabilities
5. **Recovery**: Restore normal operations
6. **Lessons Learned**: Document and improve

### Emergency Procedures

```bash
# Emergency API key revocation
curl -X DELETE "https://api.openai.com/v1/api_keys/$COMPROMISED_KEY" \
  -H "Authorization: Bearer $ADMIN_KEY"

# Emergency configuration lockdown
export LLM_EMERGENCY_MODE=true
export LLM_DISABLE_ALL_PROVIDERS=true

# Emergency monitoring activation
export LLM_ENABLE_EMERGENCY_MONITORING=true
```

This comprehensive guide ensures that your multi-provider LLM system maintains the highest security standards while providing the flexibility and reliability needed for production operations.
