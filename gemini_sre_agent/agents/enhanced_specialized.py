"""
Enhanced Specialized Agent Classes with Multi-Provider Support.

This module provides enhanced specialized agent classes that inherit from
EnhancedBaseAgent and are tailored for specific types of tasks with
intelligent model selection and multi-provider capabilities.
"""

import logging
from typing import Any, Dict, List, Optional

from ..llm.base import ModelType
from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .enhanced_base import EnhancedBaseAgent
from .response_models import (
    AnalysisResponse,
    CodeResponse,
    RemediationResponse,
    TextResponse,
    TriageResponse,
)

logger = logging.getLogger(__name__)


class EnhancedTextAgent(EnhancedBaseAgent[TextResponse]):
    """
    Enhanced agent specialized for text generation tasks with multi-provider support.

    Optimized for general text generation with intelligent model selection
    based on content complexity and quality requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.7,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced text agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for text generation
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=TextResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.SMART,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info("EnhancedTextAgent initialized with quality-focused optimization")

    async def generate_text(
        self,
        prompt: str,
        max_length: Optional[int] = None,
        temperature: float = 0.7,
        provider: Optional[ProviderType] = None,
        optimization_goal: Optional[OptimizationGoal] = None,
        **kwargs: Any,
    ) -> TextResponse:
        """
        Generate text using intelligent model selection.

        Args:
            prompt: Text generation prompt
            max_length: Maximum length of generated text
            temperature: Temperature for generation
            provider: Specific provider to use
            optimization_goal: Override default optimization goal
            **kwargs: Additional arguments

        Returns:
            TextResponse with generated text and metadata
        """
        prompt_args = {
            "input": prompt,
            "max_length": max_length,
            **kwargs,
        }

        return await self.execute(
            prompt_name="generate_text",
            prompt_args=prompt_args,
            provider=provider,
            optimization_goal=optimization_goal,
            temperature=temperature,
        )

    async def summarize_text(
        self,
        text: str,
        max_length: Optional[int] = None,
        focus_points: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> TextResponse:
        """
        Summarize text with intelligent model selection.

        Args:
            text: Text to summarize
            max_length: Maximum length of summary
            focus_points: Specific points to focus on in summary
            **kwargs: Additional arguments

        Returns:
            TextResponse with summary
        """
        prompt_args = {
            "input": text,
            "max_length": max_length,
            "focus_points": focus_points or [],
            "task": "summarize",
            **kwargs,
        }

        return await self.execute(
            prompt_name="summarize_text",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def translate_text(
        self,
        text: str,
        target_language: str,
        source_language: Optional[str] = None,
        **kwargs: Any,
    ) -> TextResponse:
        """
        Translate text with intelligent model selection.

        Args:
            text: Text to translate
            target_language: Target language for translation
            source_language: Source language (auto-detect if None)
            **kwargs: Additional arguments

        Returns:
            TextResponse with translation
        """
        prompt_args = {
            "input": text,
            "target_language": target_language,
            "source_language": source_language,
            "task": "translate",
            **kwargs,
        }

        return await self.execute(
            prompt_name="translate_text",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )


class EnhancedAnalysisAgent(EnhancedBaseAgent[AnalysisResponse]):
    """
    Enhanced agent specialized for analysis tasks with multi-provider support.

    Optimized for complex analysis tasks with intelligent model selection
    based on analysis complexity and accuracy requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced analysis agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for analysis
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=AnalysisResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.DEEP_THINKING,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info(
            "EnhancedAnalysisAgent initialized with quality-focused optimization"
        )

    async def analyze(
        self,
        content: str,
        criteria: List[str],
        analysis_type: str = "general",
        depth: str = "detailed",
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform analysis with intelligent model selection.

        Args:
            content: Content to analyze
            criteria: Analysis criteria
            analysis_type: Type of analysis (general, technical, business, etc.)
            depth: Analysis depth (brief, detailed, comprehensive)
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with analysis results
        """
        prompt_args = {
            "content": content,
            "criteria": criteria,
            "analysis_type": analysis_type,
            "depth": depth,
            **kwargs,
        }

        return await self.execute(
            prompt_name="analyze",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def compare_analysis(
        self,
        items: List[str],
        comparison_criteria: List[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform comparative analysis with intelligent model selection.

        Args:
            items: Items to compare
            comparison_criteria: Criteria for comparison
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with comparison results
        """
        prompt_args = {
            "items": items,
            "comparison_criteria": comparison_criteria,
            "task": "compare",
            **kwargs,
        }

        return await self.execute(
            prompt_name="compare_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )

    async def trend_analysis(
        self,
        data: List[Dict[str, Any]],
        time_period: str,
        metrics: List[str],
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Perform trend analysis with intelligent model selection.

        Args:
            data: Data for trend analysis
            time_period: Time period for analysis
            metrics: Metrics to analyze
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with trend analysis results
        """
        prompt_args = {
            "data": data,
            "time_period": time_period,
            "metrics": metrics,
            "task": "trend_analysis",
            **kwargs,
        }

        return await self.execute(
            prompt_name="trend_analysis",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )


class EnhancedCodeAgent(EnhancedBaseAgent[CodeResponse]):
    """
    Enhanced agent specialized for code generation tasks with multi-provider support.

    Optimized for code generation with intelligent model selection
    based on code complexity and language requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced code agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for code generation
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=CodeResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
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
        framework: Optional[str] = None,
        style_guide: Optional[str] = None,
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
        error_message: Optional[str] = None,
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


class EnhancedTriageAgent(EnhancedBaseAgent[TriageResponse]):
    """
    Enhanced agent specialized for triage tasks with multi-provider support.

    Optimized for fast triage with intelligent model selection
    based on urgency and complexity requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.PERFORMANCE,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_performance: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced triage agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for triage
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: PERFORMANCE)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_performance: Minimum performance score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=TriageResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.FAST,
            max_cost=max_cost,
            min_performance=min_performance,
            **kwargs,
        )

        logger.info(
            "EnhancedTriageAgent initialized with performance-focused optimization"
        )

    async def triage_issue(
        self,
        issue: str,
        context: Optional[Dict[str, Any]] = None,
        urgency_level: str = "medium",
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Triage an issue with intelligent model selection.

        Args:
            issue: Issue description
            context: Additional context information
            urgency_level: Urgency level (low, medium, high, critical)
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with triage results
        """
        prompt_args = {
            "issue": issue,
            "context": context or {},
            "urgency_level": urgency_level,
            "task": "triage",
            **kwargs,
        }

        result = await self.execute(
            prompt_name="triage_issue",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )
        
        # Convert TriageResponse to AnalysisResponse if needed
        if hasattr(result, 'category') and hasattr(result, 'description'):
            from .response_models import AnalysisResponse
            return AnalysisResponse(
                summary=result.description,
                key_points=[result.category],
                scores={"urgency": 8 if urgency_level == "high" else 5},
                recommendations=["Investigate the issue further", "Monitor for similar patterns"]
            )
        # If result is already an AnalysisResponse, return it
        if hasattr(result, 'summary') and hasattr(result, 'key_points'):
            return result  # type: ignore
        # Fallback: create a basic AnalysisResponse
        from .response_models import AnalysisResponse
        return AnalysisResponse(
            summary=str(result),
            key_points=["Unknown issue type"],
            scores={"urgency": 5},
            recommendations=["Manual investigation required"]
        )


class EnhancedRemediationAgent(EnhancedBaseAgent[AnalysisResponse]):
    """
    Enhanced agent specialized for remediation tasks with multi-provider support.

    Optimized for comprehensive remediation with intelligent model selection
    based on problem complexity and solution quality requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced remediation agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for remediation
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=AnalysisResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.DEEP_THINKING,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info(
            "EnhancedRemediationAgent initialized with quality-focused optimization"
        )

    async def provide_remediation(
        self,
        problem: str,
        context: Optional[Dict[str, Any]] = None,
        remediation_type: str = "general",
        **kwargs: Any,
    ) -> AnalysisResponse:
        """
        Provide remediation with intelligent model selection.

        Args:
            problem: Problem description
            context: Additional context information
            remediation_type: Type of remediation (technical, process, etc.)
            **kwargs: Additional arguments

        Returns:
            AnalysisResponse with remediation recommendations
        """
        prompt_args = {
            "problem": problem,
            "context": context or {},
            "remediation_type": remediation_type,
            "task": "remediate",
            **kwargs,
        }

        return await self.execute(
            prompt_name="remediate",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )


class EnhancedRemediationAgentV2(EnhancedBaseAgent[RemediationResponse]):
    """
    Enhanced Remediation Agent for generating code patches and remediation plans.

    This agent specializes in creating detailed remediation plans including:
    - Root cause analysis
    - Proposed fixes
    - Code patches
    - Priority assessment
    - Effort estimation
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = None,
        **kwargs: Any,
    ):
        """
        Initialize the Enhanced Remediation Agent.

        Args:
            llm_config: LLM configuration
            primary_model: Primary model to use
            fallback_model: Fallback model if primary fails
            optimization_goal: Optimization strategy
            provider_preference: Preferred LLM provider
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=RemediationResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.CODE,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info(
            "EnhancedRemediationAgent initialized with code generation optimization"
        )

    async def create_remediation_plan(
        self,
        issue_description: str,
        error_context: str,
        target_file: str,
        **kwargs: Any,
    ) -> RemediationResponse:
        """
        Create a comprehensive remediation plan for an issue.

        Args:
            issue_description: Description of the issue to fix
            error_context: Context about the error (logs, stack traces, etc.)
            target_file: Target file path for the fix
            **kwargs: Additional context

        Returns:
            RemediationResponse with detailed remediation plan
        """
        prompt_args = {
            "problem": f"Issue: {issue_description}\nError Context: {error_context}\nTarget File: {target_file}\nAnalysis: {kwargs.get('analysis_summary', '')}\nKey Points: {', '.join(kwargs.get('key_points', []))}",
            **kwargs,
        }

        return await self.execute(
            prompt_name="remediate",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )
