# tests/test_specialized_prompt_templates.py

"""
Tests for specialized prompt templates.

This module contains comprehensive tests for specialized prompt templates
including database, API, and security error templates.
"""


from gemini_sre_agent.ml.prompt_context_models import (
    IssueContext,
    IssueType,
    PromptContext,
    RepositoryContext,
)
from gemini_sre_agent.ml.specialized_prompt_templates import (
    APIErrorPromptTemplate,
    DatabaseErrorPromptTemplate,
    SecurityErrorPromptTemplate,
)


class TestDatabaseErrorPromptTemplate:
    """Test DatabaseErrorPromptTemplate."""

    def test_database_template_creation(self) -> None:
        """Test creating a database error prompt template."""
        template = DatabaseErrorPromptTemplate("database")

        assert template.template_name == "database"
        assert "database engineer" in template.system_prompt
        assert "DATABASE ISSUE ANALYSIS REQUEST" in template.user_prompt_template

    def test_database_template_system_prompt(self) -> None:
        """Test database template system prompt content."""
        template = DatabaseErrorPromptTemplate("database")

        system_prompt = template.system_prompt

        # Check for database-specific expertise areas
        assert "connection management" in system_prompt
        assert "query optimization" in system_prompt
        assert "transaction handling" in system_prompt
        assert "connection pooling" in system_prompt
        assert "retry mechanisms" in system_prompt

    def test_database_template_context_variables(self) -> None:
        """Test context variable extraction for database template."""
        template = DatabaseErrorPromptTemplate("database")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"database": "postgresql", "language": "python"},
            coding_standards={"linting": "pylint"},
            error_handling_patterns=["connection_retry", "timeout_handling"],
            testing_patterns=["db_tests"],
            dependency_structure={},
            recent_changes=[{"type": "db_migration"}],
            historical_fixes=[{"issue": "connection_pool"}],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=["db/connection.py"],
            error_patterns=["connection_timeout", "deadlock"],
            severity_level=9,
            impact_analysis={"performance": {"response_time": 5000}},
            related_services=["user_service", "auth_service"],
            temporal_context={"frequency": "high"},
            user_impact="Database unavailable",
            business_impact="Critical service failure",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="database_error",
        )

        context_vars = template._get_context_variables(prompt_context)

        # Check database-specific variables
        assert context_vars["database_type"] == "postgresql"
        assert "connection pool" in context_vars["connection_pool_config"]
        assert "connection_timeout" in context_vars["error_patterns"]
        assert "5000" in context_vars["performance_metrics"]
        assert "user_service, auth_service" in context_vars["affected_services"]
        assert "db/connection.py" in context_vars["affected_files"]

    def test_database_template_extract_db_config(self) -> None:
        """Test database configuration extraction."""
        template = DatabaseErrorPromptTemplate("database")

        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={"database": "mysql"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        config = template._extract_db_config(repo_context)
        assert "Connection pool" in config
        assert "timeout" in config

    def test_database_template_prompt_generation(self) -> None:
        """Test full prompt generation with database template."""
        template = DatabaseErrorPromptTemplate("database")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"database": "postgresql"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.DATABASE_ERROR,
            affected_files=["db.py"],
            error_patterns=["timeout"],
            severity_level=8,
            impact_analysis={},
            related_services=["db_service"],
            temporal_context={},
            user_impact="DB error",
            business_impact="Service down",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="database_error",
        )

        prompt = template.generate_prompt(prompt_context)

        assert "database engineer" in prompt
        assert "DATABASE ISSUE ANALYSIS REQUEST" in prompt
        assert "postgresql" in prompt
        assert "database_error" in prompt
        assert "8/10" in prompt


