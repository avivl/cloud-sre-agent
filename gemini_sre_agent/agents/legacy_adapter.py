"""
Legacy Adapter for Backward Compatibility.

This module provides adapters that allow the original agent interfaces to work
with the new enhanced multi-provider system while maintaining full backward compatibility.
"""

import logging
from typing import Any, Dict, List, Optional

from ..llm.config import LLMConfig
from .enhanced_analysis_agent import EnhancedAnalysisAgent
from .enhanced_remediation_agent import EnhancedRemediationAgent
from .enhanced_triage_agent import EnhancedTriageAgent

logger = logging.getLogger(__name__)


class LegacyTriageAgentAdapter:
    """
    Legacy adapter for TriageAgent that uses the enhanced system internally.
    
    Maintains 100% backward compatibility with the original TriageAgent interface
    while using the new multi-provider system under the hood.
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        triage_model: str,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the legacy adapter.

        Args:
            project_id: The Google Cloud project ID (for compatibility)
            location: The GCP region (for compatibility)
            triage_model: The name of the Gemini model (for compatibility)
            llm_config: Optional LLM configuration for enhanced features
        """
        self.project_id = project_id
        self.location = location
        self.triage_model = triage_model
        
        # Initialize enhanced agent if config is provided
        if llm_config:
            self.enhanced_agent = EnhancedTriageAgent(llm_config)
            self.use_enhanced = True
            logger.info(
                f"[LEGACY_ADAPTER] TriageAgent adapter initialized with enhanced system: "
                f"project={project_id}, location={location}, model={triage_model}"
            )
        else:
            self.enhanced_agent = None
            self.use_enhanced = False
            logger.info(
                f"[LEGACY_ADAPTER] TriageAgent adapter initialized in legacy mode: "
                f"project={project_id}, location={location}, model={triage_model}"
            )

    async def analyze_logs(self, logs: List[str], flow_id: str):
        """
        Analyze logs using either enhanced or legacy system.

        Args:
            logs: List of log entries to analyze
            flow_id: Flow ID for tracking this processing pipeline

        Returns:
            TriagePacket: Structured triage information
        """
        if self.use_enhanced and self.enhanced_agent:
            # Use enhanced system
            response = await self.enhanced_agent.analyze_logs(logs, flow_id)
            # Convert to legacy format
            return await self.enhanced_agent.analyze_logs_legacy(logs, flow_id)
        else:
            # Fall back to original implementation
            from ..triage_agent import TriageAgent
            original_agent = TriageAgent(self.project_id, self.location, self.triage_model)
            return await original_agent.analyze_logs(logs, flow_id)


