"""
Enhanced Triage Agent with Multi-Provider Support.

This module provides an enhanced TriageAgent that uses the new multi-provider
LLM system while maintaining backward compatibility with the original interface.
"""

import logging
from typing import Any, Dict, List, Optional

from ..llm.base import ModelType
from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .enhanced_base import EnhancedBaseAgent
from .response_models import TriageResponse

logger = logging.getLogger(__name__)


class EnhancedTriageAgent(EnhancedBaseAgent[TriageResponse]):
    """
    Enhanced Triage Agent with multi-provider support.
    
    Provides intelligent model selection for triage tasks while maintaining
    backward compatibility with the original TriageAgent interface.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_name: str = "triage_agent",
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced triage agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            agent_name: Name of the agent for configuration lookup
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=TriageResponse,
            agent_name=agent_name,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.SMART,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info("EnhancedTriageAgent initialized with quality-focused optimization")

    async def analyze_logs(self, logs: List[str], flow_id: str) -> TriageResponse:
        """
        Analyze logs using intelligent model selection and return structured triage response.

        Args:
            logs: List of log entries to analyze
            flow_id: Flow ID for tracking this processing pipeline

        Returns:
            TriageResponse: Structured triage information
        """
        logger.info(
            f"[ENHANCED_TRIAGE] Analyzing {len(logs)} log entries: flow_id={flow_id}"
        )

        # Construct the prompt for triage analysis
        prompt = self._build_triage_prompt(logs)
        
        # Use the enhanced base agent's intelligent model selection
        response = await self.execute(
            prompt_name="triage_analysis",
            prompt_args={
                "input": prompt,
                "context": {
                    "task_type": "triage",
                    "log_count": len(logs),
                    "flow_id": flow_id,
                },
            },
            optimization_goal=OptimizationGoal.QUALITY,
        )

        logger.info(
            f"[ENHANCED_TRIAGE] Triage analysis complete: flow_id={flow_id}, "
            f"severity={response.severity}, category={response.category}"
        )
        
        return response

    def _build_triage_prompt(self, logs: List[str]) -> str:
        """Build the triage analysis prompt."""
        log_entries = "\n".join(logs)
        
        return f"""
You are an expert SRE Triage Agent. Your task is to analyze the provided log entries, 
identify any critical issues, and provide a structured triage assessment.

Analyze the following log entries:
{log_entries}

Provide a structured analysis with:
1. Severity level (low, medium, high, critical)
2. Issue category (performance, error, security, availability, etc.)
3. Urgency level (low, medium, high, critical)
4. Clear description of the issue
5. Suggested immediate actions

Focus on identifying patterns, anomalies, and potential service impacts.
"""


    def _severity_to_score(self, severity: str) -> int:
        """Convert severity string to numeric score."""
        severity_map = {
            "low": 2,
            "medium": 5,
            "high": 8,
            "critical": 10,
        }
        return severity_map.get(severity.lower(), 5)
