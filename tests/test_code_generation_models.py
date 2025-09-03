# tests/test_code_generation_models.py

from datetime import datetime

from gemini_sre_agent.ml.code_generation_models import (
    CodeFix,
    CodeGenerationContext,
    CodeGenerationResult,
    CodePattern,
    CodeQualityLevel,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)


class TestValidationSeverity:
    """Test ValidationSeverity enum"""

    def test_severity_values(self):
        """Test that severity values are properly ordered"""
        assert ValidationSeverity.LOW.value == 1
        assert ValidationSeverity.MEDIUM.value == 2
        assert ValidationSeverity.HIGH.value == 3
        assert ValidationSeverity.CRITICAL.value == 4

    def test_severity_comparison(self):
        """Test severity comparison operations"""
        assert ValidationSeverity.LOW.value < ValidationSeverity.MEDIUM.value
        assert ValidationSeverity.HIGH.value > ValidationSeverity.MEDIUM.value
        assert ValidationSeverity.CRITICAL.value > ValidationSeverity.HIGH.value


class TestCodeQualityLevel:
    """Test CodeQualityLevel enum"""

    def test_quality_values(self):
        """Test that quality values are properly ordered"""
        assert CodeQualityLevel.POOR.value == 1
        assert CodeQualityLevel.FAIR.value == 2
        assert CodeQualityLevel.GOOD.value == 3
        assert CodeQualityLevel.EXCELLENT.value == 4
        assert CodeQualityLevel.OUTSTANDING.value == 5


class TestValidationIssue:
    """Test ValidationIssue dataclass"""

    def test_validation_issue_creation(self):
        """Test creating a validation issue"""
        issue = ValidationIssue(
            issue_id="test_issue",
            severity=ValidationSeverity.HIGH,
            category="syntax",
            message="Test validation issue",
        )

        assert issue.issue_id == "test_issue"
        assert issue.severity == ValidationSeverity.HIGH
        assert issue.category == "syntax"
        assert issue.message == "Test validation issue"
        assert issue.line_number is None
        assert issue.column_number is None
        assert issue.file_path is None
        assert issue.suggestion is None
        assert issue.code_snippet is None

    def test_validation_issue_with_optional_fields(self):
        """Test creating a validation issue with optional fields"""
        issue = ValidationIssue(
            issue_id="test_issue_full",
            severity=ValidationSeverity.CRITICAL,
            category="security",
            message="Critical security issue",
            line_number=42,
            column_number=10,
            file_path="src/main.py",
            suggestion="Use secure authentication",
            code_snippet="password = 'hardcoded'",
        )

        assert issue.line_number == 42
        assert issue.column_number == 10
        assert issue.file_path == "src/main.py"
        assert issue.suggestion == "Use secure authentication"
        assert issue.code_snippet == "password = 'hardcoded'"


class TestValidationResult:
    """Test ValidationResult dataclass"""

    def test_validation_result_creation(self):
        """Test creating a validation result"""
        result = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=8.5
        )

        assert result.is_valid is True
        assert result.severity == ValidationSeverity.LOW
        assert result.quality_score == 8.5
        assert len(result.issues) == 0
        assert len(result.suggestions) == 0
        assert isinstance(result.validation_time, datetime)

    def test_add_issue(self):
        """Test adding issues to validation result"""
        result = ValidationResult(is_valid=True, severity=ValidationSeverity.LOW)

        issue = ValidationIssue(
            issue_id="test_issue",
            severity=ValidationSeverity.MEDIUM,
            category="syntax",
            message="Test issue",
        )

        result.add_issue(issue)
        assert len(result.issues) == 1
        assert result.issues[0] == issue

    def test_add_suggestion(self):
        """Test adding suggestions to validation result"""
        result = ValidationResult(is_valid=True, severity=ValidationSeverity.LOW)

        result.add_suggestion("Use better error handling")
        assert len(result.suggestions) == 1
        assert "Use better error handling" in result.suggestions

    def test_critical_issue_affects_validity(self):
        """Test that critical issues make result invalid"""
        result = ValidationResult(is_valid=True, severity=ValidationSeverity.LOW)

        critical_issue = ValidationIssue(
            issue_id="critical_issue",
            severity=ValidationSeverity.CRITICAL,
            category="security",
            message="Critical security vulnerability",
        )

        result.add_issue(critical_issue)
        assert result.is_valid is False

    def test_get_critical_issues(self):
        """Test getting critical issues"""
        result = ValidationResult(is_valid=False, severity=ValidationSeverity.CRITICAL)

        critical_issue = ValidationIssue(
            issue_id="critical_issue",
            severity=ValidationSeverity.CRITICAL,
            category="security",
            message="Critical security vulnerability",
        )

        medium_issue = ValidationIssue(
            issue_id="medium_issue",
            severity=ValidationSeverity.MEDIUM,
            category="style",
            message="Style issue",
        )

        result.add_issue(critical_issue)
        result.add_issue(medium_issue)

        critical_issues = result.get_critical_issues()
        assert len(critical_issues) == 1
        assert critical_issues[0] == critical_issue

    def test_get_high_priority_issues(self):
        """Test getting high priority issues"""
        result = ValidationResult(is_valid=False, severity=ValidationSeverity.HIGH)

        high_issue = ValidationIssue(
            issue_id="high_issue",
            severity=ValidationSeverity.HIGH,
            category="performance",
            message="Performance issue",
        )

        critical_issue = ValidationIssue(
            issue_id="critical_issue",
            severity=ValidationSeverity.CRITICAL,
            category="security",
            message="Critical security vulnerability",
        )

        low_issue = ValidationIssue(
            issue_id="low_issue",
            severity=ValidationSeverity.LOW,
            category="style",
            message="Style issue",
        )

        result.add_issue(high_issue)
        result.add_issue(critical_issue)
        result.add_issue(low_issue)

        high_priority_issues = result.get_high_priority_issues()
        assert len(high_priority_issues) == 2
        assert high_issue in high_priority_issues
        assert critical_issue in high_priority_issues
        assert low_issue not in high_priority_issues