class LegacyAnalysisAgentAdapter:
    """
    Legacy adapter for AnalysisAgent that uses the enhanced system internally.
    
    Maintains 100% backward compatibility with the original AnalysisAgent interface
    while using the new multi-provider system under the hood.
    """

    def __init__(
        self,
        project_id: str,
        location: str,
        analysis_model: str,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the legacy adapter.

        Args:
            project_id: The Google Cloud project ID (for compatibility)
            location: The GCP region (for compatibility)
            analysis_model: The name of the Gemini model (for compatibility)
            llm_config: Optional LLM configuration for enhanced features
        """
        self.project_id = project_id
        self.location = location
        self.analysis_model = analysis_model
        
        # Initialize enhanced agent if config is provided
        if llm_config:
            self.enhanced_agent = EnhancedAnalysisAgent(llm_config)
            self.use_enhanced = True
            logger.info(
                f"[LEGACY_ADAPTER] AnalysisAgent adapter initialized with enhanced system: "
                f"project={project_id}, location={location}, model={analysis_model}"
            )
        else:
            self.enhanced_agent = None
            self.use_enhanced = False
            logger.info(
                f"[LEGACY_ADAPTER] AnalysisAgent adapter initialized in legacy mode: "
                f"project={project_id}, location={location}, model={analysis_model}"
            )

    async def analyze_issue(
        self,
        triage_packet: Any,
        historical_logs: List[str],
        configs: Dict[str, str],
        flow_id: str,
    ):
        """
        Analyze an issue using either enhanced or legacy system.

        Args:
            triage_packet: The triage information for the issue
            historical_logs: List of relevant historical log entries
            configs: Dictionary of configuration files
            flow_id: Flow ID for tracking this processing pipeline

        Returns:
            RemediationPlan: Structured remediation plan
        """
        if self.use_enhanced and self.enhanced_agent:
            # Use enhanced system
            return await self.enhanced_agent.analyze_issue(
                triage_packet, historical_logs, configs, flow_id
            )
        else:
            # Fall back to original implementation
            from ..analysis_agent import AnalysisAgent
            original_agent = AnalysisAgent(self.project_id, self.location, self.analysis_model)
            return original_agent.analyze_issue(triage_packet, historical_logs, configs, flow_id)


class LegacyRemediationAgentAdapter:
    """
    Legacy adapter for RemediationAgent that uses the enhanced system internally.
    
    Maintains 100% backward compatibility with the original RemediationAgent interface
    while using the new multi-provider system under the hood.
    """

    def __init__(
        self,
        github_token: str,
        repo_name: str,
        use_local_patches: bool = False,
        patch_dir: str = "/tmp/real_patches",
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        Initialize the legacy adapter.

        Args:
            github_token: The GitHub personal access token
            repo_name: The name of the GitHub repository
            use_local_patches: Whether to use local patches instead of GitHub
            patch_dir: Directory for local patches when use_local_patches is True
            llm_config: Optional LLM configuration for enhanced features
        """
        self.github_token = github_token
        self.repo_name = repo_name
        self.use_local_patches = use_local_patches
        self.patch_dir = patch_dir
        
        # Initialize enhanced agent if config is provided
        if llm_config:
            self.enhanced_agent = EnhancedRemediationAgent(
                llm_config=llm_config,
                github_token=github_token,
                repo_name=repo_name,
                use_local_patches=use_local_patches,
                patch_dir=patch_dir,
            )
            self.use_enhanced = True
            logger.info(
                f"[LEGACY_ADAPTER] RemediationAgent adapter initialized with enhanced system: "
                f"repo={repo_name}, use_local_patches={use_local_patches}"
            )
        else:
            self.enhanced_agent = None
            self.use_enhanced = False
            logger.info(
                f"[LEGACY_ADAPTER] RemediationAgent adapter initialized in legacy mode: "
                f"repo={repo_name}, use_local_patches={use_local_patches}"
            )

    async def create_pull_request(
        self,
        remediation_plan: Any,
        branch_name: str,
        base_branch: str,
        flow_id: str,
        issue_id: str,
    ) -> str:
        """
        Create a pull request using either enhanced or legacy system.

        Args:
            remediation_plan: The remediation plan containing the service code fix
            branch_name: The name of the new branch to create for the pull request
            base_branch: The name of the base branch to merge into
            flow_id: The flow ID for tracking this processing pipeline
            issue_id: The issue ID from the triage analysis

        Returns:
            str: The HTML URL of the created pull request or local patch file path
        """
        if self.use_enhanced and self.enhanced_agent:
            # Use enhanced system
            return await self.enhanced_agent.create_pull_request_legacy(
                remediation_plan, branch_name, base_branch, flow_id, issue_id
            )
        else:
            # Fall back to original implementation
            from ..remediation_agent import RemediationAgent
            original_agent = RemediationAgent(
                self.github_token, self.repo_name, self.use_local_patches, self.patch_dir
            )
            return await original_agent.create_pull_request(
                remediation_plan, branch_name, base_branch, flow_id, issue_id
            )


# Convenience functions for easy migration
def create_enhanced_triage_agent(
    project_id: str,
    location: str,
    triage_model: str,
    llm_config: LLMConfig,
) -> LegacyTriageAgentAdapter:
    """Create a triage agent with enhanced capabilities."""
    return LegacyTriageAgentAdapter(project_id, location, triage_model, llm_config)


def create_enhanced_analysis_agent(
    project_id: str,
    location: str,
    analysis_model: str,
    llm_config: LLMConfig,
) -> LegacyAnalysisAgentAdapter:
    """Create an analysis agent with enhanced capabilities."""
    return LegacyAnalysisAgentAdapter(project_id, location, analysis_model, llm_config)


def create_enhanced_remediation_agent(
    github_token: str,
    repo_name: str,
    llm_config: LLMConfig,
    use_local_patches: bool = False,
    patch_dir: str = "/tmp/real_patches",
) -> LegacyRemediationAgentAdapter:
    """Create a remediation agent with enhanced capabilities."""
    return LegacyRemediationAgentAdapter(
        github_token, repo_name, use_local_patches, patch_dir, llm_config
    )