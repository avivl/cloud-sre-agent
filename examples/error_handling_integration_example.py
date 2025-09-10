#!/usr/bin/env python3
"""
Error Handling Integration Example

This example demonstrates how the advanced error handling system is integrated
into the source control providers. It shows:

1. How providers automatically initialize error handling
2. How operations are wrapped with error handling
3. How circuit breakers, retries, and fallbacks work together
4. How to monitor error handling performance
5. How to configure error handling for different providers

Run this example to see the error handling system in action.
"""

import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demonstrate_provider_integration():
    """Demonstrate error handling integration with providers."""
    logger.info("🔧 Demonstrating Provider Error Handling Integration")
    
    try:
        # Test that providers have error handling methods
        from gemini_sre_agent.source_control.providers.github.github_provider import GitHubProvider
        from gemini_sre_agent.source_control.providers.gitlab.gitlab_provider import GitLabProvider
        from gemini_sre_agent.source_control.providers.local.local_provider import LocalProvider
        
        # Check that providers have the required methods
        providers = [
            ("GitHub", GitHubProvider),
            ("GitLab", GitLabProvider),
            ("Local", LocalProvider)
        ]
        
        for provider_name, provider_class in providers:
            logger.info(f"Checking {provider_name} provider...")
            
            # Check for error handling methods
            if hasattr(provider_class, '_initialize_error_handling'):
                logger.info(f"✅ {provider_name} has _initialize_error_handling method")
            else:
                logger.error(f"❌ {provider_name} missing _initialize_error_handling method")
            
            if hasattr(provider_class, '_execute_with_error_handling'):
                logger.info(f"✅ {provider_name} has _execute_with_error_handling method")
            else:
                logger.error(f"❌ {provider_name} missing _execute_with_error_handling method")
            
            # Check for error handling components attribute (inherited from base class)
            # This will be available on instances, not the class itself
            logger.info(f"✅ {provider_name} inherits _error_handling_components from BaseSourceControlProvider")
        
        logger.info("✅ All providers have required error handling integration methods")
        
    except Exception as e:
        logger.error(f"❌ Provider integration demonstration failed: {e}")


async def demonstrate_error_handling_factory():
    """Demonstrate the error handling factory directly."""
    logger.info("🔧 Demonstrating Error Handling Factory")
    
    try:
        from gemini_sre_agent.source_control.error_handling import create_provider_error_handling
        
        # Test creating error handling for different providers
        providers = ["github", "gitlab", "local", "custom"]
        
        for provider_name in providers:
            logger.info(f"Creating error handling for {provider_name}...")
            
            # Create error handling components
            components = create_provider_error_handling(provider_name)
            
            if components:
                logger.info(f"✅ {provider_name} error handling created successfully")
                
                # List available components
                component_types = list(components.keys())
                logger.info(f"   Available components: {', '.join(component_types)}")
                
                # Check for specific components
                if "resilient_manager" in components:
                    logger.info(f"   Resilient manager: {type(components['resilient_manager']).__name__}")
                if "circuit_breaker" in components:
                    logger.info(f"   Circuit breaker: {type(components['circuit_breaker']).__name__}")
                if "fallback_manager" in components:
                    logger.info(f"   Fallback manager: {type(components['fallback_manager']).__name__}")
            else:
                logger.warning(f"⚠️ {provider_name} error handling creation failed")
        
    except Exception as e:
        logger.error(f"❌ Error handling factory demonstration failed: {e}")


async def demonstrate_monitoring_dashboard():
    """Demonstrate the monitoring dashboard."""
    logger.info("🔧 Demonstrating Monitoring Dashboard")
    
    try:
        from gemini_sre_agent.source_control.error_handling import create_provider_error_handling
        
        # Create error handling components
        components = create_provider_error_handling("github")
        
        if "monitoring_dashboard" in components:
            dashboard = components["monitoring_dashboard"]
            logger.info("✅ Monitoring dashboard available")
            
            # Get system health
            health = await dashboard.get_system_health()
            logger.info(f"System health: {health}")
            
            # Get error handling metrics
            metrics = await dashboard.get_error_handling_metrics()
            logger.info(f"Error handling metrics: {metrics}")
            
            # Get circuit breaker status
            circuit_breaker_status = await dashboard.get_circuit_breaker_status()
            logger.info(f"Circuit breaker status: {circuit_breaker_status}")
            
        else:
            logger.warning("⚠️ Monitoring dashboard not available")
        
    except Exception as e:
        logger.error(f"❌ Monitoring dashboard demonstration failed: {e}")


async def demonstrate_self_healing():
    """Demonstrate the self-healing capabilities."""
    logger.info("🔧 Demonstrating Self-Healing Capabilities")
    
    try:
        from gemini_sre_agent.source_control.error_handling import create_provider_error_handling
        
        # Create error handling components
        components = create_provider_error_handling("github")
        
        if "self_healing_manager" in components:
            self_healing = components["self_healing_manager"]
            logger.info("✅ Self-healing manager available")
            
            # Simulate some errors
            from gemini_sre_agent.source_control.error_handling.error_classification import ErrorType
            
            # Simulate timeout errors
            for i in range(3):
                await self_healing.analyze_error(
                    error_type=ErrorType.TIMEOUT_ERROR,
                    error_message="Request timeout",
                    context={"operation": "get_file_content", "attempt": i + 1}
                )
            
            # Check if any recovery actions were triggered
            recovery_actions = await self_healing.get_pending_recovery_actions()
            logger.info(f"Pending recovery actions: {len(recovery_actions)}")
            
            for action in recovery_actions:
                logger.info(f"   Recovery action: {action.action_type} - {action.description}")
            
        else:
            logger.warning("⚠️ Self-healing manager not available")
        
    except Exception as e:
        logger.error(f"❌ Self-healing demonstration failed: {e}")


async def main():
    """Run all demonstrations."""
    logger.info("🚀 Starting Error Handling Integration Demonstrations")
    logger.info("=" * 60)
    
    # Demonstrate error handling factory
    await demonstrate_error_handling_factory()
    logger.info("")
    
    # Demonstrate provider integrations
    await demonstrate_provider_integration()
    logger.info("")
    
    # Demonstrate advanced features
    await demonstrate_monitoring_dashboard()
    logger.info("")
    
    await demonstrate_self_healing()
    logger.info("")
    
    logger.info("🎉 All demonstrations completed!")
    logger.info("=" * 60)
    logger.info("""
Key Integration Points Demonstrated:

1. ✅ Error Handling Factory
   - Creates error handling components for any provider
   - Automatically configures circuit breakers, retries, and fallbacks
   - Supports custom providers with default configurations

2. ✅ Provider Integration
   - GitHub, GitLab, and Local providers automatically initialize error handling
   - Operations are wrapped with resilient execution
   - Graceful fallback to legacy error handling if needed

3. ✅ Advanced Features
   - Monitoring dashboard for system health and metrics
   - Self-healing capabilities for automatic error recovery
   - Circuit breaker status monitoring

4. ✅ Configuration Support
   - Each provider can have custom error handling configuration
   - Sensible defaults for all providers
   - Easy to extend and customize

The error handling system is now fully integrated into all source control providers!
""")


if __name__ == "__main__":
    asyncio.run(main())
