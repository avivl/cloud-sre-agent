# gemini_sre_agent/agents/specialized/code_agent.py

"""
Enhanced Code Agent for code generation tasks.

This module provides the EnhancedCodeAgent class specialized for code generation
with multi-provider support and intelligent model selection.
"""

import logging
from typing import Any

from ...llm.base import ModelType
from ...llm.common.enums import ProviderType
from ...llm.config import LLMConfig
from ...llm.strategy_manager import OptimizationGoal
from ..enhanced_base import EnhancedBaseAgent
from ..response_models import CodeResponse

logger = logging.getLogger(__name__)


class EnhancedCodeAgent(EnhancedBaseAgent[CodeResponse]):
    """
    Enhanced agent specialized for code generation tasks with multi-provider support.

    Optimized for code generation with intelligent model selection
    based on code complexity and language requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "code_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced code agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=CodeResponse,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.CODE,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info("EnhancedCodeAgent initialized with quality-focused optimization")

    async def generate_code(
        self,
        description: str,
        language: str,
        framework: str | None = None,
        style_guide: str | None = None,
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Generate code with intelligent model selection.

        Args:
            description: Code generation description
            language: Programming language
            framework: Framework to use (if applicable)
            style_guide: Coding style guide to follow
            **kwargs: Additional arguments

        Returns:
            CodeResponse with generated code and metadata
        """
        prompt_args = {
            "description": description,
            "language": language,
            "framework": framework,
            "style_guide": style_guide,
            **kwargs,
        }

        return await self.execute(
            prompt_name="generate_code",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def refactor_code(
        self,
        code: str,
        language: str,
        refactor_type: str = "general",
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Refactor code with intelligent model selection.

        Args:
            code: Code to refactor
            language: Programming language
            refactor_type: Type of refactoring (performance, readability, etc.)
            **kwargs: Additional arguments

        Returns:
            CodeResponse with refactored code
        """
        prompt_args = {
            "code": code,
            "language": language,
            "refactor_type": refactor_type,
            "task": "refactor",
            **kwargs,
        }

        return await self.execute(
            prompt_name="refactor_code",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def debug_code(
        self,
        code: str,
        language: str,
        error_message: str | None = None,
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Debug code with intelligent model selection.

        Args:
            code: Code to debug
            language: Programming language
            error_message: Error message (if available)
            **kwargs: Additional arguments

        Returns:
            CodeResponse with debugged code
        """
        prompt_args = {
            "code": code,
            "language": language,
            "error_message": error_message,
            "task": "debug",
            **kwargs,
        }

        return await self.execute(
            prompt_name="debug_code",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def optimize_code(
        self,
        code: str,
        language: str,
        optimization_goal: str = "performance",
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Optimize code with intelligent model selection.

        Args:
            code: Code to optimize
            language: Programming language
            optimization_goal: Optimization goal (performance, memory, readability)
            **kwargs: Additional arguments

        Returns:
            CodeResponse with optimized code
        """
        prompt_args = {
            "code": code,
            "language": language,
            "optimization_goal": optimization_goal,
            "task": "optimize",
            **kwargs,
        }

        return await self.execute(
            prompt_name="optimize_code",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def generate_tests(
        self,
        code: str,
        language: str,
        test_framework: str | None = None,
        test_type: str = "unit",
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Generate tests for code with intelligent model selection.

        Args:
            code: Code to generate tests for
            language: Programming language
            test_framework: Test framework to use
            test_type: Type of tests (unit, integration, e2e)
            **kwargs: Additional arguments

        Returns:
            CodeResponse with generated test code
        """
        prompt_args = {
            "code": code,
            "language": language,
            "test_framework": test_framework,
            "test_type": test_type,
            "task": "generate_tests",
            **kwargs,
        }

        return await self.execute(
            prompt_name="generate_tests",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def generate_documentation(
        self,
        code: str,
        language: str,
        doc_format: str = "docstring",
        **kwargs: Any,
    ) -> CodeResponse:
        """
        Generate documentation for code with intelligent model selection.

        Args:
            code: Code to generate documentation for
            language: Programming language
            doc_format: Documentation format (docstring, markdown, etc.)
            **kwargs: Additional arguments

        Returns:
            CodeResponse with generated documentation
        """
        prompt_args = {
            "code": code,
            "language": language,
            "doc_format": doc_format,
            "task": "generate_documentation",
            **kwargs,
        }

        return await self.execute(
            prompt_name="generate_documentation",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    def get_agent_capabilities(self) -> dict[str, Any]:
        """
        Get the capabilities and configuration of this code agent.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "code_generation",
            "optimization_goal": self.optimization_goal.value,
            "min_quality": self.min_quality,
            "supported_languages": [
                "python",
                "javascript",
                "typescript",
                "java",
                "go",
                "rust",
                "c++",
                "c#",
            ],
            "supported_tasks": [
                "code_generation",
                "refactoring",
                "debugging",
                "optimization",
                "test_generation",
                "documentation_generation",
            ],
            "model_type_preference": ModelType.CODE.value,
        }
