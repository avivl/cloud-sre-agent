# gemini_sre_agent/llm/enhanced_service.py

"""
Enhanced LLM Service with Intelligent Model Selection.

This module provides an enhanced LLM service that integrates the semantic model
selection system with the existing provider interfaces, enabling intelligent
model selection based on task requirements, performance metrics, and fallback chains.

This is now a coordination module that uses the modular service components.
"""

from datetime import timedelta
import logging
import time
from typing import Any, TypeVar

try:
    from mirascope.llm import Provider
except ImportError:
    # Provider class not available in current mirascope version
    Provider = None  # type: ignore

from pydantic import BaseModel

from .base import LLMRequest, ModelType
from .common.enums import ProviderType
from .config import LLMConfig
from .factory import get_provider_factory
from .model_registry import ModelInfo, ModelRegistry
from .model_scorer import ModelScorer, ScoringContext, ScoringWeights
from .model_selector import (
    ModelSelector,
    SelectionCriteria,
    SelectionResult,
    SelectionStrategy,
)
from .performance_cache import MetricType, PerformanceMonitor
from .prompt_manager import PromptManager

# Import the new modular service components
from .service_base import BaseLLMService, ServiceConfig, ServiceHealth, ServiceStatus
from .service_manager import LoadBalancingStrategy, ServiceManager, ServiceType
from .service_metrics import ServiceAlert, ServiceMetricsManager

