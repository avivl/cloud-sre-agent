# gemini_sre_agent/ml/meta_prompt_generator.py

"""
Meta-prompt generation system for dynamic prompt optimization.

This module implements a sophisticated meta-prompt generation system where
a specialized Gemini model analyzes context and generates optimized prompts
for the main code generation model.
"""

from dataclasses import dataclass
import json
import logging
from typing import Any

from google.cloud import aiplatform
from google.generativeai.generative_models import GenerativeModel

from .prompt_context_models import MetaPromptContext, ValidationResult


@dataclass
class MetaPromptConfig:
    """Configuration for meta-prompt generation."""

    project_id: str
    location: str
    meta_model: str = "gemini-1.5-flash-001"
    max_retries: int = 3
    timeout_seconds: int = 30
    enable_validation: bool = True
    enable_fallback: bool = True


class MetaPromptGenerator:
    """Generates optimized prompts for code generation using Gemini."""

    def __init__(self, config: MetaPromptConfig) -> None:
        """
        Initialize the meta-prompt generator.

        Args:
            config: Configuration for meta-prompt generation
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize the meta-prompt generation model
        aiplatform.init(project=config.project_id, location=config.location)
        self.meta_model_instance = GenerativeModel(config.meta_model)

        # Load prompt optimization strategies
        self.optimization_strategies = self._load_optimization_strategies()

        self.logger.info(f"[META-PROMPT] Initialized with model: {config.meta_model}")

    async def generate_optimized_prompt(self, context: MetaPromptContext) -> str:
        """
        Generate an optimized prompt for the main code generation model.

        Args:
            context: Complete context for prompt generation

        Returns:
            Optimized prompt string for the main code generation model
        """
        self.logger.info(
            f"[META-PROMPT] Generating optimized prompt for flow_id={context.flow_id}"
        )

        try:
            # 1. Build meta-prompt for prompt generation
            meta_prompt = self._build_meta_prompt(context)

            # 2. Generate optimized prompt using meta-model
            response = self.meta_model_instance.generate_content(meta_prompt)
            optimized_prompt = response.text.strip()

            # 3. Validate and refine the generated prompt
            if self.config.enable_validation:
                validated_prompt = await self._validate_and_refine_prompt(
                    optimized_prompt, context
                )
            else:
                validated_prompt = optimized_prompt

            self.logger.info(
                f"[META-PROMPT] Generated optimized prompt: {len(validated_prompt)} chars"
            )
            return validated_prompt

        except Exception as e:
            self.logger.error(f"[META-PROMPT] Error generating prompt: {e}")

            if self.config.enable_fallback:
                return self._generate_fallback_prompt(context)
            else:
                raise ValueError(f"Meta-prompt generation failed: {e}") from e

    def _build_meta_prompt(self, context: MetaPromptContext) -> str:
        """Build the meta-prompt that will generate the optimized prompt."""

        return f"""You are an expert prompt engineer specializing in code generation for SRE and DevOps scenarios. Your task is to generate an optimized prompt that will be used by another AI model to generate high-quality code fixes.

CONTEXT ANALYSIS:
You need to analyze the following context and create a prompt that will help another AI model generate the best possible code fix for this specific situation.

ISSUE CONTEXT:
{json.dumps(context.issue_context, indent=2)}

REPOSITORY CONTEXT:
{json.dumps(context.repository_context, indent=2)}

TRIAGE INFORMATION:
{json.dumps(context.triage_packet, indent=2)}

HISTORICAL LOGS:
{json.dumps(context.historical_logs, indent=2)}

CONFIGURATIONS:
{json.dumps(context.configs, indent=2)}

PREVIOUS ATTEMPTS (if any):
{json.dumps(context.previous_attempts or [], indent=2)}

VALIDATION FEEDBACK (if any):
{json.dumps(context.validation_feedback or {}, indent=2)}

PROMPT GENERATION INSTRUCTIONS:

1. ANALYZE THE CONTEXT:
   - Identify the issue type (database, API, service, configuration, performance, security)
   - Determine the technology stack and frameworks involved
   - Assess the severity and impact of the issue
   - Consider the repository's coding standards and patterns
   - Evaluate any previous attempts and their outcomes

2. OPTIMIZE FOR THE SPECIFIC SITUATION:
   - Tailor the prompt to the specific issue type and technology stack
   - Include relevant coding standards and patterns from the repository
   - Incorporate lessons learned from previous attempts
   - Address any validation feedback from previous iterations
   - Consider the business impact and user experience

3. GENERATE AN OPTIMIZED PROMPT:
   Create a comprehensive prompt that will guide another AI model to generate the best possible code fix. The prompt should include:

   a) CLEAR ROLE DEFINITION:
      - Define the AI's role as an expert in the specific domain
      - Specify the expertise areas relevant to this issue
      - Set expectations for code quality and standards

   b) DETAILED CONTEXT:
      - Provide all relevant technical context
      - Include specific error patterns and symptoms
      - Reference similar issues and their solutions
      - Include performance and security considerations

   c) SPECIFIC INSTRUCTIONS:
      - Clear step-by-step analysis approach
      - Specific coding standards to follow
      - Error handling requirements
      - Testing and validation requirements
      - Documentation requirements

   d) OUTPUT FORMAT:
      - Specify the exact JSON schema for the response
      - Include examples of good vs bad approaches
      - Define success criteria

   e) CONSTRAINTS AND REQUIREMENTS:
      - Performance requirements
      - Security considerations
      - Backward compatibility requirements
      - Integration requirements

4. INCLUDE FEW-SHOT EXAMPLES:
   If relevant examples exist in the context, include them as few-shot examples to guide the model.

