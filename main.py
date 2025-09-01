import asyncio
import os
import json  # Added
from src.gemini_sre_agent.config import load_config, ServiceMonitorConfig, GlobalConfig
from src.gemini_sre_agent.logger import setup_logging
from src.gemini_sre_agent.log_subscriber import LogSubscriber
from src.gemini_sre_agent.triage_agent import TriageAgent
from src.gemini_sre_agent.analysis_agent import AnalysisAgent
from src.gemini_sre_agent.remediation_agent import RemediationAgent


async def monitor_service(
    service_config: ServiceMonitorConfig, global_config: GlobalConfig
):
    """Monitor a single service"""
    logger = setup_logging(
        log_level=global_config.logging.log_level,
        json_format=global_config.logging.json_format,
        log_file=global_config.logging.log_file,
    )
    logger.info(f"Setting up monitoring for service: {service_config.service_name}")

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
    analysis_agent = AnalysisAgent(
        project_id=service_config.project_id,
        location=service_config.location,
        analysis_model=model_selection.analysis_model,
    )

    # Get GitHub token from environment variable
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error(
            "GITHUB_TOKEN environment variable is not set. Remediation agent cannot be initialized."
        )
        raise ValueError(
            "GITHUB_TOKEN environment variable is required for RemediationAgent."
        )

    remediation_agent = RemediationAgent(
        github_token=github_token, repo_name=github_config.repository
    )

    # Define the async callback for log subscriber
    async def process_log_data(log_data: dict):
        # This is where the log data will be processed by the agents
        logger.info(
            f"Processing log data for {service_config.service_name}: {log_data.get('insertId', 'N/A')}"
        )

        # Example: Call triage agent
        # In a real scenario, you'd pass the relevant log entries to the triage agent
        # For now, we'll just pass a dummy list or the raw log_data if it's a single entry
        try:
            # Assuming log_data is a single log entry, wrap it in a list for triage_agent
            triage_packet = triage_agent.analyze_logs(
                [json.dumps(log_data)]
            )  # Pass log_data as a string in a list
            logger.info(
                f"Triage result for {service_config.service_name}: Issue ID {triage_packet.issue_id}"
            )

            # Example: Call analysis agent
            # You'd typically pass more context here, like historical logs and configs
            remediation_plan = analysis_agent.analyze_issue(
                triage_packet, [], {}
            )  # Pass empty lists for now
            logger.info(
                f"Analysis result for {service_config.service_name}: Proposed fix {remediation_plan.proposed_fix}"
            )

            # Example: Call remediation agent
            # This would trigger the PR creation
            pr_url = remediation_agent.create_pull_request(remediation_plan, f"fix/{triage_packet.issue_id}", github_config.base_branch) # Uncommented
            logger.info(f"Remediation PR triggered for {service_config.service_name}: {triage_packet.issue_id} - {pr_url}") # Uncommented

        except Exception as e:
            logger.error(
                f"Error during log processing for {service_config.service_name}: {e}"
            )

    log_subscriber = LogSubscriber(
        project_id=service_config.project_id,
        subscription_id=service_config.subscription_id,
        triage_callback=process_log_data,  # Pass the callback
    )

    logger.info(
        f"Starting log subscription for {service_config.service_name} on {service_config.subscription_id}"
    )
    await log_subscriber.start()  # Actually start the subscriber


async def main():
    config = load_config()
    global_config = config.gemini_cloud_log_monitor

    # Setup global logging (only once)
    log_config = global_config.logging
    logger = setup_logging(
        log_level=log_config.log_level,
        json_format=log_config.json_format,
        log_file=log_config.log_file,
    )
    logger.info("Gemini SRE Agent started.")

    # Create tasks for each service
    tasks = []
    for service_config in global_config.services:
        task = asyncio.create_task(monitor_service(service_config, global_config))
        tasks.append(task)

    # Run all services concurrently
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())