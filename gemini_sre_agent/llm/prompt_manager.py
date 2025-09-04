# gemini_sre_agent/llm/prompt_manager.py

"""
Prompt management using Mirascope.

This module provides prompt loading, caching, and management capabilities
using the Mirascope library for advanced prompt management.
"""

import logging
import os
from typing import Dict, List

# Note: Mirascope integration will be added in a future update
# For now, we'll use simple string templates
try:
    import yaml
except ImportError as e:
    raise ImportError(
        "Required dependency not installed. Please install: pip install pyyaml"
    ) from e

logger = logging.getLogger(__name__)


class PromptManager:
    """
    Manager for prompt templates with basic functionality.

    Provides prompt loading, caching, and basic management capabilities.
    """

    def __init__(self, prompt_directory: str = "prompts"):
        """Initialize the prompt manager."""
        self.prompt_directory = prompt_directory
        self.prompts: Dict[str, str] = {}  # Changed from Prompt to str
        self.logger = logging.getLogger(__name__)
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load prompts from the prompt directory."""
        if not os.path.exists(self.prompt_directory):
            os.makedirs(self.prompt_directory, exist_ok=True)
            self.logger.info(f"Created prompt directory: {self.prompt_directory}")
            return

        for filename in os.listdir(self.prompt_directory):
            if filename.endswith((".yaml", ".yml")):
                try:
                    path = os.path.join(self.prompt_directory, filename)
                    with open(path, "r") as f:
                        prompt_data = yaml.safe_load(f)
                        prompt_name = os.path.splitext(filename)[0]
                        self.prompts[prompt_name] = prompt_data.get("template", "")
                        self.logger.debug(f"Loaded prompt: {prompt_name}")
                except Exception as e:
                    self.logger.error(f"Failed to load prompt {filename}: {str(e)}")

    def get_prompt(self, name: str) -> str:
        """
        Get a prompt template by name.

        Args:
            name: Prompt name

        Returns:
            Prompt template string

        Raises:
            ValueError: If prompt not found
        """
        if name not in self.prompts:
            raise ValueError(f"Prompt '{name}' not found")
        return self.prompts[name]

    def add_prompt(self, name: str, template: str) -> None:
        """
        Add a new prompt to the manager.

        Args:
            name: Prompt name
            template: Prompt template string
        """
        self.prompts[name] = Prompt(template)
        self.logger.info(f"Added prompt: {name}")

    def list_prompts(self) -> List[str]:
        """Get list of available prompt names."""
        return list(self.prompts.keys())

    def save_prompt(self, name: str, template: str) -> None:
        """
        Save a prompt to disk.

        Args:
            name: Prompt name
            template: Prompt template string
        """
        prompt_data = {"template": template}
        path = os.path.join(self.prompt_directory, f"{name}.yaml")

        with open(path, "w") as f:
            yaml.dump(prompt_data, f, default_flow_style=False)

        # Reload prompts to include the new one
        self._load_prompts()
        self.logger.info(f"Saved prompt: {name}")

    def delete_prompt(self, name: str) -> None:
        """
        Delete a prompt from disk and memory.

        Args:
            name: Prompt name
        """
        if name in self.prompts:
            del self.prompts[name]

        path = os.path.join(self.prompt_directory, f"{name}.yaml")
        if os.path.exists(path):
            os.remove(path)

        self.logger.info(f"Deleted prompt: {name}")

    def reload_prompts(self) -> None:
        """Reload all prompts from disk."""
        self.prompts.clear()
        self._load_prompts()
        self.logger.info("Reloaded all prompts")
