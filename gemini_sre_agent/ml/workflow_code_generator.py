# gemini_sre_agent/ml/workflow_code_generator.py

"""
Workflow Code Generator for enhanced code generation.

This module handles code generation, enhancement, and specialized generator
coordination for the unified workflow orchestrator.
"""

import logging
from typing import Any, Dict

from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .prompt_context_models import IssueType, PromptContext


class WorkflowCodeGenerator:
    """
    Handles code generation and enhancement for the workflow orchestrator.

    This class manages:
    - Enhanced code generation using specialized generators
    - Code enhancement with domain-specific generators
    - Fallback to basic code generation
    - Generator type determination and coordination
    """

    def __init__(self, enhanced_agent: EnhancedAnalysisAgent):
        """
        Initialize the code generator.

        Args:
            enhanced_agent: Enhanced analysis agent instance
        """
        self.enhanced_agent = enhanced_agent
        self.logger = logging.getLogger(__name__)

    async def generate_enhanced_code(
        self,
        analysis_result: Dict[str, Any],
        prompt_context: PromptContext,
        enable_specialized_generators: bool,
    ) -> str:
        """
        Generate enhanced code using specialized generators.

        Args:
            analysis_result: Analysis result from enhanced agent
            prompt_context: Enhanced prompt context
            enable_specialized_generators: Whether to use specialized generators

        Returns:
            Generated code
        """
        try:
            if not analysis_result.get("success", False):
                return ""

            analysis = analysis_result.get("analysis", {})
            base_code_patch = analysis.get("code_patch", "")

            if not base_code_patch:
                return ""

            if not enable_specialized_generators:
                return base_code_patch

            # Enhance code using specialized generators
            enhanced_code = await self._enhance_code_with_specialized_generators(
                base_code_patch, prompt_context
            )

            return enhanced_code or base_code_patch

        except Exception as e:
            self.logger.error(f"[GENERATION] Code generation failed: {e}")
            return analysis_result.get("analysis", {}).get("code_patch", "")

    async def _enhance_code_with_specialized_generators(
        self, base_code: str, prompt_context: PromptContext
    ) -> str:
        """
        Enhance code using specialized generators.

        Args:
            base_code: Base generated code
            prompt_context: Enhanced prompt context

        Returns:
            Enhanced code
        """
        try:
            if not hasattr(self.enhanced_agent, "code_generator_factory"):
                return base_code

            # Get appropriate generator
            generator_type = self.enhanced_agent._determine_generator_type(
                prompt_context.issue_context
            )

            if not generator_type:
                return base_code

            # Check if specialized generators are enabled
            if not self.enhanced_agent.code_generator_factory:
                self.logger.warning(
                    "Specialized generators not enabled, skipping enhancement"
                )
                return base_code

            # Convert string generator_type back to IssueType for the factory
            try:
                issue_type = IssueType(generator_type)
                generator = self.enhanced_agent.code_generator_factory.create_generator(
                    issue_type
                )
            except ValueError:
                # If conversion fails, use UNKNOWN type
                generator = self.enhanced_agent.code_generator_factory.create_generator(
                    IssueType.UNKNOWN
                )

            if not generator:
                return base_code

            # Enhance the code
            enhanced_code = await generator.enhance_code_patch(
                base_code, prompt_context
            )

            return enhanced_code

        except Exception as e:
            self.logger.error(f"[ENHANCEMENT] Code enhancement failed: {e}")
            return base_code

    def get_generator_type(self, prompt_context: PromptContext) -> str:
        """
        Get the appropriate generator type for the given context.

        Args:
            prompt_context: Enhanced prompt context

        Returns:
            Generator type string
        """
        try:
            return self.enhanced_agent._determine_generator_type(
                prompt_context.issue_context
            )
        except Exception as e:
            self.logger.error(f"Failed to determine generator type: {e}")
            return "unknown"

    def is_specialized_generation_enabled(self) -> bool:
        """
        Check if specialized code generation is enabled.

        Returns:
            True if specialized generators are available and enabled
        """
        try:
            return (
                hasattr(self.enhanced_agent, "code_generator_factory")
                and self.enhanced_agent.code_generator_factory is not None
            )
        except Exception:
            return False

    async def generate_basic_code_patch(self, analysis_result: Dict[str, Any]) -> str:
        """
        Generate basic code patch from analysis result.

        Args:
            analysis_result: Analysis result containing code patch

        Returns:
            Basic code patch
        """
        try:
            analysis = analysis_result.get("analysis", {})
            return analysis.get("code_patch", "")
        except Exception as e:
            self.logger.error(f"Failed to generate basic code patch: {e}")
            return ""
