# gemini_sre_agent/ml/enhanced_analysis_agent.py

"""
Enhanced analysis agent with dynamic prompt generation and specialized code generation.

This module integrates the enhanced prompt generation system with specialized code
generators to provide context-aware, adaptive code generation capabilities.
"""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from google.generativeai.generative_models import GenerativeModel

from .adaptive_prompt_strategy import AdaptivePromptStrategy, StrategyConfig
from .code_generator_factory import CodeGeneratorFactory
from .meta_prompt_generator import MetaPromptConfig, MetaPromptGenerator
from .prompt_context_models import (
    IssueContext,
    IssueType,
    MetaPromptContext,
    PromptContext,
    RepositoryContext,
    TaskContext,
)


@dataclass
class EnhancedAnalysisConfig:
    """Configuration for enhanced analysis agent."""

    project_id: str
    location: str
    main_model: str = "gemini-1.5-pro-001"
    meta_model: str = "gemini-1.5-flash-001"
    enable_meta_prompt: bool = True
    enable_validation: bool = True
    enable_specialized_generators: bool = True
    max_retries: int = 3
    timeout_seconds: int = 30


class EnhancedAnalysisAgent:
    """
    Enhanced analysis agent with dynamic prompt generation and specialized code generation.

    This agent uses the enhanced prompt generation system and specialized code generators
    to create context-aware, adaptive prompts and high-quality code fixes.
    """

    def __init__(self, config: EnhancedAnalysisConfig):
        """
        Initialize the enhanced analysis agent.

        Args:
            config: Configuration for the enhanced analysis agent
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize models
        self.main_model = GenerativeModel(config.main_model)
        self.meta_model = GenerativeModel(config.meta_model)

        # Initialize prompt generation components
        self.adaptive_strategy = AdaptivePromptStrategy(StrategyConfig())
        self.meta_prompt_generator = MetaPromptGenerator(
            MetaPromptConfig(
                project_id=config.project_id,
                location=config.location,
                meta_model=config.meta_model,
                max_retries=config.max_retries,
                timeout_seconds=config.timeout_seconds,
                enable_validation=config.enable_validation,
                enable_fallback=True,
            )
        )

        # Initialize specialized code generation components
        if config.enable_specialized_generators:
            self.code_generator_factory = CodeGeneratorFactory()
            self.logger.info("Specialized code generators enabled")
        else:
            self.code_generator_factory = None
            self.logger.info("Specialized code generators disabled")

        self.logger.info("Enhanced analysis agent initialized")

    async def analyze_issue(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
    ) -> Dict[str, Any]:
        """
        Analyze an issue using enhanced prompt generation and specialized code generation.

        Args:
            triage_packet: Triage information from the triage agent
            historical_logs: Historical log data for context
            configs: Configuration data
            flow_id: Unique flow identifier

        Returns:
            Analysis result with generated code fix
        """
        try:
            self.logger.info(f"Starting enhanced analysis for flow {flow_id}")

            # 1. Build context from triage packet and logs
            context = await self._build_analysis_context(
                triage_packet, historical_logs, configs, flow_id
            )

            # 2. Generate optimized prompt using adaptive strategy
            prompt = await self._generate_optimized_prompt(context)

            # 3. Execute analysis with the optimized prompt
            analysis_result = await self._execute_analysis(prompt, context)

            # 4. If specialized generators are enabled, enhance the code generation
            if self.config.enable_specialized_generators and analysis_result.get(
                "success", False
            ):
                enhanced_result = await self._enhance_with_specialized_generator(
                    analysis_result, context
                )
                if enhanced_result:
                    analysis_result = enhanced_result

            # 5. Validate and refine the result
            validated_result = await self._validate_and_refine(analysis_result, context)

            self.logger.info(f"Enhanced analysis completed for flow {flow_id}")
            return validated_result

        except Exception as e:
            self.logger.error(f"Enhanced analysis failed for flow {flow_id}: {e}")
            return await self._fallback_analysis(
                triage_packet, historical_logs, configs
            )

    async def _enhance_with_specialized_generator(
        self, analysis_result: Dict[str, Any], context: PromptContext
    ) -> Dict[str, Any]:
        """
        Enhance the analysis result using specialized code generators.

        Args:
            analysis_result: The initial analysis result
            context: The prompt context

        Returns:
            Enhanced analysis result with improved code generation
        """
        try:
            if not self.code_generator_factory:
                return analysis_result

            # Get the appropriate specialized generator
            # Convert string generator_type back to IssueType for the factory
            try:
                issue_type = IssueType(context.generator_type)
                generator = self.code_generator_factory.create_generator(issue_type)
                # Set the context for the generator
                generator.set_context(context)
            except ValueError:
                # If conversion fails, use UNKNOWN type
                generator = self.code_generator_factory.create_generator(
                    IssueType.UNKNOWN
                )
                generator.set_context(context)

            if not generator:
                self.logger.warning(
                    f"No specialized generator found for {context.generator_type}"
                )
                return analysis_result

            # Extract the current code patch
            current_code = analysis_result.get("analysis", {}).get("code_patch", "")
            if not current_code:
                return analysis_result

            # Use the specialized generator to enhance the code
            enhanced_code = await generator.enhance_code_patch(current_code, context)

            if enhanced_code and enhanced_code != current_code:
                # Update the analysis result with enhanced code
                analysis_result["analysis"]["code_patch"] = enhanced_code
                analysis_result["enhanced_by_specialized_generator"] = True
                analysis_result["generator_type"] = context.generator_type

                self.logger.info(f"Code enhanced by {context.generator_type} generator")

                # Also enhance the proposed fix description if possible
                if hasattr(generator, "enhance_fix_description"):
                    enhanced_description = await generator.enhance_fix_description(
                        analysis_result["analysis"]["proposed_fix"], context
                    )
                    if enhanced_description:
                        analysis_result["analysis"][
                            "proposed_fix"
                        ] = enhanced_description

            return analysis_result

        except Exception as e:
            self.logger.warning(f"Specialized generator enhancement failed: {e}")
            return analysis_result

    async def _build_analysis_context(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
    ) -> PromptContext:
        """Build comprehensive context for analysis."""

        # Extract issue information
        issue_context = self._extract_issue_context(triage_packet)

        # Extract repository information
        repository_context = self._extract_repository_context(configs)

        # Create prompt context
        context = PromptContext(
            issue_context=issue_context,
            repository_context=repository_context,
            generator_type=self._determine_generator_type(issue_context),
            validation_feedback=None,
            iteration_count=0,
        )

        return context

    def _extract_issue_context(self, triage_packet: Dict[str, Any]) -> IssueContext:
        """Extract issue context from triage packet."""

        # Determine issue type from triage packet
        issue_type = self._classify_issue_type(triage_packet)

        # Extract affected files
        affected_files = triage_packet.get("affected_files", [])

        # Extract error patterns
        error_patterns = triage_packet.get("error_patterns", [])

        # Extract severity level
        severity_level = triage_packet.get("severity_level", 5)

        # Extract impact analysis
        impact_analysis = triage_packet.get("impact_analysis", {})

        # Extract related services
        related_services = triage_packet.get("related_services", [])

        # Extract temporal context
        temporal_context = triage_packet.get("temporal_context", {})

        # Extract user and business impact
        user_impact = triage_packet.get("user_impact", "Unknown impact")
        business_impact = triage_packet.get(
            "business_impact", "Unknown business impact"
        )

        return IssueContext(
            issue_type=issue_type,
            affected_files=affected_files,
            error_patterns=error_patterns,
            severity_level=severity_level,
            impact_analysis=impact_analysis,
            related_services=related_services,
            temporal_context=temporal_context,
            user_impact=user_impact,
            business_impact=business_impact,
            complexity_score=self._calculate_complexity_score(triage_packet),
            context_richness=self._calculate_context_richness(triage_packet),
        )

    def _extract_repository_context(self, configs: Dict[str, Any]) -> RepositoryContext:
        """Extract repository context from configuration."""

        return RepositoryContext(
            architecture_type=configs.get("architecture_type", "unknown"),
            technology_stack=configs.get("technology_stack", {}),
            coding_standards=configs.get("coding_standards", {}),
            error_handling_patterns=configs.get("error_handling_patterns", []),
            testing_patterns=configs.get("testing_patterns", []),
            dependency_structure=configs.get("dependency_structure", {}),
            recent_changes=configs.get("recent_changes", []),
            historical_fixes=configs.get("historical_fixes", []),
            code_quality_metrics=configs.get("code_quality_metrics", {}),
        )

    def _classify_issue_type(self, triage_packet: Dict[str, Any]) -> IssueType:
        """Classify the issue type from triage packet."""

        error_patterns = triage_packet.get("error_patterns", [])
        triage_packet.get("affected_files", [])

        # Simple classification logic
        if any("database" in pattern.lower() for pattern in error_patterns):
            return IssueType.DATABASE_ERROR
        elif any("api" in pattern.lower() for pattern in error_patterns):
            return IssueType.API_ERROR
        elif any("security" in pattern.lower() for pattern in error_patterns):
            return IssueType.SECURITY_ERROR
        elif any("config" in pattern.lower() for pattern in error_patterns):
            return IssueType.CONFIGURATION_ERROR
        elif any("performance" in pattern.lower() for pattern in error_patterns):
            return IssueType.PERFORMANCE_ERROR
        elif any("network" in pattern.lower() for pattern in error_patterns):
            return IssueType.NETWORK_ERROR
        elif any("auth" in pattern.lower() for pattern in error_patterns):
            return IssueType.AUTHENTICATION_ERROR
        else:
            return IssueType.UNKNOWN

    def _determine_generator_type(self, issue_context: IssueContext) -> str:
        """Determine the appropriate generator type for the issue."""

        issue_type_mapping = {
            IssueType.DATABASE_ERROR: "database_error",
            IssueType.API_ERROR: "api_error",
            IssueType.SECURITY_ERROR: "security_error",
            IssueType.CONFIGURATION_ERROR: "configuration_error",
            IssueType.PERFORMANCE_ERROR: "performance_error",
            IssueType.NETWORK_ERROR: "network_error",
            IssueType.AUTHENTICATION_ERROR: "authentication_error",
            IssueType.SERVICE_ERROR: "service_error",
            IssueType.UNKNOWN: "generic_error",
        }

        return issue_type_mapping.get(issue_context.issue_type, "generic_error")

    def _calculate_complexity_score(self, triage_packet: Dict[str, Any]) -> int:
        """Calculate complexity score for the issue."""

        score = 1  # Base score

        # Add points based on various factors
        if triage_packet.get("affected_files"):
            score += len(triage_packet["affected_files"])

        if triage_packet.get("related_services"):
            score += len(triage_packet["related_services"])

        if triage_packet.get("severity_level", 0) > 7:
            score += 2

        return min(score, 10)  # Cap at 10

    def _calculate_context_richness(self, triage_packet: Dict[str, Any]) -> float:
        """Calculate context richness score."""

        richness = 0.0

        # Check for various context elements
        if triage_packet.get("affected_files"):
            richness += 0.2
        if triage_packet.get("error_patterns"):
            richness += 0.2
        if triage_packet.get("impact_analysis"):
            richness += 0.2
        if triage_packet.get("related_services"):
            richness += 0.2
        if triage_packet.get("temporal_context"):
            richness += 0.2

        return min(richness, 1.0)  # Cap at 1.0

    async def _generate_optimized_prompt(self, context: PromptContext) -> str:
        """Generate optimized prompt using adaptive strategy."""

        if self.config.enable_meta_prompt:
            try:
                # Use meta-prompt generation for complex cases
                if context.issue_context.complexity_score >= 7:
                    # Create MetaPromptContext for meta-prompt generation
                    meta_context = MetaPromptContext(
                        issue_context=context.issue_context.to_dict(),
                        repository_context=context.repository_context.to_dict(),
                        triage_packet={},  # Empty for now, would be populated from triage
                        historical_logs=[],  # Empty for now, would be populated from logs
                        configs={},  # Empty for now, would be populated from configs
                        flow_id="unknown",  # Would be populated from flow
                    )
                    return await self.meta_prompt_generator.generate_optimized_prompt(
                        meta_context
                    )
            except Exception as e:
                self.logger.warning(f"Meta-prompt generation failed: {e}")

        # Fallback to adaptive strategy
        # Create a TaskContext for the adaptive strategy
        task_context = TaskContext(
            task_type="issue_analysis",
            complexity_score=context.issue_context.complexity_score,
            context_variability=0.5,  # Default value
            business_impact=context.issue_context.severity_level,
            accuracy_requirement=0.9,  # High accuracy for issue analysis
            latency_requirement=5000,  # 5 seconds
            context_richness=context.issue_context.context_richness,
            frequency="medium",  # Default value
            cost_sensitivity=0.3,  # Low cost sensitivity
        )

        return await self.adaptive_strategy.get_optimal_prompt(
            task_context,
            context.issue_context.to_dict(),
            context.repository_context.to_dict(),
        )

    async def _execute_analysis(
        self, prompt: str, context: PromptContext
    ) -> Dict[str, Any]:
        """Execute the analysis with the generated prompt."""

        try:
            response = await self.main_model.generate_content_async(prompt)

            if not response.text:
                raise ValueError("Empty response from model")

            # Parse the response
            result = json.loads(response.text)

            return {
                "success": True,
                "analysis": result,
                "prompt_used": prompt,
                "context": context.to_dict(),
            }

        except Exception as e:
            self.logger.error(f"Analysis execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "prompt_used": prompt,
                "context": context.to_dict(),
            }

    async def _validate_and_refine(
        self, analysis_result: Dict[str, Any], context: PromptContext
    ) -> Dict[str, Any]:
        """Validate and refine the analysis result."""

        if not analysis_result.get("success", False):
            return analysis_result

        # Basic validation
        analysis = analysis_result.get("analysis", {})

        if not analysis.get("root_cause_analysis"):
            analysis_result["success"] = False
            analysis_result["error"] = "Missing root cause analysis"
            return analysis_result

        if not analysis.get("proposed_fix"):
            analysis_result["success"] = False
            analysis_result["error"] = "Missing proposed fix"
            return analysis_result

        if not analysis.get("code_patch"):
            analysis_result["success"] = False
            analysis_result["error"] = "Missing code patch"
            return analysis_result

        return analysis_result

    async def _fallback_analysis(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Fallback analysis using simple prompt."""

        self.logger.info("Using fallback analysis")

        # Simple fallback prompt
        prompt = f"""
        Analyze the following issue and provide a fix:
        
        Triage Packet: {json.dumps(triage_packet, indent=2)}
        Historical Logs: {historical_logs[:5]}  # Limit to first 5 logs
        Configs: {json.dumps(configs, indent=2)}
        
        Provide a JSON response with:
        - root_cause_analysis: Analysis of the root cause
        - proposed_fix: Description of the proposed fix
        - code_patch: Complete corrected code
        """

        try:
            response = await self.main_model.generate_content_async(prompt)

            if not response.text:
                raise ValueError("Empty response from model")

            result = json.loads(response.text)

            return {
                "success": True,
                "analysis": result,
                "prompt_used": prompt,
                "fallback": True,
            }

        except Exception as e:
            self.logger.error(f"Fallback analysis failed: {e}")
            return {"success": False, "error": str(e), "fallback": True}
