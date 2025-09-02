"""
Advanced prompt engineering system for Gemini-based pattern detection.

Provides structured prompt templates, few-shot learning capabilities,
and context-aware prompt generation for incident pattern analysis.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class PromptTemplate:
    """Template for generating Gemini prompts."""

    name: str
    system_prompt: str
    user_prompt_template: str
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)
    output_format: Dict[str, Any] = field(default_factory=dict)
    temperature: float = 0.3
    max_tokens: int = 2048


@dataclass
class PatternContext:
    """Structured context for pattern analysis."""

    # Temporal features
    time_window: str
    error_frequency: int
    error_burst_pattern: str
    temporal_distribution: str

    # Service features
    affected_services: List[str]
    primary_service: Optional[str]
    service_interaction_pattern: str
    cross_service_timing: str

    # Error characteristics
    error_types: List[str]
    severity_distribution: Dict[str, int]
    error_messages_sample: List[str]
    error_similarity_score: float

    # Historical context
    baseline_comparison: str
    trend_analysis: str
    similar_incidents: List[str]
    recent_changes: List[str]

    # Source code context (optional)
    code_changes_context: Optional[str] = None
    static_analysis_findings: Optional[Dict[str, Any]] = None
    code_quality_metrics: Optional[Dict[str, float]] = None
    dependency_vulnerabilities: Optional[List[str]] = None
    error_related_files: Optional[List[str]] = None
    recent_commits: Optional[List[str]] = None


class GeminiPromptEngine:
    """Advanced prompt engineering for Gemini-based pattern detection."""

    def __init__(self, few_shot_db_path: str = "few_shot_examples.json"):
        """Initialize the prompt engine.

        Args:
            few_shot_db_path: Path to few-shot examples database
        """
        self.few_shot_db_path = few_shot_db_path
        self.logger = logging.getLogger(__name__)
        self.few_shot_examples = self._load_few_shot_examples()

        # Initialize prompt templates
        self.templates = self._initialize_templates()

    def _initialize_templates(self) -> Dict[str, PromptTemplate]:
        """Initialize Gemini prompt templates for different tasks."""

        classification_template = PromptTemplate(
            name="pattern_classification",
            system_prompt="""You are an expert SRE pattern recognition system. Your role is to analyze log patterns and classify incident types with high accuracy.

PATTERN TYPES:
- cascade_failure: Multi-service dependency chain failures
- service_degradation: Single service performance issues
- traffic_spike: Volume-induced system stress
- configuration_issue: Deployment/config-related problems
- dependency_failure: External service problems
- resource_exhaustion: Memory/CPU/storage limits
- sporadic_errors: Random distributed failures

ANALYSIS APPROACH:
1. Examine temporal patterns (concentration, burst, acceleration)
2. Analyze service topology (correlation, cascade indicators)
3. Evaluate error characteristics (types, severity, similarity)
4. Consider historical context and baselines
5. Provide confidence reasoning""",
            user_prompt_template="""INCIDENT ANALYSIS REQUEST

Time Window: {time_window}
Error Count: {error_frequency}

TEMPORAL PATTERNS:
- Burst Pattern: {error_burst_pattern}
- Distribution: {temporal_distribution}

SERVICE IMPACT:
- Affected Services: {affected_services}
- Primary Service: {primary_service}
- Interaction Pattern: {service_interaction_pattern}
- Cross-Service Timing: {cross_service_timing}

ERROR CHARACTERISTICS:
- Error Types: {error_types}
- Severity Distribution: {severity_distribution}
- Sample Messages: {error_messages_sample}
- Message Similarity: {error_similarity_score}

HISTORICAL CONTEXT:
- Baseline Comparison: {baseline_comparison}
- Trend Analysis: {trend_analysis}
- Similar Past Incidents: {similar_incidents}
- Recent Changes: {recent_changes}

SOURCE CODE CONTEXT (if available):
- Code Changes: {code_changes_context}
- Static Analysis: {static_analysis_findings}
- Quality Metrics: {code_quality_metrics}
- Security Issues: {dependency_vulnerabilities}
- Related Files: {error_related_files}
- Recent Commits: {recent_commits}

REQUIRED OUTPUT FORMAT:
```json
{{
    "pattern_type": "one of: cascade_failure, service_degradation, traffic_spike, configuration_issue, dependency_failure, resource_exhaustion, sporadic_errors",
    "confidence_score": 0.85,
    "reasoning": "Detailed explanation of classification logic",
    "key_indicators": ["indicator1", "indicator2", "indicator3"],
    "alternative_patterns": {{
        "pattern_name": confidence_score
    }},
    "severity_assessment": "CRITICAL|HIGH|MEDIUM|LOW",
    "affected_services_analysis": {{
        "primary": "service_name",
        "secondary": ["service1", "service2"]
    }},
    "temporal_analysis": {{
        "onset_type": "rapid|gradual|mixed",
        "concentration_level": "high|medium|low",
        "escalation_pattern": "description"
    }},
    "recommended_actions": ["action1", "action2", "action3"]
}}
```

