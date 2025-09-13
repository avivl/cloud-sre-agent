# gemini_sre_agent/ml/specialized_prompt_templates.py

"""
Specialized prompt templates for different issue types.

This module contains specialized prompt templates that are optimized
for specific types of issues like database errors, API errors, etc.
"""

import json
from typing import Any

from .base_prompt_template import BasePromptTemplate
from .prompt_context_models import PromptContext


class DatabaseErrorPromptTemplate(BasePromptTemplate):
    """Specialized template for database-related issues."""

    def _build_system_prompt(self) -> str:
        """Build database-specific system prompt."""
        return """You are an expert database engineer and SRE specialist. Your task is to analyze database-related issues and generate precise, production-ready code fixes.

EXPERTISE AREAS:
- Database connection management and pooling
- Query optimization and performance tuning
- Transaction handling and consistency
- Error handling and retry mechanisms
- Database migration and schema changes
- Connection timeout and deadlock resolution
- Data integrity and ACID compliance

CODE GENERATION PRINCIPLES:
1. Always include proper error handling and logging
2. Implement connection pooling best practices
3. Use appropriate retry mechanisms with exponential backoff
4. Ensure transaction consistency and rollback capabilities
5. Follow the repository's established database patterns
6. Include comprehensive error messages for debugging
7. Consider performance implications of the fix
8. Implement proper connection cleanup and resource management

OUTPUT FORMAT:
Provide a structured JSON response with root cause analysis, proposed fix, and complete code implementation."""

    def _build_user_template(self) -> str:
        """Build database-specific user template."""
        return """DATABASE ISSUE ANALYSIS REQUEST

Issue Context:
- Issue Type: {issue_type}
- Affected Services: {affected_services}
- Severity Level: {severity_level}/10
- User Impact: {user_impact}
- Business Impact: {business_impact}

Database Context:
- Database Type: {database_type}
- Connection Pool Settings: {connection_pool_config}
- Current Error Patterns: {error_patterns}
- Performance Metrics: {performance_metrics}

Repository Context:
- Technology Stack: {technology_stack}
- Coding Standards: {coding_standards}
- Error Handling Patterns: {error_handling_patterns}
- Testing Patterns: {testing_patterns}

Issue Details:
- Triage Information: {triage_packet}
- Log Context: {log_context}
- Affected Files: {affected_files}
- Related Services: {related_services}

Historical Context:
- Similar Past Issues: {similar_issues}
- Recent Database Changes: {recent_db_changes}
- Previous Fixes: {previous_fixes}

Please provide a comprehensive analysis and code fix following the repository's established database patterns."""

    def _get_context_variables(self, context: PromptContext) -> dict[str, Any]:
        """Extract database-specific context variables."""
        repo_ctx = context.repository_context
        issue_ctx = context.issue_context

        return {
            "issue_type": issue_ctx.issue_type.value,
            "affected_services": ", ".join(issue_ctx.related_services),
            "severity_level": issue_ctx.severity_level,
            "user_impact": issue_ctx.user_impact,
            "business_impact": issue_ctx.business_impact,
            "database_type": repo_ctx.technology_stack.get("database", "Unknown"),
            "connection_pool_config": self._extract_db_config(repo_ctx),
            "error_patterns": ", ".join(issue_ctx.error_patterns),
            "performance_metrics": json.dumps(
                issue_ctx.impact_analysis.get("performance", {})
            ),
            "technology_stack": json.dumps(repo_ctx.technology_stack),
            "coding_standards": json.dumps(repo_ctx.coding_standards),
            "error_handling_patterns": ", ".join(repo_ctx.error_handling_patterns),
            "testing_patterns": ", ".join(repo_ctx.testing_patterns),
            "triage_packet": json.dumps(issue_ctx.to_dict()),
            "log_context": json.dumps(issue_ctx.temporal_context),
            "affected_files": ", ".join(issue_ctx.affected_files),
            "related_services": ", ".join(issue_ctx.related_services),
            "similar_issues": json.dumps(repo_ctx.historical_fixes[:3]),
            "recent_db_changes": json.dumps(repo_ctx.recent_changes[:5]),
            "previous_fixes": json.dumps(repo_ctx.historical_fixes[:2]),
        }

    def _extract_db_config(self, repo_context) -> str:
        """Extract database configuration from repository context."""
        # Implementation would parse config files and extract DB settings
        return "Connection pool: 10-50 connections, timeout: 30s"


