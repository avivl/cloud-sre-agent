# gemini_sre_agent/agents/specialized.py

"""
Specialized agent classes for different types of tasks.

This module provides specialized agent classes that inherit from BaseAgent
and are tailored for specific types of tasks like text generation, analysis,
and code generation.
"""

from typing import List, Optional

from ..llm.service import LLMService
from .base import BaseAgent
from .response_models import TextResponse, AnalysisResponse, CodeResponse


class TextAgent(BaseAgent[TextResponse]):
    """Agent specialized for text generation tasks."""
    
    def __init__(
        self,
        llm_service: LLMService,
        primary_model: str = "smart",
        fallback_model: Optional[str] = "fast",
    ):
        super().__init__(
            llm_service=llm_service,
            response_model=TextResponse,
            primary_model=primary_model,
            fallback_model=fallback_model
        )
    
    async def generate_text(self, prompt: str, **kwargs) -> TextResponse:
        """Generate text using the agent."""
        return await self.execute(
            prompt_name="generate_text",
            prompt_args={"input": prompt, **kwargs}
        )


class AnalysisAgent(BaseAgent[AnalysisResponse]):
    """Agent specialized for analysis tasks."""
    
    def __init__(
        self,
        llm_service: LLMService,
        primary_model: str = "smart",
        fallback_model: Optional[str] = None,  # No fallback by default for analysis
    ):
        super().__init__(
            llm_service=llm_service,
            response_model=AnalysisResponse,
            primary_model=primary_model,
            fallback_model=fallback_model
        )
    
    async def analyze(self, content: str, criteria: List[str], **kwargs) -> AnalysisResponse:
        """Analyze content based on provided criteria."""
        return await self.execute(
            prompt_name="analyze_content",
            prompt_args={"content": content, "criteria": criteria, **kwargs}
        )


class CodeAgent(BaseAgent[CodeResponse]):
    """Agent specialized for code generation tasks."""
    
    def __init__(
        self,
        llm_service: LLMService,
        primary_model: str = "code",
        fallback_model: Optional[str] = "smart",
    ):
        super().__init__(
            llm_service=llm_service,
            response_model=CodeResponse,
            primary_model=primary_model,
            fallback_model=fallback_model
        )
    
    async def generate_code(self, description: str, language: str, **kwargs) -> CodeResponse:
        """Generate code based on description and language."""
        return await self.execute(
            prompt_name="generate_code",
            prompt_args={"description": description, "language": language, **kwargs}
        )
