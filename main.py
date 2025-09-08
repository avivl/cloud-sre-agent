import asyncio
import json
import os
from typing import Optional, Any

# New ingestion system imports
from gemini_sre_agent.config.ingestion_config import GCPPubSubConfig, SourceType, IngestionConfigManager
from gemini_sre_agent.ingestion.adapters.gcp_pubsub import GCPPubSubAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.manager.log_manager import LogManager
from gemini_sre_agent.ingestion.monitoring.monitoring_manager import MonitoringManager
from gemini_sre_agent.legacy_config import (
    GlobalConfig,
    ServiceMonitorConfig,
    load_config,
)
from gemini_sre_agent.log_subscriber import LogSubscriber
from gemini_sre_agent.logger import setup_logging
from gemini_sre_agent.ml.enhanced_analysis_agent import (
    EnhancedAnalysisAgent,
    EnhancedAnalysisConfig,
)
from gemini_sre_agent.remediation_agent import RemediationAgent
from gemini_sre_agent.resilience_core import HyxResilientClient, create_resilience_config
from gemini_sre_agent.triage_agent import TriageAgent
from gemini_sre_agent.local_patch_manager import LocalPatchManager


def validate_environment():
    """Validate required environment variables at startup"""
    logger = setup_logging()  # Get a basic logger for early validation

    # Check if we're using the new ingestion system
    use_new_system = os.getenv("USE_NEW_INGESTION_SYSTEM", "false").lower() == "true"
    
    if use_new_system:
        # New system doesn't require GITHUB_TOKEN for local testing
        required_vars = []
        optional_vars = ["GITHUB_TOKEN", "GOOGLE_APPLICATION_CREDENTIALS"]
        logger.info("[STARTUP] Using new ingestion system - GITHUB_TOKEN is optional")
    else:
        # Legacy system requires GITHUB_TOKEN
        required_vars = ["GITHUB_TOKEN"]
        optional_vars = ["GOOGLE_APPLICATION_CREDENTIALS"]

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
        "use_new_ingestion_system": os.getenv(
            "USE_NEW_INGESTION_SYSTEM", "false"
        ).lower()
        == "true",
        "enable_monitoring": os.getenv("ENABLE_MONITORING", "true").lower() == "true",
        "enable_legacy_fallback": os.getenv("ENABLE_LEGACY_FALLBACK", "true").lower()
        == "true",
    }


