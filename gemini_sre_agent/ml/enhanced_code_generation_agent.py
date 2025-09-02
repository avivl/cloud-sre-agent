# gemini_sre_agent/ml/enhanced_code_generation_agent.py

import time
from typing import Any, Dict, List

from .code_generation_models import CodeGenerationResult
from .code_generator_factory import CodeGeneratorFactory
from .enhanced_analysis_agent import EnhancedAnalysisAgent, EnhancedAnalysisConfig
from .enhanced_code_generation_config import EnhancedCodeGenerationConfig
from .enhanced_code_generation_learning import EnhancedCodeGenerationLearning
from .prompt_context_models import IssueContext, IssueType, RepositoryContext


class EnhancedCodeGenerationAgent:
    """Enhanced analysis agent with integrated code generation capabilities"""

    def __init__(self, config: EnhancedCodeGenerationConfig):
        self.config = config
        self.enhanced_analysis_agent = EnhancedAnalysisAgent(
            EnhancedAnalysisConfig(
                project_id=config.project_id,
                location=config.location,
                main_model=config.main_model,
                meta_model=config.meta_model,
            )
        )
        self.code_generator_factory = CodeGeneratorFactory()
        self.learning = EnhancedCodeGenerationLearning()

    async def analyze_andGenerate(
        self,
        triage_packet: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, Any],
        flow_id: str,
    ) -> Dict[str, Any]:
        """Analyze issue and generate code fix using our unified approach"""
        start_time = time.time()

        try:
            # 1. Use existing enhanced analysis for root cause analysis
            analysis_result = await self.enhanced_analysis_agent.analyze_issue(
                triage_packet, historical_logs, configs, flow_id
            )

            if not analysis_result.get("success", False):
                return {
                    "success": False,
                    "error": "Analysis failed",
                    "analysis_result": analysis_result,
                }

            # 2. Extract issue context for code generation
            issue_context, repository_context = self._build_issue_context(
                triage_packet, analysis_result, configs
            )

            # 3. Generate code fix using specialized generator
            code_generation_result = await self._generate_code_fix(
                issue_context, repository_context
            )

            # 4. Integrate results
            final_result = self._integrate_results(
                analysis_result, code_generation_result
            )

            # 5. Record generation history for learning
            self.learning.record_generation_history(
                issue_context, code_generation_result, start_time
            )

            # 6. Update learning data
            if self.config.enable_learning:
                self.learning.update_learning_data(
                    issue_context, code_generation_result
                )

            return final_result

        except Exception as e:
            generation_time = int((time.time() - start_time) * 1000)
            return {
                "success": False,
                "error": str(e),
                "generation_time_ms": generation_time,
            }

    def _build_issue_context(
        self,
        triage_packet: Dict[str, Any],
        analysis_result: Dict[str, Any],
        configs: Dict[str, Any],
    ) -> tuple[IssueContext, RepositoryContext]:
        """Build issue context from triage packet and analysis result"""
        # Extract issue type from triage packet or analysis
        issue_type_str = triage_packet.get("issue_type", "unknown")
        try:
            issue_type = IssueType(issue_type_str)
        except ValueError:
            issue_type = IssueType.UNKNOWN

        # Build repository context
        repository_context = RepositoryContext(
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

        # Create issue context
        issue_context = IssueContext(
            issue_type=issue_type,
            affected_files=triage_packet.get("affected_files", []),
            error_patterns=analysis_result.get("error_patterns", []),
            severity_level=triage_packet.get("severity", 5),
            impact_analysis=analysis_result.get("impact_analysis", {}),
            related_services=triage_packet.get("related_services", []),
            temporal_context=analysis_result.get("temporal_context", {}),
            user_impact=analysis_result.get("user_impact", "unknown"),
            business_impact=analysis_result.get("business_impact", "unknown"),
            complexity_score=analysis_result.get("complexity_score", 5),
            context_richness=0.8,
        )

        return issue_context, repository_context

    async def _generate_code_fix(
        self, issue_context: IssueContext, repository_context: RepositoryContext
    ) -> CodeGenerationResult:
        """Generate code fix using appropriate specialized generator"""
        # Get appropriate generator for issue type
        generator = self.code_generator_factory.create_generator(
            issue_context.issue_type
        )

        # Set context for the generator
        from .prompt_context_models import PromptContext

        prompt_context = PromptContext(
            issue_context=issue_context,
            repository_context=repository_context,
            generator_type=generator._get_generator_type(),
        )
        generator.set_context(prompt_context)

        # Generate code fix
        return await generator.generate_code_fix(issue_context)

    def _integrate_results(
        self,
        analysis_result: Dict[str, Any],
        code_generation_result: CodeGenerationResult,
    ) -> Dict[str, Any]:
        """Integrate analysis and code generation results"""
        if not code_generation_result.success:
            return {
                "success": False,
                "error": "Code generation failed",
                "analysis_result": analysis_result,
                "code_generation_error": code_generation_result.error_message,
            }

        # Check if human review is required
        requires_human_review = (
            code_generation_result.quality_score < self.config.human_review_threshold
            or code_generation_result.validation_result
            and len(code_generation_result.validation_result.get_critical_issues()) > 0
        )

        # Add null checks for code_fix and validation_result
        code_fix = code_generation_result.code_fix
        validation_result = code_generation_result.validation_result

        return {
            "success": True,
            "analysis": analysis_result.get("analysis", {}),
            "code_generation": {
                "success": code_generation_result.success,
                "code_fix": {
                    "code": code_fix.code if code_fix else "",
                    "language": code_fix.language if code_fix else "",
                    "file_path": code_fix.file_path if code_fix else "",
                    "tests": code_fix.tests if code_fix else "",
                    "documentation": code_fix.documentation if code_fix else "",
                },
                "validation": {
                    "is_valid": (
                        validation_result.is_valid if validation_result else False
                    ),
                    "quality_score": (
                        validation_result.quality_score if validation_result else 0.0
                    ),
                    "critical_issues": (
                        len(validation_result.get_critical_issues())
                        if validation_result
                        else 0
                    ),
                    "high_priority_issues": (
                        len(validation_result.get_high_priority_issues())
                        if validation_result
                        else 0
                    ),
                },
                "generation_time_ms": code_generation_result.generation_time_ms,
                "iteration_count": code_generation_result.iteration_count,
            },
            "requires_human_review": requires_human_review,
            "quality_score": code_generation_result.quality_score,
            "prompt_used": analysis_result.get("prompt_used", ""),
            "context": analysis_result.get("context", {}),
            "generation_summary": code_generation_result.get_summary(),
        }

    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get statistics about code generation performance"""
        return self.learning.get_generation_statistics()

    def get_generator_info(self) -> Dict[str, Any]:
        """Get information about available generators"""
        return {
            "supported_issue_types": [
                issue_type.value
                for issue_type in self.code_generator_factory.get_supported_issue_types()
            ],
            "generator_count": self.code_generator_factory.get_generator_count(),
            "generator_domains": self.code_generator_factory.get_generator_domains(),
            "generator_details": self.code_generator_factory.get_all_generators_info(),
        }

    def reset_learning_data(self):
        """Reset learning data (useful for testing or starting fresh)"""
        self.learning.reset_learning_data()

    def export_learning_data(self) -> Dict[str, Any]:
        """Export learning data for external analysis"""
        return self.learning.export_learning_data(self.get_generator_info())