5. ADD VALIDATION CHECKPOINTS:
   Include specific validation steps the model should perform on its own output.

OUTPUT FORMAT:
Provide only the optimized prompt that will be used by the main code generation model. The prompt should be comprehensive, specific, and tailored to this exact situation.

The generated prompt should be ready to use immediately without any additional formatting or modification."""

    async def _validate_and_refine_prompt(
        self, prompt: str, context: MetaPromptContext
    ) -> str:
        """Validate and refine the generated prompt."""

        # Basic validation checks
        validation_checks = [
            self._check_prompt_completeness,
            self._check_technical_accuracy,
            self._check_output_format,
            self._check_context_relevance,
        ]

        validation_results = []
        for check in validation_checks:
            result = check(prompt, context)
            validation_results.append(result)

            if not result.success:
                self.logger.warning(
                    f"[META-PROMPT] Prompt validation failed: {check.__name__}"
                )

        # If validation fails, attempt refinement
        if not all(result.success for result in validation_results):
            refined_prompt = await self._refine_prompt_with_validation(
                prompt, validation_results, context
            )
            return refined_prompt

        return prompt

    def _check_prompt_completeness(
        self, prompt: str, context: MetaPromptContext
    ) -> ValidationResult:
        """Check if the prompt includes all necessary components."""
        required_components = [
            "role definition",
            "context",
            "instructions",
            "output format",
            "constraints",
        ]

        prompt_lower = prompt.lower()
        missing_components = [
            comp for comp in required_components if comp not in prompt_lower
        ]

        return ValidationResult(
            success=len(missing_components) == 0,
            issues=missing_components,
            suggestions=(
                ["Include missing components: " + ", ".join(missing_components)]
                if missing_components
                else []
            ),
            confidence_score=0.9 if len(missing_components) == 0 else 0.3,
        )

    def _check_technical_accuracy(
        self, prompt: str, context: MetaPromptContext
    ) -> ValidationResult:
        """Check if the prompt includes accurate technical information."""
        # Implementation would validate technical accuracy
        return ValidationResult(
            success=True, issues=[], suggestions=[], confidence_score=0.8
        )

    def _check_output_format(
        self, prompt: str, context: MetaPromptContext
    ) -> ValidationResult:
        """Check if the prompt specifies a clear output format."""
        has_json = "json" in prompt.lower()
        has_schema = "schema" in prompt.lower()

        return ValidationResult(
            success=has_json and has_schema,
            issues=(
                []
                if (has_json and has_schema)
                else ["Missing JSON schema specification"]
            ),
            suggestions=(
                ["Specify exact JSON output format"]
                if not (has_json and has_schema)
                else []
            ),
            confidence_score=0.9 if (has_json and has_schema) else 0.4,
        )

    def _check_context_relevance(
        self, prompt: str, context: MetaPromptContext
    ) -> ValidationResult:
        """Check if the prompt is relevant to the given context."""
        # Implementation would check context relevance
        return ValidationResult(
            success=True, issues=[], suggestions=[], confidence_score=0.8
        )

    async def _refine_prompt_with_validation(
        self,
        prompt: str,
        validation_results: list[ValidationResult],
        context: MetaPromptContext,
    ) -> str:
        """Refine prompt based on validation feedback."""

        refinement_meta_prompt = f"""You are an expert prompt engineer. You need to refine an existing prompt based on validation feedback.

CURRENT PROMPT:
{prompt}

VALIDATION FEEDBACK:
{json.dumps([result.to_dict() for result in validation_results], indent=2)}

ORIGINAL CONTEXT:
{json.dumps(context.to_dict(), indent=2)}

REFINEMENT INSTRUCTIONS:
1. Analyze the validation feedback to identify specific issues
2. Identify which parts of the prompt need improvement
3. Refine the prompt to address the validation issues
4. Maintain the overall structure while improving specific sections
5. Ensure the refined prompt is more likely to produce successful results

Provide the refined prompt that addresses the validation feedback."""

        try:
            response = self.meta_model_instance.generate_content(refinement_meta_prompt)
            return response.text.strip()
        except Exception as e:
            self.logger.error(f"[META-PROMPT] Error refining prompt: {e}")
            return prompt  # Return original if refinement fails

    def _generate_fallback_prompt(self, context: MetaPromptContext) -> str:
        """Generate a fallback prompt if meta-generation fails."""
        return f"""You are an expert SRE Analysis Agent. Analyze the following issue and generate a comprehensive remediation plan.

Issue Context: {json.dumps(context.issue_context, indent=2)}
Repository Context: {json.dumps(context.repository_context, indent=2)}
Triage Information: {json.dumps(context.triage_packet, indent=2)}

Provide a JSON response with root_cause_analysis, proposed_fix, and code_patch."""

    def _load_optimization_strategies(self) -> dict[str, Any]:
        """Load prompt optimization strategies."""
        return {
            "database_issues": {
                "focus_areas": [
                    "connection management",
                    "query optimization",
                    "transaction handling",
                ],
                "common_patterns": [
                    "connection pooling",
                    "retry mechanisms",
                    "error logging",
                ],
            },
            "api_issues": {
                "focus_areas": ["rate limiting", "authentication", "validation"],
                "common_patterns": [
                    "circuit breaker",
                    "exponential backoff",
                    "status codes",
                ],
            },
            "service_issues": {
                "focus_areas": [
                    "service communication",
                    "timeout handling",
                    "resilience",
                ],
                "common_patterns": [
                    "health checks",
                    "graceful degradation",
                    "monitoring",
                ],
            },
            "security_issues": {
                "focus_areas": [
                    "vulnerability assessment",
                    "secure coding",
                    "authentication",
                ],
                "common_patterns": ["input validation", "encryption", "access control"],
            },
        }
