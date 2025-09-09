"""
Enhanced Multi-Provider LLM System Demo.

This example demonstrates the full capabilities of the enhanced multi-provider
LLM system including intelligent model selection, cost optimization, and advanced features.
"""

import asyncio
import json
import logging
from typing import Dict, List

from gemini_sre_agent.agents.enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedRemediationAgentV2,
    EnhancedTriageAgent,
)
from gemini_sre_agent.agents.legacy_adapter import (
    create_enhanced_analysis_agent,
    create_enhanced_remediation_agent,
    create_enhanced_triage_agent,
)
from gemini_sre_agent.llm.capabilities.discovery import CapabilityDiscovery
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.monitoring.llm_metrics import get_llm_metrics_collector
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_legacy_adapters():
    """Demonstrate migration using legacy adapters (zero-code migration)."""
    logger.info("=== Demo: Legacy Adapters (Zero-Code Migration) ===")
    
    # Load enhanced LLM configuration
    config_manager = ConfigManager("examples/llm_configs/multi_provider_config.yaml")
    llm_config = config_manager.get_config()
    
    # Create enhanced agents using legacy adapters
    triage_agent = create_enhanced_triage_agent(
        project_id="demo-project",
        location="us-central1",
        triage_model="gemini-1.5-flash",
        llm_config=llm_config
    )
    
    analysis_agent = create_enhanced_analysis_agent(
        project_id="demo-project",
        location="us-central1", 
        analysis_model="gemini-1.5-flash",
        llm_config=llm_config
    )
    
    remediation_agent = create_enhanced_remediation_agent(
        github_token="dummy_token",  # Use local patches
        repo_name="demo/repo",
        llm_config=llm_config,
        use_local_patches=True
    )
    
    # Sample log data
    sample_logs = [
        "2024-01-15 10:30:15 ERROR [ServiceA] Database connection failed: timeout after 30s",
        "2024-01-15 10:30:16 WARN [ServiceA] Retrying database connection...",
        "2024-01-15 10:30:17 ERROR [ServiceA] Database connection failed again: timeout after 30s",
        "2024-01-15 10:30:18 CRITICAL [ServiceA] Service unavailable - database unreachable",
    ]
    
    # Process using legacy interface (unchanged code)
    logger.info("Processing logs with legacy interface...")
    triage_packet = await triage_agent.analyze_logs(sample_logs, "demo_flow_1")
    logger.info(f"Triage completed: {triage_packet}")
    
    remediation_plan = analysis_agent.analyze_issue(
        triage_packet, sample_logs, {}, "demo_flow_1"
    )
    logger.info(f"Analysis completed: {remediation_plan}")
    
    pr_url = await remediation_agent.create_pull_request(
        remediation_plan, "fix-db-connection", "main", "demo_flow_1", "issue_1"
    )
    logger.info(f"Remediation completed: {pr_url}")


async def demo_enhanced_agents():
    """Demonstrate full enhanced agents with advanced features."""
    logger.info("=== Demo: Enhanced Agents (Full Features) ===")
    
    # Load enhanced LLM configuration
    config_manager = ConfigManager("examples/llm_configs/multi_provider_config.yaml")
    llm_config = config_manager.get_config()
    
    # Create enhanced agents with full capabilities
    triage_agent = EnhancedTriageAgent(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
        optimization_goal=OptimizationGoal.COST_EFFECTIVE,
        max_cost=0.01,
        min_quality=0.7,
        collect_stats=True,
    )
    
    analysis_agent = EnhancedAnalysisAgent(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
        optimization_goal=OptimizationGoal.QUALITY,
        max_cost=0.02,
        min_quality=0.8,
        collect_stats=True,
    )
    
    remediation_agent = EnhancedRemediationAgentV2(
        llm_config=llm_config,
        primary_model="llama3.2:3b",
        fallback_model="llama3.2:1b",
        optimization_goal=OptimizationGoal.HYBRID,
        max_cost=0.03,
        min_quality=0.9,
        collect_stats=True,
    )
    
    # Sample log data
    sample_logs = [
        "2024-01-15 11:45:22 ERROR [ServiceB] Memory usage exceeded 95% threshold",
        "2024-01-15 11:45:23 WARN [ServiceB] Garbage collection taking longer than expected",
        "2024-01-15 11:45:24 ERROR [ServiceB] OutOfMemoryError: Java heap space",
        "2024-01-15 11:45:25 CRITICAL [ServiceB] Service crashed due to memory exhaustion",
    ]
    
    # Process using enhanced interface
    logger.info("Processing logs with enhanced interface...")
    
    # Step 1: Enhanced Triage
    triage_response = await triage_agent.analyze_logs(sample_logs, "demo_flow_2")
    logger.info(f"Enhanced triage: severity={triage_response.severity}, category={triage_response.category}")
    logger.info(f"Suggested actions: {triage_response.suggested_actions}")
    
    # Step 2: Enhanced Analysis
    triage_data = {
        "issue_id": "memory_issue_1",
        "severity": triage_response.severity,
        "description": triage_response.description,
        "category": triage_response.category,
    }
    
    analysis_response = await analysis_agent.analyze_issue(
        triage_data, sample_logs, {}, "demo_flow_2"
    )
    logger.info(f"Enhanced analysis: priority={analysis_response.priority}")
    logger.info(f"Root cause: {analysis_response.root_cause_analysis[:100]}...")
    
    # Step 3: Enhanced Remediation
    remediation_response = await remediation_agent.create_remediation_plan(
        issue_description=triage_response.description,
        error_context=json.dumps(sample_logs),
        target_file="ServiceB/src/main/java/ServiceB.java",
        analysis_summary=analysis_response.root_cause_analysis,
        key_points=[analysis_response.proposed_fix],
    )
    
    logger.info(f"Enhanced remediation: priority={remediation_response.priority}")
    logger.info(f"Estimated effort: {remediation_response.estimated_effort}")
    logger.info(f"Code patch preview: {remediation_response.code_patch[:200]}...")


