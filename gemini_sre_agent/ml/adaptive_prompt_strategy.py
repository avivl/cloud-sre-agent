# gemini_sre_agent/ml/adaptive_prompt_strategy.py

"""
Adaptive prompt strategy selector for choosing optimal prompt generation approach.

This module implements an adaptive strategy that chooses between meta-prompt generation,
static templates, and hybrid approaches based on context analysis.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .base_prompt_template import BasePromptTemplate, GenericErrorPromptTemplate
from .prompt_context_models import IssueType, TaskContext
from .specialized_prompt_templates import (
    APIErrorPromptTemplate,
    DatabaseErrorPromptTemplate,
    SecurityErrorPromptTemplate,
)


@dataclass
class StrategyConfig:
    """Configuration for adaptive prompt strategy."""

    enable_meta_prompt: bool = True
    enable_static_templates: bool = True
    enable_hybrid_approach: bool = True
    enable_caching: bool = True
    meta_prompt_threshold: float = 0.7
    static_template_threshold: float = 0.3
    cache_ttl_seconds: int = 3600


class PromptCache:
    """Simple in-memory cache for generated prompts."""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize prompt cache.

        Args:
            ttl_seconds: Time-to-live for cached prompts
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl_seconds = ttl_seconds
        self.logger = logging.getLogger(__name__)

    def get(self, key: str) -> Optional[str]:
        """Get cached prompt if valid."""
        if key in self.cache:
            entry = self.cache[key]
            if self._is_valid(entry):
                self.logger.debug(f"[CACHE] Hit for key: {key}")
                return entry["prompt"]
            else:
                del self.cache[key]

        self.logger.debug(f"[CACHE] Miss for key: {key}")
        return None

    def set(self, key: str, prompt: str) -> None:
        """Cache a prompt."""
        import time

        self.cache[key] = {"prompt": prompt, "timestamp": time.time()}
        self.logger.debug(f"[CACHE] Stored prompt for key: {key}")

    def _is_valid(self, entry: Dict[str, Any]) -> bool:
        """Check if cache entry is still valid."""
        import time

        return (time.time() - entry["timestamp"]) < self.ttl_seconds

    def clear(self) -> None:
        """Clear all cached prompts."""
        self.cache.clear()
        self.logger.info("[CACHE] Cleared all cached prompts")


class AdaptivePromptStrategy:
    """Adaptive strategy for choosing prompt generation approach."""

    def __init__(self, config: StrategyConfig):
        """
        Initialize adaptive prompt strategy.

        Args:
            config: Configuration for the strategy
        """
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Initialize components
        self.cached_prompts = (
            PromptCache(config.cache_ttl_seconds) if config.enable_caching else None
        )
        self.static_templates = self._initialize_static_templates()

        # Strategy decision thresholds
        self.meta_prompt_threshold = config.meta_prompt_threshold
        self.static_template_threshold = config.static_template_threshold

        self.logger.info(
            "[ADAPTIVE-STRATEGY] Initialized with adaptive prompt selection"
        )

    async def get_optimal_prompt(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Choose the optimal prompt generation strategy and return the prompt.

        Args:
            task_context: Context for determining strategy
            issue_context: Optional issue context for template selection
            repository_context: Optional repository context for template selection

        Returns:
            Generated prompt string
        """
        self.logger.info(
            f"[ADAPTIVE-STRATEGY] Selecting strategy for task: {task_context.task_type}"
        )

        # 1. Check cache first
        cache_key = None
        if self.config.enable_caching and self.cached_prompts:
            cache_key = self._generate_cache_key(task_context, issue_context)
            cached_prompt = self.cached_prompts.get(cache_key)
            if cached_prompt:
                return cached_prompt

        # 2. Select strategy based on context
        strategy = self._select_strategy(task_context)
        self.logger.info(f"[ADAPTIVE-STRATEGY] Selected strategy: {strategy}")

        # 3. Generate prompt using selected strategy
        prompt = await self._execute_strategy(
            strategy, task_context, issue_context, repository_context
        )

        # 4. Cache the result if caching is enabled
        if self.config.enable_caching and self.cached_prompts and cache_key:
            self.cached_prompts.set(cache_key, prompt)

        return prompt

    def _select_strategy(self, context: TaskContext) -> str:
        """
        Select the optimal prompt generation strategy.

        Args:
            context: Task context for decision making

        Returns:
            Strategy name: "meta_prompt", "static_template", "cached_prompt", or "hybrid"
        """
        # High-value, complex tasks → Meta-prompt
        if (
            self.config.enable_meta_prompt
            and context.business_impact >= 8
            and context.complexity_score >= 7
            and context.context_richness >= 0.6
        ):
            return "meta_prompt"

        # Simple, frequent tasks → Static template
        elif (
            self.config.enable_static_templates
            and context.complexity_score <= 3
            and context.frequency == "high"
            and context.latency_requirement < 500
        ):
            return "static_template"

        # Medium complexity, cached context → Cached prompt
        elif context.complexity_score <= 6 and self._has_cached_context(context):
            return "cached_prompt"

        # Everything else → Hybrid approach
        elif self.config.enable_hybrid_approach:
            return "hybrid"

        # Fallback to static template
        else:
            return "static_template"

    async def _execute_strategy(
        self,
        strategy: str,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Execute the selected strategy to generate a prompt.

        Args:
            strategy: Selected strategy name
            task_context: Task context
            issue_context: Optional issue context
            repository_context: Optional repository context

        Returns:
            Generated prompt string
        """
        if strategy == "meta_prompt":
            return await self._use_meta_prompt(
                task_context, issue_context, repository_context
            )
        elif strategy == "static_template":
            return await self._use_static_template(
                task_context, issue_context, repository_context
            )
        elif strategy == "cached_prompt":
            return await self._use_cached_prompt(
                task_context, issue_context, repository_context
            )
        elif strategy == "hybrid":
            return await self._use_hybrid_approach(
                task_context, issue_context, repository_context
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

    async def _use_meta_prompt(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Use meta-prompt generation approach."""
        # This would integrate with MetaPromptGenerator
        # For now, return a placeholder
        return f"""Meta-prompt generated for {task_context.task_type} with complexity {task_context.complexity_score}"""

    async def _use_static_template(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Use static template approach."""
        # Select appropriate template based on context
        template = self._select_static_template(task_context, issue_context)

        # Generate prompt using selected template
        # This would require proper context building
        return f"""Static template prompt for {task_context.task_type} using {template.template_name}"""

    async def _use_cached_prompt(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Use cached prompt approach."""
        # This would retrieve from cache or generate and cache
        return f"""Cached prompt for {task_context.task_type}"""

    async def _use_hybrid_approach(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Use hybrid approach combining multiple strategies."""
        # Combine static template with dynamic elements
        self._select_static_template(task_context, issue_context)

        # Add dynamic context elements
        dynamic_elements = self._extract_dynamic_elements(
            task_context, issue_context, repository_context
        )

        return f"""Hybrid prompt for {task_context.task_type} with dynamic elements: {dynamic_elements}"""

    def _select_static_template(
        self, task_context: TaskContext, issue_context: Optional[Dict[str, Any]] = None
    ) -> BasePromptTemplate:
        """Select appropriate static template based on context."""
        if issue_context:
            issue_type = issue_context.get("issue_type", "unknown")

            if issue_type == IssueType.DATABASE_ERROR.value:
                return self.static_templates["database"]
            elif issue_type == IssueType.API_ERROR.value:
                return self.static_templates["api"]
            elif issue_type == IssueType.SECURITY_ERROR.value:
                return self.static_templates["security"]

        # Default to generic template
        return self.static_templates["generic"]

    def _initialize_static_templates(self) -> Dict[str, BasePromptTemplate]:
        """Initialize static template registry."""
        return {
            "generic": GenericErrorPromptTemplate("generic"),
            "database": DatabaseErrorPromptTemplate("database"),
            "api": APIErrorPromptTemplate("api"),
            "security": SecurityErrorPromptTemplate("security"),
        }

    def _has_cached_context(self, context: TaskContext) -> bool:
        """Check if context is suitable for caching."""
        return context.context_variability < 0.3 and context.frequency in [
            "medium",
            "high",
        ]

    def _generate_cache_key(
        self, task_context: TaskContext, issue_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate cache key for the context."""
        import hashlib

        key_data = {
            "task_type": task_context.task_type,
            "complexity": task_context.complexity_score,
            "context_variability": task_context.context_variability,
        }

        if issue_context:
            key_data["issue_type"] = issue_context.get("issue_type", "unknown")

        key_string = str(sorted(key_data.items()))
        return hashlib.md5(key_string.encode(), usedforsecurity=False).hexdigest()

    def _extract_dynamic_elements(
        self,
        task_context: TaskContext,
        issue_context: Optional[Dict[str, Any]] = None,
        repository_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Extract dynamic elements for hybrid approach."""
        elements = []

        if issue_context:
            elements.append(f"issue_type={issue_context.get('issue_type', 'unknown')}")

        if repository_context:
            tech_stack = repository_context.get("technology_stack", {})
            if tech_stack:
                elements.append(f"tech_stack={list(tech_stack.keys())}")

        elements.append(f"complexity={task_context.complexity_score}")

        return ", ".join(elements)

    def select_model(
        self,
        context: TaskContext,
        strategy: str,
        issue_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Select optimal model based on strategy and context.

        Args:
            context: Task context for model selection
            strategy: Selected generation strategy
            issue_context: Optional issue context for additional context

        Returns:
            Optimal model identifier
        """
        # High complexity tasks get more powerful models
        if context.complexity_score >= 8:
            if strategy == "meta_prompt":
                return "gemini-1.5-pro-001"  # Most powerful for complex meta-prompt generation
            else:
                return "gemini-1.5-pro-001"  # Pro for complex code generation

        # Medium complexity tasks get balanced models
        elif context.complexity_score >= 5:
            if strategy == "meta_prompt":
                return "gemini-1.5-flash-001"  # Fast for prompt generation
            else:
                return "gemini-1.5-pro-001"  # Balanced for quality

        # Low complexity tasks get fast models
        else:
            if strategy == "meta_prompt":
                return "gemini-1.5-flash-001"  # Fast for simple prompt generation
            else:
                return "gemini-1.5-flash-001"  # Fast for simple code generation

        # Fallback to flash for any edge cases
        return "gemini-1.5-flash-001"

    def get_model_selection_stats(self) -> Dict[str, Any]:
        """Get statistics about model selection decisions."""
        return {
            "model_selection_enabled": True,
            "available_models": [
                "gemini-1.5-flash-001",  # Fast, cost-effective
                "gemini-1.5-pro-001",  # Balanced, high-quality
            ],
            "selection_criteria": {
                "complexity_threshold_high": 8,
                "complexity_threshold_medium": 5,
                "strategy_consideration": True,
                "context_awareness": True,
            },
        }

    def get_strategy_stats(self) -> Dict[str, Any]:
        """Get statistics about strategy usage."""
        return {
            "cache_size": len(self.cached_prompts.cache) if self.cached_prompts else 0,
            "available_templates": list(self.static_templates.keys()),
            "config": {
                "enable_meta_prompt": self.config.enable_meta_prompt,
                "enable_static_templates": self.config.enable_static_templates,
                "enable_hybrid_approach": self.config.enable_hybrid_approach,
                "enable_caching": self.config.enable_caching,
            },
        }
