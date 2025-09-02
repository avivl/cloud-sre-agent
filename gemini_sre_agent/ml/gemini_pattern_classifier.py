"""
Gemini AI-powered pattern classification for incident analysis.

This module provides intelligent pattern classification using Google's Gemini models
with structured output support for reliable incident pattern detection and analysis.
"""

import logging
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..pattern_detector.models import PatternMatch, PatternType, TimeWindow
from .gemini_api_client import GeminiAPIClient, GeminiRequest, GeminiResponse


class PatternClassificationResult(BaseModel):
    """Structured output model for pattern classification results."""

    pattern_type: str = Field(..., description="Detected pattern type")
    confidence_score: float = Field(
        ..., ge=0.0, le=1.0, description="Classification confidence"
    )
    reasoning: str = Field(
        ..., description="Detailed explanation of classification logic"
    )
    key_indicators: List[str] = Field(
        default_factory=list, description="Key evidence indicators"
    )
    alternative_patterns: Dict[str, float] = Field(
        default_factory=dict, description="Alternative patterns with confidence scores"
    )
    severity_assessment: str = Field(..., description="Incident severity level")
    affected_services_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Service impact analysis"
    )
    temporal_analysis: Dict[str, Any] = Field(
        default_factory=dict, description="Temporal pattern analysis"
    )
    recommended_actions: List[str] = Field(
        default_factory=list, description="Recommended response actions"
    )


class ConfidenceAssessmentResult(BaseModel):
    """Structured output model for confidence assessment results."""

    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_level: str = Field(..., description="HIGH|MEDIUM|LOW|VERY_LOW")
    factor_scores: Dict[str, float] = Field(default_factory=dict)
    reliability_indicators: List[str] = Field(default_factory=list)
    uncertainty_sources: List[str] = Field(default_factory=list)
    confidence_reasoning: str = Field(..., description="Detailed confidence analysis")


