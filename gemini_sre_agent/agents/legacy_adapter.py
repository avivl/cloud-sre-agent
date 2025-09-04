# gemini_sre_agent/agents/legacy_adapter.py

"""
Legacy adapter for backward compatibility with existing agents.

This module provides the LegacyAgentAdapter class that allows existing code
to work with the new agent system while maintaining backward compatibility.
"""

from typing import Any, Dict

from .base import BaseAgent


class LegacyAgentAdapter:
    """Adapter to provide backward compatibility with existing agents."""
    
    def __init__(self, agent: BaseAgent):
        self.agent = agent
    
    async def legacy_execute(self, prompt: str, **kwargs) -> str:
        """Execute using the new agent but return a simple string for legacy compatibility."""
        response = await self.agent.execute(
            prompt_name="legacy",
            prompt_args={"input": prompt, **kwargs}
        )
        
        # Extract the text field from the structured response
        if hasattr(response, 'text'):
            return response.text
        elif hasattr(response, 'summary'):
            return response.summary
        elif hasattr(response, 'code'):
            return response.code
        else:
            # Fallback to string representation
            return str(response)
    
    async def legacy_analyze(self, content: str, **kwargs) -> Dict[str, Any]:
        """Legacy analysis method that returns a dictionary."""
        response = await self.agent.execute(
            prompt_name="legacy_analyze",
            prompt_args={"content": content, **kwargs}
        )
        
        # Convert structured response to dictionary
        if hasattr(response, 'model_dump'):
            return response.model_dump()
        else:
            return {"result": str(response)}
    
    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics in legacy format."""
        return self.agent.get_stats_summary()
