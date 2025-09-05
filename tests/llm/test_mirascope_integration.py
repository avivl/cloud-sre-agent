# tests/llm/test_mirascope_integration.py

"""
Tests for Mirascope Prompt Management Integration.
"""

import tempfile
from unittest.mock import AsyncMock, MagicMock

import pytest
from pydantic import BaseModel

from gemini_sre_agent.llm.mirascope_integration import (
    PromptCollaborationManager,
    PromptEnvironment,
    PromptManager,
    PromptOptimizer,
)
from gemini_sre_agent.llm.prompt_service import (
    LLMPromptService,
    MirascopeIntegratedLLMService,
)


class MockResponseModel(BaseModel):
    """Test response model for testing."""

    answer: str
    confidence: float


@pytest.fixture
def temp_storage():
    """Create a temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield temp_dir


@pytest.fixture
def prompt_manager(temp_storage):
    """Create a prompt manager for testing."""
    return PromptManager(storage_path=temp_storage)


@pytest.fixture
def mock_llm_service():
    """Create a mock LLM service for testing."""
    service = MagicMock()
    service.generate_structured_output = AsyncMock()
    service.generate_text = AsyncMock()
    service.generate = AsyncMock()
    service.last_token_count = 100
    service.last_model_used = "test-model"
    return service


class TestPromptManager:
    """Test the PromptManager class."""

    def test_create_prompt(self, prompt_manager):
        """Test creating a new prompt."""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt",
            template="This is a {{test}} prompt",
            description="A test prompt",
        )

        assert prompt_id is not None
        assert prompt_id in prompt_manager.prompts
        assert prompt_manager.prompts[prompt_id].name == "Test Prompt"
        assert prompt_manager.prompts[prompt_id].current_version == "1.0.0"
        assert prompt_manager.prompts[prompt_id].description == "A test prompt"

    def test_get_prompt(self, prompt_manager):
        """Test getting a prompt."""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt", template="This is a {{test}} prompt"
        )

        prompt = prompt_manager.get_prompt(prompt_id)
        assert prompt is not None

        # Test formatting if it's a string template
        if isinstance(prompt, str):
            # Use string replacement for template variables
            formatted = prompt.replace("{{test}}", "formatted")
            assert "This is a formatted prompt" in formatted

    def test_create_version(self, prompt_manager):
        """Test creating a new version of a prompt."""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt", template="Version 1"
        )

        version = prompt_manager.create_version(prompt_id, "Version 2")
        assert version == "1.0.1"

        # Test getting the new version
        prompt = prompt_manager.get_prompt(prompt_id, version)
        if isinstance(prompt, str):
            assert "Version 2" in prompt

    def test_test_prompt(self, prompt_manager):
        """Test running tests on a prompt."""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt", template="The answer is {{value}}"
        )

        test_cases = [
            {"inputs": {"value": "42"}, "expected": "The answer is 42"},
            {"inputs": {"value": "wrong"}, "expected": "The answer is 43"},
        ]

        results = prompt_manager.test_prompt(prompt_id, test_cases)
        assert results["success_rate"] == 0.5
        assert len(results["results"]) == 2
        assert results["results"][0]["success"] is True
        assert results["results"][1]["success"] is False

    def test_record_metrics(self, prompt_manager):
        """Test recording metrics for a prompt."""
        prompt_id = prompt_manager.create_prompt(
            name="Test Prompt", template="Test template"
        )

        metrics = {"duration_seconds": 1.5, "token_count": 100, "success": True}

        prompt_manager.record_metrics(prompt_id, metrics)

        prompt_data = prompt_manager.prompts[prompt_id]
        version_data = prompt_data.versions[prompt_data.current_version]

        assert "duration_seconds" in version_data.metrics
        assert version_data.metrics["duration_seconds"] == 1.5
        assert len(version_data.metrics_history) == 1

    def test_list_prompts(self, prompt_manager):
        """Test listing all prompts."""
        prompt_manager.create_prompt("Prompt 1", "Template 1")
        prompt_manager.create_prompt("Prompt 2", "Template 2")

        prompts = prompt_manager.list_prompts()
        assert len(prompts) == 2

        prompt_names = [p["name"] for p in prompts]
        assert "Prompt 1" in prompt_names
        assert "Prompt 2" in prompt_names

    def test_get_prompt_versions(self, prompt_manager):
        """Test getting all versions for a prompt."""
        prompt_id = prompt_manager.create_prompt("Test Prompt", "Version 1")
        prompt_manager.create_version(prompt_id, "Version 2")
        prompt_manager.create_version(prompt_id, "Version 3")

        versions = prompt_manager.get_prompt_versions(prompt_id)
        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "1.0.1" in versions
        assert "1.0.2" in versions

    def test_prompt_not_found(self, prompt_manager):
        """Test error handling for non-existent prompts."""
        with pytest.raises(ValueError, match="Prompt with ID.*not found"):
            prompt_manager.get_prompt("non-existent-id")

    def test_version_not_found(self, prompt_manager):
        """Test error handling for non-existent versions."""
        prompt_id = prompt_manager.create_prompt("Test Prompt", "Template")

        with pytest.raises(ValueError, match="Version.*not found"):
            prompt_manager.get_prompt(prompt_id, "non-existent-version")


class TestPromptEnvironment:
    """Test the PromptEnvironment class."""

    def test_environment_deployment(self, prompt_manager):
        """Test environment-specific prompt deployment."""
        prompt_id = prompt_manager.create_prompt(
            name="Environment Test", template="Production version"
        )

        # Create a new version
        prompt_manager.create_version(prompt_id, "Development version")

        # Create environments
        prod_env = PromptEnvironment("production", prompt_manager)
        dev_env = PromptEnvironment("development", prompt_manager)

        # Deploy specific versions
        prod_env.deploy_prompt(prompt_id, "1.0.0")
        dev_env.deploy_prompt(prompt_id, "1.0.1")

        # Verify environment-specific prompts
        prod_prompt = prod_env.get_prompt(prompt_id)
        dev_prompt = dev_env.get_prompt(prompt_id)

        if isinstance(prod_prompt, str):
            assert "Production version" in prod_prompt
        if isinstance(dev_prompt, str):
            assert "Development version" in dev_prompt

    def test_environment_fallback(self, prompt_manager):
        """Test environment fallback to current version."""
        prompt_id = prompt_manager.create_prompt(
            name="Fallback Test", template="Current version"
        )

        env = PromptEnvironment("test", prompt_manager)

        # Get prompt without deploying specific version
        prompt = env.get_prompt(prompt_id)
        assert prompt is not None


class TestPromptCollaborationManager:
    """Test the PromptCollaborationManager class."""

    def test_collaboration_workflow(self, prompt_manager):
        """Test review workflow."""
        prompt_id = prompt_manager.create_prompt(
            name="Collaboration Test", template="Initial version"
        )

        collab_manager = PromptCollaborationManager(prompt_manager)

        # Create a review
        review_id = collab_manager.create_review(
            prompt_id=prompt_id,
            version="1.0.0",
            reviewer="test@example.com",
            comments="Looks good but needs improvement",
        )

        # Verify review was created
        assert prompt_id in collab_manager.reviews
        assert len(collab_manager.reviews[prompt_id]) == 1
        assert collab_manager.reviews[prompt_id][0]["status"] == "pending"

        # Approve the review
        collab_manager.approve_review(review_id)
        assert collab_manager.reviews[prompt_id][0]["status"] == "approved"

    def test_review_rejection(self, prompt_manager):
        """Test review rejection."""
        prompt_id = prompt_manager.create_prompt("Test Prompt", "Template")

        collab_manager = PromptCollaborationManager(prompt_manager)
        review_id = collab_manager.create_review(
            prompt_id=prompt_id,
            version="1.0.0",
            reviewer="test@example.com",
            comments="Needs work",
        )

        collab_manager.reject_review(review_id, "Not clear enough")

        review = collab_manager.reviews[prompt_id][0]
        assert review["status"] == "rejected"
        assert review["rejection_reason"] == "Not clear enough"

    def test_review_not_found(self, prompt_manager):
        """Test error handling for non-existent reviews."""
        collab_manager = PromptCollaborationManager(prompt_manager)

        with pytest.raises(ValueError, match="Review with ID.*not found"):
            collab_manager.approve_review("non-existent-review")


class TestPromptOptimizer:
    """Test the PromptOptimizer class."""

    @pytest.mark.asyncio
    async def test_prompt_optimization(self, prompt_manager, mock_llm_service):
        """Test prompt optimization."""
        mock_llm_service.generate_text.return_value = "Optimized prompt template"

        optimizer = PromptOptimizer(prompt_manager, mock_llm_service)

        prompt_id = prompt_manager.create_prompt(
            name="Optimization Test", template="Initial template"
        )

        test_cases = [{"inputs": {"value": "test"}, "expected": "Expected output"}]

        new_version = await optimizer.optimize_prompt(
            prompt_id, ["clarity", "conciseness"], test_cases
        )

        assert new_version == "1.0.1"
        assert (
            prompt_manager.prompts[prompt_id].versions[new_version].template
            == "Optimized prompt template"
        )

    @pytest.mark.asyncio
    async def test_optimization_without_llm_service(self, prompt_manager):
        """Test optimization without LLM service."""
        optimizer = PromptOptimizer(prompt_manager, None)

        prompt_id = prompt_manager.create_prompt("Test Prompt", "Template")

        with pytest.raises(ValueError, match="LLM service required for optimization"):
            await optimizer.optimize_prompt(prompt_id, ["clarity"], [])


class TestLLMPromptService:
    """Test the LLMPromptService class."""

    @pytest.mark.asyncio
    async def test_execute_prompt_structured(self, prompt_manager, mock_llm_service):
        """Test executing a prompt with structured output."""
        mock_llm_service.generate_structured_output.return_value = MockResponseModel(
            answer="Test answer", confidence=0.95
        )

        prompt_service = LLMPromptService(mock_llm_service, prompt_manager)

        prompt_id = prompt_manager.create_prompt(
            name="Service Test", template="Answer this: {{question}}"
        )

        result = await prompt_service.execute_prompt(
            prompt_id, {"question": "What is the meaning of life?"}, MockResponseModel
        )

        assert result.answer == "Test answer"
        assert result.confidence == 0.95
        mock_llm_service.generate_structured_output.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_prompt_text(self, prompt_manager, mock_llm_service):
        """Test executing a prompt with text output."""
        mock_llm_service.generate_text.return_value = "Test response"

        prompt_service = LLMPromptService(mock_llm_service, prompt_manager)

        prompt_id = prompt_manager.create_prompt(
            name="Text Test", template="Generate: {{topic}}"
        )

        result = await prompt_service.execute_prompt_text(
            prompt_id, {"topic": "test content"}
        )

        assert result == "Test response"
        mock_llm_service.generate_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_prompt_with_environment(
        self, prompt_manager, mock_llm_service
    ):
        """Test executing a prompt with environment-specific version."""
        mock_llm_service.generate_text.return_value = "Environment response"

        # Create environment and deploy specific version
        env = PromptEnvironment("test", prompt_manager)
        prompt_id = prompt_manager.create_prompt("Test Prompt", "Version 1")
        prompt_manager.create_version(prompt_id, "Version 2")
        env.deploy_prompt(prompt_id, "1.0.1")

        prompt_service = LLMPromptService(mock_llm_service, prompt_manager, env)

        result = await prompt_service.execute_prompt_text(prompt_id, {"input": "test"})

        assert result == "Environment response"

    @pytest.mark.asyncio
    async def test_execute_prompt_error_handling(
        self, prompt_manager, mock_llm_service
    ):
        """Test error handling in prompt execution."""
        mock_llm_service.generate_text.side_effect = Exception("LLM service error")

        prompt_service = LLMPromptService(mock_llm_service, prompt_manager)

        prompt_id = prompt_manager.create_prompt("Test Prompt", "Template")

        with pytest.raises(Exception, match="LLM service error"):
            await prompt_service.execute_prompt_text(prompt_id, {})

        # Check that error metrics were recorded
        prompt_data = prompt_manager.prompts[prompt_id]
        version_data = prompt_data.versions[prompt_data.current_version]
        assert len(version_data.metrics_history) == 1
        assert version_data.metrics_history[0]["data"]["success"] is False


class TestMirascopeIntegratedLLMService:
    """Test the MirascopeIntegratedLLMService class."""

    def test_integrated_service_creation(self, prompt_manager, mock_llm_service):
        """Test creating an integrated LLM service."""
        integrated_service = MirascopeIntegratedLLMService(
            mock_llm_service, prompt_manager
        )

        assert integrated_service.llm_service == mock_llm_service
        assert integrated_service.prompt_manager == prompt_manager
        assert isinstance(integrated_service.prompt_service, LLMPromptService)

    def test_create_environment(self, prompt_manager, mock_llm_service):
        """Test creating a new environment."""
        integrated_service = MirascopeIntegratedLLMService(
            mock_llm_service, prompt_manager
        )

        env = integrated_service.create_environment("test-env")
        assert isinstance(env, PromptEnvironment)
        assert env.name == "test-env"

    def test_get_managers(self, prompt_manager, mock_llm_service):
        """Test getting manager instances."""
        integrated_service = MirascopeIntegratedLLMService(
            mock_llm_service, prompt_manager
        )

        assert integrated_service.get_prompt_manager() == prompt_manager
        assert isinstance(integrated_service.get_prompt_service(), LLMPromptService)


class TestPersistence:
    """Test persistence functionality."""

    def test_save_and_load_prompts(self, temp_storage):
        """Test saving and loading prompts from storage."""
        # Create first manager and add prompts
        manager1 = PromptManager(storage_path=temp_storage)
        prompt_id1 = manager1.create_prompt("Prompt 1", "Template 1")
        prompt_id2 = manager1.create_prompt("Prompt 2", "Template 2")

        # Create second manager and load prompts
        manager2 = PromptManager(storage_path=temp_storage)

        # Verify prompts were loaded
        assert prompt_id1 in manager2.prompts
        assert prompt_id2 in manager2.prompts
        assert manager2.prompts[prompt_id1].name == "Prompt 1"
        assert manager2.prompts[prompt_id2].name == "Prompt 2"

    def test_version_persistence(self, temp_storage):
        """Test that prompt versions are persisted correctly."""
        manager1 = PromptManager(storage_path=temp_storage)
        prompt_id = manager1.create_prompt("Test Prompt", "Version 1")
        manager1.create_version(prompt_id, "Version 2")
        manager1.create_version(prompt_id, "Version 3")

        manager2 = PromptManager(storage_path=temp_storage)

        versions = manager2.get_prompt_versions(prompt_id)
        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "1.0.1" in versions
        assert "1.0.2" in versions


if __name__ == "__main__":
    pytest.main([__file__])
