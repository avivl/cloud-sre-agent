# gemini_sre_agent/ml/base_code_generator.py

import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from .code_generation_models import (
    CodeFix,
    CodeGenerationResult,
    CodePattern,
    ValidationIssue,
    ValidationResult,
    ValidationRule,
    ValidationSeverity,
)
from .prompt_context_models import IssueContext, PromptContext


class BaseCodeGenerator(ABC):
    """Base class for all code generators"""

    def __init__(self):
        self.context: Optional[PromptContext] = None
        self.validation_rules: List[ValidationRule] = []
        self.code_patterns: List[CodePattern] = []
        self.generator_id: str = str(uuid.uuid4())
        self.generation_count: int = 0

    def set_context(self, context: PromptContext):
        """Set the context for code generation"""
        self.context = context
        self._load_domain_specific_patterns()
        self._load_domain_specific_rules()

    @abstractmethod
    def _get_domain(self) -> str:
        """Get the domain this generator specializes in"""
        pass

    @abstractmethod
    def _get_generator_type(self) -> str:
        """Get the type identifier for this generator"""
        pass

    @abstractmethod
    def _load_domain_specific_patterns(self):
        """Load domain-specific code patterns"""
        pass

    @abstractmethod
    def _load_domain_specific_rules(self):
        """Load domain-specific validation rules"""
        pass

    async def generate_code_fix(
        self, issue_context: IssueContext
    ) -> CodeGenerationResult:
        """Generate code fix using our existing prompt system"""
        start_time = time.time()

        try:
            # 1. Use our existing prompt generation
            prompt = await self._generate_domain_specific_prompt(issue_context)

            # 2. Generate initial code
            initial_code = await self._generate_initial_code(prompt, issue_context)

            # 3. Apply domain-specific patterns
            patterned_code = self._apply_domain_patterns(initial_code)

            # 4. Validate against domain rules
            validation_result = await self._validate_domain_rules(patterned_code)

            # 5. Create code fix object
            code_fix = CodeFix(
                code=patterned_code,
                language=self._detect_language(patterned_code),
                file_path=(
                    issue_context.affected_files[0]
                    if issue_context.affected_files
                    else "unknown"
                ),
                original_issue=str(issue_context.issue_type),
                fix_description=f"Fix for {issue_context.issue_type.value} issue",
                validation_results=validation_result,
            )

            # 6. Generate tests and documentation
            code_fix.tests = await self._generate_tests(code_fix)
            code_fix.documentation = await self._generate_documentation(code_fix)

            # 7. Update generation count
            self.generation_count += 1

            generation_time = int((time.time() - start_time) * 1000)

            return CodeGenerationResult(
                success=True,
                code_fix=code_fix,
                validation_result=validation_result,
                generation_time_ms=generation_time,
                quality_score=validation_result.quality_score,
            )

        except Exception as e:
            generation_time = int((time.time() - start_time) * 1000)
            return CodeGenerationResult(
                success=False, error_message=str(e), generation_time_ms=generation_time
            )

    async def enhance_code_patch(
        self,
        code_patch: str,
        context: PromptContext
    ) -> str:
        """
        Enhance an existing code patch using domain-specific knowledge.

        Args:
            code_patch: The existing code patch to enhance
            context: The prompt context for enhancement

        Returns:
            Enhanced code patch
        """
        try:
            # Set context if not already set
            if not self.context:
                self.set_context(context)

            # Apply domain-specific enhancements
            enhanced_code = self._apply_domain_patterns(code_patch)

            # Validate the enhanced code
            validation_result = await self._validate_domain_rules(enhanced_code)

            # If validation fails, return original code
            if not validation_result.is_valid:
                self.logger.warning(f"Enhanced code validation failed: {validation_result.issues}")
                return code_patch

            return enhanced_code

        except Exception as e:
            self.logger.error(f"Code enhancement failed: {e}")
            return code_patch

    async def enhance_fix_description(
        self,
        description: str,
        context: PromptContext
    ) -> str:
        """
        Enhance the fix description using domain-specific knowledge.

        Args:
            description: The existing fix description
            context: The prompt context for enhancement

        Returns:
            Enhanced fix description
        """
        try:
            # Set context if not already set
            if not self.context:
                self.set_context(context)

            # For now, return the original description
            # This can be enhanced later with domain-specific improvements
            return description

        except Exception as e:
            self.logger.error(f"Description enhancement failed: {e}")
            return description

    @property
    def logger(self):
        """Get logger for this generator"""
        import logging
        return logging.getLogger(f"{self.__class__.__name__}")

    async def _generate_domain_specific_prompt(
        self, issue_context: IssueContext
    ) -> str:
        """Generate domain-specific prompt using our existing system"""
        if not self.context:
            raise ValueError("Context not set. Call set_context() first.")

        # For now, create a simple domain-specific prompt
        # In the future, this will integrate with our existing prompt system
        domain = self._get_domain()
        prompt = f"""You are an expert {domain} engineer and SRE specialist.

Your task is to generate code to fix the following issue:

ISSUE TYPE: {issue_context.issue_type.value}
AFFECTED FILES: {', '.join(issue_context.affected_files)}
ERROR PATTERNS: {', '.join(issue_context.error_patterns)}
SEVERITY: {issue_context.severity_level}
COMPLEXITY: {issue_context.complexity_score}

TECHNOLOGY STACK: {self.context.repository_context.technology_stack}
ARCHITECTURE: {self.context.repository_context.architecture_type}

Generate a complete, production-ready code fix that:
1. Follows the project's coding standards
2. Includes proper error handling
3. Is well-documented
4. Follows {domain} best practices
5. Can be immediately deployed

Return only the code fix, no explanations."""

        return prompt

    async def _generate_initial_code(
        self, prompt: str, issue_context: IssueContext
    ) -> str:
        """Generate initial code using the main model"""
        if not self.context:
            raise ValueError("Context not set. Call set_context() first.")

        # For now, return a placeholder implementation
        # In the future, this will integrate with our existing model system
        domain = self._get_domain()
        return f"""# Generated {domain} fix
# TODO: Replace with actual AI-generated code
def fix_{domain}_issue():
    # Implementation will be generated by AI model
    pass"""

    def _extract_code_from_response(self, response_text: str) -> str:
        """Extract code from the model response"""
        # This is a simplified implementation
        # In practice, this would use more sophisticated parsing
        lines = response_text.split("\n")
        code_lines = []
        in_code_block = False

        for line in lines:
            if "```" in line:
                in_code_block = not in_code_block
                continue
            if in_code_block:
                code_lines.append(line)

        return "\n".join(code_lines) if code_lines else response_text

    def _apply_domain_patterns(self, code: str) -> str:
        """Apply domain-specific patterns and best practices"""
        if not self.code_patterns:
            return code

        for pattern in self.code_patterns:
            code = pattern.apply(code, self._get_pattern_context())

        return code

    def _get_pattern_context(self) -> Dict[str, Any]:
        """Get context for pattern application"""
        if not self.context:
            return {}

        return {
            "technology_stack": self.context.repository_context.technology_stack,
            "coding_standards": self.context.repository_context.coding_standards,
            "architecture_type": self.context.repository_context.architecture_type,
            "domain": self._get_domain(),
        }

    async def _validate_domain_rules(self, code: str) -> ValidationResult:
        """Validate code against domain-specific rules"""
        if not self.validation_rules:
            return ValidationResult(
                is_valid=True, severity=ValidationSeverity.LOW, quality_score=7.0
            )

        validation_result = ValidationResult(
            is_valid=True, severity=ValidationSeverity.LOW, quality_score=10.0
        )

        for rule in self.validation_rules:
            try:
                # In practice, this would call actual validation functions
                # For now, we'll simulate validation
                is_valid, issues = await self._execute_validation_rule(rule, code)

                if not is_valid:
                    validation_result.is_valid = False
                    for issue in issues:
                        validation_result.add_issue(issue)

                    # Update severity based on rule severity
                    if rule.severity.value > validation_result.severity.value:
                        validation_result.severity = rule.severity

                # Adjust quality score based on validation results
                validation_result.quality_score = max(
                    0.0, validation_result.quality_score - len(issues) * 0.5
                )

            except Exception as e:
                # Add validation error as a critical issue
                error_issue = ValidationIssue(
                    issue_id=f"validation_error_{rule.rule_id}",
                    severity=ValidationSeverity.CRITICAL,
                    category="validation_error",
                    message=f"Validation rule '{rule.name}' failed: {str(e)}",
                )
                validation_result.add_issue(error_issue)
                validation_result.is_valid = False

        return validation_result

    async def _execute_validation_rule(
        self, rule: ValidationRule, code: str
    ) -> tuple[bool, List[ValidationIssue]]:
        """Execute a validation rule and return results"""
        # This is a simplified implementation
        # In practice, this would call actual validation functions based on rule.validation_function

        # Simulate validation based on rule type
        if rule.rule_type == "syntax":
            return self._validate_syntax(code)
        elif rule.rule_type == "security":
            return self._validate_security(code)
        elif rule.rule_type == "performance":
            return self._validate_performance(code)
        else:
            return True, []

    def _validate_syntax(self, code: str) -> tuple[bool, List[ValidationIssue]]:
        """Basic syntax validation"""
        issues = []

        # Check for basic syntax issues
        if not code.strip():
            issues.append(
                ValidationIssue(
                    issue_id="empty_code",
                    severity=ValidationSeverity.CRITICAL,
                    category="syntax",
                    message="Generated code is empty",
                )
            )

        # Check for common syntax patterns
        if "TODO" in code or "FIXME" in code:
            issues.append(
                ValidationIssue(
                    issue_id="todo_fixme",
                    severity=ValidationSeverity.MEDIUM,
                    category="syntax",
                    message="Code contains TODO or FIXME comments",
                )
            )

        return len(issues) == 0, issues

    def _validate_security(self, code: str) -> tuple[bool, List[ValidationIssue]]:
        """Basic security validation"""
        issues = []

        # Check for common security issues
        security_patterns = [
            ("password", "Hardcoded password detected"),
            ("secret", "Hardcoded secret detected"),
            ("api_key", "Hardcoded API key detected"),
        ]

        for pattern, message in security_patterns:
            if pattern in code.lower():
                issues.append(
                    ValidationIssue(
                        issue_id=f"security_{pattern}",
                        severity=ValidationSeverity.HIGH,
                        category="security",
                        message=message,
                    )
                )

        return len(issues) == 0, issues

    def _validate_performance(self, code: str) -> tuple[bool, List[ValidationIssue]]:
        """Basic performance validation"""
        issues = []

        # Check for common performance issues
        if "sleep(" in code or "time.sleep(" in code:
            issues.append(
                ValidationIssue(
                    issue_id="performance_sleep",
                    severity=ValidationSeverity.MEDIUM,
                    category="performance",
                    message="Code contains sleep statements which may impact performance",
                )
            )

        return len(issues) == 0, issues

    async def _generate_tests(self, code_fix: CodeFix) -> str:
        """Generate tests for the code fix"""
        # This is a simplified implementation
        # In practice, this would use our existing prompt system to generate tests
        return (
            f"# Tests for {code_fix.file_path}\n# TODO: Implement comprehensive tests"
        )

    async def _generate_documentation(self, code_fix: CodeFix) -> str:
        """Generate documentation for the code fix"""
        # This is a simplified implementation
        # In practice, this would use our existing prompt system to generate documentation
        return f"# Documentation for {code_fix.file_path}\n# TODO: Add comprehensive documentation"

    def _detect_language(self, code: str) -> str:
        """Detect the programming language of the generated code"""
        # Simple language detection based on common patterns
        if "def " in code or "import " in code or "class " in code:
            return "python"
        elif "function " in code or "const " in code or "let " in code:
            return "javascript"
        elif "public " in code or "private " in code or "class " in code:
            return "java"
        else:
            return "unknown"

    def get_generator_info(self) -> Dict[str, Any]:
        """Get information about this generator"""
        return {
            "generator_id": self.generator_id,
            "domain": self._get_domain(),
            "generator_type": self._get_generator_type(),
            "generation_count": self.generation_count,
            "patterns_count": len(self.code_patterns),
            "rules_count": len(self.validation_rules),
        }
