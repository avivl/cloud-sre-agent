# gemini_sre_agent/llm/service_implementations.py

"""
Concrete service implementations for enhanced LLM service.

This module contains the concrete implementations of the enhanced LLM service
with intelligent model selection capabilities.

Classes:
    EnhancedLLMService: Main enhanced LLM service implementation
    StructuredResponseGenerator: Handles structured response generation
    TextResponseGenerator: Handles text response generation
    FallbackResponseGenerator: Handles fallback response generation

Author: Gemini SRE Agent
Created: 2024
"""

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Type, Union

try:
    from mirascope.llm import Provider
except ImportError:
    # Provider class not available in current mirascope version
    Provider = None  # type: ignore


from .base import LLMRequest
from .common.enums import ProviderType
from .model_registry import ModelInfo, ModelRegistry
from .model_scorer import ModelScorer, ScoringContext
from .model_selector import (
    ModelSelector,
    SelectionCriteria,
    SelectionResult,
)
from .performance_cache import PerformanceMonitor
from .service_base import (
    ServiceContext,
    T,
)

logger = logging.getLogger(__name__)


class StructuredResponseGenerator:
    """Handles structured response generation with intelligent model selection."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        model_selector: ModelSelector,
        model_scorer: ModelScorer,
        performance_monitor: PerformanceMonitor,
        providers: Dict[str, Any],
    ):
        """Initialize the structured response generator.

        Args:
            model_registry: Model registry instance
            model_selector: Model selector instance
            model_scorer: Model scorer instance
            performance_monitor: Performance monitor instance
            providers: Dictionary of available providers
        """
        self.model_registry = model_registry
        self.model_selector = model_selector
        self.model_scorer = model_scorer
        self.performance_monitor = performance_monitor
        self.providers = providers
        self.logger = logging.getLogger(__name__)

    async def generate(
        self,
        prompt: Union[str, Any],
        response_model: Type[T],
        context: ServiceContext,
        **kwargs: Any,
    ) -> T:
        """Generate a structured response.

        Args:
            prompt: Input prompt
            response_model: Pydantic model for structured response
            context: Service context
            **kwargs: Additional arguments

        Returns:
            Structured response of type T
        """
        start_time = time.time()
        selected_model = None

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                context=context,
                required_capabilities=[],  # Could be enhanced to detect from response_model
            )

            # Get the provider for the selected model
            provider_name = selected_model.provider.value
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available for model '{selected_model.name}'"
                )

            provider_instance = self.providers[provider_name]

            self.logger.info(
                f"Generating structured response using model: {selected_model.name} via provider: {provider_name}"
            )

            # Generate the response using regular generate method
            # Convert prompt to LLMRequest format with structured output instruction
            if isinstance(prompt, str):
                structured_prompt = self._create_structured_prompt(
                    prompt, response_model
                )
                request = LLMRequest(
                    prompt=structured_prompt,
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 1000),
                    model_type=context.model_type,
                )
            else:
                # Assume it's already a structured prompt
                request = prompt

            response = await provider_instance.generate(request)

            # Parse the response into the structured format
            result = self._parse_structured_response(response.content, response_model)

            # Record performance metrics
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            self.performance_monitor.record_latency(
                model_name=selected_model.name,
                latency_ms=latency_ms,
                provider=selected_model.provider,
                context={
                    "task_type": "structured_generation",
                    "model_type": (
                        context.model_type.value if context.model_type else "unknown"
                    ),
                    "selection_strategy": context.selection_strategy.value,
                    "response_model": response_model.__name__,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "structured_generation"},
            )

            return result

        except Exception as e:
            # Record failure metrics if we have a selected model
            try:
                if "selected_model" in locals() and selected_model is not None:
                    self.performance_monitor.record_success(
                        model_name=selected_model.name,
                        success=False,
                        provider=selected_model.provider,
                        context={
                            "task_type": "structured_generation",
                            "error": str(e),
                        },
                    )
            except Exception as metrics_error:
                self.logger.warning(f"Failed to record metrics: {metrics_error}")

            self.logger.error(f"Error generating structured response: {str(e)}")
            raise

    def _create_structured_prompt(self, prompt: str, response_model: Type[T]) -> str:
        """Create a structured prompt based on the response model.

        Args:
            prompt: Original prompt
            response_model: Pydantic model for structured response

        Returns:
            Structured prompt string
        """
        if response_model.__name__ == "TriageResponse":
            return f"""Please triage the following issue and provide a structured JSON response:

{prompt}

Please respond with a valid JSON object that includes all required fields for triage. The response should be in this format:
{{
    "severity": "low|medium|high|critical",
    "category": "Issue category (e.g., error, warning, performance)",
    "urgency": "low|medium|high|critical",
    "description": "Brief description of the issue",
    "suggested_actions": ["action1", "action2", "action3"]
}}

