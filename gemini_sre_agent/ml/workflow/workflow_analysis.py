# gemini_sre_agent/ml/workflow/workflow_analysis.py

"""
Workflow analysis module for the unified workflow orchestrator.

This module handles analysis operations within the workflow, including
issue analysis, pattern detection, and context analysis.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ...core.interfaces import ProcessableComponent
from ...core.types import ConfigDict, Timestamp
from ...llm.base import ModelType
from ...llm.config import LLMConfig
from ..enhanced_analysis_agent import EnhancedAnalysisAgent
from ..prompt_context_models import IssueContext, RepositoryContext

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """
    Result of workflow analysis operations.

    This class holds the results of analysis operations including
    detected patterns, insights, and recommendations.
    """

    # Analysis metadata
    analysis_id: str
    workflow_id: str
    analysis_type: str
    timestamp: Timestamp

    # Analysis results
    detected_patterns: List[Dict[str, Any]]
    insights: List[str]
    recommendations: List[str]
    confidence_score: float

    # Performance metrics
    analysis_duration: float
    patterns_analyzed: int
    success: bool
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary."""
        return {
            "analysis_id": self.analysis_id,
            "workflow_id": self.workflow_id,
            "analysis_type": self.analysis_type,
            "timestamp": self.timestamp,
            "detected_patterns": self.detected_patterns,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "confidence_score": self.confidence_score,
            "analysis_duration": self.analysis_duration,
            "patterns_analyzed": self.patterns_analyzed,
            "success": self.success,
            "error_message": self.error_message,
        }


