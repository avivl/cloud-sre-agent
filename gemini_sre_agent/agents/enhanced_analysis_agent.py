"""
Enhanced Analysis Agent with Multi-Provider Support.

This module provides an enhanced AnalysisAgent that uses the new multi-provider
LLM system while maintaining backward compatibility with the original interface.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from ..llm.base import ModelType
from ..llm.common.enums import ProviderType
from ..llm.config import LLMConfig
from ..llm.strategy_manager import OptimizationGoal
from .enhanced_base import EnhancedBaseAgent
from .response_models import RemediationResponse

logger = logging.getLogger(__name__)


class EnhancedAnalysisAgent(EnhancedBaseAgent[RemediationResponse]):
    """
    Enhanced Analysis Agent with multi-provider support.
    
    Provides intelligent model selection for deep analysis tasks while maintaining
    backward compatibility with the original AnalysisAgent interface.
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        primary_model: Optional[str] = None,
        fallback_model: Optional[str] = None,
        optimization_goal: OptimizationGoal = OptimizationGoal.QUALITY,
        provider_preference: Optional[List[ProviderType]] = None,
        max_cost: Optional[float] = None,
        min_quality: Optional[float] = 0.8,
        **kwargs: Any,
    ):
        """
        Initialize the enhanced analysis agent.

        Args:
            llm_config: LLM configuration for multi-provider support
            primary_model: Primary model for analysis
            fallback_model: Fallback model for error recovery
            optimization_goal: Strategy for model selection (default: QUALITY)
            provider_preference: Preferred providers in order
            max_cost: Maximum cost per 1k tokens
            min_quality: Minimum quality score required
            **kwargs: Additional arguments for the base agent
        """
        super().__init__(
            llm_config=llm_config,
            response_model=RemediationResponse,
            primary_model=primary_model,
            fallback_model=fallback_model,
            optimization_goal=optimization_goal,
            provider_preference=provider_preference,
            model_type_preference=ModelType.SMART,
            max_cost=max_cost,
            min_quality=min_quality,
            **kwargs,
        )

        logger.info("EnhancedAnalysisAgent initialized with quality-focused optimization")

    async def analyze_issue(
        self,
        triage_data: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, str],
        flow_id: str,
    ) -> RemediationResponse:
        """
        Analyze an issue using intelligent model selection and return structured remediation response.

        Args:
            triage_data: Triage information for the issue
            historical_logs: List of relevant historical log entries
            configs: Dictionary of configuration files
            flow_id: Flow ID for tracking this processing pipeline

        Returns:
            RemediationResponse: Structured remediation plan
        """
        logger.info(
            f"[ENHANCED_ANALYSIS] Analyzing issue: flow_id={flow_id}, "
            f"historical_logs={len(historical_logs)}, configs={len(configs)}"
        )

        # Build the analysis prompt
        prompt = self._build_analysis_prompt(triage_data, historical_logs, configs)
        
        # Use the enhanced base agent's intelligent model selection
        response = await self.execute(
            prompt_name="analysis_planning",
            prompt_args={
                "input": prompt,
                "context": {
                    "task_type": "analysis",
                    "triage_data": triage_data,
                    "log_count": len(historical_logs),
                    "config_count": len(configs),
                    "flow_id": flow_id,
                },
            },
            optimization_goal=OptimizationGoal.QUALITY,
        )

        logger.info(
            f"[ENHANCED_ANALYSIS] Analysis complete: flow_id={flow_id}, "
            f"priority={response.priority}, effort={response.estimated_effort}"
        )
        
        return response

    def _build_analysis_prompt(
        self,
        triage_data: Dict[str, Any],
        historical_logs: List[str],
        configs: Dict[str, str],
    ) -> str:
        """Build the analysis prompt."""
        triage_json = json.dumps(triage_data, indent=2)
        logs_str = json.dumps(historical_logs, indent=2)
        configs_str = json.dumps(configs, indent=2)
        
        return f"""
You are an expert SRE Analysis Agent. Your task is to perform a deep root cause analysis 
of the provided issue, considering the triage information, log context, and relevant 
configurations. Then, generate a comprehensive remediation plan focused on SERVICE CODE fixes.

Triage Information:
{triage_json}

Log Context (including current triggering log):
{logs_str}

Configurations:
{configs_str}

Provide a structured remediation plan with:
1. Detailed root cause analysis
2. Clear description of the proposed service code fix
3. Complete code patch with proper file path comment (e.g., # FILE: path/to/file.py)
4. Priority level (low, medium, high, critical)
5. Estimated effort required

Focus on service code fixes that address the root cause of the issue.
"""