Respond only with the JSON object, no additional text."""
        elif response_model.__name__ == "RemediationResponse":
            return f"""Please provide a detailed remediation plan for the following problem and respond with a structured JSON:

{prompt}

Please respond with a valid JSON object that includes all required fields for remediation. The response should be in this format:
{{
    "root_cause_analysis": "Detailed analysis of what caused the issue",
    "proposed_fix": "Description of the proposed solution",
    "code_patch": "Actual code changes needed (in Git patch format if applicable)",
    "priority": "low|medium|high|critical",
    "estimated_effort": "Estimated time/effort required (e.g., '2 hours', '1 day', 'immediate')"
}}

Focus on providing actionable, specific solutions with actual code when applicable. Respond only with the JSON object, no additional text."""
        else:
            return f"""Please analyze the following and provide a structured JSON response:

{prompt}

Please respond with a valid JSON object that includes all required fields for the analysis. The response should be in this format:
{{
    "summary": "Brief summary of the analysis",
    "scores": {{"criterion1": 0.8, "criterion2": 0.6}},
    "key_points": ["point1", "point2", "point3"],
    "recommendations": ["recommendation1", "recommendation2"]
}}

Respond only with the JSON object, no additional text."""

    def _parse_structured_response(self, content: str, response_model: Type[T]) -> T:
        """Parse structured response from content.

        Args:
            content: Response content
            response_model: Pydantic model for structured response

        Returns:
            Parsed structured response
        """
        try:
            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                return response_model(**parsed_data)
            else:
                # Fallback: create a basic response with the raw content
                return self._create_fallback_response(content, response_model)
        except (json.JSONDecodeError, ValueError):
            # Fallback: create a basic response with the raw content
            return self._create_fallback_response(content, response_model)

    def _create_fallback_response(self, content: str, response_model: Type[T]) -> T:
        """Create a fallback response when JSON parsing fails.

        Args:
            content: Response content
            response_model: Pydantic model for structured response

        Returns:
            Fallback structured response
        """
        if response_model.__name__ == "TriageResponse":
            return response_model(
                severity="medium",
                category="unknown",
                urgency="medium",
                description=(content[:200] + "..." if len(content) > 200 else content),
                suggested_actions=["Investigate further"],
            )
        elif response_model.__name__ == "RemediationResponse":
            return response_model(
                root_cause_analysis=(
                    content[:200] + "..." if len(content) > 200 else content
                ),
                proposed_fix="Manual review required",
                code_patch="# TODO: Generate proper code patch\n# " + content[:100],
                priority="medium",
                estimated_effort="Unknown",
            )
        else:
            return response_model(
                summary=(content[:200] + "..." if len(content) > 200 else content),
                scores={"confidence": 0.5},
                key_points=[content[:100] + "..." if len(content) > 100 else content],
                recommendations=[],
            )

    async def _select_model_for_task(
        self,
        context: ServiceContext,
        required_capabilities: Optional[List] = None,
    ) -> tuple[ModelInfo, SelectionResult]:
        """Select the best model for a task based on criteria.

        Args:
            context: Service context
            required_capabilities: List of required capabilities

        Returns:
            Tuple of (selected_model, selection_result)
        """
        # If specific model is requested, try to find it in registry
        if context.model:
            model_info = self.model_registry.get_model(context.model)
            if model_info:
                # Create a simple selection result
                scoring_context = ScoringContext(
                    task_type=context.model_type,
                    required_capabilities=required_capabilities or [],
                    max_cost=context.max_cost,
                    min_performance=context.min_performance,
                    min_reliability=context.min_reliability,
                )
                score = self.model_scorer.score_model(model_info, scoring_context)

                selection_result = SelectionResult(
                    selected_model=model_info,
                    score=score,
                    fallback_chain=[model_info],
                    selection_reason=f"Explicitly requested model: {context.model}",
                    criteria=SelectionCriteria(
                        semantic_type=context.model_type,
                        strategy=context.selection_strategy,
                        custom_weights=context.custom_weights,
                        max_cost=context.max_cost,
                        min_performance=context.min_performance,
                        min_reliability=context.min_reliability,
                    ),
                )
                return model_info, selection_result

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=context.model_type,
            required_capabilities=required_capabilities or [],
            max_cost=context.max_cost,
            min_performance=context.min_performance,
            min_reliability=context.min_reliability,
            provider_preference=(
                ProviderType(context.provider) if context.provider else None
            ),
            strategy=context.selection_strategy,
            custom_weights=context.custom_weights,
            allow_fallback=True,
        )

        # Select model with fallback support
        selected_model, selection_result = (
            self.model_selector.select_model_with_fallback(criteria)
        )

        return selected_model, selection_result


class TextResponseGenerator:
    """Handles text response generation with intelligent model selection."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        model_selector: ModelSelector,
        model_scorer: ModelScorer,
        performance_monitor: PerformanceMonitor,
        providers: Dict[str, Any],
    ):
        """Initialize the text response generator.

        Args:
            model_registry: Model registry instance
            model_selector: Model selector instance
            model_scorer: Model scorer instance
            performance_monitor: Performance monitor instance
            providers: Dictionary of available providers
        """
        self.model_registry = model_registry
        self.model_selector = model_selector
        self.model_scorer = model_scorer
        self.performance_monitor = performance_monitor
        self.providers = providers
        self.logger = logging.getLogger(__name__)

    async def generate(
        self,
        prompt: Union[str, Any],
        context: ServiceContext,
        **kwargs: Any,
    ) -> str:
        """Generate a text response.

        Args:
            prompt: Input prompt
            context: Service context
            **kwargs: Additional arguments

        Returns:
            Text response
        """
        start_time = time.time()

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                context=context,
                required_capabilities=[],
            )

            # Get the provider for the selected model
            provider_name = selected_model.provider.value
            if provider_name not in self.providers:
                raise ValueError(
                    f"Provider '{provider_name}' not available for model '{selected_model.name}'"
                )

            provider_instance = self.providers[provider_name]

            self.logger.info(
                f"Generating text response using model: {selected_model.name} via provider: {provider_name}"
            )

            # Generate the response using the correct interface
            request = LLMRequest(
                prompt=prompt, model_type=selected_model.semantic_type, **kwargs
            )
            response = await provider_instance.generate(request)
            result = response.content

            # Record performance metrics
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            self.performance_monitor.record_latency(
                model_name=selected_model.name,
                latency_ms=latency_ms,
                provider=selected_model.provider,
                context={
                    "task_type": "text_generation",
                    "model_type": (
                        context.model_type.value if context.model_type else "unknown"
                    ),
                    "selection_strategy": context.selection_strategy.value,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "text_generation"},
            )

            return result

        except Exception as e:
            # Record failure metrics if we have a selected model
            try:
                if "selected_model" in locals():
                    selected_model = locals().get("selected_model")
                    if selected_model:
                        self.performance_monitor.record_success(
                            model_name=selected_model.name,
                            success=False,
                            provider=selected_model.provider,
                            context={"task_type": "text_generation", "error": str(e)},
                        )
            except Exception as metrics_error:
                self.logger.warning(f"Failed to record metrics: {metrics_error}")

            self.logger.error(f"Error generating text response: {str(e)}")
            raise

    async def _select_model_for_task(
        self,
        context: ServiceContext,
        required_capabilities: Optional[List] = None,
    ) -> tuple[ModelInfo, SelectionResult]:
        """Select the best model for a task based on criteria.

        Args:
            context: Service context
            required_capabilities: List of required capabilities

        Returns:
            Tuple of (selected_model, selection_result)
        """
        # If specific model is requested, try to find it in registry
        if context.model:
            model_info = self.model_registry.get_model(context.model)
            if model_info:
                # Create a simple selection result
                scoring_context = ScoringContext(
                    task_type=context.model_type,
                    required_capabilities=required_capabilities or [],
                    max_cost=context.max_cost,
                    min_performance=context.min_performance,
                    min_reliability=context.min_reliability,
                )
                score = self.model_scorer.score_model(model_info, scoring_context)

                selection_result = SelectionResult(
                    selected_model=model_info,
                    score=score,
                    fallback_chain=[model_info],
                    selection_reason=f"Explicitly requested model: {context.model}",
                    criteria=SelectionCriteria(
                        semantic_type=context.model_type,
                        strategy=context.selection_strategy,
                        custom_weights=context.custom_weights,
                        max_cost=context.max_cost,
                        min_performance=context.min_performance,
                        min_reliability=context.min_reliability,
                    ),
                )
                return model_info, selection_result

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=context.model_type,
            required_capabilities=required_capabilities or [],
            max_cost=context.max_cost,
            min_performance=context.min_performance,
            min_reliability=context.min_reliability,
            provider_preference=(
                ProviderType(context.provider) if context.provider else None
            ),
            strategy=context.selection_strategy,
            custom_weights=context.custom_weights,
            allow_fallback=True,
        )

        # Select model with fallback support
        selected_model, selection_result = (
            self.model_selector.select_model_with_fallback(criteria)
        )

        return selected_model, selection_result