async def monitor_service_new_system(
    service_config: ServiceMonitorConfig,
    global_config: GlobalConfig,
    feature_flags: dict,
):
    """Monitor a single service using the new ingestion system"""
    logger = setup_logging(
        log_level=global_config.logging.log_level,
        json_format=global_config.logging.json_format,
        log_file=global_config.logging.log_file,
    )
    logger.info(
        f"[STARTUP] Setting up monitoring for service: {service_config.service_name} (NEW SYSTEM)"
    )

    try:
        # Initialize monitoring if enabled
        monitoring_manager = None
        if feature_flags.get("enable_monitoring", True):
            monitoring_manager = MonitoringManager()
            await monitoring_manager.start()
            logger.info(
                f"[MONITORING] Monitoring system initialized for {service_config.service_name}"
            )

        # Determine model selection for this service (override global if specified)
        model_selection = (
            service_config.model_selection or global_config.default_model_selection
        )

        # Determine GitHub config for this service (override global if specified)
        github_config = service_config.github or global_config.default_github_config

        # Initialize agents for this service
        triage_agent = TriageAgent(
            project_id=service_config.project_id,
            location=service_config.location,
            triage_model=model_selection.triage_model,
        )
        analysis_agent = EnhancedAnalysisAgent(
            EnhancedAnalysisConfig(
                project_id=service_config.project_id,
                location=service_config.location,
                main_model=model_selection.analysis_model,
                meta_model="gemini-1.5-flash-001",
                enable_specialized_generators=True,
                enable_validation=True,
            )
        )

        # Get GitHub token from environment variable
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token is None:
            raise RuntimeError("GITHUB_TOKEN should be set by validate_environment()")

        remediation_agent = RemediationAgent(
            github_token=github_token, repo_name=github_config.repository
        )

        # Initialize resilience client for this service
        resilience_config = create_resilience_config(environment="production")
        resilient_client = HyxResilientClient(resilience_config)

        # Create log processing callback
        async def process_log_entry(log_entry: LogEntry):
            """Process incoming log entry through the agent pipeline."""
            flow_id = log_entry.metadata.get("insertId", "N/A")

            logger.info(
                f"[LOG_INGESTION] Processing log entry for {service_config.service_name}: flow_id={flow_id}"
            )

            try:
                # Convert LogEntry to dict format expected by legacy agents
                log_data = {
                    "insertId": log_entry.metadata.get("insertId", flow_id),
                    "timestamp": log_entry.timestamp.isoformat(),
                    "severity": (
                        log_entry.severity.value if log_entry.severity else "INFO"
                    ),
                    "textPayload": log_entry.message,
                    "resource": log_entry.metadata.get("resource", {}),
                    "labels": log_entry.metadata.get("labels", {}),
                }

                # Process through the same pipeline as legacy system
                logger.info(f"[TRIAGE] Starting triage analysis: flow_id={flow_id}")
                triage_packet = await resilient_client.execute(
                    lambda: triage_agent.analyze_logs([json.dumps(log_data)], flow_id)
                )
                logger.info(
                    f"[TRIAGE] Triage completed for service={service_config.service_name}: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )

                logger.info(
                    f"[ANALYSIS] Starting deep analysis: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )
                current_log_context = [json.dumps(log_data, indent=2)]

                analysis_result = await analysis_agent.analyze_issue(
                    triage_packet.model_dump(), current_log_context, {}, flow_id
                )

                if not analysis_result.get("success", False):
                    logger.error(
                        f"[ANALYSIS] Analysis failed: {analysis_result.get('error', 'Unknown error')}"
                    )
                    return

                # Convert enhanced agent response to RemediationPlan for compatibility
                from gemini_sre_agent.analysis_agent import RemediationPlan

                remediation_plan = RemediationPlan(
                    root_cause_analysis=analysis_result["analysis"][
                        "root_cause_analysis"
                    ],
                    proposed_fix=analysis_result["analysis"]["proposed_fix"],
                    code_patch=analysis_result["analysis"]["code_patch"],
                )

                logger.info(
                    f"[ANALYSIS] Analysis completed for service={service_config.service_name}: flow_id={flow_id}, issue_id={triage_packet.issue_id}, proposed_fix={remediation_plan.proposed_fix[:100]}..."
                )

                logger.info(
                    f"[REMEDIATION] Creating pull request: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )
                pr_url = await resilient_client.execute(
                    lambda: remediation_agent.create_pull_request(
                        remediation_plan,
                        f"fix/{triage_packet.issue_id}",
                        github_config.base_branch,
                        flow_id,
                        triage_packet.issue_id,
                    )
                )
                logger.info(
                    f"[REMEDIATION] Pull request created successfully: flow_id={flow_id}, issue_id={triage_packet.issue_id}, pr_url={pr_url}"
                )

                # Update monitoring metrics if enabled
                if monitoring_manager:
                    monitoring_manager.record_operation_metrics(
                        component=service_config.service_name,
                        operation="log_processing",
                        duration_ms=0.0,  # Would need to track actual duration
                        success=True,
                    )

            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error during log processing: service={service_config.service_name}, flow_id={flow_id}, error={e}"
                )
                if monitoring_manager:
                    monitoring_manager.record_operation_metrics(
                        component=service_config.service_name,
                        operation="log_processing",
                        duration_ms=0.0,  # Would need to track actual duration
                        success=False,
                    )

        # Create and configure log manager
        log_manager = LogManager(callback=process_log_entry)

        # Create GCP Pub/Sub adapter
        pubsub_config = GCPPubSubConfig(
            name=f"{service_config.service_name}_pubsub",
            type=SourceType.GCP_PUBSUB,
            project_id=service_config.project_id,
            subscription_id=service_config.subscription_id,
            enabled=True,
            max_messages=100,
            ack_deadline_seconds=60,
        )

        pubsub_adapter = GCPPubSubAdapter(pubsub_config)
        await log_manager.add_source(pubsub_adapter)

        # Register health checks with monitoring if enabled
        if monitoring_manager:
            await monitoring_manager.register_component_health_check(
                f"{service_config.service_name}_log_manager",
                lambda: log_manager.get_health_status(),
            )

        logger.info(
            f"[STARTUP] Starting new log ingestion system for {service_config.service_name} on {service_config.subscription_id}"
        )

        # Start the log manager
        await log_manager.start()

        return log_manager

    except Exception as e:
        logger.error(
            f"[ERROR_HANDLING] Failed to initialize new system for service {service_config.service_name}: {e}"
        )
        return None


def monitor_service(service_config: ServiceMonitorConfig, global_config: GlobalConfig):
    """Monitor a single service"""
    logger = setup_logging(
        log_level=global_config.logging.log_level,
        json_format=global_config.logging.json_format,
        log_file=global_config.logging.log_file,
    )
    logger.info(
        f"[STARTUP] Setting up monitoring for service: {service_config.service_name}"
    )

    try:
        # Determine model selection for this service (override global if specified)
        model_selection = (
            service_config.model_selection or global_config.default_model_selection
        )

        # Determine GitHub config for this service (override global if specified)
        github_config = service_config.github or global_config.default_github_config

        # Initialize agents for this service
        triage_agent = TriageAgent(
            project_id=service_config.project_id,
            location=service_config.location,
            triage_model=model_selection.triage_model,
        )
        analysis_agent = EnhancedAnalysisAgent(
            EnhancedAnalysisConfig(
                project_id=service_config.project_id,
                location=service_config.location,
                main_model=model_selection.analysis_model,
                meta_model="gemini-1.5-flash-001",
                enable_specialized_generators=True,
                enable_validation=True,
            )
        )

        # Get GitHub token from environment variable
        github_token = os.getenv("GITHUB_TOKEN")
        # Runtime check that github_token is not None, as validate_environment() should have ensured it
        if github_token is None:
            raise RuntimeError("GITHUB_TOKEN should be set by validate_environment()")

        remediation_agent = RemediationAgent(
            github_token=github_token, repo_name=github_config.repository
        )

        # Initialize resilience client for this service
        resilience_config = create_resilience_config(environment="production")
        resilient_client = HyxResilientClient(resilience_config)

        # Define the async callback for log subscriber
        async def process_log_data(log_data: dict):
            """
            Process incoming log data through the agent pipeline.

            Args:
                log_data (dict): Raw log entry from Pub/Sub, expected format:
                    {
                        "insertId": "unique-id",
                        "timestamp": "2025-01-27T10:00:00Z",
                        "severity": "ERROR",
                        "textPayload": "Error message",
                        "resource": {"type": "cloud_run_revision", ...}
                    }

            Example:
                >>> # This function is called by LogSubscriber
                >>> # Example log_data:
                >>> # log_data = {
                >>> # #     "insertId": "abc-123",
                >>> # #     "timestamp": "2025-01-27T10:00:00Z",
                >>> # #     "severity": "ERROR",
                >>> # #     "textPayload": "Database connection failed",
                >>> # #     "resource": {"type": "cloud_run_revision", "labels": {"service_name": "my-service"}}
                >>> # # }
                >>> # # await process_log_data(log_data)
            """
            # Generate flow ID for tracking this specific processing flow
            flow_id = log_data.get("insertId", "N/A")

            # This is where the log data will be processed by the agents
            logger.info(
                f"[LOG_INGESTION] Processing log data for {service_config.service_name}: flow_id={flow_id}"
            )

            try:
                # Wrap agent calls with resilience patterns
                logger.info(f"[TRIAGE] Starting triage analysis: flow_id={flow_id}")
                triage_packet = await resilient_client.execute(
                    lambda: triage_agent.analyze_logs([json.dumps(log_data)], flow_id)
                )
                logger.info(
                    f"[TRIAGE] Triage completed for service={service_config.service_name}: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )

                logger.info(
                    f"[ANALYSIS] Starting deep analysis: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )
                # Provide current log as historical context for better analysis
                current_log_context = [json.dumps(log_data, indent=2)]

                analysis_result = await analysis_agent.analyze_issue(
                    triage_packet.model_dump(), current_log_context, {}, flow_id
                )

                if not analysis_result.get("success", False):
                    logger.error(
                        f"[ANALYSIS] Analysis failed: {analysis_result.get('error', 'Unknown error')}"
                    )
                    return

                # Convert enhanced agent response to RemediationPlan for compatibility
                from gemini_sre_agent.analysis_agent import RemediationPlan

                remediation_plan = RemediationPlan(
                    root_cause_analysis=analysis_result["analysis"][
                        "root_cause_analysis"
                    ],
                    proposed_fix=analysis_result["analysis"]["proposed_fix"],
                    code_patch=analysis_result["analysis"]["code_patch"],
                )

                logger.info(
                    f"[ANALYSIS] Analysis completed for service={service_config.service_name}: flow_id={flow_id}, issue_id={triage_packet.issue_id}, proposed_fix={remediation_plan.proposed_fix[:100]}..."
                )

                logger.info(
                    f"[REMEDIATION] Creating pull request: flow_id={flow_id}, issue_id={triage_packet.issue_id}"
                )
                pr_url = await resilient_client.execute(
                    lambda: remediation_agent.create_pull_request(
                        remediation_plan,
                        f"fix/{triage_packet.issue_id}",
                        github_config.base_branch,
                        flow_id,
                        triage_packet.issue_id,
                    )
                )
                logger.info(
                    f"[REMEDIATION] Pull request created successfully: flow_id={flow_id}, issue_id={triage_packet.issue_id}, pr_url={pr_url}"
                )

            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Error during log processing: service={service_config.service_name}, flow_id={flow_id}, error={e}"
                )

        log_subscriber = LogSubscriber(
            project_id=service_config.project_id,
            subscription_id=service_config.subscription_id,
            triage_callback=process_log_data,
        )

        logger.info(
            f"[STARTUP] Starting log subscription for {service_config.service_name} on {service_config.subscription_id}"
        )
        return asyncio.create_task(log_subscriber.start())

    except Exception as e:
        logger.error(
            f"[ERROR_HANDLING] Failed to initialize service {service_config.service_name}: {e}"
        )
        return None


async def main():
    # Validate environment variables before proceeding
    validate_environment()  # Call validation function

    # Get feature flags
    feature_flags = get_feature_flags()

    # Initialize variables
    ingestion_config: Optional[Any] = None
    global_config: Optional[Any] = None
    # Load config based on feature flags
    if feature_flags.get("use_new_ingestion_system", False):
        # Use new ingestion system config
        # Get config file from command line arguments or use default
        import sys
        config_file = "config/config.yaml"  # default
        if "--config-file" in sys.argv:
            config_file_index = sys.argv.index("--config-file")
            if config_file_index + 1 < len(sys.argv):
                config_file = sys.argv[config_file_index + 1]
        
        config_manager = IngestionConfigManager(config_file)
        ingestion_config = config_manager.load_config()
        import tempfile
        import os
        temp_dir = tempfile.mkdtemp(prefix="sre-dogfooding-")
        log_file = os.path.join(temp_dir, "agent.log")
        logger = setup_logging(
            log_level="DEBUG",
            json_format=True,
            log_file=log_file,
        )
        logger.info("[STARTUP] Using NEW ingestion system configuration")
    else:
        # Use legacy config
        config = load_config()
        global_config = config.gemini_cloud_log_monitor
        log_config = global_config.logging
        logger = setup_logging(
            log_level=log_config.log_level,
            json_format=log_config.json_format,
            log_file=log_config.log_file,
        )
        logger.info("[STARTUP] Using LEGACY configuration")

    # Log feature flags
    logger.info(f"[STARTUP] Feature flags: {feature_flags}")
    logger.info("[STARTUP] Gemini SRE Agent started.")

    # Create tasks for each service
    tasks = []
    log_managers = []  # Track log managers for graceful shutdown

    if feature_flags.get("use_new_ingestion_system", False):
        # For new ingestion system, create a single log manager for all sources
        logger.info("[STARTUP] Setting up NEW ingestion system with file system sources")
        
        # Create a callback function to process logs through the agent pipeline
        async def process_log_entry(log_entry):
            """Process log entries through the agent pipeline for new ingestion system."""
            try:
                # Convert LogEntry to dict format expected by agents
                timestamp = getattr(log_entry, 'timestamp', '')
                if hasattr(timestamp, 'isoformat') and callable(getattr(timestamp, 'isoformat', None)):
                    # Only call isoformat if it's not a string (datetime objects have isoformat)
                    if not isinstance(timestamp, str):
                        timestamp = timestamp.isoformat()
                
                log_data = {
                    "insertId": getattr(log_entry, 'id', 'N/A'),
                    "timestamp": timestamp,
                    "severity": getattr(log_entry, 'severity', LogSeverity.INFO).value if hasattr(getattr(log_entry, 'severity', LogSeverity.INFO), 'value') else str(getattr(log_entry, 'severity', 'INFO')),
                    "textPayload": getattr(log_entry, 'message', ''),
                    "resource": {
                        "type": "file_system",
                        "labels": {
                            "service_name": "dogfood_service",
                            "source": getattr(log_entry, 'source', 'unknown')
                        }
                    }
                }
                
                # Generate flow ID for tracking
                flow_id = log_data.get("insertId", "N/A")
                logger.info(f"[LOG_INGESTION] Processing log entry: flow_id={flow_id}")
                
                # Initialize enhanced agents for processing
                from gemini_sre_agent.agents.enhanced_specialized import EnhancedTriageAgent, EnhancedAnalysisAgent, EnhancedRemediationAgent
                from gemini_sre_agent.remediation_agent import RemediationAgent
                from gemini_sre_agent.llm.strategy_manager import OptimizationGoal
                
                # Load LLM configuration from config file
                from gemini_sre_agent.llm.config_manager import ConfigManager
                config_manager = ConfigManager("examples/dogfooding/configs/llm_config.yaml")
                llm_config = config_manager.get_config()
                
                # Create enhanced agents with Ollama configuration
                triage_agent = EnhancedTriageAgent(
                    llm_config=llm_config,
                    primary_model="llama3.2:3b",
                    fallback_model="llama3.2:1b"
                )
                analysis_agent = EnhancedAnalysisAgent(
                    llm_config=llm_config,
                    primary_model="llama3.2:3b",
                    fallback_model="llama3.2:1b"
                )
                import tempfile
                import os
                patch_dir = tempfile.mkdtemp(prefix="real_patches-")
                remediation_agent = RemediationAgent(
                    github_token=os.getenv("GITHUB_TOKEN", "dummy_token"),
                    repo_name="gemini-sre-agent",
                    use_local_patches=True,
                    patch_dir=patch_dir
                )
                
                # Create local patch manager
                patch_manager = LocalPatchManager(patch_dir)
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
                        "urgency_level": "high"
                    }
                )
                
                # Create a mock TriagePacket for compatibility
                from gemini_sre_agent.triage_agent import TriagePacket
                triage_packet = TriagePacket(
                    issue_id=f"issue_{flow_id}",
                    initial_timestamp=log_data.get("timestamp", ""),
                    detected_pattern=triage_response.category,
                    preliminary_severity_score=8,  # High severity for errors
                    affected_services=["dogfood_service"],
                    sample_log_entries=[log_text],
                    natural_language_summary=triage_response.description
                )
                
                logger.info(f"[TRIAGE] Triage completed: flow_id={flow_id}, issue_id={triage_packet.issue_id}")
                
                logger.info(f"[ANALYSIS] Starting deep analysis: flow_id={flow_id}, issue_id={triage_packet.issue_id}")
                
                # Use enhanced analysis agent with correct prompt
                analysis_response = await analysis_agent.execute(
                    prompt_name="analyze",
                    prompt_args={
                        "content": log_text,
                        "criteria": ["error_type", "root_cause", "impact", "solution"],
                        "analysis_type": "error_analysis",
                        "depth": "detailed"
                    }
                )
                
                # Debug: Check what type analysis_response actually is
                logger.info(f"[DEBUG] analysis_response type: {type(analysis_response)}")
                logger.info(f"[DEBUG] analysis_response attributes: {dir(analysis_response)}")
                try:
                    logger.info(f"[DEBUG] analysis_response.summary: {analysis_response.summary}")
                except AttributeError as e:
                    logger.error(f"[DEBUG] Error accessing summary: {e}")
                try:
                    logger.info(f"[DEBUG] analysis_response.scores: {analysis_response.scores}")
                except AttributeError as e:
                    logger.error(f"[DEBUG] Error accessing scores: {e}")
                
                # Create remediation agent to generate code patches
                remediation_agent = EnhancedRemediationAgent(
                    llm_config=llm_config,
                    primary_model="llama3.2:3b",
                    fallback_model="llama3.2:1b",
                    optimization_goal=OptimizationGoal.QUALITY,
                )
                
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

                logger.info(f"[REMEDIATION] Remediation completed: flow_id={flow_id}, issue_id={issue_id}")
            except Exception as e:
                # flow_id might not be defined if error occurs early
                flow_id = getattr(log_entry, 'id', 'unknown')
                logger.error(f"[ERROR_HANDLING] Error processing log entry: flow_id={flow_id}, error={e}")
        
        log_manager = LogManager(process_log_entry)
        # Create sources from the ingestion config and add them to the log manager
        from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
        
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
                    # Create file system adapter - need to convert SourceConfig to FileSystemConfig
                    from gemini_sre_agent.config.ingestion_config import FileSystemConfig
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
                        rate_limit_per_second=source_config.rate_limit_per_second
                    )
                    adapter = FileSystemAdapter(file_system_config)
                    await log_manager.add_source(adapter)
                    logger.info(f"[STARTUP] Added file system source: {source_config.name}")
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
    else:
        # For legacy system, process each service
        if global_config is None:
            logger.error("[STARTUP] global_config not defined for legacy system")
            return
        for service_config in global_config.services:
            try:
                logger.info(
                    f"[STARTUP] Using LEGACY ingestion system for {service_config.service_name}"
                )
                task = monitor_service(service_config, global_config)
                if task is not None:
                    tasks.append(task)
            except Exception as e:
                logger.error(
                    f"[ERROR_HANDLING] Failed to initialize service {service_config.service_name}: {e}"
                )

            # Fallback to legacy system if enabled
            if feature_flags.get("enable_legacy_fallback", True):
                logger.info(
                    f"[FALLBACK] Attempting legacy system for {service_config.service_name}"
                )
                try:
                    task = monitor_service(service_config, global_config)
                    if task is not None:
                        tasks.append(task)
                except Exception as fallback_error:
                    logger.error(
                        f"[FALLBACK] Legacy system also failed for {service_config.service_name}: {fallback_error}"
                    )

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
