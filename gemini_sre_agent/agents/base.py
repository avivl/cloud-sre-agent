# gemini_sre_agent/agents/base.py

"""
Base agent class with structured output support.

This module provides the BaseAgent class that all specialized agents inherit from,
including structured output capabilities, primary/fallback model logic, and
integration with Mirascope for prompt management.
"""

import logging
import time
from typing import Any, Dict, Generic, Optional, Type, TypeVar

# Note: Mirascope integration will be added in a future update
# For now, we'll use simple string templates

from pydantic import BaseModel

from ..llm.service import LLMService
from .stats import AgentStats

T = TypeVar('T', bound=BaseModel)

logger = logging.getLogger(__name__)


class BaseAgent(Generic[T]):
    """Base class for all agents with structured output support."""
    
    def __init__(
        self,
        llm_service: LLMService,
        response_model: Type[T],
        primary_model: str = "smart",
        fallback_model: Optional[str] = "fast",
        max_retries: int = 2,
        collect_stats: bool = True
    ):
        self.llm_service = llm_service
        self.response_model = response_model
        self.primary_model = primary_model
        self.fallback_model = fallback_model
        self.max_retries = max_retries
        self.collect_stats = collect_stats
        self.stats = AgentStats(agent_name=self.__class__.__name__)
        self._prompts = {}  # Cache for Mirascope prompts
    
    async def execute(
        self, 
        prompt_name: str, 
        prompt_args: Dict[str, Any],
        model: Optional[str] = None,
        temperature: float = 0.7,
        use_fallback: bool = True
    ) -> T:
        """Execute the agent with structured output."""
        model = model or self.primary_model
        prompt = self._get_prompt(prompt_name)
        
        try:
            start_time = time.time()
            # Format the prompt template with the provided arguments
            formatted_prompt = prompt.format(**prompt_args)
            response = await self.llm_service.generate_structured(
                prompt=formatted_prompt,
                response_model=self.response_model,
                model=model,
                temperature=temperature
            )
            
            if self.collect_stats:
                self.stats.record_success(
                    model=model,
                    latency_ms=int((time.time() - start_time) * 1000),
                    prompt_name=prompt_name
                )
            
            return response
            
        except Exception as e:
            if self.collect_stats:
                self.stats.record_error(model=model, error=str(e), prompt_name=prompt_name)
            
            # Try fallback model if available and enabled
            if use_fallback and self.fallback_model and model != self.fallback_model:
                return await self.execute(
                    prompt_name=prompt_name,
                    prompt_args=prompt_args,
                    model=self.fallback_model,
                    temperature=temperature,
                    use_fallback=False  # Prevent cascading fallbacks
                )
            raise
    
    def _get_prompt(self, prompt_name: str) -> str:
        """Get or create a prompt template by name."""
        if prompt_name not in self._prompts:
            # For now, use simple templates. Mirascope integration will be added later
            self._prompts[prompt_name] = self._get_default_prompt(prompt_name)
        return self._prompts[prompt_name]
    
    def _get_default_prompt(self, prompt_name: str) -> str:
        """Get default prompt template for the given prompt name."""
        # Simple template system for now
        templates = {
            "generate_text": "Generate text based on the following input: {input}",
            "analyze_content": "Analyze the following content: {content}\nCriteria: {criteria}",
            "generate_code": "Generate {language} code for: {description}",
            "legacy": "{input}",
            "legacy_analyze": "Analyze: {content}"
        }
        return templates.get(prompt_name, "{input}")
    
    def get_stats_summary(self) -> Dict[str, Any]:
        """Get a summary of agent statistics."""
        return self.stats.get_summary()
    
    def reset_stats(self):
        """Reset agent statistics."""
        self.stats.reset()
