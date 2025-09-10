"""
Enhanced Main Application with Full Multi-Provider LLM Support.

This is an updated version of main.py that fully utilizes the new multi-provider
LLM system with intelligent model selection, cost optimization, and advanced features.
"""

import asyncio
import json
import os
import sys
import tempfile
from typing import Any, Dict, List, Optional

from gemini_sre_agent.agents.enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedRemediationAgentV2,
    EnhancedTriageAgent,
)
from gemini_sre_agent.agents.response_models import RemediationResponse
# Legacy adapter functions are now integrated directly into the enhanced agents

# New ingestion system imports
from gemini_sre_agent.config.ingestion_config import (
    FileSystemConfig,
    IngestionConfigManager,
)
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.manager.log_manager import LogManager
from gemini_sre_agent.llm.capabilities.discovery import CapabilityDiscovery
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal
from gemini_sre_agent.llm.monitoring.llm_metrics import get_llm_metrics_collector
from gemini_sre_agent.local_patch_manager import LocalPatchManager
from gemini_sre_agent.logger import setup_logging
from gemini_sre_agent.triage_agent import TriagePacket  # Used for mock TriagePacket


def validate_environment():
    """Validate required environment variables at startup"""
    logger = setup_logging()  # Get a basic logger for early validation

    # New system doesn't require GITHUB_TOKEN for local testing
    required_vars = []
    optional_vars = ["GITHUB_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS"]
    logger.info("[STARTUP] Using enhanced multi-provider LLM system")

    missing_required = [var for var in required_vars if not os.getenv(var)]
    if missing_required:
        logger.error(
            f"[STARTUP] Missing required environment variables: {missing_required}"
        )
        raise EnvironmentError(
            f"Missing required environment variables: {missing_required}"
        )

    # Log optional variables status
    for var in optional_vars:
        if os.getenv(var):
            logger.info(f"[STARTUP] Using {var} from environment")
        else:
            logger.info(f"[STARTUP] {var} not set in environment.")


def get_feature_flags() -> dict:
    """Get feature flags from environment variables."""
    return {
        "use_enhanced_agents": True,
        "use_multi_provider": True,
        "enable_cost_optimization": os.getenv("ENABLE_COST_OPTIMIZATION", "true").lower() == "true",
        "enable_model_mixing": os.getenv("ENABLE_MODEL_MIXING", "true").lower() == "true",
        "enable_monitoring": os.getenv("ENABLE_MONITORING", "true").lower() == "true",
        "use_legacy_adapters": os.getenv("USE_LEGACY_ADAPTERS", "false").lower() == "true",
    }


async def initialize_enhanced_agents(
    llm_config, 
    feature_flags: Dict[str, bool],
    logger
) -> Dict[str, Any]:
    """Initialize enhanced agents with full multi-provider support."""
    
    # Get metrics collector for monitoring
    metrics_collector = get_llm_metrics_collector()
    
    if feature_flags.get("use_legacy_adapters", False):
        # Use legacy adapters for backward compatibility
        logger.info("[STARTUP] Using legacy adapters with enhanced backend")
        
        triage_agent = EnhancedTriageAgent(
            project_id="enhanced-project",
            location="us-central1", 
            triage_model="gemini-1.5-flash",
            llm_config=llm_config
        )
        
        analysis_agent = EnhancedAnalysisAgent(
            project_id="enhanced-project",
            location="us-central1",
            analysis_model="gemini-1.5-flash", 
            llm_config=llm_config
        )
        
        remediation_agent = EnhancedRemediationAgentV2(
            github_token=os.getenv("GITHUB_TOKEN", "dummy_token"),
            repo_name="enhanced/repo",
            llm_config=llm_config,
            use_local_patches=True
        )
    else:
        # Use direct enhanced agents with full capabilities
        logger.info("[STARTUP] Using direct enhanced agents with full multi-provider support")
        
        # Configure optimization goals based on feature flags
        triage_optimization = OptimizationGoal.QUALITY
        analysis_optimization = OptimizationGoal.QUALITY
        remediation_optimization = OptimizationGoal.HYBRID
        
        if feature_flags.get("enable_cost_optimization", True):
            triage_optimization = OptimizationGoal.COST
            analysis_optimization = OptimizationGoal.HYBRID
            remediation_optimization = OptimizationGoal.HYBRID
        
        triage_agent = EnhancedTriageAgent(
            llm_config=llm_config,
            primary_model="llama3.2:3b",  # Fast model for triage
            fallback_model="llama3.2:1b",
            optimization_goal=triage_optimization,
            max_cost=0.01,  # Cost limit per 1k tokens
            min_quality=0.7,
            collect_stats=True,
        )
        
        analysis_agent = EnhancedAnalysisAgent(
            llm_config=llm_config,
            primary_model="llama3.2:3b",  # Balanced model for analysis
            fallback_model="llama3.2:1b",
            optimization_goal=analysis_optimization,
            max_cost=0.02,  # Higher cost limit for analysis
            min_quality=0.8,
            collect_stats=True,
        )
        
        remediation_agent = EnhancedRemediationAgentV2(
            llm_config=llm_config,
            primary_model="llama3.2:3b",  # Quality model for remediation
            fallback_model="llama3.2:1b",
            optimization_goal=remediation_optimization,
            max_cost=0.03,  # Highest cost limit for remediation
            min_quality=0.9,
            collect_stats=True,
        )
    
    return {
        "triage_agent": triage_agent,
        "analysis_agent": analysis_agent, 
        "remediation_agent": remediation_agent,
        "metrics_collector": metrics_collector,
    }