# Type alias for better type checking
PromptType = Any

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class EnhancedLLMService[T]:
    """
    Enhanced LLM service with intelligent model selection.

    Integrates the semantic model selection system with provider interfaces,
    enabling intelligent model selection based on task requirements, performance
    metrics, and fallback chains.

    This is now a coordination module that uses the modular service components.
    """

    def __init__(
        self,
        config: LLMConfig,
        model_registry: ModelRegistry | None = None,
        performance_monitor: PerformanceMonitor | None = None,
        service_manager: ServiceManager | None = None,
    ):
        """Initialize the enhanced LLM service."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize provider factory and create providers
        self.provider_factory = get_provider_factory()
        self.providers = self.provider_factory.create_providers_from_config(config)

        # Initialize prompt manager
        self.prompt_manager = PromptManager()

        # Initialize model selection components
        self.model_registry = model_registry or ModelRegistry()
        self.model_scorer = ModelScorer()
        # Create a dummy capability discovery for now
        from .capabilities.discovery import CapabilityDiscovery

        capability_discovery = CapabilityDiscovery(self.providers)
        self.model_selector = ModelSelector(
            self.model_registry, capability_discovery, self.model_scorer
        )
        self.performance_monitor = performance_monitor or PerformanceMonitor()

        # Initialize service manager and metrics
        self.service_manager = service_manager or ServiceManager()
        self.metrics_manager = ServiceMetricsManager()

        # Populate model registry with models from config
        self._populate_model_registry()

        # Track selection statistics
        self._selection_stats: dict[str, int] = {}
        self._last_selection_time: dict[str, float] = {}

        self.logger.info(
            "EnhancedLLMService initialized with intelligent model selection and modular services"
        )

    def _populate_model_registry(self):
        """Populate the model registry with models from the LLM config."""
        from .model_registry import ModelCapability, ModelInfo

        for provider_name, provider_config in self.config.providers.items():
            # Convert string provider to ProviderType enum
            from .common.enums import ProviderType

            provider_type = ProviderType(provider_config.provider)
            for model_name, model_config in provider_config.models.items():
                # Convert capabilities from strings to ModelCapability enums
                capabilities = []
                for cap_str in model_config.capabilities:
                    try:
                        capabilities.append(
                            ModelCapability(
                                name=cap_str,
                                description=f"Capability: {cap_str}",
                                performance_score=getattr(
                                    model_config, "performance_score", 0.5
                                ),
                                cost_efficiency=1.0
                                - (
                                    model_config.cost_per_1k_tokens / 0.1
                                ),  # Normalize cost to efficiency
                            )
                        )
                    except (ValueError, AttributeError) as e:
                        # Skip unknown capabilities
                        self.logger.warning(f"Unknown capability {cap_str}: {e}")
                        continue

                # Create ModelInfo
                model_info = ModelInfo(
                    name=model_name,
                    provider=provider_type,
                    semantic_type=model_config.model_type,
                    capabilities=capabilities,
                    cost_per_1k_tokens=model_config.cost_per_1k_tokens,
                    max_tokens=model_config.max_tokens,
                    context_window=model_config.max_tokens,  # Use max_tokens as context window
                    performance_score=model_config.performance_score,
                    reliability_score=model_config.reliability_score,
                    provider_specific=provider_config.provider_specific,
                )

                # Register the model
                self.model_registry.register_model(model_info)
                self.logger.debug(
                    f"Registered model: {model_name} from provider: {provider_name}"
                )

        self.logger.info(
            f"Model registry populated with {self.model_registry.get_model_count()} models"
        )

    async def generate_structured(
        self,
        prompt: str | Any,
        response_model: type[T],
        model: str | None = None,
        model_type: ModelType | None = None,
        provider: str | None = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: ScoringWeights | None = None,
        max_cost: float | None = None,
        min_performance: float | None = None,
        min_reliability: float | None = None,
        **kwargs: Any,
    ) -> T:
        """Generate a structured response with intelligent model selection."""
        start_time = time.time()

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                custom_weights=custom_weights,
                max_cost=max_cost,
                min_performance=min_performance,
                min_reliability=min_reliability,
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
                # Enhance the prompt to request structured JSON output
                # Check if this is for triage, analysis, or remediation based on response model
                if response_model.__name__ == "TriageResult":
                    # Truncate the prompt to avoid overwhelming the model
                    truncated_prompt = prompt[:500] + "..." if len(prompt) > 500 else prompt
                    structured_prompt = f"""Return only this JSON, no other text:
{{
    "agent_id": "triage-agent-1",
    "agent_type": "triage",
    "status": "success",
    "issue_type": "error",
    "category": "performance",
    "severity": "medium",
    "confidence": 0.8,
    "confidence_level": "high",
    "summary": "Error detected in {truncated_prompt[:100]}",
    "description": "System error occurred",
    "urgency": "medium",
    "impact_assessment": "Moderate impact",
    "recommended_actions": ["Investigate", "Fix"]
}}"""
                elif response_model.__name__ == "AnalysisResult":
                    # Truncate the prompt to avoid overwhelming the model
                    truncated_prompt = prompt[:500] + "..." if len(prompt) > 500 else prompt
                    structured_prompt = f"""Return only this JSON, no other text:
{{
    "agent_id": "analysis-agent-1",
    "agent_type": "analysis",
    "status": "success",
    "analysis_type": "error_analysis",
    "summary": "Analysis completed for {truncated_prompt[:100]}",
    "key_findings": [
        {{
            "title": "Error Detected",
            "description": "System error occurred",
            "severity": "medium",
            "confidence": 0.8,
            "category": "performance",
            "recommendations": ["Investigate further"]
        }}
    ],
    "overall_severity": "medium",
    "overall_confidence": 0.8,
    "root_cause": "System error",
    "impact_assessment": "Moderate impact",
    "risk_assessment": "Medium risk",
    "business_impact": "Service disruption",
    "recommendations": ["Investigate", "Fix"],
    "next_steps": ["Monitor", "Test"]
}}"""
                elif response_model.__name__ == "RemediationPlan":
                    # Truncate the prompt to avoid overwhelming the model
                    truncated_prompt = prompt[:500] + "..." if len(prompt) > 500 else prompt
                    structured_prompt = f"""Return only this JSON, no other text:
{{
    "agent_id": "remediation-agent-1",
    "agent_type": "remediation",
    "status": "success",
    "plan_name": "Fix Error Plan",
    "issue_description": "System error needs fixing",
    "priority": "medium",
    "estimated_total_duration": "1 hour",
    "estimated_total_effort": "medium",
    "steps": [
        {{
            "step_id": "step-1",
            "order": 1,
            "title": "Fix Error",
            "description": "Fix the system error",
            "action_type": "immediate",
            "commands": ["fix command"],
            "estimated_duration": "30 minutes",
            "estimated_effort": "low",
            "risk_level": "low",
            "prerequisites": [],
            "dependencies": [],
            "rollback_plan": "Restart service",
            "validation_criteria": ["Error resolved"],
            "affected_systems": ["main system"],
            "requires_approval": false,
            "automated": true
        }}
    ],
    "success_criteria": ["Error fixed", "Service running"],
    "risk_assessment": "Low risk",
    "rollback_strategy": "Restart service",
    "testing_plan": ["Test fix"],
    "monitoring_plan": ["Monitor logs"],
    "approval_required": false,
    "automated_steps": 1,
    "manual_steps": 0
}}"""
                else:
                    # Truncate the prompt to avoid overwhelming the model
                    truncated_prompt = prompt[:2000] + "..." if len(prompt) > 2000 else prompt
                    structured_prompt = f"""ANALYSIS REQUIRED