class GeminiPatternClassifier:
    """Gemini AI-powered pattern classification system with structured output."""

    def __init__(
        self,
        api_key: str,
        cost_tracker: Optional[Any] = None,
        rate_limiter: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Initialize the Gemini pattern classifier."""
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.config = config or self._get_default_config()
        self.confidence_assessment_threshold = self.config.get(
            "confidence_threshold", 0.7
        )

        # Gemini API client
        self.gemini_client = GeminiAPIClient(
            api_key=api_key, cost_tracker=cost_tracker, rate_limiter=rate_limiter
        )

        # Performance tracking
        self._classification_count = 0
        self._successful_classifications = 0

        self.logger.info(
            "[GEMINI_CLASSIFIER] Initialized with confidence threshold: %.2f",
            self.confidence_assessment_threshold,
        )

    async def classify_patterns(
        self,
        window: TimeWindow,
        threshold_results: List[Dict[str, Any]],
        historical_context: Optional[Dict[str, Any]] = None,
        code_context: Optional[Dict[str, Any]] = None,
    ) -> List[PatternMatch]:
        """Classify patterns using Gemini AI with structured output."""
        try:
            self._classification_count += 1

            # Select appropriate model based on complexity
            model_name = self._select_model(window, threshold_results)

            # Generate classification
            classification_result = await self._classify_pattern(
                window, threshold_results, historical_context, code_context, model_name
            )

            if not classification_result.success:
                self.logger.warning(
                    "[GEMINI_CLASSIFIER] Classification failed: %s",
                    classification_result.error_message,
                )
                return []

            # Parse structured results
            pattern_data = classification_result.parsed_json
            if not pattern_data:
                self.logger.warning(
                    "[GEMINI_CLASSIFIER] No valid JSON in classification response"
                )
                return []

            # Generate confidence assessment if needed
            confidence_data = None
            confidence_score = pattern_data.get("confidence_score", 0.0)

            if confidence_score < self.confidence_assessment_threshold:
                confidence_data = await self._assess_confidence(pattern_data, window)

            # Convert to PatternMatch
            pattern_matches = self._convert_to_pattern_matches(
                pattern_data, window, confidence_data
            )

            if pattern_matches:
                self._successful_classifications += 1

            self.logger.info(
                "[GEMINI_CLASSIFIER] Classified %d patterns with confidence %.3f",
                len(pattern_matches),
                confidence_score,
            )

            return pattern_matches

        except Exception as e:
            self.logger.error("[GEMINI_CLASSIFIER] Classification error: %s", str(e))
            return []

    async def _classify_pattern(
        self,
        window: TimeWindow,
        threshold_results: List[Dict[str, Any]],
        historical_context: Optional[Dict[str, Any]],
        code_context: Optional[Dict[str, Any]],
        model_name: str,
    ) -> GeminiResponse:
        """Perform pattern classification using Gemini with structured output."""

        # Generate classification prompt
        prompt = self._build_classification_prompt(
            window, threshold_results, historical_context, code_context
        )

        # Create structured output schema
        schema = self._build_classification_schema()

        # Create Gemini request
        request = GeminiRequest(
            model=model_name,
            messages=[
                {"role": "system", "content": self._get_system_prompt()},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=2048,
            response_schema=schema,
        )

        return await self.gemini_client.generate_response(request)

    async def _assess_confidence(
        self, pattern_data: Dict[str, Any], window: TimeWindow
    ) -> Optional[Dict[str, Any]]:
        """Generate detailed confidence assessment for low-confidence classifications."""
        try:
            confidence_prompt = self._build_confidence_prompt(pattern_data, window)
            confidence_schema = self._build_confidence_schema()

            request = GeminiRequest(
                model="gemini-1.5-flash",  # Use faster model for confidence assessment
                messages=[
                    {"role": "system", "content": self._get_confidence_system_prompt()},
                    {"role": "user", "content": confidence_prompt},
                ],
                temperature=0.2,
                max_tokens=1024,
                response_schema=confidence_schema,
            )

            response = await self.gemini_client.generate_response(request)

            if response.success and response.parsed_json:
                return response.parsed_json

            self.logger.warning("[GEMINI_CLASSIFIER] Confidence assessment failed")
            return None

        except Exception as e:
            self.logger.error(
                "[GEMINI_CLASSIFIER] Confidence assessment error: %s", str(e)
            )
            return None

    def _select_model(
        self, window: TimeWindow, threshold_results: List[Dict[str, Any]]
    ) -> str:
        """Select appropriate Gemini model based on complexity."""

        # Calculate complexity factors
        log_count = len(window.logs)
        service_count = len(
            set(log.service_name for log in window.logs if log.service_name)
        )
        threshold_count = len(threshold_results)
        duration_hours = window.duration_minutes / 60.0

        complexity_score = (
            (log_count / 1000.0) * 0.3
            + (service_count / 10.0) * 0.3
            + (threshold_count / 20.0) * 0.2
            + (duration_hours / 24.0) * 0.2
        )

        # Select model based on complexity
        if complexity_score > 0.7:
            model = "gemini-1.5-pro"  # Most capable for complex incidents
        elif complexity_score > 0.3:
            model = "gemini-1.5-flash"  # Balanced speed/capability
        else:
            model = "gemini-1.5-flash"  # Fast for simple patterns

        self.logger.debug(
            "[GEMINI_CLASSIFIER] Selected model %s (complexity: %.3f)",
            model,
            complexity_score,
        )

        return model

    def _build_classification_prompt(
        self,
        window: TimeWindow,
        threshold_results: List[Dict[str, Any]],
        historical_context: Optional[Dict[str, Any]],
        code_context: Optional[Dict[str, Any]],
    ) -> str:
        """Build comprehensive classification prompt."""

        # Extract key log patterns
        error_logs = [
            log for log in window.logs if log.severity in ["ERROR", "CRITICAL"]
        ]
        service_errors = {}
        for log in error_logs:
            service = log.service_name or "unknown"
            if service not in service_errors:
                service_errors[service] = []
            service_errors[service].append(log.error_message or "No message")

        # Build prompt sections
        prompt_parts = [
            f"TIME WINDOW: {window.start_time} to {window.end_time}",
            f"DURATION: {window.duration_minutes} minutes",
            f"TOTAL LOGS: {len(window.logs)}",
            f"ERROR LOGS: {len(error_logs)}",
            "",
            "SERVICE ERRORS:",
        ]

        for service, messages in service_errors.items():
            prompt_parts.append(f"- {service}: {len(messages)} errors")
            # Include sample error messages
            for msg in messages[:3]:  # Limit to first 3 errors per service
                prompt_parts.append(f"  * {msg[:200]}...")  # Truncate long messages

        if threshold_results:
            prompt_parts.extend(
                [
                    "",
                    "THRESHOLD VIOLATIONS:",
                    *[
                        f"- {result.get('type', 'unknown')}: {result.get('description', 'N/A')}"
                        for result in threshold_results[:5]
                    ],  # Limit to top 5
                ]
            )

        if historical_context:
            prompt_parts.extend(
                [
                    "",
                    "HISTORICAL CONTEXT:",
                    f"- Similar incidents: {historical_context.get('similar_count', 0)}",
                    f"- Recent trends: {historical_context.get('trend_analysis', 'N/A')}",
                ]
            )

        if code_context:
            prompt_parts.extend(
                [
                    "",
                    "SOURCE CODE CONTEXT:",
                    f"- Recent commits: {len(code_context.get('recent_commits', []))}",
                    f"- Code changes: {code_context.get('changes_summary', 'N/A')}",
                    f"- Related files: {len(code_context.get('related_files', []))}",
                ]
            )

        prompt_parts.append(
            "\nAnalyze this incident and provide detailed classification."
        )

        return "\n".join(prompt_parts)

    def _build_confidence_prompt(
        self, pattern_data: Dict[str, Any], window: TimeWindow
    ) -> str:
        """Build confidence assessment prompt."""
        return f"""
CLASSIFICATION RESULT TO ASSESS:
- Pattern Type: {pattern_data.get('pattern_type')}
- Confidence: {pattern_data.get('confidence_score')}
- Reasoning: {pattern_data.get('reasoning')}

TIME WINDOW CHARACTERISTICS:
- Duration: {window.duration_minutes} minutes
- Log count: {len(window.logs)}
- Services affected: {len(set(log.service_name for log in window.logs if log.service_name))}

Provide detailed confidence assessment considering data quality, evidence strength, and uncertainty factors.
"""

    def _convert_to_pattern_matches(
        self,
        pattern_data: Dict[str, Any],
        window: TimeWindow,
        confidence_data: Optional[Dict[str, Any]] = None,
    ) -> List[PatternMatch]:
        """Convert Gemini classification results to PatternMatch objects."""

        pattern_matches = []

        try:
            # Map pattern type string to enum
            pattern_type_str = pattern_data.get("pattern_type", "")
            pattern_type = self._map_pattern_type(pattern_type_str)

            if pattern_type is None:
                self.logger.warning(
                    "[GEMINI_CLASSIFIER] Unknown pattern type: %s", pattern_type_str
                )
                return []

            # Use confidence assessment if available
            final_confidence = pattern_data.get("confidence_score", 0.0)
            if confidence_data:
                final_confidence = confidence_data.get(
                    "overall_confidence", final_confidence
                )

            # Create primary pattern match
            affected_services = self._extract_affected_services(pattern_data)
            pattern_match = PatternMatch(
                pattern_type=pattern_type,
                confidence_score=final_confidence,
                primary_service=affected_services[0] if affected_services else None,
                affected_services=affected_services,
                severity_level=pattern_data.get("severity_assessment", "MEDIUM"),
                evidence={
                    "gemini_classification": True,
                    "key_indicators": pattern_data.get("key_indicators", []),
                    "recommended_actions": pattern_data.get("recommended_actions", []),
                    "temporal_analysis": pattern_data.get("temporal_analysis", {}),
                    "confidence_assessment": confidence_data,
                    "reasoning": pattern_data.get("reasoning", ""),
                },
                remediation_priority=(
                    "HIGH"
                    if pattern_data.get("severity_assessment") in ["HIGH", "CRITICAL"]
                    else "MEDIUM"
                ),
                suggested_actions=pattern_data.get(
                    "recommended_actions", ["Investigation required"]
                ),
            )

            pattern_matches.append(pattern_match)

            # Add alternative patterns if confidence is high enough
            alternatives = pattern_data.get("alternative_patterns", {})
            for alt_pattern, alt_confidence in alternatives.items():
                if alt_confidence >= 0.3:  # Threshold for alternative patterns
                    alt_type = self._map_pattern_type(alt_pattern)
                    if alt_type:
                        alt_services = self._extract_affected_services(pattern_data)
                        alt_match = PatternMatch(
                            pattern_type=alt_type,
                            confidence_score=alt_confidence,
                            primary_service=alt_services[0] if alt_services else None,
                            affected_services=alt_services,
                            severity_level="MEDIUM",
                            evidence={
                                "gemini_classification": True,
                                "alternative_pattern": True,
                                "primary_pattern": pattern_type_str,
                                "reasoning": f"Alternative pattern: {alt_pattern}",
                            },
                            remediation_priority="MEDIUM",
                            suggested_actions=[
                                "Alternative pattern - review primary pattern first"
                            ],
                        )
                        pattern_matches.append(alt_match)

            return pattern_matches

        except Exception as e:
            self.logger.error(
                "[GEMINI_CLASSIFIER] Error converting results: %s", str(e)
            )
            return []

    def _extract_affected_services(self, pattern_data: Dict[str, Any]) -> List[str]:
        """Extract affected services from classification results."""
        services = []

        analysis = pattern_data.get("affected_services_analysis", {})

        # Add primary service
        primary = analysis.get("primary")
        if primary:
            services.append(primary)

        # Add secondary services
        secondary = analysis.get("secondary", [])
        if isinstance(secondary, list):
            services.extend(secondary)

        # Remove duplicates while preserving order (primary service first)
        seen = set()
        unique_services = []
        for service in services:
            if service not in seen:
                seen.add(service)
                unique_services.append(service)
        return unique_services

    def _map_pattern_type(self, pattern_str: str) -> Optional[str]:
        """Map string pattern type to PatternType enum."""
        mapping = {
            "cascade_failure": PatternType.CASCADE_FAILURE,
            "service_degradation": PatternType.SERVICE_DEGRADATION,
            "traffic_spike": PatternType.TRAFFIC_SPIKE,
            "configuration_issue": PatternType.CONFIGURATION_ISSUE,
            "dependency_failure": PatternType.DEPENDENCY_FAILURE,
            "resource_exhaustion": PatternType.RESOURCE_EXHAUSTION,
            "sporadic_errors": PatternType.SPORADIC_ERRORS,
        }

        return mapping.get(pattern_str.lower())

    def _get_system_prompt(self) -> str:
        """Get system prompt for pattern classification."""
        return """You are an expert incident pattern classifier for SRE teams. Your role is to analyze system incidents and classify them into specific pattern types based on log data, metrics, and context.

PATTERN TYPES:
- cascade_failure: Failures spreading across multiple services
- service_degradation: Gradual performance decline in services  
- traffic_spike: Sudden increase in request volume
- configuration_issue: Problems from configuration changes
- dependency_failure: External service or database failures
- resource_exhaustion: CPU, memory, or storage exhaustion
- sporadic_errors: Intermittent, hard-to-reproduce errors

Focus on evidence-based analysis with high confidence classifications."""

    def _get_confidence_system_prompt(self) -> str:
        """Get system prompt for confidence assessment."""
        return """You are an expert confidence assessor for incident pattern detection. Evaluate the reliability of pattern classifications by analyzing data quality, evidence strength, and uncertainty factors.

Consider factors like data completeness, temporal evidence clarity, service correlation strength, and historical pattern consistency."""

    def _build_classification_schema(self) -> Dict[str, Any]:
        """Build JSON schema for classification structured output."""
        return {
            "type": "object",
            "properties": {
                "pattern_type": {
                    "type": "string",
                    "enum": [
                        "cascade_failure",
                        "service_degradation",
                        "traffic_spike",
                        "configuration_issue",
                        "dependency_failure",
                        "resource_exhaustion",
                        "sporadic_errors",
                    ],
                },
                "confidence_score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "reasoning": {"type": "string"},
                "key_indicators": {"type": "array", "items": {"type": "string"}},
                "alternative_patterns": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "severity_assessment": {
                    "type": "string",
                    "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"],
                },
                "affected_services_analysis": {
                    "type": "object",
                    "properties": {
                        "primary": {"type": "string"},
                        "secondary": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "temporal_analysis": {
                    "type": "object",
                    "properties": {
                        "onset_type": {
                            "type": "string",
                            "enum": ["rapid", "gradual", "mixed"],
                        },
                        "concentration_level": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                        },
                        "escalation_pattern": {"type": "string"},
                    },
                },
                "recommended_actions": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["pattern_type", "confidence_score", "reasoning"],
        }

    def _build_confidence_schema(self) -> Dict[str, Any]:
        """Build JSON schema for confidence assessment structured output."""
        return {
            "type": "object",
            "properties": {
                "overall_confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
                "confidence_level": {
                    "type": "string",
                    "enum": ["HIGH", "MEDIUM", "LOW", "VERY_LOW"],
                },
                "factor_scores": {
                    "type": "object",
                    "additionalProperties": {"type": "number"},
                },
                "reliability_indicators": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "uncertainty_sources": {"type": "array", "items": {"type": "string"}},
                "confidence_reasoning": {"type": "string"},
            },
            "required": [
                "overall_confidence",
                "confidence_level",
                "confidence_reasoning",
            ],
        }

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration."""
        return {
            "confidence_threshold": 0.7,
            "max_alternative_patterns": 3,
            "enable_confidence_assessment": True,
        }

    def get_performance_stats(self) -> Dict[str, Any]:
        """Get classifier performance statistics."""
        success_rate = (
            self._successful_classifications / max(1, self._classification_count) * 100
        )

        return {
            "total_classifications": self._classification_count,
            "successful_classifications": self._successful_classifications,
            "success_rate_percent": round(success_rate, 2),
            "confidence_threshold": self.confidence_assessment_threshold,
        }