Analyze this incident and provide classification:""",
            output_format={
                "type": "json",
                "required_fields": ["pattern_type", "confidence_score", "reasoning"],
            },
            temperature=0.3,
        )

        confidence_template = PromptTemplate(
            name="confidence_assessment",
            system_prompt="""You are an expert confidence assessor for incident pattern detection. Your role is to evaluate the reliability of pattern classifications by analyzing multiple evidence factors.

CONFIDENCE FACTORS:
- Data Quality: Completeness, consistency, noise level
- Temporal Evidence: Pattern clarity, timing correlation
- Service Evidence: Topology alignment, interaction patterns
- Error Evidence: Type consistency, message similarity
- Historical Evidence: Baseline deviation, trend alignment
- Context Evidence: Recent changes, external factors

CONFIDENCE LEVELS:
- 0.9-1.0: Very High - Clear, unambiguous pattern with strong evidence
- 0.7-0.89: High - Strong pattern with good supporting evidence
- 0.5-0.69: Medium - Moderate pattern with some ambiguity
- 0.3-0.49: Low - Weak pattern with significant uncertainty
- 0.0-0.29: Very Low - Unclear or conflicting evidence""",
            user_prompt_template="""CONFIDENCE ASSESSMENT REQUEST

PATTERN CLASSIFICATION RESULT:
{classification_result}

EVIDENCE ANALYSIS:
Data Quality Factors:
- Log completeness: {log_completeness}%
- Timestamp consistency: {timestamp_consistency}
- Missing data points: {missing_data_rate}%

Temporal Evidence:
- Error concentration score: {error_concentration}
- Timing correlation strength: {timing_correlation}
- Pattern clarity: {pattern_clarity}

Service Evidence:
- Service topology alignment: {topology_alignment}
- Cross-service correlation: {cross_service_correlation}
- Cascade indicators present: {cascade_indicators}

Error Evidence:
- Error type consistency: {error_consistency}
- Message similarity score: {message_similarity}
- Severity distribution alignment: {severity_alignment}

Historical Evidence:
- Baseline deviation significance: {baseline_deviation}
- Trend alignment: {trend_alignment}
- Similar incident matches: {similar_incidents_count}

Context Evidence:
- Recent deployment correlation: {deployment_correlation}
- External dependency status: {dependency_status}
- System resource pressure: {resource_pressure}

REQUIRED OUTPUT FORMAT:
```json
{{
    "overall_confidence": 0.75,
    "confidence_level": "HIGH|MEDIUM|LOW|VERY_LOW",
    "factor_scores": {{
        "data_quality": 0.8,
        "temporal_evidence": 0.9,
        "service_evidence": 0.7,
        "error_evidence": 0.85,
        "historical_evidence": 0.6,
        "context_evidence": 0.7
    }},
    "confidence_reasoning": "Detailed explanation of confidence assessment",
    "uncertainty_factors": ["factor1", "factor2"],
    "confidence_boosters": ["factor1", "factor2"],
    "recommendation": "accept|review|reject"
}}
```

