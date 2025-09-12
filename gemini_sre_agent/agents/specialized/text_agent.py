# gemini_sre_agent/agents/specialized/text_agent.py

"""
Enhanced Text Agent for text generation tasks.

This module provides the EnhancedTextAgent class specialized for text generation
with multi-provider support and intelligent model selection.
"""

import logging
from typing import Any, Dict, List, Optional

from ...llm.base import ModelType
from ...llm.common.enums import ProviderType
from ...llm.config import LLMConfig
from ...llm.strategy_manager import OptimizationGoal
from ..enhanced_base import EnhancedBaseAgent
from ..response_models import TextResponse

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
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.7,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced text agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name identifier for this agent
            optimization_goal: Primary optimization goal (quality, speed, cost)
            provider_preference: Preferred providers in order of preference
            max_cost: Maximum cost per request
            min_quality: Minimum quality threshold for responses
            **kwargs: Additional configuration parameters
        """
        super().__init__(
            llm_config=llm_config,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        # Text-specific configuration
        self.max_length = kwargs.get("max_length", 2000)
        self.temperature = kwargs.get("temperature", 0.7)
        self.creativity_level = kwargs.get("creativity_level", "balanced")

    def _get_optimal_model_type(self, task_context: Dict[str, Any]) -> ModelType:
        """
        Determine the optimal model type for text generation tasks.

        Args:
            task_context: Context about the current task

        Returns:
            Optimal ModelType for the task
        """
        content_length = task_context.get("content_length", 0)
        complexity = task_context.get("complexity", "medium")
        quality_requirement = task_context.get("quality_requirement", 0.7)

        # Select model based on content requirements
        if content_length > 1500 or complexity == "high":
            return ModelType.DEEP_THINKING
        elif content_length > 500 or quality_requirement > 0.8:
            return ModelType.SMART
        else:
            return ModelType.FAST

    def _prepare_text_prompt(
        self, prompt: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Prepare and enhance the text generation prompt.

        Args:
            prompt: Base prompt for text generation
            context: Additional context for prompt enhancement

        Returns:
            Enhanced prompt ready for LLM processing
        """
        enhanced_prompt = f"""You are an expert text generation assistant. Generate high-quality, coherent text based on the following request:

{prompt}

Guidelines:
- Maintain appropriate tone and style
- Ensure factual accuracy where applicable
- Structure content logically
- Use clear and engaging language
- Adapt length to requirements (max {self.max_length} characters)
"""

        if context:
            if "style" in context:
                enhanced_prompt += f"\nStyle: {context['style']}"
            if "audience" in context:
                enhanced_prompt += f"\nTarget audience: {context['audience']}"
            if "format" in context:
                enhanced_prompt += f"\nFormat: {context['format']}"

        return enhanced_prompt

    async def generate_text(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> TextResponse:
        """
        Generate text content based on the given prompt.

        Args:
            prompt: Text generation prompt
            context: Additional context for generation
            **kwargs: Additional parameters for text generation

        Returns:
            TextResponse containing the generated text
        """
        try:
            # Prepare the enhanced prompt
            enhanced_prompt = self._prepare_text_prompt(prompt, context)

            # Determine optimal model configuration
            task_context = {
                "content_length": len(prompt),
                "complexity": (
                    context.get("complexity", "medium") if context else "medium"
                ),
                "quality_requirement": self.min_quality,
            }

            model_type = self._get_optimal_model_type(task_context)

            # Generate text using the base agent
            response = await self.execute(
                prompt_name="generate_text",
                prompt_args={
                    "prompt": enhanced_prompt,
                    "model_type": model_type.value,
                    "temperature": self.temperature,
                    "max_tokens": self.max_length,
                    **kwargs,
                },
            )

            return response

        except Exception as e:
            logger.error(f"Text generation failed: {e}")
            return TextResponse(
                text="",
                confidence=0.0,
            )

    async def generate_summary(
        self,
        text: str,
        max_length: Optional[int] = None,
        style: str = "concise",
        **kwargs: Any,
    ) -> TextResponse:
        """
        Generate a summary of the provided text.

        Args:
            text: Text to summarize
            max_length: Maximum length of the summary
            style: Summary style (concise, detailed, bulleted)
            **kwargs: Additional parameters

        Returns:
            TextResponse containing the summary
        """
        summary_length = max_length or min(len(text) // 4, 500)

        prompt = f"""Summarize the following text in a {style} style (max {summary_length} characters):

{text}

Summary:"""

        context = {
            "style": style,
            "max_length": summary_length,
            "task_type": "summarization",
        }

        return await self.generate_text(prompt, context, **kwargs)

    async def generate_explanation(
        self,
        topic: str,
        level: str = "intermediate",
        audience: str = "general",
        **kwargs: Any,
    ) -> TextResponse:
        """
        Generate an explanation of a topic.

        Args:
            topic: Topic to explain
            level: Explanation level (beginner, intermediate, advanced)
            audience: Target audience
            **kwargs: Additional parameters

        Returns:
            TextResponse containing the explanation
        """
        prompt = f"""Explain the following topic in a clear, {level}-level way for a {audience} audience:

{topic}

Explanation:"""

        context = {
            "level": level,
            "audience": audience,
            "task_type": "explanation",
        }

        return await self.generate_text(prompt, context, **kwargs)

    def get_agent_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities and configuration of this text agent.

        Returns:
            Dictionary containing agent capabilities
        """
        return {
            "agent_type": "text_generation",
            "max_length": self.max_length,
            "temperature": self.temperature,
            "creativity_level": self.creativity_level,
            "supported_tasks": [
                "general_text_generation",
                "summarization",
                "explanation",
                "content_creation",
            ],
            "optimization_goal": self.optimization_goal.value,
            "min_quality": self.min_quality,
        }
