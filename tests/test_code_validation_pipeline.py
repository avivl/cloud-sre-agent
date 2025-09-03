# tests/test_code_validation_pipeline.py

"""
Comprehensive tests for the code validation pipeline.

This module tests the multi-level validation capabilities including
syntax validation, pattern compliance, security review, and performance analysis.
"""

from unittest.mock import Mock

import pytest

from gemini_sre_agent.ml.validation import (
    CodeValidationPipeline,
    ValidationIssue,
    ValidationLevel,
    ValidationResult,
    ValidationType,
)


class TestCodeValidationPipeline:
    """Test cases for CodeValidationPipeline class."""

    @pytest.fixture
    def validation_pipeline(self):
        """Create a CodeValidationPipeline instance."""
        return CodeValidationPipeline()

    @pytest.fixture
    def valid_python_code(self):
        """Valid Python code for testing."""
        return """
def process_data(data):
    try:
        result = []
        for item in data:
            if item is not None:
                result.append(item.upper())
        return result
    except Exception as e:
        logging.error(f"Error processing data: {e}")
        return []
"""

    @pytest.fixture
    def invalid_python_code(self):
        """Invalid Python code for testing."""
        return """
def process_data(data:
    result = []
    for item in data
        result.append(item.upper())
    return result
"""

    @pytest.fixture
    def code_with_security_issues(self):
        """Code with security vulnerabilities."""
        return """
def execute_query(user_input):
    query = "SELECT * FROM users WHERE name = '" + user_input + "'"
    cursor.execute(query)
    return cursor.fetchall()

def save_file(filename):
    with open(filename, 'w') as f:
        f.write("data")
"""

    @pytest.fixture
    def code_with_performance_issues(self):
        """Code with performance anti-patterns."""
        return """
def process_large_dataset(data):
    result = []
    for i in range(len(data)):
        for j in range(len(data)):
            result.append(data[i] + data[j])
    return result

def infinite_loop():
    while True:
        process_data()
"""

    @pytest.fixture
    def code_with_todo_comments(self):
        """Code with TODO/FIXME comments."""
        return """
def incomplete_function():
    # TODO: Implement proper error handling
    result = process_data()
    # FIXME: Add validation
    return result
"""

    @pytest.mark.asyncio
    async def test_validate_valid_code(self, validation_pipeline, valid_python_code):
        """Test validation of valid Python code."""
        code_result = {
            "code_patch": valid_python_code,
            "file_path": "test.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.is_valid is True
        assert result.overall_score > 0.8
        assert result.syntax_valid is True
        assert result.security_valid is True
        assert result.performance_valid is True
        assert len(result.issues) == 0

    @pytest.mark.asyncio
    async def test_validate_invalid_syntax(
        self, validation_pipeline, invalid_python_code
    ):
        """Test validation of code with syntax errors."""
        code_result = {
            "code_patch": invalid_python_code,
            "file_path": "test.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.is_valid is False
        assert result.syntax_valid is False
        assert result.syntax_score == 0.0
        assert len(result.issues) > 0

        syntax_issues = [
            issue
            for issue in result.issues
            if issue.validation_type == ValidationType.SYNTAX
        ]
        assert len(syntax_issues) > 0
        assert syntax_issues[0].level == ValidationLevel.ERROR

    @pytest.mark.asyncio
    async def test_validate_security_issues(
        self, validation_pipeline, code_with_security_issues
    ):
        """Test validation of code with security vulnerabilities."""
        code_result = {
            "code_patch": code_with_security_issues,
            "file_path": "test.py",
            "generator_type": "security_error",
            "issue_type": "security_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.security_valid is False
        assert result.security_score < 1.0

        security_issues = [
            issue
            for issue in result.issues
            if issue.validation_type == ValidationType.SECURITY
        ]
        assert len(security_issues) > 0
        assert any(issue.level == ValidationLevel.CRITICAL for issue in security_issues)

    @pytest.mark.asyncio
    async def test_validate_performance_issues(
        self, validation_pipeline, code_with_performance_issues
    ):
        """Test validation of code with performance issues."""
        code_result = {
            "code_patch": code_with_performance_issues,
            "file_path": "test.py",
            "generator_type": "performance_error",
            "issue_type": "performance_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.performance_valid is False
        assert result.performance_score < 1.0

        performance_issues = [
            issue
            for issue in result.issues
            if issue.validation_type == ValidationType.PERFORMANCE
        ]
        assert len(performance_issues) > 0
        assert any(
            issue.level == ValidationLevel.WARNING for issue in performance_issues
        )

    @pytest.mark.asyncio
    async def test_validate_todo_comments(
        self, validation_pipeline, code_with_todo_comments
    ):
        """Test validation of code with TODO/FIXME comments."""
        code_result = {
            "code_patch": code_with_todo_comments,
            "file_path": "test.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.pattern_compliant is False
        assert result.pattern_score < 1.0

        pattern_issues = [
            issue
            for issue in result.issues
            if issue.validation_type == ValidationType.PATTERN_COMPLIANCE
        ]
        assert len(pattern_issues) > 0
        assert any(
            "TODO" in issue.message or "FIXME" in issue.message
            for issue in pattern_issues
        )

    @pytest.mark.asyncio
    async def test_validate_empty_code(self, validation_pipeline):
        """Test validation of empty code."""
        code_result = {
            "code_patch": "",
            "file_path": "test.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        assert result.is_valid is False
        assert result.overall_score == 0.0
        assert len(result.issues) > 0
        assert any("empty" in issue.message.lower() for issue in result.issues)

    @pytest.mark.asyncio
    async def test_validate_with_context(self, validation_pipeline, valid_python_code):
        """Test validation with additional context."""
        code_result = {
            "code_patch": valid_python_code,
            "file_path": "test.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        context = {
            "repository_context": Mock(),
            "issue_context": Mock(),
        }

        result = await validation_pipeline.validate_code(code_result, context)

        assert result.is_valid is True
        assert "repository_context" in result.validation_metadata

    @pytest.mark.asyncio
    async def test_api_specific_validation(self, validation_pipeline):
        """Test API-specific validation patterns."""
        api_code = """
def api_endpoint(request):
    data = request.json
    return process_data(data)
"""

        code_result = {
            "code_patch": api_code,
            "file_path": "api.py",
            "generator_type": "api_error",
            "issue_type": "api_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        # Should have feedback about missing authentication and validation
        assert len(result.feedback) > 0
        auth_feedback = [f for f in result.feedback if "auth" in f.message.lower()]
        assert len(auth_feedback) > 0

    @pytest.mark.asyncio
    async def test_database_specific_validation(self, validation_pipeline):
        """Test database-specific validation patterns."""
        db_code = """
def get_user_data(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    return cursor.fetchone()
"""

        code_result = {
            "code_patch": db_code,
            "file_path": "db.py",
            "generator_type": "database_error",
            "issue_type": "database_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        # Should have issues about connection not being closed
        connection_issues = [
            issue for issue in result.issues if "connection" in issue.message.lower()
        ]
        assert len(connection_issues) > 0

    @pytest.mark.asyncio
    async def test_security_specific_validation(self, validation_pipeline):
        """Test security-specific validation patterns."""
        security_code = """
def process_user_input(user_input):
    result = user_input
    return result
"""

        code_result = {
            "code_patch": security_code,
            "file_path": "security.py",
            "generator_type": "security_error",
            "issue_type": "security_error",
        }

        result = await validation_pipeline.validate_code(code_result)

        # Should have feedback about input sanitization
        sanitization_feedback = [
            f for f in result.feedback if "sanitiz" in f.message.lower()
        ]
        assert len(sanitization_feedback) > 0

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, validation_pipeline):
        """Test validation error handling."""
        # Test with malformed code result
        result = await validation_pipeline.validate_code(None)

        assert result.is_valid is False
        assert result.overall_score == 0.0
        assert len(result.issues) > 0

    def test_get_line_number(self, validation_pipeline):
        """Test line number calculation."""
        code = "line1\nline2\nline3"

        # Test various positions
        assert validation_pipeline._get_line_number(code, 0) == 1
        assert validation_pipeline._get_line_number(code, 5) == 1
        assert validation_pipeline._get_line_number(code, 6) == 2
        assert validation_pipeline._get_line_number(code, 12) == 3

    def test_create_empty_code_result(self, validation_pipeline):
        """Test creation of empty code validation result."""
        result = validation_pipeline._create_empty_code_result()

        assert result.is_valid is False
        assert result.overall_score == 0.0
        assert len(result.issues) == 1
        assert "empty" in result.issues[0].message.lower()

    def test_create_error_result(self, validation_pipeline):
        """Test creation of error validation result."""
        error_msg = "Test error"
        result = validation_pipeline._create_error_result(error_msg)

        assert result.is_valid is False
        assert result.overall_score == 0.0
        assert len(result.issues) == 1
        assert error_msg in result.issues[0].message


class TestValidationModels:
    """Test cases for validation models."""

    def test_validation_result_get_issues_by_level(self):
        """Test filtering issues by level."""
        issues = [
            ValidationIssue(
                issue_id="1",
                validation_type=ValidationType.SYNTAX,
                level=ValidationLevel.ERROR,
                message="Error 1",
                description="Description 1",
            ),
            ValidationIssue(
                issue_id="2",
                validation_type=ValidationType.SECURITY,
                level=ValidationLevel.CRITICAL,
                message="Critical 1",
                description="Description 2",
            ),
            ValidationIssue(
                issue_id="3",
                validation_type=ValidationType.PERFORMANCE,
                level=ValidationLevel.WARNING,
                message="Warning 1",
                description="Description 3",
            ),
        ]

        result = ValidationResult(
            is_valid=False,
            overall_score=0.5,
            issues=issues,
            feedback=[],
            validation_metadata={},
        )

        error_issues = result.get_issues_by_level(ValidationLevel.ERROR)
        assert len(error_issues) == 1
        assert error_issues[0].issue_id == "1"

        critical_issues = result.get_issues_by_level(ValidationLevel.CRITICAL)
        assert len(critical_issues) == 1
        assert critical_issues[0].issue_id == "2"

    def test_validation_result_get_issues_by_type(self):
        """Test filtering issues by type."""
        issues = [
            ValidationIssue(
                issue_id="1",
                validation_type=ValidationType.SYNTAX,
                level=ValidationLevel.ERROR,
                message="Syntax Error",
                description="Description 1",
            ),
            ValidationIssue(
                issue_id="2",
                validation_type=ValidationType.SECURITY,
                level=ValidationLevel.CRITICAL,
                message="Security Issue",
                description="Description 2",
            ),
        ]

        result = ValidationResult(
            is_valid=False,
            overall_score=0.5,
            issues=issues,
            feedback=[],
            validation_metadata={},
        )

        syntax_issues = result.get_issues_by_type(ValidationType.SYNTAX)
        assert len(syntax_issues) == 1
        assert syntax_issues[0].issue_id == "1"

        security_issues = result.get_issues_by_type(ValidationType.SECURITY)
        assert len(security_issues) == 1
        assert security_issues[0].issue_id == "2"

    def test_validation_result_has_critical_issues(self):
        """Test critical issues detection."""
        issues = [
            ValidationIssue(
                issue_id="1",
                validation_type=ValidationType.SYNTAX,
                level=ValidationLevel.ERROR,
                message="Error",
                description="Description",
            ),
            ValidationIssue(
                issue_id="2",
                validation_type=ValidationType.SECURITY,
                level=ValidationLevel.CRITICAL,
                message="Critical",
                description="Description",
            ),
        ]

        result = ValidationResult(
            is_valid=False,
            overall_score=0.5,
            issues=issues,
            feedback=[],
            validation_metadata={},
        )

        assert result.has_critical_issues() is True

    def test_validation_result_get_validation_summary(self):
        """Test validation summary generation."""
        issues = [
            ValidationIssue(
                issue_id="1",
                validation_type=ValidationType.SYNTAX,
                level=ValidationLevel.ERROR,
                message="Error",
                description="Description",
            ),
            ValidationIssue(
                issue_id="2",
                validation_type=ValidationType.SECURITY,
                level=ValidationLevel.CRITICAL,
                message="Critical",
                description="Description",
            ),
        ]

        result = ValidationResult(
            is_valid=False,
            overall_score=0.5,
            issues=issues,
            feedback=[],
            validation_metadata={},
            syntax_score=0.8,
            pattern_score=0.6,
            security_score=0.3,
            performance_score=0.9,
        )

        summary = result.get_validation_summary()

        assert summary["is_valid"] is False
        assert summary["overall_score"] == 0.5
        assert summary["total_issues"] == 2
        assert summary["critical_issues"] == 1
        assert summary["errors"] == 1
        assert summary["scores"]["syntax"] == 0.8
        assert summary["scores"]["security"] == 0.3


if __name__ == "__main__":
    pytest.main([__file__])