Assess the confidence of this pattern classification:""",
            output_format={
                "type": "json",
                "required_fields": [
                    "overall_confidence",
                    "confidence_level",
                    "confidence_reasoning",
                ],
            },
            temperature=0.2,
        )

        return {
            "classification": classification_template,
            "confidence": confidence_template,
        }

    async def generate_classification_prompt(self, context: PatternContext) -> str:
        """Generate prompt for pattern classification.

        Args:
            context: Structured pattern context

        Returns:
            Formatted prompt string
        """
        template = self.templates["classification"]

        # Add few-shot examples if available
        few_shot_examples = self._get_relevant_few_shot_examples(
            "classification", context.affected_services
        )

        prompt = template.system_prompt + "\n\n"

        # Add few-shot examples
        if few_shot_examples:
            prompt += "EXAMPLES OF SIMILAR CLASSIFICATIONS:\n"
            for i, example in enumerate(few_shot_examples[:3], 1):
                prompt += f"\nExample {i}:\n"
                prompt += f"Context: {example.get('context', 'N/A')}\n"
                prompt += f"Classification: {example.get('classification', 'N/A')}\n"
                prompt += f"Reasoning: {example.get('reasoning', 'N/A')}\n"
            prompt += "\n"

        # Format the user prompt with context
        user_prompt = template.user_prompt_template.format(
            time_window=context.time_window,
            error_frequency=context.error_frequency,
            error_burst_pattern=context.error_burst_pattern,
            temporal_distribution=context.temporal_distribution,
            affected_services=", ".join(context.affected_services),
            primary_service=context.primary_service or "Unknown",
            service_interaction_pattern=context.service_interaction_pattern,
            cross_service_timing=context.cross_service_timing,
            error_types=", ".join(context.error_types),
            severity_distribution=json.dumps(context.severity_distribution),
            error_messages_sample=context.error_messages_sample,
            error_similarity_score=context.error_similarity_score,
            baseline_comparison=context.baseline_comparison,
            trend_analysis=context.trend_analysis,
            similar_incidents=", ".join(context.similar_incidents),
            recent_changes=", ".join(context.recent_changes),
            code_changes_context=context.code_changes_context or "Not available",
            static_analysis_findings=json.dumps(context.static_analysis_findings or {}),
            code_quality_metrics=json.dumps(context.code_quality_metrics or {}),
            dependency_vulnerabilities=", ".join(
                context.dependency_vulnerabilities or []
            ),
            error_related_files=", ".join(context.error_related_files or []),
            recent_commits=", ".join(context.recent_commits or []),
        )

        prompt += user_prompt
        return prompt

    async def generate_confidence_prompt(
        self, classification_result: Dict[str, Any], evidence_metrics: Dict[str, Any]
    ) -> str:
        """Generate prompt for confidence assessment.

        Args:
            classification_result: Previous classification result
            evidence_metrics: Evidence quality metrics

        Returns:
            Formatted confidence assessment prompt
        """
        template = self.templates["confidence"]

        # Format the user prompt with evidence
        user_prompt = template.user_prompt_template.format(
            classification_result=json.dumps(classification_result, indent=2),
            **evidence_metrics,
        )

        return template.system_prompt + "\n\n" + user_prompt

    def get_template_config(self, template_name: str) -> Dict[str, Any]:
        """Get configuration for a specific template.

        Args:
            template_name: Name of the template

        Returns:
            Template configuration including temperature, max_tokens
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]
        return {
            "temperature": template.temperature,
            "max_tokens": template.max_tokens,
            "output_format": template.output_format,
        }

    def _load_few_shot_examples(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load few-shot examples from database."""
        try:
            examples_path = Path(self.few_shot_db_path)
            if examples_path.exists() and examples_path.stat().st_size > 0:
                with open(examples_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
                    else:
                        return {}
            else:
                self.logger.info(
                    f"Few-shot examples file not found or empty at {self.few_shot_db_path}"
                )
                return {}
        except Exception as e:
            self.logger.error(f"Error loading few-shot examples: {e}")
            return {}

    def _get_relevant_few_shot_examples(
        self, template_type: str, services: List[str]
    ) -> List[Dict[str, Any]]:
        """Get relevant few-shot examples for the given context.

        Args:
            template_type: Type of template (classification, confidence)
            services: Affected services for context matching

        Returns:
            List of relevant examples
        """
        examples = self.few_shot_examples.get(template_type, [])

        if not examples or not services:
            return examples[:3]  # Return first 3 if no specific matching

        # Simple relevance scoring based on service overlap
        scored_examples = []
        for example in examples:
            example_services = set(example.get("affected_services", []))
            service_overlap = len(set(services) & example_services)
            score = service_overlap / max(len(services), len(example_services), 1)
            scored_examples.append((score, example))

        # Sort by relevance score and return top examples
        scored_examples.sort(key=lambda x: x[0], reverse=True)
        return [example for _, example in scored_examples[:3]]

    async def save_example(
        self, template_type: str, context: Dict[str, Any], result: Dict[str, Any]
    ) -> None:
        """Save a new few-shot example to the database.

        Args:
            template_type: Type of template (classification, confidence)
            context: Input context that led to the result
            result: The successful classification/assessment result
        """
        try:
            example = {
                "context": context,
                "result": result,
                "timestamp": context.get("timestamp"),
                "affected_services": context.get("affected_services", []),
            }

            if template_type not in self.few_shot_examples:
                self.few_shot_examples[template_type] = []

            self.few_shot_examples[template_type].append(example)

            # Keep only the most recent 100 examples per template
            if len(self.few_shot_examples[template_type]) > 100:
                self.few_shot_examples[template_type] = self.few_shot_examples[
                    template_type
                ][-100:]

            # Save to file
            with open(self.few_shot_db_path, "w", encoding="utf-8") as f:
                json.dump(self.few_shot_examples, f, indent=2, default=str)

            self.logger.info(f"Saved new few-shot example for {template_type}")

        except Exception as e:
            self.logger.error(f"Error saving few-shot example: {e}")