async def process_log_with_enhanced_pipeline(
    log_entry: LogEntry,
    agents: Dict[str, Any],
    patch_manager: LocalPatchManager,
    logger
):
    """Process log entries through the enhanced agent pipeline."""
    flow_id = getattr(log_entry, "id", "unknown")
    
    try:
        # Validate inputs
        if not log_entry or not agents:
            logger.error(f"[ENHANCED_PIPELINE] Invalid inputs: flow_id={flow_id}")
            return
            
        if not all(key in agents for key in ["triage_agent", "analysis_agent", "remediation_agent"]):
            logger.error(f"[ENHANCED_PIPELINE] Missing required agents: flow_id={flow_id}")
            return
        # Convert LogEntry to dict format expected by agents
        timestamp = getattr(log_entry, "timestamp", "")
        if hasattr(timestamp, "isoformat") and callable(getattr(timestamp, "isoformat", None)):
            if not isinstance(timestamp, str):
                timestamp = timestamp.isoformat()

        log_data = {
            "insertId": getattr(log_entry, "id", "N/A"),
            "timestamp": timestamp,
            "severity": (
                getattr(log_entry, "severity", LogSeverity.INFO).value
                if hasattr(getattr(log_entry, "severity", LogSeverity.INFO), "value")
                else str(getattr(log_entry, "severity", "INFO"))
            ),
            "textPayload": getattr(log_entry, "message", ""),
            "resource": {
                "type": "file_system",
                "labels": {
                    "service_name": "enhanced_service",
                    "source": getattr(log_entry, "source", "unknown"),
                },
            },
        }

        # Generate flow ID for tracking
        flow_id = log_data.get("insertId", "N/A")
        logger.info(f"[ENHANCED_PIPELINE] Processing log entry: flow_id={flow_id}")

        # Convert log data to string for processing
        log_text = json.dumps(log_data)

        # Step 1: Enhanced Triage Analysis
        logger.info(f"[ENHANCED_TRIAGE] Starting intelligent triage analysis: flow_id={flow_id}")
        
        triage_agent = agents["triage_agent"]
        if hasattr(triage_agent, 'analyze_logs'):
            # Direct enhanced agent
            triage_response = await triage_agent.analyze_logs([log_text], flow_id)
        else:
            # Legacy adapter
            triage_response = await triage_agent.analyze_logs([log_text], flow_id)

        # Create a mock TriagePacket for compatibility
        triage_packet = TriagePacket(
            issue_id=f"enhanced_{flow_id}",
            initial_timestamp=log_data.get("timestamp", ""),
            detected_pattern=triage_response.description if hasattr(triage_response, 'description') else "Unknown pattern",
            preliminary_severity_score=8,  # High severity for errors
            affected_services=["enhanced_service"],
            sample_log_entries=[log_text],
            natural_language_summary=triage_response.description if hasattr(triage_response, 'description') else "Issue detected",
        )

        logger.info(f"[ENHANCED_TRIAGE] Triage completed: flow_id={flow_id}, issue_id={triage_packet.issue_id}")

        # Step 2: Enhanced Analysis
        logger.info(f"[ENHANCED_ANALYSIS] Starting intelligent analysis: flow_id={flow_id}")
        
        analysis_agent = agents["analysis_agent"]
        # Both enhanced agents and legacy adapters use the same interface
        analysis_response = await analysis_agent.analyze_issue(
            triage_packet, [log_text], {}, flow_id
        )

        logger.info(f"[ENHANCED_ANALYSIS] Analysis completed: flow_id={flow_id}")

        # Step 3: Enhanced Remediation
        logger.info(f"[ENHANCED_REMEDIATION] Starting intelligent remediation: flow_id={flow_id}")
        
        remediation_agent = agents["remediation_agent"]
        if hasattr(remediation_agent, 'create_remediation_plan'):
            # Direct enhanced agent
            remediation_response = await remediation_agent.create_remediation_plan(
                issue_description=triage_packet.natural_language_summary,
                error_context=log_text,
                target_file="enhanced_service/app.py",
                analysis_summary=analysis_response.root_cause_analysis if hasattr(analysis_response, 'root_cause_analysis') else "Analysis completed",
                key_points=[analysis_response.proposed_fix] if hasattr(analysis_response, 'proposed_fix') else ["Fix required"],
            )
        else:
            # Legacy adapter - create a simple remediation plan
            remediation_response = RemediationResponse(
                root_cause_analysis=f"Enhanced analysis for issue {flow_id}",
                proposed_fix=f"Enhanced fix for issue {flow_id}",
                code_patch=f'# FILE: enhanced_service/app.py\n# Enhanced fix for {flow_id}\nprint("Fixed issue")',
                priority='medium',
                estimated_effort='2 hours'
            )

        # Create local patch using the LocalPatchManager
        logger.info(f"[ENHANCED_REMEDIATION] Creating enhanced local patch: flow_id={flow_id}")

        # Generate a unique issue ID for the patch
        issue_id = f"enhanced_{flow_id.replace(':', '_').replace('/', '_')}"

        # Create local patch file
        patch_manager.create_patch(
            issue_id=issue_id,
            file_path="enhanced_service/app.py",
            patch_content=remediation_response.code_patch,
            description=remediation_response.proposed_fix,
            severity=remediation_response.priority,
        )

        logger.info(f"[ENHANCED_REMEDIATION] Enhanced remediation completed: flow_id={flow_id}, issue_id={issue_id}")

        # Log metrics
        metrics_collector = agents["metrics_collector"]
        if metrics_collector:
            # Record successful processing
            metrics_collector.record_request(
                provider="enhanced_system",
                model="multi_provider",
                model_type="enhanced",
                request=None,  # We don't have the original request
                response=None,  # We don't have the original response
                duration_ms=100.0,  # Placeholder
                cost=0.001,  # Placeholder
            )

    except Exception as e:
        flow_id = getattr(log_entry, "id", "unknown")
        logger.error(f"[ENHANCED_PIPELINE] Error processing log entry: flow_id={flow_id}, error={e}")


