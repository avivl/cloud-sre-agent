"""
Enhanced Mirascope Integration with Advanced Prompt Management.

This module provides comprehensive Mirascope integration with advanced features
including prompt versioning, A/B testing, analytics, optimization, and team collaboration.
"""

import json
import logging
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, TypeVar, Union

from pydantic import BaseModel

# Enhanced Mirascope imports with graceful fallback
try:
    from mirascope.llm import Provider

    try:
        from mirascope.llm import CallResponse
    except ImportError:
        CallResponse = None

    try:
        # Try to import provider-specific classes if they exist
        from mirascope.llm import Provider as AnthropicCall
        from mirascope.llm import Provider as GoogleCall
        from mirascope.llm import Provider as OpenAICall
    except ImportError:
        AnthropicCall = None
        OpenAICall = None
        GoogleCall = None

    MIRASCOPE_AVAILABLE = True
except ImportError:
    MIRASCOPE_AVAILABLE = False
    Provider = None
    CallResponse = None
    AnthropicCall = None
    OpenAICall = None
    GoogleCall = None

T = TypeVar("T", bound=BaseModel)

logger = logging.getLogger(__name__)


class PromptMetrics(BaseModel):
    """Comprehensive metrics for prompt performance."""

    # Performance metrics
    avg_response_time: float = 0.0
    success_rate: float = 0.0
    error_rate: float = 0.0

    # Quality metrics
    avg_quality_score: float = 0.0
    consistency_score: float = 0.0
    user_satisfaction: float = 0.0

    # Cost metrics
    avg_cost_per_request: float = 0.0
    total_cost: float = 0.0
    cost_efficiency: float = 0.0

    # Usage metrics
    total_requests: int = 0
    unique_users: int = 0
    peak_usage_hour: int = 0

    # A/B testing metrics
    conversion_rate: float = 0.0
    engagement_score: float = 0.0


class PromptVersion(BaseModel):
    """Enhanced prompt version with comprehensive tracking."""

    version: str
    template: str
    created_at: str
    created_by: str
    description: Optional[str] = None

    # Enhanced features
    tags: List[str] = []
    metadata: Dict[str, Any] = {}

    # Metrics and testing
    metrics: PromptMetrics = PromptMetrics()
    test_results: List[Dict[str, Any]] = []
    ab_test_results: Dict[str, Any] = {}

    # Performance tracking
    performance_history: List[Dict[str, Any]] = []
    optimization_suggestions: List[str] = []

    # Status and lifecycle
    status: str = "draft"  # draft, testing, active, deprecated
    lifecycle_stage: str = (
        "development"  # development, testing, production, maintenance
    )


class PromptData(BaseModel):
    """Enhanced prompt data with advanced management features."""

    id: str
    name: str
    description: Optional[str] = None
    prompt_type: str = "chat"
    category: str = "general"

    # Version management
    versions: Dict[str, PromptVersion] = {}
    current_version: str = "1.0.0"
    active_versions: Dict[str, str] = {}  # environment -> version mapping

    # Collaboration
    owner: str = "system"
    collaborators: List[str] = []
    permissions: Dict[str, List[str]] = {}  # user -> permissions

    # Lifecycle
    created_at: str
    updated_at: str
    last_used: Optional[str] = None

    # Advanced features
    dependencies: List[str] = []  # Other prompt IDs this depends on
    tags: List[str] = []
    documentation: Optional[str] = None