class TestCodeFix:
    """Test CodeFix dataclass"""

    def test_code_fix_creation(self):
        """Test creating a code fix"""
        fix = CodeFix(
            code="def fix_issue():\n    pass",
            language="python",
            file_path="src/main.py",
            original_issue="database_connection_error",
            fix_description="Fixed database connection issue",
        )

        assert fix.code == "def fix_issue():\n    pass"
        assert fix.language == "python"
        assert fix.file_path == "src/main.py"
        assert fix.original_issue == "database_connection_error"
        assert fix.fix_description == "Fixed database connection issue"
        assert fix.tests is None
        assert fix.documentation is None
        assert fix.validation_results is None
        assert isinstance(fix.generation_time, datetime)
        assert fix.iteration_count == 0
        assert fix.quality_score == 0.0

    def test_add_validation_result(self):
        """Test adding validation results to code fix"""
        fix = CodeFix(
            code="def fix_issue():\n    pass",
            language="python",
            file_path="src/main.py",
            original_issue="test_issue",
            fix_description="Test fix",
        )

        validation_result = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=9.0
        )

        fix.add_validation_result(validation_result)
        assert fix.validation_results == validation_result
        assert fix.quality_score == 9.0

    def test_increment_iteration(self):
        """Test incrementing iteration count"""
        fix = CodeFix(
            code="def fix_issue():\n    pass",
            language="python",
            file_path="src/main.py",
            original_issue="test_issue",
            fix_description="Test fix",
        )

        assert fix.iteration_count == 0
        fix.increment_iteration()
        assert fix.iteration_count == 1
        fix.increment_iteration()
        assert fix.iteration_count == 2

    def test_is_high_quality(self):
        """Test high quality check"""
        fix = CodeFix(
            code="def fix_issue():\n    pass",
            language="python",
            file_path="src/main.py",
            original_issue="test_issue",
            fix_description="Test fix",
        )

        # Without validation results, should be False
        assert fix.is_high_quality() is False

        # With good validation results, should be True
        good_validation = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=9.0
        )
        fix.add_validation_result(good_validation)
        assert fix.is_high_quality() is True

        # With poor validation results, should be False
        poor_validation = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=6.0
        )
        fix.add_validation_result(poor_validation)
        assert fix.is_high_quality() is False


class TestCodePattern:
    """Test CodePattern dataclass"""

    def test_code_pattern_creation(self):
        """Test creating a code pattern"""
        pattern = CodePattern(
            pattern_id="test_pattern",
            name="Test Pattern",
            description="A test pattern",
            domain="test",
            pattern_type="test_type",
            code_template="test_template",
            validation_rules=["rule1", "rule2"],
            best_practices=["practice1", "practice2"],
            examples=["example1", "example2"],
        )

        assert pattern.pattern_id == "test_pattern"
        assert pattern.name == "Test Pattern"
        assert pattern.description == "A test pattern"
        assert pattern.domain == "test"
        assert pattern.pattern_type == "test_type"
        assert pattern.code_template == "test_template"
        assert len(pattern.validation_rules) == 2
        assert len(pattern.best_practices) == 2
        assert len(pattern.examples) == 2

    def test_apply_pattern(self):
        """Test applying a pattern to code"""
        pattern = CodePattern(
            pattern_id="test_pattern",
            name="Test Pattern",
            description="A test pattern",
            domain="test",
            pattern_type="test_type",
            code_template="replaced_code",
            validation_rules=[],
            best_practices=[],
            examples=[],
        )

        code = "{{pattern_placeholder}}"
        context = {"domain": "test"}

        result = pattern.apply(code, context)
        assert result == "replaced_code"