class FallbackResponseGenerator:
    """Handles fallback response generation with automatic fallback chain execution."""

    def __init__(
        self,
        model_registry: ModelRegistry,
        model_selector: ModelSelector,
        model_scorer: ModelScorer,
        performance_monitor: PerformanceMonitor,
        providers: Dict[str, Any],
    ):
        """Initialize the fallback response generator.

        Args:
            model_registry: Model registry instance
            model_selector: Model selector instance
            model_scorer: Model scorer instance
            performance_monitor: Performance monitor instance
            providers: Dictionary of available providers
        """
        self.model_registry = model_registry
        self.model_selector = model_selector
        self.model_scorer = model_scorer
        self.performance_monitor = performance_monitor
        self.providers = providers
        self.logger = logging.getLogger(__name__)

    async def generate(
        self,
        prompt: Union[str, Any],
        context: ServiceContext,
        response_model: Optional[Type[T]] = None,
        **kwargs: Any,
    ) -> Union[str, T]:
        """Generate response with automatic fallback chain execution.

        Args:
            prompt: Input prompt
            response_model: Optional Pydantic model for structured response
            context: Service context
            **kwargs: Additional arguments

        Returns:
            Response (text or structured)
        """
        last_error = None

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=context.model_type,
            strategy=context.selection_strategy,
            allow_fallback=True,
            max_models_to_consider=10,
        )

        # Get selection result with fallback chain
        selection_result = self.model_selector.select_model(criteria)

        # Try each model in the fallback chain
        for i, model_info in enumerate(selection_result.fallback_chain):
            if i >= context.max_attempts:
                break

            try:
                self.logger.info(
                    f"Attempting model: {model_info.name} (attempt {i+1}/{context.max_attempts})"
                )

                # Get the provider for this model
                provider_name = model_info.provider.value
                if provider_name not in self.providers:
                    self.logger.warning(
                        f"Provider '{provider_name}' not available for model '{model_info.name}'"
                    )
                    continue

                provider_instance = self.providers[provider_name]

                # Generate response using the correct interface
                request = LLMRequest(
                    prompt=prompt, model_type=model_info.semantic_type, **kwargs
                )
                response = await provider_instance.generate(request)
                result = response.content

                # If structured response is requested, parse it
                if response_model:
                    result = self._parse_structured_response(result, response_model)

                # Record success
                self.performance_monitor.record_success(
                    model_name=model_info.name,
                    success=True,
                    provider=model_info.provider,
                    context={"task_type": "fallback_generation", "attempt": i + 1},
                )

                self.logger.info(
                    f"Successfully generated response using model: {model_info.name}"
                )
                return result

            except Exception as e:
                last_error = e
                self.logger.warning(f"Model {model_info.name} failed: {str(e)}")

                # Record failure
                self.performance_monitor.record_success(
                    model_name=model_info.name,
                    success=False,
                    provider=model_info.provider,
                    context={
                        "task_type": "fallback_generation",
                        "attempt": i + 1,
                        "error": str(e),
                    },
                )

                continue

        # All models failed
        self.logger.error(
            f"All {context.max_attempts} models in fallback chain failed. Last error: {str(last_error)}"
        )
        raise last_error or Exception("All models in fallback chain failed")

    def _parse_structured_response(self, content: str, response_model: Type[T]) -> T:
        """Parse structured response from content.

        Args:
            content: Response content
            response_model: Pydantic model for structured response

        Returns:
            Parsed structured response
        """
        try:
            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                json_str = json_match.group()
                parsed_data = json.loads(json_str)
                return response_model(**parsed_data)
            else:
                # Fallback: create a basic response with the raw content
                return self._create_fallback_response(content, response_model)
        except (json.JSONDecodeError, ValueError):
            # Fallback: create a basic response with the raw content
            return self._create_fallback_response(content, response_model)

    def _create_fallback_response(self, content: str, response_model: Type[T]) -> T:
        """Create a fallback response when JSON parsing fails.

        Args:
            content: Response content
            response_model: Pydantic model for structured response

        Returns:
            Fallback structured response
        """
        if response_model.__name__ == "TriageResponse":
            return response_model(
                severity="medium",
                category="unknown",
                urgency="medium",
                description=(content[:200] + "..." if len(content) > 200 else content),
                suggested_actions=["Investigate further"],
            )
        elif response_model.__name__ == "RemediationResponse":
            return response_model(
                root_cause_analysis=(
                    content[:200] + "..." if len(content) > 200 else content
                ),
                proposed_fix="Manual review required",
                code_patch="# TODO: Generate proper code patch\n# " + content[:100],
                priority="medium",
                estimated_effort="Unknown",
            )
        else:
            return response_model(
                summary=(content[:200] + "..." if len(content) > 200 else content),
                scores={"confidence": 0.5},
                key_points=[content[:100] + "..." if len(content) > 100 else content],
                recommendations=[],
            )