async def demo_model_selection():
    """Demonstrate intelligent model selection and optimization."""
    logger.info("=== Demo: Intelligent Model Selection ===")
    
    # Load configuration
    config_manager = ConfigManager("examples/llm_configs/multi_provider_config.yaml")
    llm_config = config_manager.get_config()
    
    # Create providers and run capability discovery
    all_providers = LLMProviderFactory.create_providers_from_config(llm_config)
    capability_discovery = CapabilityDiscovery(all_providers)
    await capability_discovery.discover_capabilities()
    
    logger.info(f"Discovered {len(capability_discovery.model_capabilities)} model capabilities")
    
    # Show available models by provider
    for provider_name, provider in all_providers.items():
        logger.info(f"Provider {provider_name}: {len(provider.models)} models available")
        for model in provider.models[:3]:  # Show first 3 models
            logger.info(f"  - {model.name}: {model.model_type.value} (${model.cost_per_1k_tokens:.4f}/1k tokens)")


async def demo_cost_optimization():
    """Demonstrate cost optimization features."""
    logger.info("=== Demo: Cost Optimization ===")
    
    # Load configuration
    config_manager = ConfigManager("examples/llm_configs/multi_provider_config.yaml")
    llm_config = config_manager.get_config()
    
    # Create agents with different optimization goals
    cost_optimized_agent = EnhancedTriageAgent(
        llm_config=llm_config,
        optimization_goal=OptimizationGoal.COST_EFFECTIVE,
        max_cost=0.005,  # Very low cost limit
        collect_stats=True,
    )
    
    quality_optimized_agent = EnhancedTriageAgent(
        llm_config=llm_config,
        optimization_goal=OptimizationGoal.QUALITY,
        min_quality=0.9,  # High quality requirement
        collect_stats=True,
    )
    
    hybrid_agent = EnhancedTriageAgent(
        llm_config=llm_config,
        optimization_goal=OptimizationGoal.HYBRID,
        max_cost=0.01,
        min_quality=0.8,
        collect_stats=True,
    )
    
    sample_logs = ["ERROR: Service timeout after 30 seconds"]
    
    # Test different optimization strategies
    for agent_name, agent in [
        ("Cost Optimized", cost_optimized_agent),
        ("Quality Optimized", quality_optimized_agent),
        ("Hybrid", hybrid_agent),
    ]:
        logger.info(f"Testing {agent_name} agent...")
        response = await agent.analyze_logs(sample_logs, f"demo_{agent_name.lower().replace(' ', '_')}")
        logger.info(f"{agent_name} result: {response.severity} - {response.description[:50]}...")


async def demo_monitoring():
    """Demonstrate monitoring and metrics collection."""
    logger.info("=== Demo: Monitoring and Metrics ===")
    
    # Get metrics collector
    metrics_collector = get_llm_metrics_collector()
    
    # Simulate some requests
    for i in range(5):
        metrics_collector.record_request(
            provider="demo_provider",
            model="demo_model",
            model_type="demo",
            request=None,
            response=None,
            duration_ms=100.0 + i * 10,
            cost=0.001 + i * 0.0001,
        )
    
    # Get metrics summary
    summary = metrics_collector.get_metrics_summary()
    logger.info(f"Metrics summary: {summary}")
    
    # Get provider metrics
    provider_metrics = metrics_collector.get_all_provider_metrics()
    for provider, metrics in provider_metrics.items():
        logger.info(f"Provider {provider}: {metrics.total_requests} requests, "
                   f"${metrics.total_cost:.4f} total cost, "
                   f"{metrics.success_rate:.2%} success rate")


async def main():
    """Run all demos."""
    logger.info("Starting Enhanced Multi-Provider LLM System Demo")
    
    try:
        # Demo 1: Legacy adapters (zero-code migration)
        await demo_legacy_adapters()
        
        # Demo 2: Enhanced agents (full features)
        await demo_enhanced_agents()
        
        # Demo 3: Model selection
        await demo_model_selection()
        
        # Demo 4: Cost optimization
        await demo_cost_optimization()
        
        # Demo 5: Monitoring
        await demo_monitoring()
        
        logger.info("All demos completed successfully!")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