class TestValidationRule:
    """Test ValidationRule dataclass"""

    def test_validation_rule_creation(self):
        """Test creating a validation rule"""
        rule = ValidationRule(
            rule_id="test_rule",
            name="Test Rule",
            description="A test validation rule",
            domain="test",
            rule_type="test_type",
            severity=ValidationSeverity.HIGH,
            validation_function="test_validation",
            parameters={"param1": "value1"},
        )

        assert rule.rule_id == "test_rule"
        assert rule.name == "Test Rule"
        assert rule.description == "A test validation rule"
        assert rule.domain == "test"
        assert rule.rule_type == "test_type"
        assert rule.severity == ValidationSeverity.HIGH
        assert rule.validation_function == "test_validation"
        assert rule.parameters["param1"] == "value1"

    def test_get_severity_value(self):
        """Test getting severity value"""
        rule = ValidationRule(
            rule_id="test_rule",
            name="Test Rule",
            description="A test validation rule",
            domain="test",
            rule_type="test_type",
            severity=ValidationSeverity.CRITICAL,
            validation_function="test_validation",
        )

        assert rule.get_severity_value() == 4


class TestCodeGenerationContext:
    """Test CodeGenerationContext dataclass"""

    def test_code_generation_context_creation(self):
        """Test creating a code generation context"""
        context = CodeGenerationContext(
            task_type="code_generation",
            domain="database",
            complexity_score=7,
            max_iterations=5,
            validation_level="strict",
            quality_threshold=8.5,
            human_review_required=True,
            learning_enabled=False,
        )

        assert context.task_type == "code_generation"
        assert context.domain == "database"
        assert context.complexity_score == 7
        assert context.max_iterations == 5
        assert context.validation_level == "strict"
        assert context.quality_threshold == 8.5
        assert context.human_review_required is True
        assert context.learning_enabled is False

    def test_requires_strict_validation(self):
        """Test strict validation requirement check"""
        strict_context = CodeGenerationContext(validation_level="strict")
        standard_context = CodeGenerationContext(validation_level="standard")

        assert strict_context.requires_strict_validation() is True
        assert standard_context.requires_strict_validation() is False

    def test_should_escalate_to_human(self):
        """Test human escalation check"""
        # High complexity should escalate
        high_complexity = CodeGenerationContext(complexity_score=9)
        assert high_complexity.should_escalate_to_human() is True

        # Security domain should escalate
        security_domain = CodeGenerationContext(domain="security")
        assert security_domain.should_escalate_to_human() is True

        # Explicit human review required should escalate
        explicit_review = CodeGenerationContext(human_review_required=True)
        assert explicit_review.should_escalate_to_human() is True

        # Low complexity, non-security, no explicit review should not escalate
        normal_context = CodeGenerationContext(
            complexity_score=3, domain="general", human_review_required=False
        )
        assert normal_context.should_escalate_to_human() is False


class TestCodeGenerationResult:
    """Test CodeGenerationResult dataclass"""

    def test_code_generation_result_creation(self):
        """Test creating a code generation result"""
        result = CodeGenerationResult(
            success=True, generation_time_ms=1500, iteration_count=2, quality_score=8.5
        )

        assert result.success is True
        assert result.code_fix is None
        assert result.validation_result is None
        assert result.error_message is None
        assert len(result.warnings) == 0
        assert result.generation_time_ms == 1500
        assert result.iteration_count == 2
        assert result.quality_score == 8.5

    def test_add_warning(self):
        """Test adding warnings"""
        result = CodeGenerationResult(success=True)

        result.add_warning("Test warning")
        assert len(result.warnings) == 1
        assert "Test warning" in result.warnings

    def test_is_high_quality_without_code_fix(self):
        """Test high quality check without code fix"""
        result = CodeGenerationResult(success=True)
        assert result.is_high_quality() is False

    def test_is_high_quality_with_code_fix(self):
        """Test high quality check with code fix"""
        from gemini_sre_agent.ml.code_generation_models import CodeFix, ValidationResult

        # Create a high-quality code fix
        validation_result = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=9.0
        )

        code_fix = CodeFix(
            code="def fix():\n    pass",
            language="python",
            file_path="test.py",
            original_issue="test",
            fix_description="test",
            validation_results=validation_result,
        )

        result = CodeGenerationResult(
            success=True, code_fix=code_fix, quality_score=9.0
        )

        assert result.is_high_quality() is True

    def test_get_summary(self):
        """Test getting result summary"""
        result = CodeGenerationResult(
            success=True, generation_time_ms=2000, iteration_count=3, quality_score=8.0
        )

        result.add_warning("Warning 1")
        result.add_warning("Warning 2")

        summary = result.get_summary()

        assert summary["success"] is True
        assert summary["quality_score"] == 8.0
        assert summary["iteration_count"] == 3
        assert summary["validation_passed"] is False  # No validation result
        assert summary["critical_issues"] == 0
        assert summary["generation_time_ms"] == 2000
        assert summary["warnings_count"] == 2
