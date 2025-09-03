import asyncio
import json
import os

from gemini_sre_agent.legacy_config import (
    GlobalConfig,
    ServiceMonitorConfig,
    load_config
)
from gemini_sre_agent.log_subscriber import LogSubscriber
from gemini_sre_agent.logger import setup_logging
from gemini_sre_agent.ml.enhanced_analysis_agent import (
    EnhancedAnalysisAgent,
    EnhancedAnalysisConfig,
)
from gemini_sre_agent.remediation_agent import RemediationAgent
from gemini_sre_agent.resilience import HyxResilientClient, create_resilience_config
from gemini_sre_agent.triage_agent import TriageAgent


def validate_environment():
    """Validate required environment variables at startup"""
    logger = setup_logging()  # Get a basic logger for early validation

    required_vars = ["GITHUB_TOKEN"]
    # GOOGLE_APPLICATION_CREDENTIALS is typically handled by gcloud auth application-default login
    # LOG_LEVEL is handled by config.yaml
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

    config = load_config()
    global_config = config.gemini_cloud_log_monitor

    # Setup global logging (only once)
    log_config = global_config.logging
    logger = setup_logging(
        log_level=log_config.log_level,
        json_format=log_config.json_format,
        log_file=log_config.log_file,
    )
    logger.info("[STARTUP] Gemini SRE Agent started.")

    # Create tasks for each service
    tasks = []
    for service_config in global_config.services:
        task = monitor_service(service_config, global_config)
        if task:
            tasks.append(task)

    # Run all services concurrently with proper cancellation handling
    try:
        await asyncio.gather(*tasks, return_exceptions=True)
    except KeyboardInterrupt:
        logger.info("[STARTUP] KeyboardInterrupt received. Cancelling tasks...")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    finally:
        logger.info("[STARTUP] Gemini SRE Agent stopped.")


if __name__ == "__main__":
    asyncio.run(main())
