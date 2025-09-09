"""
Enhanced Mirascope Integration Demo.

This example demonstrates the advanced prompt management capabilities including
versioning, A/B testing, analytics, optimization, and team collaboration.
"""

import asyncio
import json
import logging
from typing import Dict, List

from gemini_sre_agent.llm.enhanced_mirascope_integration import (
    EnhancedPromptManager,
    get_enhanced_prompt_manager,
)
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.factory import LLMProviderFactory

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def demo_prompt_creation_and_versioning():
    """Demonstrate prompt creation and versioning."""
    logger.info("=== Demo: Prompt Creation and Versioning ===")
    
    # Initialize enhanced prompt manager
    prompt_manager = EnhancedPromptManager(storage_path="./demo_prompts")
    
    # Create a new prompt
    prompt_id = prompt_manager.create_prompt(
        name="SRE Triage Analysis",
        template="""
        You are an expert SRE analyst. Analyze the following log entries and provide a triage assessment.
        
        Log entries:
        {log_entries}
        
        Please provide:
        1. Severity level (low, medium, high, critical)
        2. Issue category
        3. Root cause analysis
        4. Recommended immediate actions
        
        Format your response as JSON.
        """,
        description="Analyzes log entries for SRE triage purposes",
        category="sre",
        owner="sre_team",
        tags=["sre", "triage", "analysis"],
        metadata={"domain": "infrastructure", "criticality": "high"}
    )
    
    logger.info(f"Created prompt with ID: {prompt_id}")
    
    # Create a new version with improvements
    version_2 = prompt_manager.create_version(
        prompt_id=prompt_id,
        template="""
        You are an expert SRE analyst with 10+ years of experience in incident response.
        Analyze the following log entries and provide a comprehensive triage assessment.
        
        Log entries:
        {log_entries}
        
        Context: This is a production system with high availability requirements.
        
        Please provide a structured analysis:
        1. Severity level (low, medium, high, critical) with justification
        2. Issue category and subcategory
        3. Root cause analysis with confidence level
        4. Impact assessment (users affected, business impact)
        5. Recommended immediate actions (prioritized)
        6. Escalation requirements
        
        Format your response as structured JSON with clear field names.
        """,
        created_by="senior_sre",
        description="Enhanced version with more detailed analysis",
        tags=["sre", "triage", "analysis", "enhanced"],
        metadata={"improvements": ["detailed_analysis", "impact_assessment", "escalation"]}
    )
    
    logger.info(f"Created version 2: {version_2}")
    
    # Deploy version to different environments
    prompt_manager.deploy_version(prompt_id, "1.0.0", "staging", "sre_team")
    prompt_manager.deploy_version(prompt_id, version_2, "production", "senior_sre")
    
    logger.info("Deployed versions to staging and production environments")
    
    return prompt_id


