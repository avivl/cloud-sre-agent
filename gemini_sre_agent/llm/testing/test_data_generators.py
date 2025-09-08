# gemini_sre_agent/llm/testing/test_data_generators.py

"""
Test Data Generators for LLM Testing.

This module provides generators for creating various types of test data
including prompts, responses, and test scenarios for comprehensive testing.
"""

import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from ..base import LLMRequest, ModelType


class PromptType(Enum):
    """Types of prompts for testing."""

    SIMPLE = "simple"
    COMPLEX = "complex"
    LONG = "long"
    SHORT = "short"
    TECHNICAL = "technical"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CONVERSATIONAL = "conversational"
    CODE_GENERATION = "code_generation"
    DATA_PROCESSING = "data_processing"


class TestScenario(Enum):
    """Test scenarios for different use cases."""

    NORMAL = "normal"
    EDGE_CASE = "edge_case"
    STRESS_TEST = "stress_test"
    ERROR_CONDITION = "error_condition"
    PERFORMANCE_TEST = "performance_test"


@dataclass
class TestDataConfig:
    """Configuration for test data generation."""

    min_length: int = 10
    max_length: int = 1000
    include_special_chars: bool = True
    include_numbers: bool = True
    include_unicode: bool = False
    language: str = "en"


class TestDataGenerator:
    """Generator for creating test data for LLM testing."""

    def __init__(self, config: Optional[TestDataConfig] = None):
        """Initialize the test data generator."""
        self.config = config or TestDataConfig()

        # Predefined templates for different prompt types
        self.prompt_templates = {
            PromptType.SIMPLE: [
                "What is {topic}?",
                "Explain {topic} in simple terms.",
                "Tell me about {topic}.",
                "How does {topic} work?",
            ],
            PromptType.COMPLEX: [
                "Analyze the relationship between {topic1} and {topic2} in the context of {context}.",
                "Compare and contrast {topic1} with {topic2}, considering their implications for {domain}.",
                "Evaluate the effectiveness of {approach} in addressing {problem} within {context}.",
                "Synthesize information about {topic1}, {topic2}, and {topic3} to provide a comprehensive analysis.",
            ],
            PromptType.TECHNICAL: [
                "Implement a {algorithm} algorithm in {language} with {requirements}.",
                "Design a {system_type} system that handles {use_case} with {constraints}.",
                "Optimize the following {code_type} code for {optimization_goal}: {code}",
                "Debug the following {language} code and explain the issues: {code}",
            ],
            PromptType.CREATIVE: [
                "Write a {genre} story about {character} who {situation}.",
                "Create a {art_form} that represents {concept} in a {style} style.",
                "Compose a {poem_type} poem about {theme}.",
                "Design a {product_type} that solves {problem} for {target_audience}.",
            ],
            PromptType.ANALYTICAL: [
                "Analyze the data in {dataset} and identify {patterns}.",
                "Perform statistical analysis on {data_type} to determine {objective}.",
                "Create a model to predict {outcome} based on {features}.",
                "Evaluate the performance of {model} using {metrics}.",
            ],
            PromptType.CONVERSATIONAL: [
                "Hi, I'm having trouble with {issue}. Can you help me?",
                "What do you think about {topic}? I'm curious about your perspective.",
                "I need advice on {situation}. What would you recommend?",
                "Can you explain {concept} like I'm {age_group}?",
            ],
            PromptType.CODE_GENERATION: [
                "Write a {language} function that {functionality}.",
                "Create a {class_type} class that implements {interface}.",
                "Generate {test_type} tests for the following {language} code: {code}",
                "Refactor this {language} code to improve {aspect}: {code}",
            ],
            PromptType.DATA_PROCESSING: [
                "Process the following {data_format} data: {data}",
                "Transform {input_format} data to {output_format} format.",
                "Clean and validate the following dataset: {data}",
                "Extract {information_type} from the following text: {text}",
            ],
        }

        # Topics and concepts for template filling
        self.topics = [
            "artificial intelligence",
            "machine learning",
            "data science",
            "software engineering",
            "web development",
            "mobile development",
            "cloud computing",
            "cybersecurity",
            "blockchain",
            "quantum computing",
            "robotics",
            "automation",
            "user experience",
            "product management",
            "business strategy",
            "marketing",
            "finance",
            "healthcare",
            "education",
            "environment",
            "sustainability",
            "innovation",
        ]

        self.languages = [
            "Python",
            "JavaScript",
            "Java",
            "C++",
            "C#",
            "Go",
            "Rust",
            "TypeScript",
            "Swift",
            "Kotlin",
            "PHP",
            "Ruby",
            "Scala",
        ]

        self.genres = [
            "science fiction",
            "fantasy",
            "mystery",
            "romance",
            "thriller",
            "horror",
            "adventure",
            "drama",
            "comedy",
            "historical",
        ]

        self.art_forms = [
            "painting",
            "sculpture",
            "digital art",
            "photography",
            "music",
            "dance",
            "theater",
            "film",
            "literature",
            "poetry",
        ]

    def generate_prompt(
        self,
        prompt_type: PromptType = PromptType.SIMPLE,
        scenario: TestScenario = TestScenario.NORMAL,
        custom_length: Optional[int] = None,
    ) -> str:
        """Generate a test prompt."""
        templates = self.prompt_templates.get(
            prompt_type, self.prompt_templates[PromptType.SIMPLE]
        )
        template = random.choice(templates)  # nosec B311

        # Fill template with random values
        prompt = self._fill_template(template, prompt_type)

        # Adjust length based on scenario
        if scenario == TestScenario.STRESS_TEST:
            prompt = self._make_stress_test_prompt(prompt)
        elif scenario == TestScenario.EDGE_CASE:
            prompt = self._make_edge_case_prompt(prompt)
        elif scenario == TestScenario.ERROR_CONDITION:
            prompt = self._make_error_condition_prompt(prompt)

        # Adjust length if specified
        if custom_length:
            prompt = self._adjust_length(prompt, custom_length)

        return prompt

    def generate_llm_request(
        self,
        prompt_type: PromptType = PromptType.SIMPLE,
        model_type: ModelType = ModelType.SMART,
        max_tokens: int = 100,
        temperature: float = 0.7,
        scenario: TestScenario = TestScenario.NORMAL,
    ) -> LLMRequest:
        """Generate an LLM request for testing."""
        prompt = self.generate_prompt(prompt_type, scenario)

        return LLMRequest(
            prompt=prompt,
            model_type=model_type,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def generate_batch_requests(
        self,
        count: int,
        prompt_type: PromptType = PromptType.SIMPLE,
        model_type: ModelType = ModelType.SMART,
        **kwargs,
    ) -> List[LLMRequest]:
        """Generate a batch of LLM requests."""
        return [
            self.generate_llm_request(prompt_type, model_type, **kwargs)
            for _ in range(count)
        ]

    def generate_test_scenarios(
        self,
        scenario_type: TestScenario,
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        """Generate test scenarios for a specific scenario type."""
        scenarios = []

        for _ in range(count):
            if scenario_type == TestScenario.NORMAL:
                scenario = self._generate_normal_scenario()
            elif scenario_type == TestScenario.EDGE_CASE:
                scenario = self._generate_edge_case_scenario()
            elif scenario_type == TestScenario.STRESS_TEST:
                scenario = self._generate_stress_test_scenario()
            elif scenario_type == TestScenario.ERROR_CONDITION:
                scenario = self._generate_error_condition_scenario()
            elif scenario_type == TestScenario.PERFORMANCE_TEST:
                scenario = self._generate_performance_test_scenario()
            else:
                scenario = self._generate_normal_scenario()

            scenarios.append(scenario)

        return scenarios

    def generate_performance_test_data(
        self,
        test_type: str,
        size: str = "medium",
    ) -> Dict[str, Any]:
        """Generate data for performance testing."""
        size_configs = {
            "small": {"prompt_length": 100, "batch_size": 10, "concurrent_requests": 5},
            "medium": {
                "prompt_length": 500,
                "batch_size": 50,
                "concurrent_requests": 20,
            },
            "large": {
                "prompt_length": 2000,
                "batch_size": 100,
                "concurrent_requests": 50,
            },
        }

        config = size_configs.get(size, size_configs["medium"])

        if test_type == "latency":
            return {
                "requests": self.generate_batch_requests(
                    config["batch_size"],
                    prompt_type=PromptType.SIMPLE,
                ),
                "expected_max_latency_ms": 5000,
                "expected_avg_latency_ms": 1000,
            }
        elif test_type == "throughput":
            return {
                "requests": self.generate_batch_requests(
                    config["batch_size"],
                    prompt_type=PromptType.SIMPLE,
                ),
                "expected_requests_per_second": 10,
                "duration_seconds": 60,
            }
        elif test_type == "concurrency":
            return {
                "requests": self.generate_batch_requests(
                    config["concurrent_requests"],
                    prompt_type=PromptType.SIMPLE,
                ),
                "max_concurrent": config["concurrent_requests"],
                "expected_success_rate": 0.95,
            }
        else:
            return {}

    def _fill_template(self, template: str, prompt_type: PromptType) -> str:
        """Fill a template with random values."""
        filled = template

        # Replace common placeholders
        replacements = {
            "{topic}": random.choice(self.topics),  # nosec B311
            "{topic1}": random.choice(self.topics),  # nosec B311
            "{topic2}": random.choice(self.topics),  # nosec B311
            "{topic3}": random.choice(self.topics),  # nosec B311
            "{language}": random.choice(self.languages),  # nosec B311
            "{genre}": random.choice(self.genres),  # nosec B311
            "{art_form}": random.choice(self.art_forms),  # nosec B311
            "{character}": self._generate_character_name(),
            "{situation}": self._generate_situation(),
            "{concept}": random.choice(self.topics),  # nosec B311
            "{style}": random.choice(
                ["modern", "classical", "abstract", "realistic"]
            ),  # nosec B311
            "{poem_type}": random.choice(
                ["haiku", "sonnet", "free verse", "limerick"]
            ),  # nosec B311
            "{theme}": random.choice(
                ["love", "nature", "technology", "adventure"]
            ),  # nosec B311
            "{product_type}": random.choice(
                ["app", "website", "service", "tool"]
            ),  # nosec B311
            "{problem}": random.choice(  # nosec B311
                ["communication", "productivity", "entertainment", "education"]
            ),
            "{target_audience}": random.choice(  # nosec B311
                ["students", "professionals", "seniors", "children"]
            ),
            "{issue}": random.choice(  # nosec B311
                ["technical problem", "design challenge", "business issue"]
            ),
            "{age_group}": random.choice(  # nosec B311
                ["5 years old", "10 years old", "a beginner", "an expert"]
            ),
            "{algorithm}": random.choice(  # nosec B311
                ["sorting", "searching", "optimization", "machine learning"]
            ),
            "{requirements}": random.choice(  # nosec B311
                ["O(n log n) complexity", "memory efficient", "thread safe"]
            ),
            "{system_type}": random.choice(  # nosec B311
                ["distributed", "microservices", "monolithic", "serverless"]
            ),
            "{use_case}": random.choice(  # nosec B311
                ["real-time processing", "batch processing", "streaming"]
            ),
            "{constraints}": random.choice(  # nosec B311
                ["low latency", "high availability", "cost effective"]
            ),
            "{code_type}": random.choice(  # nosec B311
                ["function", "class", "algorithm", "data structure"]
            ),
            "{optimization_goal}": random.choice(  # nosec B311
                ["performance", "memory usage", "readability"]
            ),
            "{code}": self._generate_sample_code(),
            "{dataset}": "sample_data.csv",
            "{patterns}": random.choice(  # nosec B311
                ["trends", "anomalies", "correlations", "clusters"]
            ),
            "{data_type}": random.choice(  # nosec B311
                ["time series", "categorical", "numerical", "text"]
            ),
            "{objective}": random.choice(  # nosec B311
                ["significance", "distribution", "relationships"]
            ),
            "{outcome}": random.choice(  # nosec B311
                ["success", "failure", "performance", "behavior"]
            ),
            "{features}": random.choice(  # nosec B311
                ["demographic", "behavioral", "temporal", "contextual"]
            ),
            "{model}": random.choice(  # nosec B311
                ["linear regression", "neural network", "decision tree"]
            ),
            "{metrics}": random.choice(
                ["accuracy", "precision", "recall", "F1 score"]
            ),  # nosec B311
            "{data_format}": random.choice(
                ["JSON", "CSV", "XML", "YAML"]
            ),  # nosec B311
            "{input_format}": random.choice(["JSON", "CSV", "XML"]),  # nosec B311
            "{output_format}": random.choice(["JSON", "CSV", "XML"]),  # nosec B311
            "{data}": self._generate_sample_data(),
            "{information_type}": random.choice(  # nosec B311
                ["entities", "sentiments", "keywords", "summaries"]
            ),
            "{text}": self._generate_sample_text(),
            "{context}": random.choice(
                ["business", "academic", "technical", "social"]
            ),  # nosec B311
            "{domain}": random.choice(  # nosec B311
                ["technology", "healthcare", "finance", "education"]
            ),
            "{approach}": random.choice(  # nosec B311
                ["agile", "waterfall", "lean", "design thinking"]
            ),
            "{interface}": random.choice(
                ["REST API", "GraphQL", "gRPC", "WebSocket"]
            ),  # nosec B311
            "{class_type}": random.choice(  # nosec B311
                ["service", "repository", "controller", "model"]
            ),
            "{test_type}": random.choice(  # nosec B311
                ["unit", "integration", "performance", "security"]
            ),
            "{aspect}": random.choice(  # nosec B311
                ["performance", "maintainability", "readability", "security"]
            ),
        }

        for placeholder, value in replacements.items():
            filled = filled.replace(placeholder, value)

        return filled

    def _generate_character_name(self) -> str:
        """Generate a random character name."""
        first_names = [
            "Alex",
            "Jordan",
            "Casey",
            "Taylor",
            "Morgan",
            "Riley",
            "Avery",
            "Quinn",
        ]
        last_names = [
            "Smith",
            "Johnson",
            "Williams",
            "Brown",
            "Jones",
            "Garcia",
            "Miller",
            "Davis",
        ]
        return f"{random.choice(first_names)} {random.choice(last_names)}"  # nosec B311

    def _generate_situation(self) -> str:
        """Generate a random situation."""
        situations = [
            "discovers a hidden talent",
            "faces an unexpected challenge",
            "embarks on a journey",
            "solves a mystery",
            "makes a difficult decision",
            "learns an important lesson",
            "overcomes a fear",
            "helps someone in need",
        ]
        return random.choice(situations)  # nosec B311

    def _generate_sample_code(self) -> str:
        """Generate sample code for testing."""
        code_samples = [
            "def example_function(x):\n    return x * 2",
            "class ExampleClass:\n    def __init__(self):\n        self.value = 0",
            "for i in range(10):\n    print(i)",
            "if condition:\n    do_something()\nelse:\n    do_something_else()",
        ]
        return random.choice(code_samples)  # nosec B311

    def _generate_sample_data(self) -> str:
        """Generate sample data for testing."""
        data_samples = [
            '{"name": "John", "age": 30, "city": "New York"}',
            "name,age,city\nJohn,30,New York\nJane,25,Los Angeles",
            "<person><name>John</name><age>30</age></person>",
            "name: John\nage: 30\ncity: New York",
        ]
        return random.choice(data_samples)  # nosec B311

    def _generate_sample_text(self) -> str:
        """Generate sample text for testing."""
        text_samples = [
            "This is a sample text for testing purposes. It contains multiple sentences and various words.",
            "The quick brown fox jumps over the lazy dog. This is a classic pangram used for testing.",
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod tempor incididunt.",
            "In a world where technology advances rapidly, we must adapt to new challenges and opportunities.",
        ]
        return random.choice(text_samples)  # nosec B311

    def _make_stress_test_prompt(self, prompt: str) -> str:
        """Make a prompt suitable for stress testing."""
        # Make the prompt very long
        return (
            prompt
            + " "
            + " ".join([random.choice(self.topics) for _ in range(50)])  # nosec B311
        )

    def _make_edge_case_prompt(self, prompt: str) -> str:
        """Make a prompt with edge case characteristics."""
        # Add special characters, numbers, and edge cases
        edge_cases = [
            "!@#$%^&*()",
            "1234567890",
            "🚀🌟💡",
            "   multiple   spaces   ",
            "\n\nnewlines\n\n",
            "UPPERCASE and lowercase",
        ]
        return prompt + " " + random.choice(edge_cases)  # nosec B311

    def _make_error_condition_prompt(self, prompt: str) -> str:
        """Make a prompt that might cause errors."""
        error_conditions = [
            "",  # Empty string
            "x" * 100000,  # Very long string
            "null",  # Null-like string
            "undefined",  # Undefined-like string
        ]
        return random.choice(error_conditions)  # nosec B311

    def _adjust_length(self, prompt: str, target_length: int) -> str:
        """Adjust prompt length to target length."""
        if len(prompt) < target_length:
            # Pad with random words
            while len(prompt) < target_length:
                prompt += " " + random.choice(self.topics)  # nosec B311
        elif len(prompt) > target_length:
            # Truncate
            prompt = prompt[:target_length]

        return prompt

    def _generate_normal_scenario(self) -> Dict[str, Any]:
        """Generate a normal test scenario."""
        return {
            "type": "normal",
            "prompt": self.generate_prompt(PromptType.SIMPLE),
            "expected_behavior": "normal_response",
            "timeout_seconds": 30,
        }

    def _generate_edge_case_scenario(self) -> Dict[str, Any]:
        """Generate an edge case test scenario."""
        return {
            "type": "edge_case",
            "prompt": self.generate_prompt(PromptType.SIMPLE, TestScenario.EDGE_CASE),
            "expected_behavior": "handled_gracefully",
            "timeout_seconds": 30,
        }

    def _generate_stress_test_scenario(self) -> Dict[str, Any]:
        """Generate a stress test scenario."""
        return {
            "type": "stress_test",
            "prompt": self.generate_prompt(PromptType.SIMPLE, TestScenario.STRESS_TEST),
            "expected_behavior": "handled_within_limits",
            "timeout_seconds": 60,
        }

    def _generate_error_condition_scenario(self) -> Dict[str, Any]:
        """Generate an error condition test scenario."""
        return {
            "type": "error_condition",
            "prompt": self.generate_prompt(
                PromptType.SIMPLE, TestScenario.ERROR_CONDITION
            ),
            "expected_behavior": "error_handled",
            "timeout_seconds": 30,
        }

    def _generate_performance_test_scenario(self) -> Dict[str, Any]:
        """Generate a performance test scenario."""
        return {
            "type": "performance_test",
            "prompt": self.generate_prompt(PromptType.SIMPLE),
            "expected_behavior": "fast_response",
            "timeout_seconds": 10,
            "expected_max_latency_ms": 1000,
        }

    def generate_edge_case_prompts(self) -> List[str]:
        """Generate edge case prompts for robust testing."""
        from ..constants import MAX_PROMPT_LENGTH

        return [
            "",  # Empty prompt
            "a" * MAX_PROMPT_LENGTH,  # Maximum length
            "🚀" * 1000,  # Unicode stress test
            "\n" * 100,  # Whitespace stress test
            "SELECT * FROM users; DROP TABLE users;",  # Injection attempt
            "<script>alert('xss')</script>",  # XSS attempt
            "javascript:alert('xss')",  # JavaScript injection
            "data:text/html,<script>alert('xss')</script>",  # Data URI injection
            "a" * (MAX_PROMPT_LENGTH + 1),  # Over limit
            "\x00\x01\x02\x03",  # Null bytes and control characters
            "   \t\n   ",  # Only whitespace
            "🎉" * 5000,  # Emoji stress test
        ]

    def generate_performance_stress_data(self, size: str = "medium") -> Dict[str, Any]:
        """Generate data for performance stress testing."""
        sizes = {
            "small": {"requests": 10, "concurrent": 2},
            "medium": {"requests": 100, "concurrent": 5},
            "large": {"requests": 1000, "concurrent": 10},
        }
        return sizes.get(size, sizes["medium"])

    def generate_realistic_failure_scenarios(self) -> List[Dict[str, Any]]:
        """Generate realistic failure scenarios for testing."""
        return [
            {
                "name": "network_timeout",
                "description": "Simulate network timeout",
                "error_type": "TimeoutError",
                "error_message": "Request timed out after 30 seconds",
                "retry_after": 5,
            },
            {
                "name": "rate_limit_exceeded",
                "description": "Simulate rate limit exceeded",
                "error_type": "RateLimitError",
                "error_message": "Rate limit exceeded. Try again in 60 seconds",
                "retry_after": 60,
            },
            {
                "name": "authentication_failed",
                "description": "Simulate authentication failure",
                "error_type": "AuthenticationError",
                "error_message": "Invalid API key",
                "retry_after": None,
            },
            {
                "name": "quota_exceeded",
                "description": "Simulate quota exceeded",
                "error_type": "QuotaExceededError",
                "error_message": "Monthly quota exceeded",
                "retry_after": None,
            },
            {
                "name": "model_unavailable",
                "description": "Simulate model unavailable",
                "error_type": "ModelUnavailableError",
                "error_message": "Model temporarily unavailable",
                "retry_after": 30,
            },
        ]