class APIErrorPromptTemplate(BasePromptTemplate):
    """Specialized template for API-related issues."""

    def _build_system_prompt(self) -> str:
        """Build API-specific system prompt."""
        return """You are an expert API engineer and SRE specialist. Your task is to analyze API-related issues and generate robust, scalable code fixes.

EXPERTISE AREAS:
- API rate limiting and throttling
- Authentication and authorization
- Request/response validation
- Error handling and status codes
- API versioning and backward compatibility
- Performance optimization and caching
- Circuit breaker patterns
- Retry mechanisms and exponential backoff
- API security and input sanitization

CODE GENERATION PRINCIPLES:
1. Implement proper HTTP status codes and error responses
2. Include comprehensive input validation
3. Use appropriate rate limiting and throttling
4. Implement circuit breaker patterns for resilience
5. Follow RESTful API design principles
6. Include proper logging and monitoring
7. Consider API versioning and backward compatibility
8. Implement proper authentication and authorization checks
9. Add request/response caching where appropriate

OUTPUT FORMAT:
Provide a structured JSON response with root cause analysis, proposed fix, and complete code implementation."""

    def _build_user_template(self) -> str:
        """Build API-specific user template."""
        return """API ISSUE ANALYSIS REQUEST

Issue Context:
- Issue Type: {issue_type}
- Affected Endpoints: {affected_endpoints}
- Severity Level: {severity_level}/10
- User Impact: {user_impact}
- Business Impact: {business_impact}

API Context:
- Framework: {api_framework}
- Authentication Method: {auth_method}
- Rate Limiting: {rate_limiting_config}
- Current Error Patterns: {error_patterns}
- Performance Metrics: {performance_metrics}

Repository Context:
- Technology Stack: {technology_stack}
- API Standards: {api_standards}
- Error Handling Patterns: {error_handling_patterns}
- Testing Patterns: {testing_patterns}

Issue Details:
- Triage Information: {triage_packet}
- Log Context: {log_context}
- Affected Files: {affected_files}
- Related Services: {related_services}

Historical Context:
- Similar Past Issues: {similar_issues}
- Recent API Changes: {recent_api_changes}
- Previous Fixes: {previous_fixes}

Please provide a comprehensive analysis and code fix following the repository's established API patterns."""

    def _get_context_variables(self, context: PromptContext) -> dict[str, Any]:
        """Extract API-specific context variables."""
        repo_ctx = context.repository_context
        issue_ctx = context.issue_context

        return {
            "issue_type": issue_ctx.issue_type.value,
            "affected_endpoints": ", ".join(issue_ctx.related_services),
            "severity_level": issue_ctx.severity_level,
            "user_impact": issue_ctx.user_impact,
            "business_impact": issue_ctx.business_impact,
            "api_framework": repo_ctx.technology_stack.get("framework", "Unknown"),
            "auth_method": self._extract_auth_method(repo_ctx),
            "rate_limiting_config": self._extract_rate_limiting_config(repo_ctx),
            "error_patterns": ", ".join(issue_ctx.error_patterns),
            "performance_metrics": json.dumps(
                issue_ctx.impact_analysis.get("performance", {})
            ),
            "technology_stack": json.dumps(repo_ctx.technology_stack),
            "api_standards": json.dumps(repo_ctx.coding_standards),
            "error_handling_patterns": ", ".join(repo_ctx.error_handling_patterns),
            "testing_patterns": ", ".join(repo_ctx.testing_patterns),
            "triage_packet": json.dumps(issue_ctx.to_dict()),
            "log_context": json.dumps(issue_ctx.temporal_context),
            "affected_files": ", ".join(issue_ctx.affected_files),
            "related_services": ", ".join(issue_ctx.related_services),
            "similar_issues": json.dumps(repo_ctx.historical_fixes[:3]),
            "recent_api_changes": json.dumps(repo_ctx.recent_changes[:5]),
            "previous_fixes": json.dumps(repo_ctx.historical_fixes[:2]),
        }

    def _extract_auth_method(self, repo_context) -> str:
        """Extract authentication method from repository context."""
        return "JWT"  # Placeholder implementation

    def _extract_rate_limiting_config(self, repo_context) -> str:
        """Extract rate limiting configuration from repository context."""
        return "100 requests/minute per user"  # Placeholder implementation