async def demo_ab_testing():
    """Demonstrate A/B testing capabilities."""
    logger.info("=== Demo: A/B Testing ===")
    
    prompt_manager = get_enhanced_prompt_manager()
    
    # Create a prompt for A/B testing
    prompt_id = prompt_manager.create_prompt(
        name="Customer Support Response",
        template="Respond to this customer inquiry: {inquiry}",
        category="support",
        owner="support_team"
    )
    
    # Create two versions for A/B testing
    version_a = prompt_manager.create_version(
        prompt_id=prompt_id,
        template="""
        Thank you for contacting us. I understand your concern about {inquiry}.
        
        Here's what I can help you with:
        1. Immediate resolution steps
        2. Alternative solutions
        3. Escalation if needed
        
        Please let me know if you need further assistance.
        """,
        created_by="support_team",
        description="Version A: Standard response format"
    )
    
    version_b = prompt_manager.create_version(
        prompt_id=prompt_id,
        template="""
        Hi there! 👋
        
        I see you're having an issue with {inquiry}. Don't worry, I'm here to help!
        
        Let me break this down for you:
        ✅ First, let's try this quick fix...
        ✅ If that doesn't work, here's an alternative...
        ✅ And if you're still stuck, I'll escalate this right away!
        
        Does this help? Feel free to ask if you need anything else! 😊
        """,
        created_by="support_team",
        description="Version B: Friendly, emoji-enhanced response"
    )
    
    # Run A/B test
    test_config = {
        "traffic_split": 0.5,  # 50/50 split
        "success_metric": "customer_satisfaction",
        "minimum_sample_size": 100,
    }
    
    test_id = prompt_manager.run_ab_test(
        prompt_id=prompt_id,
        version_a=version_a,
        version_b=version_b,
        test_config=test_config,
        duration_hours=48
    )
    
    logger.info(f"Started A/B test {test_id} between versions {version_a} and {version_b}")
    
    # Simulate some usage data
    for i in range(20):
        # Simulate version A usage
        prompt_manager.record_usage(
            prompt_id=prompt_id,
            version=version_a,
            user_id=f"user_{i}",
            request_data={"inquiry": f"Test inquiry {i}"},
            response_data={"response": f"Version A response {i}"},
            metrics={
                "response_time": 1.2 + i * 0.1,
                "success": True,
                "cost": 0.001,
                "quality_score": 0.8 + i * 0.01,
                "customer_satisfaction": 0.7 + i * 0.02,
            }
        )
        
        # Simulate version B usage
        prompt_manager.record_usage(
            prompt_id=prompt_id,
            version=version_b,
            user_id=f"user_{i+20}",
            request_data={"inquiry": f"Test inquiry {i+20}"},
            response_data={"response": f"Version B response {i+20}"},
            metrics={
                "response_time": 1.1 + i * 0.1,
                "success": True,
                "cost": 0.001,
                "quality_score": 0.85 + i * 0.01,
                "customer_satisfaction": 0.8 + i * 0.02,
            }
        )
    
    logger.info("Recorded usage data for A/B test")
    
    return prompt_id, test_id


async def demo_analytics():
    """Demonstrate analytics and reporting."""
    logger.info("=== Demo: Analytics and Reporting ===")
    
    prompt_manager = get_enhanced_prompt_manager()
    
    # Get analytics for a prompt
    analytics = prompt_manager.get_analytics(
        prompt_id="demo_prompt",  # Use the prompt from previous demo
        time_range_hours=24
    )
    
    logger.info(f"Analytics data: {json.dumps(analytics, indent=2)}")
    
    # Get version-specific analytics
    version_analytics = prompt_manager.get_analytics(
        prompt_id="demo_prompt",
        version="2.0.0",
        time_range_hours=24
    )
    
    logger.info(f"Version analytics: {json.dumps(version_analytics, indent=2)}")


async def demo_prompt_optimization():
    """Demonstrate prompt optimization."""
    logger.info("=== Demo: Prompt Optimization ===")
    
    prompt_manager = get_enhanced_prompt_manager()
    
    # Create a prompt to optimize
    prompt_id = prompt_manager.create_prompt(
        name="Code Review Assistant",
        template="Review this code: {code}",
        category="development",
        owner="dev_team"
    )
    
    # Define optimization goals
    optimization_goals = [
        "improve_code_quality_detection",
        "provide_actionable_feedback",
        "reduce_response_time",
        "increase_accuracy"
    ]
    
    # Define test cases
    test_cases = [
        {
            "inputs": {"code": "def add(a, b): return a + b"},
            "expected": "function",
            "type": "contains"
        },
        {
            "inputs": {"code": "x = 5\ny = 10\nprint(x + y)"},
            "expected": "variable",
            "type": "contains"
        },
        {
            "inputs": {"code": "import os\nos.system('rm -rf /')"},
            "expected": "security",
            "type": "contains"
        }
    ]
    
    # Run optimization
    optimized_version = prompt_manager.optimize_prompt(
        prompt_id=prompt_id,
        optimization_goals=optimization_goals,
        test_cases=test_cases
    )
    
    logger.info(f"Created optimized version: {optimized_version}")
    
    # Run tests on the optimized version
    test_results = prompt_manager.test_prompt(
        prompt_id=prompt_id,
        test_cases=test_cases,
        version=optimized_version
    )
    
    logger.info(f"Test results: {json.dumps(test_results, indent=2)}")