class EnhancedPromptManager:
    """Advanced prompt manager with comprehensive Mirascope integration."""

    def __init__(self, storage_path: str = "./prompts", enable_analytics: bool = True):
        """Initialize the enhanced prompt manager."""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        self.prompts: Dict[str, PromptData] = {}
        self.analytics_enabled = enable_analytics
        self.analytics_data: Dict[str, List[Dict[str, Any]]] = {}
        self._load_prompts()

        logger.info(
            f"Enhanced Prompt Manager initialized with Mirascope: {MIRASCOPE_AVAILABLE}"
        )

    def create_prompt(
        self,
        name: str,
        template: str,
        description: Optional[str] = None,
        prompt_type: str = "chat",
        category: str = "general",
        owner: str = "system",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new prompt with enhanced tracking."""
        prompt_id = str(uuid.uuid4())
        version = "1.0.0"
        timestamp = datetime.now().isoformat()

        prompt_version = PromptVersion(
            version=version,
            template=template,
            created_at=timestamp,
            created_by=owner,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )

        prompt_data = PromptData(
            id=prompt_id,
            name=name,
            description=description,
            prompt_type=prompt_type,
            category=category,
            versions={version: prompt_version},
            current_version=version,
            owner=owner,
            created_at=timestamp,
            updated_at=timestamp,
            tags=tags or [],
        )

        self.prompts[prompt_id] = prompt_data
        self._save_prompts()

        logger.info(f"Created prompt '{name}' with ID {prompt_id}")
        return prompt_id

    def get_prompt(
        self,
        prompt_id: str,
        version: Optional[str] = None,
        environment: str = "production",
    ) -> Union[Any, str]:
        """Get a Mirascope prompt object with environment-specific versioning."""
        if not prompt_id or prompt_id not in self.prompts:
            logger.warning(f"Prompt with ID '{prompt_id}' not found")
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]

        # Determine version to use
        if version:
            version_to_use = version
        elif environment in prompt_data.active_versions:
            version_to_use = prompt_data.active_versions[environment]
        else:
            version_to_use = prompt_data.current_version

        if version_to_use not in prompt_data.versions:
            raise ValueError(
                f"Version {version_to_use} not found for prompt {prompt_id}"
            )

        template = prompt_data.versions[version_to_use].template

        # Update last used timestamp
        prompt_data.last_used = datetime.now().isoformat()
        self._save_prompts()

        # Create Mirascope prompt object
        if not MIRASCOPE_AVAILABLE:
            return template

        try:
            # For now, just return the template string
            # TODO: Implement proper mirascope integration when API is stable
            return template
        except Exception as e:
            logger.warning(f"Failed to create Mirascope prompt object: {e}")
            return template

    def create_version(
        self,
        prompt_id: str,
        template: str,
        version: Optional[str] = None,
        created_by: str = "system",
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new version with enhanced tracking."""
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
            version=version,
            template=template,
            created_at=timestamp,
            created_by=created_by,
            description=description,
            tags=tags or [],
            metadata=metadata or {},
        )

        prompt_data.versions[version] = prompt_version
        prompt_data.current_version = version
        prompt_data.updated_at = timestamp

        self._save_prompts()

        logger.info(f"Created version {version} for prompt {prompt_id}")
        return version

    def deploy_version(
        self, prompt_id: str, version: str, environment: str, deploy_by: str = "system"
    ) -> None:
        """Deploy a specific version to an environment."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]

        if version not in prompt_data.versions:
            raise ValueError(f"Version {version} not found for prompt {prompt_id}")

        # Update environment mapping
        prompt_data.active_versions[environment] = version

        # Update version status
        prompt_data.versions[version].status = "active"
        prompt_data.versions[version].lifecycle_stage = "production"

        # Record deployment
        deployment_record = {
            "timestamp": datetime.now().isoformat(),
            "environment": environment,
            "deployed_by": deploy_by,
            "version": version,
        }

        if "deployments" not in prompt_data.versions[version].metadata:
            prompt_data.versions[version].metadata["deployments"] = []
        prompt_data.versions[version].metadata["deployments"].append(deployment_record)

        self._save_prompts()

        logger.info(
            f"Deployed version {version} of prompt {prompt_id} to {environment}"
        )

    def run_ab_test(
        self,
        prompt_id: str,
        version_a: str,
        version_b: str,
        test_config: Dict[str, Any],
        duration_hours: int = 24,
    ) -> str:
        """Run an A/B test between two prompt versions."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]

        if (
            version_a not in prompt_data.versions
            or version_b not in prompt_data.versions
        ):
            raise ValueError("Both versions must exist for A/B testing")

        test_id = str(uuid.uuid4())
        test_config["test_id"] = test_id
        test_config["start_time"] = datetime.now().isoformat()
        test_config["end_time"] = (
            datetime.now() + timedelta(hours=duration_hours)
        ).isoformat()
        test_config["status"] = "running"

        # Initialize A/B test results
        ab_test_results = {
            "test_id": test_id,
            "version_a": version_a,
            "version_b": version_b,
            "config": test_config,
            "results": {
                "version_a": {"requests": 0, "successes": 0, "avg_quality": 0.0},
                "version_b": {"requests": 0, "successes": 0, "avg_quality": 0.0},
            },
            "statistical_significance": False,
        }

        # Store A/B test in both versions
        prompt_data.versions[version_a].ab_test_results[test_id] = ab_test_results
        prompt_data.versions[version_b].ab_test_results[test_id] = ab_test_results

        self._save_prompts()

        logger.info(
            f"Started A/B test {test_id} between versions {version_a} and {version_b}"
        )
        return test_id

    def record_usage(
        self,
        prompt_id: str,
        version: str,
        user_id: str,
        request_data: Dict[str, Any],
        response_data: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> None:
        """Record usage analytics for a prompt version."""
        if not self.analytics_enabled:
            return

        if prompt_id not in self.prompts:
            return

        prompt_data = self.prompts[prompt_id]

        if version not in prompt_data.versions:
            return

        # Record usage data
        usage_record = {
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "version": version,
            "request_data": request_data,
            "response_data": response_data,
            "metrics": metrics,
        }

        # Store in analytics
        if prompt_id not in self.analytics_data:
            self.analytics_data[prompt_id] = []
        self.analytics_data[prompt_id].append(usage_record)

        # Update version metrics
        version_metrics = prompt_data.versions[version].metrics

        # Update performance metrics
        if "response_time" in metrics:
            version_metrics.avg_response_time = (
                version_metrics.avg_response_time * version_metrics.total_requests
                + metrics["response_time"]
            ) / (version_metrics.total_requests + 1)

        if "success" in metrics:
            if metrics["success"]:
                version_metrics.success_rate = (
                    version_metrics.success_rate * version_metrics.total_requests + 1
                ) / (version_metrics.total_requests + 1)
            else:
                version_metrics.error_rate = (
                    version_metrics.error_rate * version_metrics.total_requests + 1
                ) / (version_metrics.total_requests + 1)

        if "cost" in metrics:
            version_metrics.total_cost += metrics["cost"]
            version_metrics.avg_cost_per_request = version_metrics.total_cost / (
                version_metrics.total_requests + 1
            )

        if "quality_score" in metrics:
            version_metrics.avg_quality_score = (
                version_metrics.avg_quality_score * version_metrics.total_requests
                + metrics["quality_score"]
            ) / (version_metrics.total_requests + 1)

        version_metrics.total_requests += 1

        # Update prompt last used
        prompt_data.last_used = datetime.now().isoformat()

        self._save_prompts()

    def get_analytics(
        self, prompt_id: str, version: Optional[str] = None, time_range_hours: int = 24
    ) -> Dict[str, Any]:
        """Get comprehensive analytics for a prompt or version."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]

        # Filter by time range
        cutoff_time = datetime.now() - timedelta(hours=time_range_hours)

        if version:
            # Get analytics for specific version
            if version not in prompt_data.versions:
                raise ValueError(f"Version {version} not found")

            version_data = [
                record
                for record in self.analytics_data.get(prompt_id, [])
                if record["version"] == version
                and datetime.fromisoformat(record["timestamp"]) >= cutoff_time
            ]

            return {
                "prompt_id": prompt_id,
                "version": version,
                "time_range_hours": time_range_hours,
                "usage_count": len(version_data),
                "metrics": prompt_data.versions[version].metrics.model_dump(),
                "recent_usage": version_data[-10:] if version_data else [],
            }
        else:
            # Get analytics for all versions
            all_data = [
                record
                for record in self.analytics_data.get(prompt_id, [])
                if datetime.fromisoformat(record["timestamp"]) >= cutoff_time
            ]

            return {
                "prompt_id": prompt_id,
                "time_range_hours": time_range_hours,
                "total_usage": len(all_data),
                "versions": {
                    version: {
                        "usage_count": len(
                            [r for r in all_data if r["version"] == version]
                        ),
                        "metrics": prompt_data.versions[version].metrics.model_dump(),
                    }
                    for version in prompt_data.versions.keys()
                },
                "recent_usage": all_data[-20:] if all_data else [],
            }

    def optimize_prompt(
        self,
        prompt_id: str,
        optimization_goals: List[str],
        test_cases: List[Dict[str, Any]],
        llm_service=None,
    ) -> str:
        """Use LLM to optimize a prompt based on goals and test cases."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]
        current_version = prompt_data.current_version
        current_template = prompt_data.versions[current_version].template

        # Create optimization prompt
        optimization_prompt = f"""
        You are an expert prompt engineer. Optimize the following prompt based on these goals:
        {', '.join(optimization_goals)}
        
        Current prompt:
        {current_template}
        
        Test cases:
        {json.dumps(test_cases, indent=2)}
        
        Provide an optimized version of the prompt that better achieves the stated goals.
        Consider:
        1. Clarity and specificity
        2. Context and examples
        3. Output format requirements
        4. Edge case handling
        5. Performance optimization
        
        Only return the optimized prompt text, nothing else.
        """

        # Get optimization suggestion from LLM
        optimized_template = current_template  # Fallback
        if llm_service:
            try:
                # Use the LLM service to generate optimization
                response = llm_service.generate_text(optimization_prompt)
                if hasattr(response, "text"):
                    optimized_template = response.text
                elif isinstance(response, str):
                    optimized_template = response
            except Exception as e:
                logger.warning(f"LLM optimization failed: {e}")

        # Create new version with optimized template
        new_version = self.create_version(
            prompt_id=prompt_id,
            template=optimized_template,
            created_by="optimizer",
            description=f"Optimized for: {', '.join(optimization_goals)}",
            tags=["optimized", "auto-generated"],
        )

        # Run tests on the new version
        self.test_prompt(prompt_id, test_cases, new_version)

        # Add optimization suggestion to metadata
        prompt_data.versions[new_version].optimization_suggestions.extend(
            optimization_goals
        )

        self._save_prompts()

        logger.info(f"Created optimized version {new_version} for prompt {prompt_id}")
        return new_version

    def test_prompt(
        self,
        prompt_id: str,
        test_cases: List[Dict[str, Any]],
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run comprehensive tests on a prompt version."""
        if prompt_id not in self.prompts:
            raise ValueError(f"Prompt with ID {prompt_id} not found")

        prompt_data = self.prompts[prompt_id]
        version_to_use = version or prompt_data.current_version

        if version_to_use not in prompt_data.versions:
            raise ValueError(
                f"Version {version_to_use} not found for prompt {prompt_id}"
            )

        prompt = self.get_prompt(prompt_id, version_to_use)
        results = []

        for test_case in test_cases:
            inputs = test_case.get("inputs", {})
            expected = test_case.get("expected", None)
            test_type = test_case.get("type", "functional")

            try:
                # Format the prompt with test inputs
                if MIRASCOPE_AVAILABLE and hasattr(prompt, "format"):
                    result = prompt.format(**inputs)
                elif isinstance(prompt, str):
                    result = prompt
                    for key, value in inputs.items():
                        result = result.replace(f"{{{{{key}}}}}", str(value))
                else:
                    result = str(prompt)

                # Evaluate the result
                success = True
                if expected is not None:
                    if test_type == "contains":
                        success = expected in result
                    elif test_type == "exact":
                        success = expected == result
                    elif test_type == "regex":
                        import re

                        success = bool(re.search(expected, result))

                results.append(
                    {
                        "test_case": test_case,
                        "result": result,
                        "success": success,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "test_case": test_case,
                        "error": str(e),
                        "success": False,
                        "timestamp": datetime.now().isoformat(),
                    }
                )

        # Store test results
        test_record = {
            "timestamp": datetime.now().isoformat(),
            "test_cases": test_cases,
            "results": results,
            "success_rate": (
                sum(r["success"] for r in results) / len(results) if results else 0
            ),
        }

        prompt_data.versions[version_to_use].test_results.append(test_record)
        self._save_prompts()

        return test_record

    def _load_prompts(self) -> None:
        """Load prompts from storage."""
        prompts_file = self.storage_path / "enhanced_prompts.json"
        if prompts_file.exists():
            try:
                with open(prompts_file, "r") as f:
                    data = json.load(f)
                    for prompt_id, prompt_data in data.items():
                        self.prompts[prompt_id] = PromptData(**prompt_data)
            except Exception as e:
                logger.error(f"Error loading prompts: {e}")

        # Load analytics data
        analytics_file = self.storage_path / "analytics.json"
        if analytics_file.exists():
            try:
                with open(analytics_file, "r") as f:
                    self.analytics_data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading analytics: {e}")

    def _save_prompts(self) -> None:
        """Save prompts to storage."""
        prompts_file = self.storage_path / "enhanced_prompts.json"
        try:
            data = {
                prompt_id: prompt_data.model_dump()
                for prompt_id, prompt_data in self.prompts.items()
            }
            with open(prompts_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving prompts: {e}")

        # Save analytics data
        if self.analytics_enabled:
            analytics_file = self.storage_path / "analytics.json"
            try:
                with open(analytics_file, "w") as f:
                    json.dump(self.analytics_data, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving analytics: {e}")


# Global enhanced prompt manager instance
enhanced_prompt_manager = EnhancedPromptManager()


def get_enhanced_prompt_manager() -> EnhancedPromptManager:
    """Get the global enhanced prompt manager instance."""
    return enhanced_prompt_manager
