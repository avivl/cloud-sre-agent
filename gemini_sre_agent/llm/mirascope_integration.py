# gemini_sre_agent/llm/mirascope_integration.py

"""
Mirascope Prompt Management Integration.

This module provides comprehensive prompt management capabilities using Mirascope
with versioning, testing, optimization, analytics, and team collaboration features.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel

# Mirascope imports with graceful fallback
try:
    from mirascope import Prompt
    from mirascope.prompts import ChatPrompt

    MIRASCOPE_AVAILABLE = True
except ImportError:
    # Fallback for when Mirascope is not available
    MIRASCOPE_AVAILABLE = False
    Prompt = None
    ChatPrompt = None

T = TypeVar("T", bound=BaseModel)


class PromptVersion(BaseModel):
    """Represents a version of a prompt."""

    version: str
    template: str
    created_at: str
    description: Optional[str] = None
    metrics: Dict[str, Any] = {}
    tests: List[Dict[str, Any]] = []
    metrics_history: List[Dict[str, Any]] = []


class PromptData(BaseModel):
    """Represents a prompt with all its versions."""

    id: str
    name: str
    description: Optional[str] = None
    prompt_type: str = "chat"
    versions: Dict[str, PromptVersion] = {}
    current_version: str = "1.0.0"
    created_at: str
    updated_at: str


class PromptManager:
    """Advanced prompt manager with Mirascope integration."""

    def __init__(self, storage_path: str = "./prompts"):
        """Initialize the prompt manager."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.prompts: Dict[str, PromptData] = {}
        self.active_versions: Dict[str, str] = {}
        self._load_prompts()

    def create_prompt(
        self,
        name: str,
        template: str,
        description: Optional[str] = None,
        prompt_type: str = "chat",
    ) -> str:
        """Create a new prompt with version tracking."""
        prompt_id = str(uuid.uuid4())
        version = "1.0.0"
        timestamp = datetime.now().isoformat()

        prompt_version = PromptVersion(
            version=version, template=template, created_at=timestamp
        )

        prompt_data = PromptData(
            id=prompt_id,
            name=name,
            description=description,
            prompt_type=prompt_type,
            versions={version: prompt_version},
            current_version=version,
            created_at=timestamp,
            updated_at=timestamp,
        )

        self.prompts[prompt_id] = prompt_data
        self.active_versions[prompt_id] = version
        self._save_prompts()
        return prompt_id

    def get_prompt(
        self, prompt_id: str, version: Optional[str] = None
    ) -> Union[Any, str]:
        """Get a Mirascope prompt object for the specified prompt."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]
        version_to_use = version or prompt_data.current_version

        if version_to_use not in prompt_data.versions:
            raise ValueError(
                f"Version {version_to_use} not found for prompt {prompt_id}"
            )

        template = prompt_data.versions[version_to_use].template

        if not MIRASCOPE_AVAILABLE:
            return template

        if prompt_data.prompt_type == "chat" and ChatPrompt is not None:
            return ChatPrompt(template=template)
        elif Prompt is not None:
            return Prompt(template=template)
        else:
            return template

    def create_version(
        self, prompt_id: str, template: str, version: Optional[str] = None
    ) -> str:
        """Create a new version of an existing prompt."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]
        current_version = prompt_data.current_version

        # Auto-increment version if not specified
        if version is None:
            major, minor, patch = map(int, current_version.split("."))
            version = f"{major}.{minor}.{patch + 1}"

        timestamp = datetime.now().isoformat()

        prompt_version = PromptVersion(
            version=version, template=template, created_at=timestamp
        )

        prompt_data.versions[version] = prompt_version
        prompt_data.current_version = version
        prompt_data.updated_at = timestamp

        self._save_prompts()
        return version

    def test_prompt(
        self,
        prompt_id: str,
        test_cases: List[Dict[str, Any]],
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run tests on a prompt version and record results."""
        prompt = self.get_prompt(prompt_id, version)
        version_to_use = version or self.prompts[prompt_id].current_version

        results = []
        for test_case in test_cases:
            inputs = test_case.get("inputs", {})
            expected = test_case.get("expected", None)

            try:
                if MIRASCOPE_AVAILABLE and hasattr(prompt, "format"):
                    result = prompt.format(**inputs)
                elif isinstance(prompt, str):
                    # Simple string template replacement
                    result = prompt
                    for key, value in inputs.items():
                        result = result.replace(f"{{{{{key}}}}}", str(value))
                else:
                    result = str(prompt)

                success = expected is None or expected in result
                results.append(
                    {
                        "inputs": inputs,
                        "expected": expected,
                        "result": result,
                        "success": success,
                    }
                )
            except Exception as e:
                results.append(
                    {
                        "inputs": inputs,
                        "expected": expected,
                        "error": str(e),
                        "success": False,
                    }
                )

        # Store test results
        test_record = {"timestamp": datetime.now().isoformat(), "results": results}

        self.prompts[prompt_id].versions[version_to_use].tests.append(test_record)
        self._save_prompts()

        success_rate = (
            sum(r["success"] for r in results) / len(results) if results else 0
        )
        return {"success_rate": success_rate, "results": results}

    def record_metrics(
        self, prompt_id: str, metrics: Dict[str, Any], version: Optional[str] = None
    ) -> None:
        """Record performance metrics for a prompt version."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]
        version_to_use = version or prompt_data.current_version

        if version_to_use not in prompt_data.versions:
            raise ValueError(
                f"Version {version_to_use} not found for prompt {prompt_id}"
            )

        timestamp = datetime.now().isoformat()

        # Add to metrics history
        metrics_record = {"timestamp": timestamp, "data": metrics}

        self.prompts[prompt_id].versions[version_to_use].metrics_history.append(
            metrics_record
        )

        # Update current metrics summary
        current_metrics = self.prompts[prompt_id].versions[version_to_use].metrics
        for key, value in metrics.items():
            if key in current_metrics:
                # Average with existing metrics
                current_metrics[key] = (current_metrics[key] + value) / 2
            else:
                current_metrics[key] = value

        self._save_prompts()

    def list_prompts(self) -> List[Dict[str, Any]]:
        """List all prompts with their metadata."""
        return [
            {
                "id": prompt_id,
                "name": data.name,
                "description": data.description,
                "current_version": data.current_version,
                "created_at": data.created_at,
                "updated_at": data.updated_at,
            }
            for prompt_id, data in self.prompts.items()
        ]

    def get_prompt_versions(self, prompt_id: str) -> List[str]:
        """Get all versions for a specific prompt."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        return list(self.prompts[prompt_id].versions.keys())

    def _load_prompts(self) -> None:
        """Load prompts from storage."""
        prompts_file = self.storage_path / "prompts.json"
        if prompts_file.exists():
            try:
                with open(prompts_file, "r") as f:
                    data = json.load(f)
                    for prompt_id, prompt_data in data.items():
                        self.prompts[prompt_id] = PromptData(**prompt_data)
            except Exception as e:
                print(f"Error loading prompts: {e}")

    def _save_prompts(self) -> None:
        """Save prompts to storage."""
        prompts_file = self.storage_path / "prompts.json"
        try:
            data = {
                prompt_id: prompt_data.model_dump()
                for prompt_id, prompt_data in self.prompts.items()
            }
            with open(prompts_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving prompts: {e}")


class PromptEnvironment:
    """Environment-specific prompt deployment."""

    def __init__(self, name: str, prompt_manager: PromptManager):
        self.name = name
        self.prompt_manager = prompt_manager
        self.environment_versions: Dict[str, str] = {}

    def deploy_prompt(self, prompt_id: str, version: str) -> None:
        """Deploy a specific prompt version to this environment."""
        if prompt_id not in self.prompt_manager.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompt_manager.prompts[prompt_id]

        if version not in prompt_data.versions:
            raise ValueError(f"Version {version} not found for prompt {prompt_id}")

        self.environment_versions[prompt_id] = version

    def get_prompt(self, prompt_id: str) -> Union[Any, str]:
        """Get the environment-specific version of a prompt."""
        if prompt_id not in self.environment_versions:
            # Fall back to the current version if not specifically deployed
            return self.prompt_manager.get_prompt(prompt_id)

        version = self.environment_versions[prompt_id]
        return self.prompt_manager.get_prompt(prompt_id, version)


class PromptCollaborationManager:
    """Team collaboration features for prompt management."""

    def __init__(self, prompt_manager: PromptManager):
        self.prompt_manager = prompt_manager
        self.reviews: Dict[str, List[Dict[str, Any]]] = {}

    def create_review(
        self, prompt_id: str, version: str, reviewer: str, comments: str
    ) -> str:
        """Create a review for a prompt version."""
        review_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        review = {
            "id": review_id,
            "prompt_id": prompt_id,
            "version": version,
            "reviewer": reviewer,
            "comments": comments,
            "status": "pending",
            "created_at": timestamp,
            "updated_at": timestamp,
        }

        if prompt_id not in self.reviews:
            self.reviews[prompt_id] = []

        self.reviews[prompt_id].append(review)
        return review_id

    def approve_review(self, review_id: str) -> None:
        """Approve a prompt review."""
        for _prompt_id, reviews in self.reviews.items():
            for review in reviews:
                if review["id"] == review_id:
                    review["status"] = "approved"
                    review["updated_at"] = datetime.now().isoformat()
                    return

        raise ValueError(f"Review with ID {review_id} not found")

    def reject_review(self, review_id: str, reason: str) -> None:
        """Reject a prompt review with a reason."""
        for _prompt_id, reviews in self.reviews.items():
            for review in reviews:
                if review["id"] == review_id:
                    review["status"] = "rejected"
                    review["rejection_reason"] = reason
                    review["updated_at"] = datetime.now().isoformat()
                    return

        raise ValueError(f"Review with ID {review_id} not found")


class PromptOptimizer:
    """Prompt optimization capabilities."""

    def __init__(self, prompt_manager: PromptManager, llm_service=None):
        self.prompt_manager = prompt_manager
        self.llm_service = llm_service

    async def optimize_prompt(
        self,
        prompt_id: str,
        optimization_goals: List[str],
        test_cases: List[Dict[str, Any]],
    ) -> str:
        """Use LLM to optimize a prompt based on goals and test cases."""
        if not self.llm_service:
            raise ValueError("LLM service required for optimization")

        prompt_data = self.prompt_manager.prompts[prompt_id]
        current_version = prompt_data.current_version
        current_template = prompt_data.versions[current_version].template

        # Create optimization prompt
        optimization_prompt = f"""
        You are an expert prompt engineer. Optimize the following prompt based on these goals:
        {', '.join(optimization_goals)}
        
        Current prompt:
        {current_template}
        
        Test cases:
        {test_cases}
        
        Provide an optimized version of the prompt that better achieves the stated goals.
        Only return the optimized prompt text, nothing else.
        """

        # Get optimization suggestion from LLM
        try:
            optimized_template = await self.llm_service.generate_text(
                optimization_prompt
            )
        except Exception:
            # Fallback if LLM service fails
            optimized_template = current_template

        # Create new version with optimized template
        new_version = self.prompt_manager.create_version(prompt_id, optimized_template)

        # Run tests on the new version
        self.prompt_manager.test_prompt(prompt_id, test_cases, new_version)

        return new_version