class WorkflowAnalysisEngine(ProcessableComponent[Dict[str, Any], AnalysisResult]):
    """
    Analysis engine for workflow operations.

    This class handles all analysis operations within the workflow,
    including issue analysis, pattern detection, and context analysis.
    """

    def __init__(
        self,
        component_id: str = "workflow_analysis_engine",
        name: str = "Workflow Analysis Engine",
        config: Optional[ConfigDict] = None,
    ) -> None:
        """
        Initialize the workflow analysis engine.

        Args:
            component_id: Unique identifier for the component
            name: Human-readable name for the component
            config: Optional initial configuration
        """
        super().__init__(component_id, name, config)

        # Initialize analysis agent with default config
        llm_config = LLMConfig(
            default_provider="gemini",
            default_model_type=ModelType.SMART,
            enable_fallback=True,
            enable_monitoring=True,
        )
        self.analysis_agent = EnhancedAnalysisAgent(
            llm_config=llm_config, agent_name="workflow_analysis_agent"
        )

        # Analysis tracking
        self.analysis_count = 0
        self.total_analysis_time = 0.0
        self.successful_analyses = 0
        self.failed_analyses = 0
        self.error_count = 0

    async def analyze_issue(
        self,
        issue_context: IssueContext,
        repository_context: RepositoryContext,
        workflow_id: str,
        analysis_type: str = "comprehensive",
    ) -> AnalysisResult:
        """
        Analyze an issue within the workflow context.

        Args:
            issue_context: Issue context to analyze
            repository_context: Repository context
            workflow_id: Workflow identifier
            analysis_type: Type of analysis to perform

        Returns:
            Analysis result
        """
        start_time = time.time()
        analysis_id = f"analysis_{workflow_id}_{int(time.time())}"

        try:
            logger.info(f"Starting {analysis_type} analysis for workflow {workflow_id}")

            # Create triage data from issue context
            triage_data = {
                "issue_type": issue_context.issue_type.value,
                "affected_files": issue_context.affected_files,
                "severity_level": issue_context.severity_level,
                "error_patterns": issue_context.error_patterns,
                "impact_analysis": issue_context.impact_analysis,
            }

            # Create historical logs (empty for now)
            historical_logs = []

            # Create configs from repository context
            configs = {
                "architecture_type": repository_context.architecture_type,
                "technology_stack": repository_context.technology_stack,
                "coding_standards": repository_context.coding_standards,
            }

            # Perform analysis using the enhanced analysis agent
            analysis_response = await self.analysis_agent.analyze_issue(
                triage_data=triage_data,
                historical_logs=historical_logs,
                configs=configs,
                flow_id=workflow_id,
            )

            # Extract patterns and insights
            detected_patterns = self._extract_patterns(analysis_response)
            insights = self._extract_insights(analysis_response)
            recommendations = self._extract_recommendations(analysis_response)
            confidence_score = self._calculate_confidence(analysis_response)

            analysis_duration = time.time() - start_time

            result = AnalysisResult(
                analysis_id=analysis_id,
                workflow_id=workflow_id,
                analysis_type=analysis_type,
                timestamp=time.time(),
                detected_patterns=detected_patterns,
                insights=insights,
                recommendations=recommendations,
                confidence_score=confidence_score,
                analysis_duration=analysis_duration,
                patterns_analyzed=len(detected_patterns),
                success=True,
            )

            # Update metrics
            self.analysis_count += 1
            self.total_analysis_time += analysis_duration
            self.successful_analyses += 1

            logger.info(f"Completed analysis {analysis_id} in {analysis_duration:.3f}s")
            return result

        except Exception as e:
            analysis_duration = time.time() - start_time
            error_msg = f"Analysis failed: {str(e)}"

            logger.error(f"Analysis {analysis_id} failed: {error_msg}")

            result = AnalysisResult(
                analysis_id=analysis_id,
                workflow_id=workflow_id,
                analysis_type=analysis_type,
                timestamp=time.time(),
                detected_patterns=[],
                insights=[],
                recommendations=[],
                confidence_score=0.0,
                analysis_duration=analysis_duration,
                patterns_analyzed=0,
                success=False,
                error_message=error_msg,
            )

            # Update metrics
            self.analysis_count += 1
            self.total_analysis_time += analysis_duration
            self.failed_analyses += 1

            return result

    async def analyze_patterns(
        self,
        patterns: List[Dict[str, Any]],
        workflow_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        Analyze patterns for insights and recommendations.

        Args:
            patterns: Patterns to analyze
            workflow_id: Workflow identifier
            context: Optional additional context

        Returns:
            Analysis result
        """
        start_time = time.time()
        analysis_id = f"pattern_analysis_{workflow_id}_{int(time.time())}"

        try:
            logger.info(f"Starting pattern analysis for workflow {workflow_id}")

            # Create triage data from patterns
            triage_data = {
                "patterns": patterns,
                "analysis_type": "pattern_analysis",
                "context": context or {},
            }

            # Create historical logs (empty for now)
            historical_logs = []

            # Create configs (empty for now)
            configs = {}

            # Perform pattern analysis using the enhanced analysis agent
            analysis_response = await self.analysis_agent.analyze_issue(
                triage_data=triage_data,
                historical_logs=historical_logs,
                configs=configs,
                flow_id=workflow_id,
            )

            # Extract results
            detected_patterns = self._extract_patterns(analysis_response)
            insights = self._extract_insights(analysis_response)
            recommendations = self._extract_recommendations(analysis_response)
            confidence_score = self._calculate_confidence(analysis_response)

            analysis_duration = time.time() - start_time

            result = AnalysisResult(
                analysis_id=analysis_id,
                workflow_id=workflow_id,
                analysis_type="pattern_analysis",
                timestamp=time.time(),
                detected_patterns=detected_patterns,
                insights=insights,
                recommendations=recommendations,
                confidence_score=confidence_score,
                analysis_duration=analysis_duration,
                patterns_analyzed=len(patterns),
                success=True,
            )

            # Update metrics
            self.analysis_count += 1
            self.total_analysis_time += analysis_duration
            self.successful_analyses += 1

            logger.info(
                f"Completed pattern analysis {analysis_id} in {analysis_duration:.3f}s"
            )
            return result

        except Exception as e:
            analysis_duration = time.time() - start_time
            error_msg = f"Pattern analysis failed: {str(e)}"

            logger.error(f"Pattern analysis {analysis_id} failed: {error_msg}")

            result = AnalysisResult(
                analysis_id=analysis_id,
                workflow_id=workflow_id,
                analysis_type="pattern_analysis",
                timestamp=time.time(),
                detected_patterns=[],
                insights=[],
                recommendations=[],
                confidence_score=0.0,
                analysis_duration=analysis_duration,
                patterns_analyzed=len(patterns),
                success=False,
                error_message=error_msg,
            )

            # Update metrics
            self.analysis_count += 1
            self.total_analysis_time += analysis_duration
            self.failed_analyses += 1

            return result

    def process(self, input_data: Dict[str, Any]) -> AnalysisResult:
        """
        Process analysis request (synchronous wrapper).

        Args:
            input_data: Analysis request data

        Returns:
            Analysis result
        """
        # This is a synchronous wrapper for the async methods
        # In practice, this would be called from an async context
        raise NotImplementedError("Use async methods for analysis operations")

    def initialize(self) -> None:
        """Initialize the component."""
        self._status = "initialized"
        logger.info(f"Initialized {self.name}")

    def shutdown(self) -> None:
        """Shutdown the component."""
        self._status = "shutdown"
        logger.info(f"Shutdown {self.name}")

    def configure(self, config: ConfigDict) -> None:
        """
        Configure the component with new settings.

        Args:
            config: Configuration dictionary
        """
        self._config.update(config)
        logger.info(f"Configured {self.name}")

    def validate_config(self, config: ConfigDict) -> bool:
        """
        Validate a configuration.

        Args:
            config: Configuration to validate

        Returns:
            True if valid, False otherwise
        """
        return isinstance(config, dict)

    def set_state(self, key: str, value: Any) -> None:
        """
        Set a state value.

        Args:
            key: State key
            value: State value
        """
        self._state[key] = value

    def get_state(self, key: str, default: Any : Optional[str] = None) -> Any:
        """
        Get a state value.

        Args:
            key: State key
            default: Default value if key not found

        Returns:
            State value or default
        """
        return self._state.get(key, default)

    def clear_state(self, key: Optional[str] = None) -> None:
        """
        Clear state values.

        Args:
            key: Specific key to clear, or None to clear all
        """
        if key is None:
            self._state.clear()
        else:
            self._state.pop(key, None)

    def collect_metrics(self) -> Dict[str, Any]:
        """
        Collect component metrics.

        Returns:
            Dictionary containing metrics
        """
        return self.get_analysis_metrics()

    def _extract_patterns(self, analysis_response: Any) -> List[Dict[str, Any]]:
        """
        Extract patterns from analysis response.

        Args:
            analysis_response: Response from analysis agent

        Returns:
            List of detected patterns
        """
        try:
            if hasattr(analysis_response, "patterns"):
                return analysis_response.patterns
            elif hasattr(analysis_response, "detected_patterns"):
                return analysis_response.detected_patterns
            elif (
                isinstance(analysis_response, dict) and "patterns" in analysis_response
            ):
                return analysis_response["patterns"]
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract patterns: {e}")
            return []

    def _extract_insights(self, analysis_response: Any) -> List[str]:
        """
        Extract insights from analysis response.

        Args:
            analysis_response: Response from analysis agent

        Returns:
            List of insights
        """
        try:
            if hasattr(analysis_response, "insights"):
                return analysis_response.insights
            elif hasattr(analysis_response, "key_insights"):
                return analysis_response.key_insights
            elif (
                isinstance(analysis_response, dict) and "insights" in analysis_response
            ):
                return analysis_response["insights"]
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract insights: {e}")
            return []

    def _extract_recommendations(self, analysis_response: Any) -> List[str]:
        """
        Extract recommendations from analysis response.

        Args:
            analysis_response: Response from analysis agent

        Returns:
            List of recommendations
        """
        try:
            if hasattr(analysis_response, "recommendations"):
                return analysis_response.recommendations
            elif hasattr(analysis_response, "suggestions"):
                return analysis_response.suggestions
            elif (
                isinstance(analysis_response, dict)
                and "recommendations" in analysis_response
            ):
                return analysis_response["recommendations"]
            else:
                return []
        except Exception as e:
            logger.warning(f"Failed to extract recommendations: {e}")
            return []

    def _calculate_confidence(self, analysis_response: Any) -> float:
        """
        Calculate confidence score from analysis response.

        Args:
            analysis_response: Response from analysis agent

        Returns:
            Confidence score (0.0-1.0)
        """
        try:
            if hasattr(analysis_response, "confidence"):
                return float(analysis_response.confidence)
            elif hasattr(analysis_response, "confidence_score"):
                return float(analysis_response.confidence_score)
            elif (
                isinstance(analysis_response, dict)
                and "confidence" in analysis_response
            ):
                return float(analysis_response["confidence"])
            else:
                return 0.5  # Default confidence
        except Exception as e:
            logger.warning(f"Failed to calculate confidence: {e}")
            return 0.5

    def get_analysis_metrics(self) -> Dict[str, Any]:
        """
        Get analysis performance metrics.

        Returns:
            Dictionary containing analysis metrics
        """
        return {
            "total_analyses": self.analysis_count,
            "successful_analyses": self.successful_analyses,
            "failed_analyses": self.failed_analyses,
            "success_rate": (
                (self.successful_analyses / self.analysis_count * 100)
                if self.analysis_count > 0
                else 0.0
            ),
            "total_analysis_time": self.total_analysis_time,
            "average_analysis_time": (
                (self.total_analysis_time / self.analysis_count)
                if self.analysis_count > 0
                else 0.0
            ),
        }

    def get_health_status(self) -> Dict[str, Any]:
        """
        Get the component's health status.

        Returns:
            Dictionary containing health status information
        """
        metrics = self.get_analysis_metrics()

        return {
            "component_id": self.component_id,
            "name": self.name,
            "status": self.status,
            "healthy": self.check_health(),
            "analysis_metrics": metrics,
            "processing_count": self.processing_count,
            "last_processed_at": self.last_processed_at,
        }

    def check_health(self) -> bool:
        """
        Check if the component is healthy.

        Returns:
            True if healthy, False otherwise
        """
        return (
            self.status != "error"
            and self.error_count == 0
            and self.failed_analyses
            < self.successful_analyses  # More successes than failures
        )