async def demo_comprehensive_testing():
    """Demonstrate comprehensive prompt testing."""
    logger.info("=== Demo: Comprehensive Testing ===")
    
    prompt_manager = get_enhanced_prompt_manager()
    
    # Create a prompt for testing
    prompt_id = prompt_manager.create_prompt(
        name="API Documentation Generator",
        template="""
        Generate API documentation for the following endpoint:
        
        Method: {method}
        Path: {path}
        Parameters: {parameters}
        Response: {response}
        
        Please provide comprehensive documentation including:
        1. Description
        2. Parameters
        3. Response format
        4. Example usage
        5. Error handling
        """,
        category="documentation",
        owner="api_team"
    )
    
    # Define comprehensive test cases
    test_cases = [
        {
            "inputs": {
                "method": "GET",
                "path": "/api/users",
                "parameters": "limit, offset",
                "response": "User list"
            },
            "expected": "GET /api/users",
            "type": "contains"
        },
        {
            "inputs": {
                "method": "POST",
                "path": "/api/users",
                "parameters": "name, email",
                "response": "Created user"
            },
            "expected": "POST /api/users",
            "type": "contains"
        },
        {
            "inputs": {
                "method": "DELETE",
                "path": "/api/users/{id}",
                "parameters": "id",
                "response": "Success/Error"
            },
            "expected": "DELETE /api/users",
            "type": "contains"
        }
    ]
    
    # Run tests
    test_results = prompt_manager.test_prompt(
        prompt_id=prompt_id,
        test_cases=test_cases
    )
    
    logger.info(f"Comprehensive test results: {json.dumps(test_results, indent=2)}")


async def demo_team_collaboration():
    """Demonstrate team collaboration features."""
    logger.info("=== Demo: Team Collaboration ===")
    
    prompt_manager = get_enhanced_prompt_manager()
    
    # Create a prompt for team collaboration
    prompt_id = prompt_manager.create_prompt(
        name="Security Incident Response",
        template="Analyze this security incident: {incident_details}",
        category="security",
        owner="security_team"
    )
    
    # Add collaborators
    prompt_data = prompt_manager.prompts[prompt_id]
    prompt_data.collaborators = ["security_lead", "incident_manager", "sre_team"]
    prompt_data.permissions = {
        "security_lead": ["read", "write", "deploy"],
        "incident_manager": ["read", "write"],
        "sre_team": ["read"]
    }
    
    # Create a version by a collaborator
    version = prompt_manager.create_version(
        prompt_id=prompt_id,
        template="""
        SECURITY INCIDENT ANALYSIS
        
        Incident Details: {incident_details}
        
        Analysis Framework:
        1. Threat Assessment
           - Severity Level
           - Attack Vector
           - Potential Impact
        
        2. Response Actions
           - Immediate containment
           - Evidence collection
           - Communication plan
        
        3. Recovery Steps
           - System restoration
           - Security hardening
           - Monitoring enhancement
        
        4. Post-Incident
           - Root cause analysis
           - Process improvements
           - Documentation updates
        
        Please provide detailed analysis for each section.
        """,
        created_by="security_lead",
        description="Enhanced security incident analysis template",
        tags=["security", "incident", "response", "enhanced"]
    )
    
    logger.info(f"Created collaborative version: {version}")
    
    # Deploy with approval workflow
    prompt_manager.deploy_version(
        prompt_id=prompt_id,
        version=version,
        environment="production",
        deploy_by="security_lead"
    )
    
    logger.info("Deployed version with team collaboration")


async def main():
    """Run all Mirascope integration demos."""
    logger.info("Starting Enhanced Mirascope Integration Demo")
    
    try:
        # Demo 1: Prompt creation and versioning
        prompt_id = await demo_prompt_creation_and_versioning()
        
        # Demo 2: A/B testing
        ab_prompt_id, test_id = await demo_ab_testing()
        
        # Demo 3: Analytics
        await demo_analytics()
        
        # Demo 4: Prompt optimization
        await demo_prompt_optimization()
        
        # Demo 5: Comprehensive testing
        await demo_comprehensive_testing()
        
        # Demo 6: Team collaboration
        await demo_team_collaboration()
        
        logger.info("All Mirascope integration demos completed successfully!")
        
        # Summary
        prompt_manager = get_enhanced_prompt_manager()
        all_prompts = prompt_manager.prompts
        logger.info(f"Created {len(all_prompts)} prompts with enhanced Mirascope integration")
        
        for prompt_id, prompt_data in all_prompts.items():
            logger.info(f"Prompt '{prompt_data.name}': {len(prompt_data.versions)} versions")
        
    except Exception as e:
        logger.error(f"Demo failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
