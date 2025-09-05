# gemini_sre_agent/llm/prompt_service.py

"""
LLM Prompt Service Integration.

This module provides integration between the prompt management system
and the existing LLM service for executing managed prompts.
"""

from datetime import datetime
from typing import Any, Dict, Optional, Type, TypeVar

from pydantic import BaseModel

from .mirascope_integration import PromptEnvironment, PromptManager

T = TypeVar("T", bound=BaseModel)


class LLMPromptService:
    """Service for executing managed prompts with full tracking and metrics."""

    def __init__(
        self,
        llm_service,
        prompt_manager: PromptManager,
        environment: Optional[PromptEnvironment] = None,
    ):
        """Initialize the LLM prompt service."""
        self.llm_service = llm_service
        self.prompt_manager = prompt_manager
        self.environment = environment
        self.last_token_count = 0
        self.last_model_used = None

    async def execute_prompt(
        self,
        prompt_id: str,
        inputs: Dict[str, Any],
        response_model: Type[T],
        record_metrics: bool = True,
    ) -> T:
        """Execute a prompt and parse the response with structured output."""
        start_time = datetime.now()

        try:
            # Get the appropriate prompt version based on environment
            if self.environment:
                prompt = self.environment.get_prompt(prompt_id)
            else:
                prompt = self.prompt_manager.get_prompt(prompt_id)

            # Format the prompt with inputs
            if hasattr(prompt, "format"):
                formatted_prompt = prompt.format(**inputs)
            else:
                # Fallback for string templates
                formatted_prompt = (
                    prompt.format(**inputs) if isinstance(prompt, str) else str(prompt)
                )

            # Execute the prompt using the LLM service
            if hasattr(self.llm_service, "generate_structured_output"):
                response = await self.llm_service.generate_structured_output(
                    formatted_prompt, response_model
                )
            elif hasattr(self.llm_service, "generate"):
                # Fallback to regular generate method
                response_text = await self.llm_service.generate(formatted_prompt)
                # Try to parse as the response model
                if isinstance(response_text, str):
                    try:
                        response = response_model.parse_raw(response_text)
                    except Exception:
                        # Create a basic response if parsing fails
                        response = response_model(**{"text": response_text})
                else:
                    response = response_text
            else:
                raise ValueError(
                    "LLM service does not support structured output generation"
                )

            # Record metrics if enabled
            if record_metrics:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                metrics = {
                    "duration_seconds": duration,
                    "token_count": getattr(self.llm_service, "last_token_count", 0),
                    "model_used": getattr(
                        self.llm_service, "last_model_used", "unknown"
                    ),
                    "success": True,
                }

                self.prompt_manager.record_metrics(prompt_id, metrics)
                self.last_token_count = metrics["token_count"]
                self.last_model_used = metrics["model_used"]

            return response

        except Exception as e:
            # Record failure metrics
            if record_metrics:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                metrics = {
                    "duration_seconds": duration,
                    "token_count": 0,
                    "model_used": getattr(
                        self.llm_service, "last_model_used", "unknown"
                    ),
                    "success": False,
                    "error": str(e),
                }

                self.prompt_manager.record_metrics(prompt_id, metrics)

            raise

    async def execute_prompt_text(
        self, prompt_id: str, inputs: Dict[str, Any], record_metrics: bool = True
    ) -> str:
        """Execute a prompt and return raw text response."""
        start_time = datetime.now()

        try:
            # Get the appropriate prompt version based on environment
            if self.environment:
                prompt = self.environment.get_prompt(prompt_id)
            else:
                prompt = self.prompt_manager.get_prompt(prompt_id)

            # Format the prompt with inputs
            if hasattr(prompt, "format"):
                formatted_prompt = prompt.format(**inputs)
            else:
                # Fallback for string templates
                formatted_prompt = (
                    prompt.format(**inputs) if isinstance(prompt, str) else str(prompt)
                )

            # Execute the prompt using the LLM service
            if hasattr(self.llm_service, "generate_text"):
                response = await self.llm_service.generate_text(formatted_prompt)
            elif hasattr(self.llm_service, "generate"):
                response = await self.llm_service.generate(formatted_prompt)
            else:
                raise ValueError("LLM service does not support text generation")

            # Record metrics if enabled
            if record_metrics:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                metrics = {
                    "duration_seconds": duration,
                    "token_count": getattr(self.llm_service, "last_token_count", 0),
                    "model_used": getattr(
                        self.llm_service, "last_model_used", "unknown"
                    ),
                    "success": True,
                }

                self.prompt_manager.record_metrics(prompt_id, metrics)
                self.last_token_count = metrics["token_count"]
                self.last_model_used = metrics["model_used"]

            return response

        except Exception as e:
            # Record failure metrics
            if record_metrics:
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()

                metrics = {
                    "duration_seconds": duration,
                    "token_count": 0,
                    "model_used": getattr(
                        self.llm_service, "last_model_used", "unknown"
                    ),
                    "success": False,
                    "error": str(e),
                }

                self.prompt_manager.record_metrics(prompt_id, metrics)

            raise


class MirascopeIntegratedLLMService:
    """Integrated LLM service with Mirascope prompt management."""

    def __init__(self, llm_service, prompt_manager: PromptManager):
        """Initialize the integrated LLM service."""
        self.llm_service = llm_service
        self.prompt_manager = prompt_manager
        self.prompt_service = LLMPromptService(llm_service, prompt_manager)

    async def execute_managed_prompt(
        self, prompt_id: str, inputs: Dict[str, Any], response_model: Type[BaseModel]
    ) -> BaseModel:
        """Execute a managed prompt with full tracking and metrics."""
        return await self.prompt_service.execute_prompt(
            prompt_id, inputs, response_model
        )

    def create_environment(self, name: str) -> PromptEnvironment:
        """Create a new environment for prompt deployment."""
        return PromptEnvironment(name, self.prompt_manager)

    def get_prompt_manager(self) -> PromptManager:
        """Get the prompt manager instance."""
        return self.prompt_manager

    def get_prompt_service(self) -> LLMPromptService:
        """Get the prompt service instance."""
        return self.prompt_service
