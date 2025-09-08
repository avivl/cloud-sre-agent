import asyncio
import json
import os
import sys
import tempfile

from gemini_sre_agent.agents.enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedRemediationAgentV2,
    EnhancedTriageAgent,
)

# New ingestion system imports
from gemini_sre_agent.config.ingestion_config import (
    FileSystemConfig,
    IngestionConfigManager,
)
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.manager.log_manager import LogManager
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal
from gemini_sre_agent.local_patch_manager import LocalPatchManager
from gemini_sre_agent.logger import setup_logging
from gemini_sre_agent.triage_agent import TriagePacket  # Used for mock TriagePacket


def validate_environment():
    """Validate required environment variables at startup"""
    logger = setup_logging()  # Get a basic logger for early validation

    # New system doesn't require GITHUB_TOKEN for local testing
    required_vars = []
    optional_vars = ["GITHUB_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS"]
    logger.info("[STARTUP] Using new ingestion system - GITHUB_TOKEN is optional")

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
        "use_new_ingestion_system": True,  # Always use new system now
        "enable_monitoring": os.getenv("ENABLE_MONITORING", "true").lower() == "true",
        "enable_legacy_fallback": False,  # Legacy fallback removed
    }


async def main():
    # Validate environment variables before proceeding
    validate_environment()  # Call validation function

    # Get feature flags
    feature_flags = get_feature_flags()

    # Load config based on feature flags
    # Use new ingestion system config
    # Get config file from command line arguments or use default
    config_file = "config/config.yaml"  # default
    if "--config-file" in sys.argv:
        config_file_index = sys.argv.index("--config-file")
        if config_file_index + 1 < len(sys.argv):
            config_file = sys.argv[config_file_index + 1]

    ingestion_config_manager = IngestionConfigManager(config_file)
    ingestion_config = ingestion_config_manager.load_config()

    temp_dir = tempfile.mkdtemp(prefix="sre-dogfooding-")
    log_file = os.path.join(temp_dir, "agent.log")
    logger = setup_logging(
        log_level="DEBUG",
        json_format=True,
        log_file=log_file,
    )
    logger.info("[STARTUP] Using NEW ingestion system configuration")

    # Initialize enhanced agents for processing
    config_manager_llm = ConfigManager("examples/dogfooding/configs/llm_config.yaml")
    llm_config = config_manager_llm.get_config()

    triage_agent = EnhancedTriageAgent(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
    )
    analysis_agent = EnhancedAnalysisAgent(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
    )

    patch_dir = tempfile.mkdtemp(prefix="real_patches-")
    remediation_agent = EnhancedRemediationAgentV2(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
        optimization_goal=OptimizationGoal.QUALITY,
    )

    patch_manager = LocalPatchManager(patch_dir)

    # Log feature flags
    logger.info(f"[STARTUP] Feature flags: {feature_flags}")
    logger.info("[STARTUP] Gemini SRE Agent started.")

    # Create tasks for each service
    tasks = []
    log_managers = []  # Track log managers for graceful shutdown

    # For new ingestion system, create a single log manager for all sources
    logger.info("[STARTUP] Setting up NEW ingestion system with file system sources")

    # Create a callback function to process logs through the agent pipeline
    async def process_log_entry(log_entry: LogEntry):
        """Process log entries through the agent pipeline for new ingestion system."""
        try:
            # Convert LogEntry to dict format expected by agents
            timestamp = getattr(log_entry, "timestamp", "")
            if hasattr(timestamp, "isoformat") and callable(
                getattr(timestamp, "isoformat", None)
            ):
                # Only call isoformat if it's not a string (datetime objects have isoformat)
                if not isinstance(timestamp, str):
                    timestamp = timestamp.isoformat()

            log_data = {
                "insertId": getattr(log_entry, "id", "N/A"),
                "timestamp": timestamp,
                "severity": (
                    getattr(log_entry, "severity", LogSeverity.INFO).value
                    if hasattr(
                        getattr(log_entry, "severity", LogSeverity.INFO), "value"
                    )
                    else str(getattr(log_entry, "severity", "INFO"))
                ),
                "textPayload": getattr(log_entry, "message", ""),
                "resource": {
                    "type": "file_system",
                    "labels": {
                        "service_name": "dogfood_service",
                        "source": getattr(log_entry, "source", "unknown"),
                    },
                },
            }

            # Generate flow ID for tracking
            flow_id = log_data.get("insertId", "N/A")
            logger.info(f"[LOG_INGESTION] Processing log entry: flow_id={flow_id}")

            # Process through agent pipeline
            logger.info(f"[TRIAGE] Starting triage analysis: flow_id={flow_id}")

            # Convert log data to string for triage
            log_text = json.dumps(log_data)

            # Use enhanced triage agent with correct prompt
            triage_response = await triage_agent.execute(
                prompt_name="triage",
                prompt_args={
                    "issue": log_text,
                    "context": {"flow_id": flow_id, "service": "dogfood_service"},
                    "urgency_level": "high",
                },
            )

            # Create a mock TriagePacket for compatibility
            triage_packet = TriagePacket(
                issue_id=f"issue_{flow_id}",
                initial_timestamp=log_data.get("timestamp", ""),
                detected_pattern=triage_response.category,
                preliminary_severity_score=8,  # High severity for errors
                affected_services=["dogfood_service"],
                sample_log_entries=[log_text],
                natural_language_summary=triage_response.description,
            )

            logger.info(
                f"[TRIAGE] Triage completed: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
            )

            logger.info(
                f"[ANALYSIS] Starting deep analysis: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
            )

            # Use enhanced analysis agent with correct prompt
            analysis_response = await analysis_agent.execute(
                prompt_name="analyze",
                prompt_args={
                    "content": log_text,
                    "criteria": ["error_type", "root_cause", "impact", "solution"],
                    "analysis_type": "error_analysis",
                    "depth": "detailed",
                },
            )

            # Debug: Check what type analysis_response actually is
            logger.info(f"[DEBUG] analysis_response type: {type(analysis_response)}")
            logger.info(
                f"[DEBUG] analysis_response attributes: {dir(analysis_response)}"
            )
            try:
                logger.info(
                    f"[DEBUG] analysis_response.summary: {analysis_response.summary}"
                )
            except AttributeError as e:
                logger.error(f"[DEBUG] Error accessing summary: {e}")
            try:
                logger.info(
                    f"[DEBUG] analysis_response.scores: {analysis_response.scores}"
                )
            except AttributeError as e:
                logger.error(f"[DEBUG] Error accessing scores: {e}")

            # Generate remediation plan with code patch
            remediation_response = await remediation_agent.create_remediation_plan(
                issue_description=triage_packet.natural_language_summary,
                error_context=log_text,
                target_file="dogfood_service/app.py",  # Target the dogfood service
                analysis_summary=analysis_response.summary,
                key_points=analysis_response.key_points,
            )

            # Create local patch using the LocalPatchManager
            logger.info(f"[REMEDIATION] Creating local patch: flow_id={flow_id}")

            # Generate a unique issue ID for the patch
            issue_id = f"issue_{flow_id.replace(':', '_').replace('/', '_')}"

            # Create local patch file
            patch_manager.create_patch(
                issue_id=issue_id,
                file_path="dogfood_service/app.py",
                patch_content=remediation_response.code_patch,
                description=remediation_response.proposed_fix,
                severity=remediation_response.priority,
            )

            logger.info(
                f"[REMEDIATION] Remediation completed: flow_id={flow_id}, issue_id={issue_id}"
            )
        except Exception as e:
            # flow_id might not be defined if error occurs early
            flow_id = getattr(log_entry, "id", "unknown")
            logger.error(
                f"[ERROR_HANDLING] Error processing log entry: flow_id={flow_id}, error={e}"
            )

    log_manager = LogManager(process_log_entry)
    # Create sources from the ingestion config and add them to the log manager

    # Ensure ingestion_config is defined
    if ingestion_config is None:
        logger.error("[STARTUP] ingestion_config not defined")
        return
    logger.info(f"[STARTUP] Ingestion config: {ingestion_config}")
    logger.info(f"[STARTUP] Found {len(ingestion_config.sources)} sources in config")
    for source_config in ingestion_config.sources:
        logger.info(
            f"[STARTUP] Processing source: {source_config.name}, type: {source_config.type}"
        )
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
                logger.info(f"[STARTUP] Added file system source: {source_config.name}")
            except Exception as e:
                logger.error(
                    f"[STARTUP] Failed to add source {source_config.name}: {e}"
                )
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
        logger.info("[STARTUP] Gemini SRE Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