class TestAPIErrorPromptTemplate:
    """Test APIErrorPromptTemplate."""

    def test_api_template_creation(self) -> None:
        """Test creating an API error prompt template."""
        template = APIErrorPromptTemplate("api")

        assert template.template_name == "api"
        assert "API engineer" in template.system_prompt
        assert "API ISSUE ANALYSIS REQUEST" in template.user_prompt_template

    def test_api_template_system_prompt(self) -> None:
        """Test API template system prompt content."""
        template = APIErrorPromptTemplate("api")

        system_prompt = template.system_prompt

        # Check for API-specific expertise areas
        assert "rate limiting" in system_prompt
        assert "authentication" in system_prompt
        assert "validation" in system_prompt
        assert "circuit breaker" in system_prompt
        assert "exponential backoff" in system_prompt

    def test_api_template_context_variables(self) -> None:
        """Test context variable extraction for API template."""
        template = APIErrorPromptTemplate("api")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"framework": "fastapi", "language": "python"},
            coding_standards={"api_standards": "RESTful"},
            error_handling_patterns=["rate_limiting", "circuit_breaker"],
            testing_patterns=["api_tests"],
            dependency_structure={},
            recent_changes=[{"type": "api_update"}],
            historical_fixes=[{"issue": "rate_limit"}],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=["api/endpoints.py"],
            error_patterns=["rate_limit_exceeded", "timeout"],
            severity_level=7,
            impact_analysis={"performance": {"response_time": 2000}},
            related_services=["api_gateway", "user_service"],
            temporal_context={"frequency": "medium"},
            user_impact="API slow",
            business_impact="User experience degraded",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="api_error",
        )

        context_vars = template._get_context_variables(prompt_context)

        # Check API-specific variables
        assert context_vars["api_framework"] == "fastapi"
        assert "JWT" in context_vars["auth_method"]  # From _extract_auth_method
        assert "requests/minute" in context_vars["rate_limiting_config"]
        assert "rate_limit_exceeded" in context_vars["error_patterns"]
        assert "2000" in context_vars["performance_metrics"]
        assert "api_gateway, user_service" in context_vars["affected_endpoints"]
        assert "api/endpoints.py" in context_vars["affected_files"]

    def test_api_template_extract_auth_method(self) -> None:
        """Test authentication method extraction."""
        template = APIErrorPromptTemplate("api")

        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        auth_method = template._extract_auth_method(repo_context)
        assert auth_method == "JWT"  # Placeholder implementation

    def test_api_template_extract_rate_limiting_config(self) -> None:
        """Test rate limiting configuration extraction."""
        template = APIErrorPromptTemplate("api")

        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        rate_config = template._extract_rate_limiting_config(repo_context)
        assert "requests/minute" in rate_config  # Placeholder implementation

    def test_api_template_prompt_generation(self) -> None:
        """Test full prompt generation with API template."""
        template = APIErrorPromptTemplate("api")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"framework": "fastapi"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.API_ERROR,
            affected_files=["api.py"],
            error_patterns=["500_error"],
            severity_level=6,
            impact_analysis={},
            related_services=["api_service"],
            temporal_context={},
            user_impact="API error",
            business_impact="Service unavailable",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="api_error",
        )

        prompt = template.generate_prompt(prompt_context)

        assert "API engineer" in prompt
        assert "API ISSUE ANALYSIS REQUEST" in prompt
        assert "fastapi" in prompt
        assert "api_error" in prompt
        assert "6/10" in prompt


class TestSecurityErrorPromptTemplate:
    """Test SecurityErrorPromptTemplate."""

    def test_security_template_creation(self) -> None:
        """Test creating a security error prompt template."""
        template = SecurityErrorPromptTemplate("security")

        assert template.template_name == "security"
        assert "security engineer" in template.system_prompt
        assert "SECURITY ISSUE ANALYSIS REQUEST" in template.user_prompt_template

    def test_security_template_system_prompt(self) -> None:
        """Test security template system prompt content."""
        template = SecurityErrorPromptTemplate("security")

        system_prompt = template.system_prompt

        # Check for security-specific expertise areas
        assert "vulnerability assessment" in system_prompt
        assert "authentication" in system_prompt
        assert "input validation" in system_prompt
        assert "OWASP" in system_prompt
        assert "encryption" in system_prompt

    def test_security_template_context_variables(self) -> None:
        """Test context variable extraction for security template."""
        template = SecurityErrorPromptTemplate("security")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"language": "python"},
            coding_standards={"security": {"owasp": "enabled"}},
            error_handling_patterns=["input_validation", "encryption"],
            testing_patterns=["security_tests"],
            dependency_structure={},
            recent_changes=[{"type": "security_patch"}],
            historical_fixes=[{"issue": "xss_vulnerability"}],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.SECURITY_ERROR,
            affected_files=["auth/security.py"],
            error_patterns=["sql_injection", "xss"],
            severity_level=10,
            impact_analysis={"security_risk": "critical"},
            related_services=["auth_service", "user_service"],
            temporal_context={"detected": "2024-01-01"},
            user_impact="Security vulnerability",
            business_impact="Critical security risk",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="security_error",
        )

        context_vars = template._get_context_variables(prompt_context)

        # Check security-specific variables
        assert context_vars["vulnerability_type"] == "Unknown"  # Placeholder
        assert context_vars["attack_vector"] == "Unknown"  # Placeholder
        assert "owasp" in context_vars["security_standards"]
        assert "authentication" in context_vars["current_security_measures"]
        assert "sql_injection" in context_vars["error_patterns"]
        assert "auth_service, user_service" in context_vars["affected_components"]
        assert "auth/security.py" in context_vars["affected_files"]

    def test_security_template_extract_vulnerability_type(self) -> None:
        """Test vulnerability type extraction."""
        template = SecurityErrorPromptTemplate("security")

        issue_context = IssueContext(
            issue_type=IssueType.SECURITY_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        vuln_type = template._extract_vulnerability_type(issue_context)
        assert vuln_type == "Unknown"  # Placeholder implementation

    def test_security_template_extract_attack_vector(self) -> None:
        """Test attack vector extraction."""
        template = SecurityErrorPromptTemplate("security")

        issue_context = IssueContext(
            issue_type=IssueType.SECURITY_ERROR,
            affected_files=[],
            error_patterns=[],
            severity_level=5,
            impact_analysis={},
            related_services=[],
            temporal_context={},
            user_impact="test",
            business_impact="test",
        )

        attack_vector = template._extract_attack_vector(issue_context)
        assert attack_vector == "Unknown"  # Placeholder implementation

    def test_security_template_extract_security_measures(self) -> None:
        """Test security measures extraction."""
        template = SecurityErrorPromptTemplate("security")

        repo_context = RepositoryContext(
            architecture_type="test",
            technology_stack={},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        security_measures = template._extract_security_measures(repo_context)
        assert "authentication" in security_measures  # Placeholder implementation

    def test_security_template_prompt_generation(self) -> None:
        """Test full prompt generation with security template."""
        template = SecurityErrorPromptTemplate("security")

        # Create test context
        repo_context = RepositoryContext(
            architecture_type="microservices",
            technology_stack={"language": "python"},
            coding_standards={},
            error_handling_patterns=[],
            testing_patterns=[],
            dependency_structure={},
            recent_changes=[],
            historical_fixes=[],
            code_quality_metrics={},
        )

        issue_context = IssueContext(
            issue_type=IssueType.SECURITY_ERROR,
            affected_files=["security.py"],
            error_patterns=["vulnerability"],
            severity_level=10,
            impact_analysis={},
            related_services=["security_service"],
            temporal_context={},
            user_impact="Security issue",
            business_impact="Critical risk",
        )

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repo_context,
            generator_type="security_error",
        )

        prompt = template.generate_prompt(prompt_context)

        assert "security engineer" in prompt
        assert "SECURITY ISSUE ANALYSIS REQUEST" in prompt
        assert "security_error" in prompt
        assert "10/10" in prompt
        assert "Security issue" in prompt
        assert "Critical risk" in prompt
