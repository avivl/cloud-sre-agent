import logging
from abc import ABC, abstractmethod
from typing import Dict, List

from gemini_sre_agent.llm.capabilities.models import ModelCapability
from gemini_sre_agent.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class CapabilityTest(ABC):
    """
    Abstract base class for a single capability test.
    """

    def __init__(self, capability: ModelCapability):
        self.capability = capability

    @abstractmethod
    async def run_test(self, provider: LLMProvider, model_name: str) -> bool:
        """
        Run the capability test against a specific model.

        Args:
            provider: The LLMProvider instance.
            model_name: The name of the model to test.

        Returns:
            True if the model passes the test, False otherwise.
        """
        pass


class TextGenerationTest(CapabilityTest):
    """
    Tests the text generation capability of a model.
    """

    def __init__(self):
        super().__init__(
            ModelCapability(
                name="text_generation",
                description="Tests basic text generation.",
                parameters={
                    "prompt": {"type": "string"},
                    "expected_substring": {"type": "string"},
                },
                performance_score=0.8,
                cost_efficiency=0.7
            )
        )

    async def run_test(self, provider: LLMProvider, model_name: str) -> bool:
        prompt = "Write a short sentence about a cat."
        expected_substring = "cat"

        try:
            # Create a simple LLMRequest for testing
            from gemini_sre_agent.llm.base import LLMRequest
            request = LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.1
            )
            response = await provider._generate(request)
            response_content = response.content if hasattr(response, 'content') else str(response)
            return expected_substring.lower() in response_content.lower()
        except Exception as e:
            logger.error(f"Text generation test failed for {model_name}: {e}")
            return False


class CodeGenerationTest(CapabilityTest):
    """
    Tests the code generation capability of a model.
    """

    def __init__(self):
        super().__init__(
            ModelCapability(
                name="code_generation",
                description="Tests basic Python code generation.",
                parameters={
                    "prompt": {"type": "string"},
                    "expected_substring": {"type": "string"},
                },
                performance_score=0.9,
                cost_efficiency=0.6
            )
        )

    async def run_test(self, provider: LLMProvider, model_name: str) -> bool:
        prompt = "Write a Python function that adds two numbers."
        expected_substring = "def add_numbers(a, b):"

        try:
            # Create a simple LLMRequest for testing
            from gemini_sre_agent.llm.base import LLMRequest
            request = LLMRequest(
                prompt=prompt,
                max_tokens=100,
                temperature=0.1
            )
            response = await provider._generate(request)
            response_content = response.content if hasattr(response, 'content') else str(response)
            return expected_substring.lower() in response_content.lower()
        except Exception as e:
            logger.error(f"Code generation test failed for {model_name}: {e}")
            return False


class CapabilityTester:
    """
    Runs a suite of capability tests against LLM models.
    """

    def __init__(self, providers: Dict[str, LLMProvider], tests: List[CapabilityTest]):
        self.providers = providers
        self.tests = tests

    async def run_all_tests(self) -> Dict[str, Dict[str, bool]]:
        """
        Run all configured tests against all models.

        Returns:
            A dictionary with test results: {model_id: {capability_name: passed}}.
        """
        results = {}
        for provider_name, provider_instance in self.providers.items():
            available_models = provider_instance.get_available_models()
            # Handle both dict and list return types
            model_items: List[tuple] = []
            if isinstance(available_models, dict):
                model_items = list(available_models.items())
            elif isinstance(available_models, list):
                # If it's a list, create tuples with model names
                model_items = [("default", model_name) for model_name in available_models]  # type: ignore
            
            for _model_type, model_name in model_items:
                model_id = f"{provider_name}/{model_name}"
                results[model_id] = {}
                for test in self.tests:
                    logger.info(f"Running test '{test.capability.name}' for {model_id}")
                    passed = await test.run_test(provider_instance, model_name)
                    results[model_id][test.capability.name] = passed
                    logger.info(
                        f"Test '{test.capability.name}' for {model_id}: {'PASSED' if passed else 'FAILED'}"
                    )
        return results