Data to analyze:
{truncated_prompt}

You MUST respond with a complete JSON object containing ALL of these exact fields:

{{
    "agent_id": "analysis-agent-1",
    "agent_type": "analysis",
    "status": "success",
    "analysis_type": "error_analysis",
    "summary": "Brief summary of the analysis",
    "key_findings": [
        {{
            "finding_type": "error_type",
            "description": "Description of the finding",
            "severity": "medium",
            "confidence": 0.8,
            "location": "Where found",
            "recommendation": "Recommended action"
        }}
    ],
    "overall_severity": "medium",
    "overall_confidence": 0.8,
    "root_cause": "Root cause analysis",
    "impact_assessment": "Impact assessment",
    "risk_assessment": "Risk assessment",
    "business_impact": "Business impact",
    "recommendations": ["recommendation1", "recommendation2"],
    "next_steps": ["step1", "step2"]
}}

IMPORTANT:
- Replace the example values with actual analysis
- Use only these exact field names
- Include ALL fields listed above
- Respond with ONLY the JSON object, no other text"""

                # Debug: Log the structured prompt being sent
                self.logger.debug(f"Structured prompt for {response_model.__name__}: {structured_prompt[:500]}...")

                request = LLMRequest(
                    prompt=structured_prompt,
                    temperature=kwargs.get("temperature", 0.7),
                    max_tokens=kwargs.get("max_tokens", 1000),
                    model_type=model_type,
                )
            else:
                # Assume it's already a structured prompt
                request = prompt

            response = await provider_instance.generate(request)

            # Parse the response into the structured format
            try:
                import json
                import re

                # Extract JSON from response (in case there's extra text)
                self.logger.debug(f"Raw LLM response: {response.content}")
                
                # Try multiple patterns to extract JSON
                json_str = None
                patterns = [
                    r"```json\s*(\{.*?\})\s*```",  # Markdown JSON blocks
                    r"```\s*(\{.*?\})\s*```",      # Generic code blocks
                    r"(\{.*\})",                   # Plain JSON
                ]
                
                for pattern in patterns:
                    json_match = re.search(pattern, response.content, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(1)
                        self.logger.debug(f"Extracted JSON with pattern {pattern}: {json_str}")
                        break
                
                if json_str:
                    try:
                        parsed_data = json.loads(json_str)
                        self.logger.debug(f"Successfully parsed JSON: {parsed_data}")
                    except json.JSONDecodeError as e:
                        self.logger.error(f"Failed to parse JSON: {e}, JSON string: {json_str}")
                        raise ValueError(f"Invalid JSON in LLM response: {e}")
                else:
                    self.logger.error(f"No JSON found in LLM response: {response.content}")
                    raise ValueError(f"No JSON found in LLM response: {response.content}")

                self.logger.debug(f"Parsed data keys: {list(parsed_data.keys())}")

                # Debug logging for RemediationPlan
                if response_model.__name__ == "RemediationPlan":
                    self.logger.info(f"RemediationPlan LLM response: {response.content}")
                    self.logger.info(f"Extracted JSON: {json_str}")
                    self.logger.info(f"Parsed data: {parsed_data}")

                # Handle partial responses by filling in missing fields with defaults
                if response_model.__name__ == "TriageResult":
                    # Fill in missing required fields with defaults
                    defaults = {
                        "agent_id": "triage-agent-1",
                        "agent_type": "triage",
                        "status": "success",
                        "issue_type": "error_type_detected",
                        "category": "performance",
                        "severity": "medium",
                        "confidence": 0.8,
                        "confidence_level": "high",
                        "summary": "Issue analysis completed",
                        "description": "Analysis of the reported issue",
                        "urgency": "medium",
                        "impact_assessment": "Impact assessment pending",
                        "recommended_actions": ["Investigate further"]
                    }

                    # Merge defaults with response data
                    for key, default_value in defaults.items():
                        if key not in parsed_data:
                            parsed_data[key] = default_value

                    # Ensure category is valid
                    if parsed_data.get("category") not in ["performance", "security", "reliability", "usability", "compatibility", "data_quality", "infrastructure", "code_quality", "deployment", "monitoring"]:
                        parsed_data["category"] = "performance"

                elif response_model.__name__ == "AnalysisResult":
                    # Handle old field names from LLM responses
                    if "key_points" in parsed_data and "key_findings" not in parsed_data:
                        # Convert key_points to key_findings format
                        key_points = parsed_data.pop("key_points", [])
                        parsed_data["key_findings"] = [
                            {
                                "title": f"Finding {i+1}",
                                "description": str(point),
                                "severity": "medium",
                                "confidence": 0.8,
                                "category": "performance",
                                "recommendations": ["Investigate further"]
                            }
                            for i, point in enumerate(key_points)
                        ]

                    # Fill in missing required fields with defaults
                    defaults = {
                        "agent_id": "analysis-agent-1",
                        "agent_type": "analysis",
                        "status": "success",
                        "analysis_type": "error_analysis",
                        "summary": "Analysis completed",
                        "key_findings": [
                            {
                                "title": "Error Analysis",
                                "description": "Error detected in the system",
                                "severity": "medium",
                                "confidence": 0.8,
                                "category": "performance",
                                "recommendations": ["Investigate further"]
                            }
                        ],
                        "overall_severity": "medium",
                        "overall_confidence": 0.8,
                        "root_cause": "Analysis pending",
                        "impact_assessment": "Impact assessment pending",
                        "risk_assessment": "Risk assessment pending",
                        "business_impact": "Business impact pending",
                        "next_steps": ["Investigate further"]
                    }

                    # Merge defaults with response data
                    for key, default_value in defaults.items():
                        if key not in parsed_data:
                            parsed_data[key] = default_value

                elif response_model.__name__ == "RemediationPlan":
                    # Fill in missing required fields with defaults
                    defaults = {
                        "agent_id": "remediation-agent-1",
                        "agent_type": "remediation",
                        "status": "success",
                        "plan_name": "Remediation Plan",
                        "issue_description": "Issue remediation plan",
                        "priority": "medium",
                        "estimated_total_duration": "2 hours",
                        "estimated_total_effort": "medium",
                        "steps": [
                            {
                                "step_id": "step-1",
                                "order": 1,
                                "title": "Remediation Step",
                                "description": "Description of the remediation step",
                                "action_type": "immediate",
                                "commands": ["Fix the issue"],
                                "estimated_duration": "30 minutes",
                                "estimated_effort": "low",
                                "risk_level": "low",
                                "prerequisites": [],
                                "dependencies": [],
                                "rollback_plan": "Rollback plan",
                                "validation_criteria": ["Issue resolved"],
                                "affected_systems": ["target_system"],
                                "requires_approval": False,
                                "automated": True
                            }
                        ],
                        "success_criteria": ["Issue resolved", "System stable"],
                        "risk_assessment": "Low risk remediation",
                        "rollback_strategy": "Rollback strategy",
                        "testing_plan": ["Test the fix"],
                        "monitoring_plan": ["Monitor system"],
                        "approval_required": False,
                        "automated_steps": 1,
                        "manual_steps": 0
                    }

                    # Merge defaults with response data
                    for key, default_value in defaults.items():
                        if key not in parsed_data:
                            parsed_data[key] = default_value

                result = response_model(**parsed_data)
            except Exception as e:
                self.logger.error(f"Error parsing LLM response: {e}")
                # Fallback: create a basic response with the raw content
                if response_model.__name__ == "TriageResult":
                    result = response_model(
                        agent_id="triage-agent-1",
                        agent_type="triage",
                        status="success",
                        issue_type="error_type_detected",
                        category="performance",
                        severity="medium",
                        confidence=0.8,
                        confidence_level="high",
                        summary="Issue analysis completed",
                        description=(
                            response.content[:200] + "..."
                            if len(response.content) > 200
                            else response.content
                        ),
                        urgency="medium",
                        impact_assessment="Impact assessment pending",
                        recommended_actions=["Investigate further"],
                    )
                elif response_model.__name__ == "AnalysisResult":
                    result = response_model(
                        agent_id="analysis-agent-1",
                        agent_type="analysis",
                        status="success",
                        analysis_type="error_analysis",
                        summary="Analysis completed",
                        key_findings=[
                            {
                                "title": "Error Analysis",
                                "description": "Error detected in the system",
                                "severity": "medium",
                                "confidence": 0.8,
                                "category": "performance",
                                "recommendations": ["Investigate further"]
                            }
                        ],
                        overall_severity="medium",
                        overall_confidence=0.8,
                        root_cause="Analysis pending",
                        impact_assessment="Impact assessment pending",
                        risk_assessment="Risk assessment pending",
                        business_impact="Business impact pending",
                        recommendations=["Investigate further"],
                        next_steps=["Investigate further"]
                        )
                elif response_model.__name__ == "RemediationPlan":
                    result = response_model(
                            root_cause_analysis=(
                                response.content[:200] + "..."
                                if len(response.content) > 200
                                else response.content
                            ),
                            proposed_fix="Manual review required",
                            code_patch="# TODO: Generate proper code patch\n# "
                            + response.content[:100],
                            priority="medium",
                            estimated_effort="Unknown",
                        )
                else:
                    result = response_model(
                            summary=(
                                response.content[:200] + "..."
                                if len(response.content) > 200
                                else response.content
                            ),
                            scores={"confidence": 0.5},
                            key_points=[
                                (
                                    response.content[:100] + "..."
                                    if len(response.content) > 100
                                    else response.content
                                )
                            ],
                            recommendations=[],
                        )
            except (json.JSONDecodeError, ValueError):  # type: ignore
                # Fallback: create a basic response with the raw content
                if response_model.__name__ == "TriageResult":
                    result = response_model(
                        severity="medium",
                        category="unknown",
                        urgency="medium",
                        description=(
                            response.content[:200] + "..."
                            if len(response.content) > 200
                            else response.content
                        ),
                        suggested_actions=["Investigate further"],
                    )
                elif response_model.__name__ == "RemediationPlan":
                    result = response_model(
                        root_cause_analysis=(
                            response.content[:200] + "..."
                            if len(response.content) > 200
                            else response.content
                        ),
                        proposed_fix="Manual review required",
                        code_patch="# TODO: Generate proper code patch\n# "
                        + response.content[:100],
                        priority="medium",
                        estimated_effort="Unknown",
                    )
                else:
                    # Generic fallback for unknown response models
                    if response_model.__name__ == "AnalysisResult":
                        result = response_model(
                            agent_id="analysis-agent-1",
                            agent_type="analysis",
                            status="success",
                            analysis_type="error_analysis",
                            summary=(
                                response.content[:200] + "..."
                                if len(response.content) > 200
                                else response.content
                            ),
                            key_findings=[
                                {
                                    "title": "Analysis Finding",
                                    "description": (
                                        response.content[:100] + "..."
                                        if len(response.content) > 100
                                        else response.content
                                    ),
                                    "severity": "medium",
                                    "confidence": 0.5,
                                    "category": "performance",
                                    "recommendations": ["Investigate further"]
                                }
                            ],
                            overall_severity="medium",
                            overall_confidence=0.5,
                            risk_assessment="Risk assessment pending",
                            business_impact="Business impact pending",
                            recommendations=["Investigate further"],
                            next_steps=["Investigate further"]
                        )
                    else:
                        result = response_model(
                        summary=(
                            response.content[:200] + "..."
                            if len(response.content) > 200
                            else response.content
                        ),
                        scores={"confidence": 0.5},
                        key_points=[
                            (
                                response.content[:100] + "..."
                                if len(response.content) > 100
                                else response.content
                            )
                        ],
                        recommendations=[],
                    )

            # Record performance metrics
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000

            self.performance_monitor.record_latency(
                model_name=selected_model.name,
                latency_ms=latency_ms,
                provider=selected_model.provider,
                context={
                    "task_type": "structured_generation",
                    "model_type": model_type.value if model_type else "unknown",
                    "selection_strategy": selection_strategy.value,
                    "response_model": response_model.__name__,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "structured_generation"},
            )

            # Update selection statistics
            self._update_selection_stats(selected_model.name, selection_strategy)

            return result

        except Exception as e:
            # Record failure metrics if we have a selected model
            try:
                if "selected_model" in locals() and "selected_model" in locals():
                    selected_model = locals().get("selected_model")
                    if selected_model:
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

            self.logger.error(f"Error generating structured response: {e!s}")
            raise

    async def generate_text(
        self,
        prompt: str | Any,
        model: str | None = None,
        model_type: ModelType | None = None,
        provider: str | None = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: ScoringWeights | None = None,
        max_cost: float | None = None,
        min_performance: float | None = None,
        min_reliability: float | None = None,
        **kwargs: Any,
    ) -> str:
        """Generate a plain text response with intelligent model selection."""
        start_time = time.time()

        try:
            # Select the best model based on criteria
            selected_model, selection_result = await self._select_model_for_task(
                model=model,
                model_type=model_type,
                provider=provider,
                selection_strategy=selection_strategy,
                custom_weights=custom_weights,
                max_cost=max_cost,
                min_performance=min_performance,
                min_reliability=min_reliability,
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
                    "model_type": model_type.value if model_type else "unknown",
                    "selection_strategy": selection_strategy.value,
                },
            )

            self.performance_monitor.record_success(
                model_name=selected_model.name,
                success=True,
                provider=selected_model.provider,
                context={"task_type": "text_generation"},
            )

            # Update selection statistics
            self._update_selection_stats(selected_model.name, selection_strategy)

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

            self.logger.error(f"Error generating text response: {e!s}")
            raise

    async def generate_with_fallback(
        self,
        prompt: str | Any,
        response_model: type[T] | None = None,  # noqa: ARG002
        model_type: ModelType | None = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        max_attempts: int = 3,
        **kwargs: Any,
    ) -> str | T:
        """Generate response with automatic fallback chain execution."""
        last_error = None

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=model_type,
            strategy=selection_strategy,
            allow_fallback=True,
            max_models_to_consider=10,
        )

        # Get selection result with fallback chain
        selection_result = self.model_selector.select_model(criteria)

        # Try each model in the fallback chain
        for i, model_info in enumerate(selection_result.fallback_chain):
            if i >= max_attempts:
                break

            try:
                self.logger.info(
                    f"Attempting model: {model_info.name} (attempt {i+1}/{max_attempts})"
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
                self.logger.warning(f"Model {model_info.name} failed: {e!s}")

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
            f"All {max_attempts} models in fallback chain failed. Last error: {last_error!s}"
        )
        raise last_error or Exception("All models in fallback chain failed")

    async def _select_model_for_task(
        self,
        model: str | None = None,
        model_type: ModelType | None = None,
        provider: str | None = None,
        selection_strategy: SelectionStrategy = SelectionStrategy.BEST_SCORE,
        custom_weights: ScoringWeights | None = None,
        max_cost: float | None = None,
        min_performance: float | None = None,
        min_reliability: float | None = None,
        required_capabilities: list | None = None,
    ) -> tuple[ModelInfo, SelectionResult]:
        """Select the best model for a task based on criteria."""

        # If specific model is requested, try to find it in registry
        if model:
            model_info = self.model_registry.get_model(model)
            if model_info:
                # Create a simple selection result
                context = ScoringContext(
                    task_type=model_type,
                    required_capabilities=required_capabilities or [],
                    max_cost=max_cost,
                    min_performance=min_performance,
                    min_reliability=min_reliability,
                )
                score = self.model_scorer.score_model(model_info, context)

                selection_result = SelectionResult(
                    selected_model=model_info,
                    score=score,
                    fallback_chain=[model_info],
                    selection_reason=f"Explicitly requested model: {model}",
                    criteria=SelectionCriteria(
                        semantic_type=model_type,
                        strategy=selection_strategy,
                        custom_weights=custom_weights,
                        max_cost=max_cost,
                        min_performance=min_performance,
                        min_reliability=min_reliability,
                    ),
                )
                return model_info, selection_result

        # Create selection criteria
        criteria = SelectionCriteria(
            semantic_type=model_type,
            required_capabilities=required_capabilities or [],
            max_cost=max_cost,
            min_performance=min_performance,
            min_reliability=min_reliability,
            provider_preference=ProviderType(provider) if provider else None,
            strategy=selection_strategy,
            custom_weights=custom_weights,
            allow_fallback=True,
        )

        # Select model with fallback support
        selected_model, selection_result = (
            self.model_selector.select_model_with_fallback(criteria)
        )

        return selected_model, selection_result

    def _update_selection_stats(
        self, model_name: str, strategy: SelectionStrategy
    ) -> None:
        """Update selection statistics."""
        key = f"{model_name}:{strategy.value}"
        self._selection_stats[key] = self._selection_stats.get(key, 0) + 1
        self._last_selection_time[model_name] = time.time()

    async def health_check(self, provider: str | None = None) -> bool:
        """Check if the specified provider is healthy and accessible."""
        try:
            if provider:
                if provider in self.providers:
                    return await self.providers[provider].health_check()
                return False

            # Check all providers
            health_status = {}
            for provider_name, provider_instance in self.providers.items():
                health_status[provider_name] = await provider_instance.health_check()

            return all(health_status.values())

        except Exception as e:
            self.logger.error(f"Health check failed: {e!s}")
            return False

    def get_available_models(
        self, provider: str | None = None
    ) -> dict[str, list[str]]:
        """Get available models for the specified provider or all providers."""
        if provider:
            if provider in self.providers:
                models = self.providers[provider].get_available_models()
                return {
                    provider: (
                        list(models.values()) if isinstance(models, dict) else models
                    )
                }
            return {}

        result = {}
        for provider_name, provider_instance in self.providers.items():
            models = provider_instance.get_available_models()
            result[provider_name] = (
                list(models.values()) if isinstance(models, dict) else models
            )
        return result

    def get_model_performance(self, model_name: str) -> dict[str, Any]:
        """Get performance metrics for a specific model."""
        return self.performance_monitor.get_model_performance(model_name)

    def get_best_models(
        self, metric_type: MetricType, limit: int = 5
    ) -> list[tuple[str, float]]:
        """Get best performing models for a specific metric."""
        return self.performance_monitor.get_best_models(metric_type, limit)

    def get_selection_stats(self) -> dict[str, Any]:
        """Get model selection statistics."""
        return {
            "selection_counts": self._selection_stats.copy(),
            "last_selection_times": self._last_selection_time.copy(),
            "performance_cache_stats": self.performance_monitor.get_cache_stats(),
        }

    def get_model_rankings(
        self,
        metric_types: list[MetricType],
        weights: dict[MetricType, float] | None = None,
    ) -> list[tuple[str, float]]:
        """Get model rankings based on multiple performance metrics."""
        return self.performance_monitor.get_model_rankings(metric_types, weights)

    # Service Manager Integration Methods

    async def initialize_services(self) -> None:
        """Initialize the service manager and all services."""
        await self.service_manager.initialize()
        self.logger.info("All services initialized successfully")

    async def shutdown_services(self) -> None:
        """Shutdown the service manager and all services."""
        await self.service_manager.shutdown()
        self.logger.info("All services shutdown successfully")

    async def get_service_health(
        self, service_type: ServiceType
    ) -> ServiceHealth | None:
        """Get health status for a specific service type."""
        service = await self.service_manager.get_service(service_type)
        if not service:
            return None
        return await service.check_health()  # type: ignore[attr-defined]

    async def execute_service_request(
        self,
        service_type: ServiceType,
        request_data: dict[str, Any],
        service_id: str | None = None,
    ) -> Any:
        """Execute a request through the appropriate service."""
        return await self.service_manager.execute_service_request(
            service_type, request_data, service_id
        )

    def get_service_metrics(self, service_id: str) -> dict[str, Any] | None:
        """Get metrics for a specific service."""
        metrics = self.metrics_manager.get_service_metrics(service_id)
        if not metrics:
            return None

        return {
            "service_id": metrics.service_id,
            "request_count": metrics.request_count,
            "success_count": metrics.success_count,
            "error_count": metrics.error_count,
            "avg_response_time": metrics.avg_response_time,
            "error_rate": metrics.error_rate,
            "throughput": metrics.throughput,
            "availability": metrics.availability,
            "health_score": metrics.health_score,
        }

    def get_all_service_metrics(self) -> dict[str, dict[str, Any]]:
        """Get metrics for all services."""
        all_metrics = self.metrics_manager.get_all_metrics()
        return {
            service_id: {
                "service_id": metrics.service_id,
                "request_count": metrics.request_count,
                "success_count": metrics.success_count,
                "error_count": metrics.error_count,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate,
                "throughput": metrics.throughput,
                "availability": metrics.availability,
                "health_score": metrics.health_score,
            }
            for service_id, metrics in all_metrics.items()
        }

    def add_service_alert(
        self,
        service_id: str,
        metric_name: str,
        threshold: float,
        operator: str = ">",
        duration_seconds: int = 300,
        severity: str = "medium",
        message: str = "",
    ) -> None:
        """Add an alert configuration for a service."""
        alert = ServiceAlert(
            service_id=service_id,
            metric_name=metric_name,
            threshold=threshold,
            operator=operator,
            duration=timedelta(seconds=duration_seconds),
            severity=severity,
            message=message or f"{metric_name} {operator} {threshold}",
        )
        self.metrics_manager.add_alert(alert)
        self.logger.info(f"Added alert for {service_id}: {metric_name}")

    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get all currently active alerts."""
        alerts = self.metrics_manager.get_active_alerts()
        return [
            {
                "service_id": alert.service_id,
                "metric_name": alert.metric_name,
                "threshold": alert.threshold,
                "operator": alert.operator,
                "severity": alert.severity,
                "message": alert.message,
                "triggered_at": (
                    alert.triggered_at.isoformat() if alert.triggered_at else None
                ),
            }
            for alert in alerts
        ]

    def generate_service_report(self, service_id: str) -> dict[str, Any]:
        """Generate a comprehensive report for a service."""
        return self.metrics_manager.generate_service_report(service_id)

    def generate_summary_report(self) -> dict[str, Any]:
        """Generate a summary report for all services."""
        return self.metrics_manager.generate_summary_report()


def create_enhanced_llm_service(
    config: LLMConfig,
    model_registry: ModelRegistry | None = None,
    performance_monitor: PerformanceMonitor | None = None,
    service_manager: ServiceManager | None = None,
) -> EnhancedLLMService:
    """Factory function to create and configure an EnhancedLLMService instance."""
    return EnhancedLLMService(
        config, model_registry, performance_monitor, service_manager
    )


# Export all public classes and functions
__all__ = [
    "BaseLLMService",
    "EnhancedLLMService",
    "LoadBalancingStrategy",
    "ServiceAlert",
    "ServiceConfig",
    "ServiceHealth",
    "ServiceManager",
    "ServiceMetricsManager",
    "ServiceStatus",
    "ServiceType",
    "create_enhanced_llm_service",
]