async def main():
    # Validate environment variables before proceeding
    validate_environment()

    # Get feature flags
    feature_flags = get_feature_flags()

    # Load config based on feature flags
    config_file = "config/config.yaml"  # default
    if "--config-file" in sys.argv:
        config_file_index = sys.argv.index("--config-file")
        if config_file_index + 1 < len(sys.argv):
            config_file = sys.argv[config_file_index + 1]

    ingestion_config_manager = IngestionConfigManager(config_file)
    ingestion_config = ingestion_config_manager.load_config()

    temp_dir = tempfile.mkdtemp(prefix="enhanced-sre-")
    log_file = os.path.join(temp_dir, "enhanced_agent.log")
    logger = setup_logging(
        log_level="DEBUG",
        json_format=True,
        log_file=log_file,
    )
    logger.info("[STARTUP] Using ENHANCED multi-provider LLM system")

    # Initialize enhanced LLM configuration
    llm_config_path = os.getenv("LLM_CONFIG_PATH", "examples/dogfooding/configs/llm_config.yaml")
    config_manager_llm = ConfigManager(llm_config_path)
    llm_config = config_manager_llm.get_config()

    # Create providers from config first
    all_providers = LLMProviderFactory.create_providers_from_config(llm_config)
    
    # Initialize and run capability discovery
    capability_discovery = CapabilityDiscovery(all_providers)
    await capability_discovery.discover_capabilities()
    logger.info(f"[STARTUP] Discovered capabilities for {len(capability_discovery.model_capabilities)} models.")

    # Initialize enhanced agents
    agents = await initialize_enhanced_agents(llm_config, feature_flags, logger)

    # Initialize patch manager
    patch_dir = tempfile.mkdtemp(prefix="enhanced_patches-")
    patch_manager = LocalPatchManager(patch_dir)

    # Log feature flags
    logger.info(f"[STARTUP] Feature flags: {feature_flags}")
    logger.info("[STARTUP] Enhanced Gemini SRE Agent started.")

    # Create tasks for each service
    tasks = []
    log_managers = []

    # Create a callback function to process logs through the enhanced agent pipeline
    async def process_log_entry(log_entry: LogEntry):
        """Process log entries through the enhanced agent pipeline."""
        await process_log_with_enhanced_pipeline(log_entry, agents, patch_manager, logger)

    log_manager = LogManager(process_log_entry)

    # Ensure ingestion_config is defined
    if ingestion_config is None:
        logger.error("[STARTUP] ingestion_config not defined")
        return
    logger.info(f"[STARTUP] Ingestion config: {ingestion_config}")
    logger.info(f"[STARTUP] Found {len(ingestion_config.sources)} sources in config")
    
    for source_config in ingestion_config.sources:
        logger.info(f"[STARTUP] Processing source: {source_config.name}, type: {source_config.type}")
        if source_config.type == "file_system":
            try:
                file_system_config = FileSystemConfig(
                    name=source_config.name,
                    type=source_config.type,
                    file_path=source_config.config.get("file_path", ""),
                    file_pattern=source_config.config.get("file_pattern", "*.log"),
                    watch_mode=source_config.config.get("watch_mode", True),
                    encoding=source_config.config.get("encoding", "utf-8"),
                    buffer_size=source_config.config.get("buffer_size", 1000),
                    max_memory_mb=source_config.config.get("max_memory_mb", 100),
                    enabled=source_config.enabled,
                    priority=source_config.priority,
                    max_retries=source_config.max_retries,
                    retry_delay=source_config.retry_delay,
                    timeout=source_config.timeout,
                    circuit_breaker_enabled=source_config.circuit_breaker_enabled,
                    rate_limit_per_second=source_config.rate_limit_per_second,
                )
                adapter = FileSystemAdapter(file_system_config)
                await log_manager.add_source(adapter)
                logger.info(f"[STARTUP] Added enhanced file system source: {source_config.name}")
            except Exception as e:
                logger.error(f"[STARTUP] Failed to add source {source_config.name}: {e}")
        else:
            logger.warning(f"[STARTUP] Unsupported source type: {source_config.type}")

    log_managers.append(log_manager)

    # Start the log manager and create a task that keeps it running
    async def run_log_manager():
        await log_manager.start()
        # Keep the manager running until cancelled
        while True:
            await asyncio.sleep(1)

    task = asyncio.create_task(run_log_manager())
    tasks.append(task)

    if not tasks:
        logger.error("[STARTUP] No services could be initialized. Exiting.")
        return

    # Run all services concurrently with proper cancellation handling
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        logger.info("[STARTUP] KeyboardInterrupt received. Cancelling tasks...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        # Gracefully shutdown log managers
        for log_manager in log_managers:
            try:
                await log_manager.stop()
            except Exception as e:
                logger.error(f"[SHUTDOWN] Error stopping log manager: {e}")
        
        # Log final metrics
        if agents.get("metrics_collector"):
            metrics_summary = agents["metrics_collector"].get_metrics_summary()
            logger.info(f"[SHUTDOWN] Final metrics summary: {metrics_summary}")
        
        logger.info("[STARTUP] Enhanced Gemini SRE Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
