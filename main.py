import asyncio
import os
from src.gemini_sre_agent.config import load_config, ServiceMonitorConfig, GlobalConfig # Added ServiceMonitorConfig, GlobalConfig
from src.gemini_sre_agent.logger import setup_logging
from src.gemini_sre_agent.log_subscriber import LogSubscriber
from src.gemini_sre_agent.triage_agent import TriageAgent
from src.gemini_sre_agent.analysis_agent import AnalysisAgent
from src.gemini_sre_agent.remediation_agent import RemediationAgent

async def monitor_service(service_config: ServiceMonitorConfig, global_config: GlobalConfig):
    """Monitor a single service"""
    logger = setup_logging( # Get logger for this async function
        log_level=global_config.logging.log_level,
        json_format=global_config.logging.json_format,
        log_file=global_config.logging.log_file
    )
    logger.info(f"Setting up monitoring for service: {service_config.service_name}")

    # Determine model selection for this service (override global if specified)
    model_selection = service_config.model_selection or global_config.default_model_selection
    
    # Determine GitHub config for this service (override global if specified)
    github_config = service_config.github or global_config.default_github_config

    # Initialize agents for this service
    log_subscriber = LogSubscriber(
        project_id=service_config.project_id,
        subscription_id=service_config.subscription_id
    )
    triage_agent = TriageAgent(
        project_id=service_config.project_id,
        location=service_config.location,
        triage_model=model_selection.triage_model
    )
    analysis_agent = AnalysisAgent(
        project_id=service_config.project_id,
        location=service_config.location,
        analysis_model=model_selection.analysis_model
    )
    
    # Get GitHub token from environment variable
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        logger.error("GITHUB_TOKEN environment variable is not set. Remediation agent cannot be initialized.")
        raise ValueError("GITHUB_TOKEN environment variable is required for RemediationAgent.")

    remediation_agent = RemediationAgent(
        github_token=github_token,
        repo_name=github_config.repository
    )

    logger.info(f"Starting log subscription for {service_config.service_name} on {service_config.subscription_id}")
    # In a real application, you'd run log_subscriber.start() in a separate asyncio task
    # For now, we'll just log that it's starting
    # await log_subscriber.start() # This would block, so we'll keep it commented for now

async def main():
    config = load_config()
    global_config = config.gemini_cloud_log_monitor

    # Setup global logging (only once)
    log_config = global_config.logging
    logger = setup_logging(
        log_level=log_config.log_level,
        json_format=log_config.json_format,
        log_file=log_config.log_file
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
