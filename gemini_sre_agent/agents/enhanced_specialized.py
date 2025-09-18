# gemini_sre_agent/agents/enhanced_specialized.py

"""
Enhanced Specialized Agent Classes with Multi-Provider Support.

This module provides enhanced specialized agent classes that inherit from
EnhancedBaseAgent and are tailored for specific types of tasks with
intelligent model selection and multi-provider capabilities.
"""

import logging
from typing import Any

from ..llm.base import ModelType
from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .enhanced_base import EnhancedBaseAgent
from .response_models import (
    AnalysisResult,
    CodeResponse,
    RemediationPlan,
    TextResponse,
    TriageResult,
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
        agent_name: str = "text_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = 0.7,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced text agent.

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
            response_model=TextResponse,
            agent_name=agent_name,
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
        max_length: int | None = None,
        temperature: float = 0.7,
        provider: ProviderType | None = None,
        optimization_goal: OptimizationGoal | None = None,
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
        max_length: int | None = None,
        focus_points: list[str] | None = None,
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
        source_language: str | None = None,
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


class EnhancedAnalysisAgent(EnhancedBaseAgent[AnalysisResult]):
    """
    Enhanced agent specialized for analysis tasks with multi-provider support.

    Optimized for complex analysis tasks with intelligent model selection
    based on analysis complexity and accuracy requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "analysis_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced analysis agent.

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
            response_model=AnalysisResult,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.FAST,
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
        criteria: list[str],
        analysis_type: str = "general",
        depth: str = "detailed",
        **kwargs: Any,
    ) -> AnalysisResult:
        """
        Perform analysis with intelligent model selection.

        Args:
            content: Content to analyze
            criteria: Analysis criteria
            analysis_type: Type of analysis (general, technical, business, etc.)
            depth: Analysis depth (brief, detailed, comprehensive)
            **kwargs: Additional arguments

        Returns:
            AnalysisResult with analysis results
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
        items: list[str],
        comparison_criteria: list[str],
        **kwargs: Any,
    ) -> AnalysisResult:
        """
        Perform comparative analysis with intelligent model selection.

        Args:
            items: Items to compare
            comparison_criteria: Criteria for comparison
            **kwargs: Additional arguments

        Returns:
            AnalysisResult with comparison results
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
        data: list[dict[str, Any]],
        time_period: str,
        metrics: list[str],
        **kwargs: Any,
    ) -> AnalysisResult:
        """
        Perform trend analysis with intelligent model selection.

        Args:
            data: Data for trend analysis
            time_period: Time period for analysis
            metrics: Metrics to analyze
            **kwargs: Additional arguments

        Returns:
            AnalysisResult with trend analysis results
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
            model_type_preference=ModelType.FAST,
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


class EnhancedTriageAgent(EnhancedBaseAgent[TriageResult]):
    """
    Enhanced agent specialized for triage tasks with multi-provider support.

    Optimized for fast triage with intelligent model selection
    based on urgency and complexity requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "triage_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.PERFORMANCE,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_performance: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced triage agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Strategy for model selection (default: PERFORMANCE)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_performance: Minimum performance score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=TriageResult,
            agent_name=agent_name,
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
        context: dict[str, Any] | None = None,
        urgency_level: str = "medium",
        **kwargs: Any,
    ) -> AnalysisResult:
        """
        Triage an issue with intelligent model selection.

        Args:
            issue: Issue description
            context: Additional context information
            urgency_level: Urgency level (low, medium, high, critical)
            **kwargs: Additional arguments

        Returns:
            AnalysisResult with triage results
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

        # Convert TriageResult to AnalysisResult if needed
        if hasattr(result, "category") and hasattr(result, "description"):
            from .response_models import AnalysisResult

            return AnalysisResult(
                agent_id="analysis-agent-1",
                agent_type="analysis",
                status="success",
                analysis_type="error_analysis",
                summary=result.description,
                key_findings=[
                    {
                        "title": "Error Analysis",
                        "description": result.description,
                        "severity": "medium",
                        "confidence": 0.8,
                        "category": "performance",
                        "recommendations": ["Investigate the issue further"]
                    }
                ],
                overall_severity="medium",
                overall_confidence=0.8,
                root_cause="Analysis pending",
                impact_assessment="Impact assessment pending",
                risk_assessment="Risk assessment pending",
                business_impact="Business impact pending",
                recommendations=[
                    "Investigate the issue further",
                    "Monitor for similar patterns",
                ],
                next_steps=["Investigate further"]
            )
        # If result is already an AnalysisResult, return it
        if hasattr(result, "summary") and hasattr(result, "key_findings"):
            return result  # type: ignore
        # Fallback: create a basic AnalysisResult
        from .response_models import AnalysisResult

        return AnalysisResult(
            agent_id="analysis-agent-1",
            agent_type="analysis",
            status="success",
            analysis_type="error_analysis",
            summary=str(result),
            key_findings=[
                {
                    "title": "Unknown Issue",
                    "description": "Unknown issue type",
                    "severity": "medium",
                    "confidence": 0.5,
                    "category": "performance",
                    "recommendations": ["Manual investigation required"]
                }
            ],
            overall_severity="medium",
            overall_confidence=0.5,
            root_cause="Analysis pending",
            impact_assessment="Impact assessment pending",
            risk_assessment="Risk assessment pending",
            business_impact="Business impact pending",
            recommendations=["Manual investigation required"],
            next_steps=["Investigate further"]
        )


class EnhancedRemediationAgent(EnhancedBaseAgent[AnalysisResult]):
    """
    Enhanced agent specialized for remediation tasks with multi-provider support.

    Optimized for comprehensive remediation with intelligent model selection
    based on problem complexity and solution quality requirements.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "remediation_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced remediation agent.

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
            response_model=AnalysisResult,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.FAST,
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
        context: dict[str, Any] | None = None,
        remediation_type: str = "general",
        **kwargs: Any,
    ) -> AnalysisResult:
        """
        Provide remediation with intelligent model selection.

        Args:
            problem: Problem description
            context: Additional context information
            remediation_type: Type of remediation (technical, process, etc.)
            **kwargs: Additional arguments

        Returns:
            AnalysisResult with remediation recommendations
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


class EnhancedRemediationAgentV2(EnhancedBaseAgent[RemediationPlan]):
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
        agent_name: str = "remediation_agent_v2",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: list[ProviderType] | None = None,
        max_cost: float | None = None,
        min_quality: float | None = None,
        **kwargs: Any,
    ):
        """
        Initialize the Enhanced Remediation Agent.

        Args:
            llm_config: LLM configuration
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Optimization strategy
            provider_preference: Preferred LLM provider
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=RemediationPlan,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.FAST,
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
    ) -> RemediationPlan:
        """
        Create a comprehensive remediation plan for an issue.

        Args:
            issue_description: Description of the issue to fix
            error_context: Context about the error (logs, stack traces, etc.)
            target_file: Target file path for the fix
            **kwargs: Additional context

        Returns:
            RemediationPlan with detailed remediation plan
        """
        prompt_args = {
            "problem": (
                f"Issue: {issue_description}\nError Context: {error_context}\n"
                f"Target File: {target_file}\nAnalysis: {kwargs.get('analysis_summary', '')}\n"
                f"Key Points: {', '.join(kwargs.get('key_points', []))}"
            ),
            **kwargs,
        }

        return await self.execute(
            prompt_name="remediate",
            prompt_args=prompt_args,
            optimization_goal=OptimizationGoal.QUALITY,
        )