class SecurityErrorPromptTemplate(BasePromptTemplate):
    """Specialized template for security-related issues."""

    def _build_system_prompt(self) -> str:
        """Build security-specific system prompt."""
        return """You are an expert security engineer and SRE specialist. Your task is to analyze security-related issues and generate secure, production-ready code fixes.

EXPERTISE AREAS:
- Vulnerability assessment and remediation
- Authentication and authorization security
- Input validation and sanitization
- Secure coding practices
- OWASP security guidelines
- Data encryption and protection
- Security monitoring and logging
- Threat modeling and risk assessment

CODE GENERATION PRINCIPLES:
1. Follow OWASP security guidelines and best practices
2. Implement comprehensive input validation and sanitization
3. Use secure authentication and authorization mechanisms
4. Include proper error handling without information disclosure
5. Implement security logging and monitoring
6. Consider data encryption and protection requirements
7. Follow principle of least privilege
8. Include security testing and validation
9. Ensure compliance with security standards

OUTPUT FORMAT:
Provide a structured JSON response with root cause analysis, proposed fix, and complete code implementation."""

    def _build_user_template(self) -> str:
        """Build security-specific user template."""
        return """SECURITY ISSUE ANALYSIS REQUEST

Issue Context:
- Issue Type: {issue_type}
- Affected Components: {affected_components}
- Severity Level: {severity_level}/10
- User Impact: {user_impact}
- Business Impact: {business_impact}

Security Context:
- Vulnerability Type: {vulnerability_type}
- Attack Vector: {attack_vector}
- Security Standards: {security_standards}
- Current Security Measures: {current_security_measures}

Repository Context:
- Technology Stack: {technology_stack}
- Security Standards: {security_standards}
- Error Handling Patterns: {error_handling_patterns}
- Testing Patterns: {testing_patterns}

Issue Details:
- Triage Information: {triage_packet}
- Log Context: {log_context}
- Affected Files: {affected_files}
- Related Services: {related_services}

Historical Context:
- Similar Past Issues: {similar_issues}
- Recent Security Changes: {recent_security_changes}
- Previous Fixes: {previous_fixes}

Please provide a comprehensive security analysis and code fix following security best practices."""

    def _get_context_variables(self, context: PromptContext) -> dict[str, Any]:
        """Extract security-specific context variables."""
        repo_ctx = context.repository_context
        issue_ctx = context.issue_context

        return {
            "issue_type": issue_ctx.issue_type.value,
            "affected_components": ", ".join(issue_ctx.related_services),
            "severity_level": issue_ctx.severity_level,
            "user_impact": issue_ctx.user_impact,
            "business_impact": issue_ctx.business_impact,
            "vulnerability_type": self._extract_vulnerability_type(issue_ctx),
            "attack_vector": self._extract_attack_vector(issue_ctx),
            "security_standards": json.dumps(
                repo_ctx.coding_standards.get("security", {})
            ),
            "current_security_measures": self._extract_security_measures(repo_ctx),
            "technology_stack": json.dumps(repo_ctx.technology_stack),
            "error_handling_patterns": ", ".join(repo_ctx.error_handling_patterns),
            "testing_patterns": ", ".join(repo_ctx.testing_patterns),
            "triage_packet": json.dumps(issue_ctx.to_dict()),
            "log_context": json.dumps(issue_ctx.temporal_context),
            "affected_files": ", ".join(issue_ctx.affected_files),
            "related_services": ", ".join(issue_ctx.related_services),
            "similar_issues": json.dumps(repo_ctx.historical_fixes[:3]),
            "recent_security_changes": json.dumps(repo_ctx.recent_changes[:5]),
            "previous_fixes": json.dumps(repo_ctx.historical_fixes[:2]),
        }

    def _extract_vulnerability_type(self, issue_context) -> str:
        """Extract vulnerability type from issue context."""
        return "Unknown"  # Placeholder implementation

    def _extract_attack_vector(self, issue_context) -> str:
        """Extract attack vector from issue context."""
        return "Unknown"  # Placeholder implementation

    def _extract_security_measures(self, repo_context) -> str:
        """Extract current security measures from repository context."""
        return "Basic authentication, input validation"  # Placeholder implementation
