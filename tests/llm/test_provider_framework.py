"""
Unit tests for the Provider Addition Framework.

Tests the provider framework components including templates, auto-registry,
validation, plugin loading, and capability discovery.
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gemini_sre_agent.llm.base import LLMRequest, LLMResponse, ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMProviderConfig
from gemini_sre_agent.llm.provider_framework import (
    ProviderAutoRegistry,
    ProviderCapabilityDiscovery,
    ProviderPluginLoader,
    ProviderValidator,
)
from gemini_sre_agent.llm.provider_framework.base_template import BaseProviderTemplate
from gemini_sre_agent.llm.provider_framework.templates import (
    HTTPAPITemplate,
    OpenAICompatibleTemplate,
    RESTAPITemplate,
    StreamingTemplate,
)


class TestBaseProviderTemplate:
    """Test the BaseProviderTemplate class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock LLMProviderConfig."""
        return LLMProviderConfig(
            provider=ProviderType.GEMINI,
            api_key="test_key",
            base_url="https://api.test.com",
            timeout=30,
            max_retries=3,
            rate_limit=100,
        )

    @pytest.fixture
    def concrete_provider(self, mock_config):
        """Create a concrete provider for testing."""

        class TestProvider(BaseProviderTemplate):
            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {
                    "choices": [{"message": {"content": "test response"}}],
                    "model": request.model,
                    "usage": {"total_tokens": 10},
                }

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(
                    content="test response",
                    model="test-model",
                    usage={"total_tokens": 10},
                    finish_reason="stop",
                )

            def _get_model_mapping(self) -> dict:
                return {ModelType.FAST: "test-fast", ModelType.SMART: "test-smart"}

        return TestProvider(mock_config)

    def test_initialization(self, concrete_provider, mock_config):
        """Test provider initialization."""
        assert concrete_provider.api_key == "test_key"
        assert concrete_provider.base_url == "https://api.test.com"
        assert concrete_provider.timeout == 30
        assert concrete_provider.max_retries == 3

    @pytest.mark.asyncio
    async def test_generate(self, concrete_provider):
        """Test response generation."""
        request = LLMRequest(
            messages=[{"role": "user", "content": "Hello"}],
            model="test-model",
            max_tokens=100,
            temperature=0.7,
        )

        response = await concrete_provider.generate(request)

        assert isinstance(response, LLMResponse)
        assert response.content == "test response"
        assert response.model == "test-model"

    @pytest.mark.asyncio
    async def test_health_check(self, concrete_provider):
        """Test health check functionality."""
        with patch.object(concrete_provider, "_make_api_request") as mock_request:
            mock_request.return_value = {"choices": [{"message": {"content": "Hello"}}]}

            health = await concrete_provider.health_check()
            assert isinstance(health, bool)

    def test_get_available_models(self, concrete_provider):
        """Test getting available models."""
        models = concrete_provider.get_available_models()
        assert ModelType.FAST in models
        assert ModelType.SMART in models
        assert models[ModelType.FAST] == "test-fast"
        assert models[ModelType.SMART] == "test-smart"

    def test_supports_streaming(self, concrete_provider):
        """Test streaming support check."""
        assert isinstance(concrete_provider.supports_streaming(), bool)

    def test_supports_tools(self, concrete_provider):
        """Test tools support check."""
        assert isinstance(concrete_provider.supports_tools(), bool)

    def test_token_count(self, concrete_provider):
        """Test token counting."""
        count = concrete_provider.token_count("Hello world")
        assert isinstance(count, int)
        assert count > 0

    def test_cost_estimate(self, concrete_provider):
        """Test cost estimation."""
        cost = concrete_provider.cost_estimate(100, 50)
        assert isinstance(cost, float)
        assert cost >= 0

    def test_validate_config(self, mock_config):
        """Test configuration validation."""

        class TestProvider(BaseProviderTemplate):
            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        # Should not raise an exception
        TestProvider.validate_config(mock_config)

    def test_validate_config_invalid(self):
        """Test configuration validation with invalid config."""

        class TestProvider(BaseProviderTemplate):
            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        invalid_config = LLMProviderConfig(
            provider=ProviderType.GEMINI,
            api_key="",  # Invalid: empty API key
            base_url="https://api.test.com",
            timeout=30,
            max_retries=3,
            rate_limit=100,
        )

        with pytest.raises(ValueError, match="API key is required"):
            TestProvider.validate_config(invalid_config)


class TestProviderTemplates:
    """Test the pre-built provider templates."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock LLMProviderConfig."""
        return LLMProviderConfig(
            provider=ProviderType.GEMINI,
            api_key="test_key",
            base_url="https://api.test.com",
            timeout=30,
            max_retries=3,
            rate_limit=100,
        )

    @pytest.mark.asyncio
    async def test_http_api_template(self, mock_config):
        """Test HTTPAPITemplate."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}],
                "model": "test-model",
                "usage": {"total_tokens": 10},
            }
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.post.return_value = mock_response

            provider = HTTPAPITemplate(mock_config)

            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model="test-model",
                max_tokens=100,
                temperature=0.7,
            )

            response = await provider.generate(request)
            assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_openai_compatible_template(self, mock_config):
        """Test OpenAICompatibleTemplate."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}],
                "model": "test-model",
                "usage": {"total_tokens": 10},
            }
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.post.return_value = mock_response

            provider = OpenAICompatibleTemplate(mock_config)

            assert provider.supports_streaming()
            assert provider.supports_tools()

    @pytest.mark.asyncio
    async def test_rest_api_template(self, mock_config):
        """Test RESTAPITemplate."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}],
                "model": "test-model",
                "usage": {"total_tokens": 10},
            }
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.post.return_value = mock_response

            provider = RESTAPITemplate(mock_config)

            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model="test-model",
                max_tokens=100,
                temperature=0.7,
            )

            response = await provider.generate(request)
            assert isinstance(response, LLMResponse)

    @pytest.mark.asyncio
    async def test_streaming_template(self, mock_config):
        """Test StreamingTemplate."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "test response"}}],
                "model": "test-model",
                "usage": {"total_tokens": 10},
            }
            mock_response.raise_for_status.return_value = None

            mock_client.return_value.post.return_value = mock_response

            provider = StreamingTemplate(mock_config)

            assert provider.supports_streaming()


class TestProviderAutoRegistry:
    """Test the ProviderAutoRegistry class."""

    @pytest.fixture
    def auto_registry(self):
        """Create a ProviderAutoRegistry instance."""
        return ProviderAutoRegistry()

    def test_discover_builtin_providers(self, auto_registry):
        """Test discovering built-in providers."""
        with patch("importlib.import_module") as mock_import:
            mock_module = MagicMock()
            mock_module.__file__ = "/path/to/providers/__init__.py"

            # Mock provider class
            class MockProvider:
                pass

            mock_module.__dict__ = {"MockProvider": MockProvider}
            mock_import.return_value = mock_module

            with patch("pkgutil.iter_modules") as mock_iter:
                mock_iter.return_value = [MagicMock(name="mock_provider")]

                with patch("importlib.import_module") as mock_import_module:
                    mock_import_module.return_value = mock_module

                    auto_registry.discover_builtin_providers()

                    # Should have discovered the provider
                    assert len(auto_registry.discovered_providers) > 0

    def test_extract_provider_name(self, auto_registry):
        """Test provider name extraction."""
        assert auto_registry._extract_provider_name("OpenAIProvider") == "openai"
        assert auto_registry._extract_provider_name("AnthropicProvider") == "anthropic"
        assert auto_registry._extract_provider_name("CustomProvider") == "custom"
        assert auto_registry._extract_provider_name("NotAProvider") is None

    def test_register_discovered_providers(self, auto_registry):
        """Test registering discovered providers."""

        # Mock a provider class
        class MockProvider:
            pass

        auto_registry.discovered_providers["test"] = MockProvider

        with patch(
            "gemini_sre_agent.llm.factory.LLMProviderFactory.register_provider"
        ) as mock_register:
            auto_registry.register_discovered_providers()
            mock_register.assert_called_once_with("test", MockProvider)

    def test_get_provider_info(self, auto_registry):
        """Test getting provider information."""

        class MockProvider:
            """Mock provider class."""

            pass

        auto_registry.discovered_providers["test"] = MockProvider

        info = auto_registry.get_provider_info("test")
        assert info is not None
        assert info["name"] == "test"
        assert info["class"] == "MockProvider"

    def test_validate_discovered_providers(self, auto_registry):
        """Test validating discovered providers."""

        class MockProvider:
            pass

        auto_registry.discovered_providers["test"] = MockProvider

        with patch(
            "gemini_sre_agent.llm.provider_framework.validator.ProviderValidator"
        ) as mock_validator:
            mock_validator.return_value.validate_provider_class.return_value = [
                "error1",
                "error2",
            ]

            results = auto_registry.validate_discovered_providers()
            assert "test" in results
            assert results["test"] == ["error1", "error2"]


class TestProviderValidator:
    """Test the ProviderValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a ProviderValidator instance."""
        return ProviderValidator()

    def test_validate_inheritance(self, validator):
        """Test inheritance validation."""

        class ValidProvider(BaseProviderTemplate):
            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        errors = validator._validate_inheritance(ValidProvider)
        assert len(errors) == 0

        class InvalidProvider:
            pass

        errors = validator._validate_inheritance(InvalidProvider)
        assert len(errors) > 0
        assert "must inherit from LLMProvider" in errors[0]

    def test_validate_abstract_methods(self, validator):
        """Test abstract method validation."""

        class ValidProvider(BaseProviderTemplate):
            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        errors = validator._validate_abstract_methods(ValidProvider)
        assert len(errors) == 0

        class InvalidProvider(BaseProviderTemplate):
            # Missing implementation of abstract methods
            pass

        errors = validator._validate_abstract_methods(InvalidProvider)
        assert len(errors) > 0

    def test_validate_constructor(self, validator):
        """Test constructor validation."""

        class ValidProvider(BaseProviderTemplate):
            def __init__(self, config):
                super().__init__(config)

            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        errors = validator._validate_constructor(ValidProvider)
        assert len(errors) == 0

    def test_validate_config_validation(self, validator):
        """Test config validation method validation."""

        class ValidProvider(BaseProviderTemplate):
            @classmethod
            def validate_config(cls, config):
                super().validate_config(config)

            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        errors = validator._validate_config_validation(ValidProvider)
        assert len(errors) == 0

    def test_generate_validation_report(self, validator):
        """Test validation report generation."""

        class ValidProvider(BaseProviderTemplate):
            """A valid provider implementation."""

            async def _make_api_request(self, request: LLMRequest) -> dict:
                return {}

            def _parse_response(self, response_data: dict) -> LLMResponse:
                return LLMResponse(content="", model="", usage={}, finish_reason="stop")

            def _get_model_mapping(self) -> dict:
                return {}

        report = validator.generate_validation_report(ValidProvider)

        assert "provider_name" in report
        assert "is_valid" in report
        assert "errors" in report
        assert "recommendations" in report
        assert "code_quality_score" in report
        assert report["provider_name"] == "ValidProvider"


class TestProviderPluginLoader:
    """Test the ProviderPluginLoader class."""

    @pytest.fixture
    def plugin_loader(self):
        """Create a ProviderPluginLoader instance."""
        return ProviderPluginLoader()

    def test_add_plugin_path(self, plugin_loader):
        """Test adding plugin paths."""
        plugin_loader.add_plugin_path("/test/path")
        assert "/test/path" in plugin_loader.plugin_paths

    def test_extract_provider_name(self, plugin_loader):
        """Test provider name extraction."""
        assert plugin_loader._extract_provider_name("TestProvider") == "test"
        assert plugin_loader._extract_provider_name("CustomProvider") == "custom"
        assert plugin_loader._extract_provider_name("NotAProvider") is None

    def test_list_loaded_plugins(self, plugin_loader):
        """Test listing loaded plugins."""
        plugins = plugin_loader.list_loaded_plugins()
        assert isinstance(plugins, list)

    def test_get_plugin_info(self, plugin_loader):
        """Test getting plugin information."""
        info = plugin_loader.get_plugin_info("nonexistent")
        assert info is None

    def test_discover_plugins(self, plugin_loader):
        """Test plugin discovery."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create a test plugin file
            plugin_file = Path(temp_dir) / "test_plugin.py"
            plugin_file.write_text(
                """
class TestProvider:
    pass
"""
            )

            discovered = plugin_loader.discover_plugins([temp_dir])
            assert len(discovered) > 0
            assert str(plugin_file) in discovered


class TestProviderCapabilityDiscovery:
    """Test the ProviderCapabilityDiscovery class."""

    @pytest.fixture
    def capability_discovery(self):
        """Create a ProviderCapabilityDiscovery instance."""
        return ProviderCapabilityDiscovery()

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider for testing."""
        provider = MagicMock()
        provider.provider_name = "test_provider"
        provider.supports_streaming.return_value = True
        provider.supports_tools.return_value = False
        provider.get_available_models.return_value = {ModelType.FAST: "test-fast"}
        provider.embeddings = AsyncMock(side_effect=NotImplementedError())
        return provider

    @pytest.mark.asyncio
    async def test_discover_provider_capabilities(
        self, capability_discovery, mock_provider
    ):
        """Test capability discovery for a provider."""
        capabilities = await capability_discovery.discover_provider_capabilities(
            mock_provider
        )

        assert "streaming" in capabilities
        assert "tools" in capabilities
        assert "embeddings" in capabilities

        assert capabilities["streaming"].supported is True
        assert capabilities["tools"].supported is False
        assert capabilities["embeddings"].supported is False

    @pytest.mark.asyncio
    async def test_test_streaming_capability(self, capability_discovery, mock_provider):
        """Test streaming capability detection."""
        result = await capability_discovery._test_streaming_capability(mock_provider)
        assert result is True

    @pytest.mark.asyncio
    async def test_test_tools_capability(self, capability_discovery, mock_provider):
        """Test tools capability detection."""
        result = await capability_discovery._test_tools_capability(mock_provider)
        assert result is False

    @pytest.mark.asyncio
    async def test_test_embeddings_capability(
        self, capability_discovery, mock_provider
    ):
        """Test embeddings capability detection."""
        result = await capability_discovery._test_embeddings_capability(mock_provider)
        assert result is False

    def test_get_capability_description(self, capability_discovery):
        """Test getting capability descriptions."""
        desc = capability_discovery._get_capability_description("streaming")
        assert "streaming" in desc.lower()

        desc = capability_discovery._get_capability_description("unknown")
        assert "unknown" in desc

    def test_find_providers_with_capability(self, capability_discovery):
        """Test finding providers with specific capabilities."""
        # Mock capability registry
        capability_discovery.capability_registry = {
            "provider1": {
                "streaming": MagicMock(supported=True),
                "tools": MagicMock(supported=False),
            },
            "provider2": {
                "streaming": MagicMock(supported=False),
                "tools": MagicMock(supported=True),
            },
        }

        streaming_providers = capability_discovery.find_providers_with_capability(
            "streaming"
        )
        assert "provider1" in streaming_providers
        assert "provider2" not in streaming_providers

        tools_providers = capability_discovery.find_providers_with_capability("tools")
        assert "provider1" not in tools_providers
        assert "provider2" in tools_providers

    def test_find_providers_matching_requirements(self, capability_discovery):
        """Test finding providers matching requirements."""
        # Mock capability registry
        capability_discovery.capability_registry = {
            "provider1": {
                "streaming": MagicMock(supported=True),
                "tools": MagicMock(supported=True),
            },
            "provider2": {
                "streaming": MagicMock(supported=True),
                "tools": MagicMock(supported=False),
            },
        }

        matching = capability_discovery.find_providers_matching_requirements(
            ["streaming", "tools"]
        )
        assert "provider1" in matching
        assert "provider2" not in matching

    def test_get_capability_compatibility_matrix(self, capability_discovery):
        """Test getting compatibility matrix."""
        # Mock capability registry
        capability_discovery.capability_registry = {
            "provider1": {
                "streaming": MagicMock(supported=True),
                "tools": MagicMock(supported=False),
            },
        }

        matrix = capability_discovery.get_capability_compatibility_matrix()
        assert "provider1" in matrix
        assert matrix["provider1"]["streaming"] is True
        assert matrix["provider1"]["tools"] is False

    def test_validate_provider_for_use_case(self, capability_discovery):
        """Test validating provider for use case."""
        # Mock capability registry
        capability_discovery.capability_registry = {
            "provider1": {
                "streaming": MagicMock(supported=True),
                "tools": MagicMock(supported=True),
            },
        }

        validation = capability_discovery.validate_provider_for_use_case(
            "provider1", "tools"
        )
        assert validation["valid"] is True
        assert validation["score"] == 1.0

        validation = capability_discovery.validate_provider_for_use_case(
            "provider1", "vision"
        )
        assert validation["valid"] is False
        assert validation["score"] == 0.0

    def test_export_capability_report(self, capability_discovery):
        """Test exporting capability report."""
        # Mock capability registry
        capability_discovery.capability_registry = {
            "provider1": {
                "streaming": MagicMock(
                    supported=True,
                    to_dict=lambda: {"name": "streaming", "supported": True},
                ),
            },
        }

        report = capability_discovery.export_capability_report()
        assert "summary" in report
        assert "compatibility_matrix" in report
        assert "detailed_capabilities" in report


class TestProviderFrameworkIntegration:
    """Test integration between framework components."""

    @pytest.mark.asyncio
    async def test_end_to_end_provider_creation(self):
        """Test creating a provider using the framework end-to-end."""
        # This test demonstrates the complete workflow of creating a provider
        # using the framework and validating it

        # Create a simple provider using the template
        class TestProvider(HTTPAPITemplate):
            def _get_model_mapping(self):
                return {ModelType.FAST: "test-fast"}

        # Create configuration
        config = LLMProviderConfig(
            provider=ProviderType.GEMINI,
            api_key="test_key",
            base_url="https://api.test.com",
            timeout=30,
            max_retries=3,
            rate_limit=100,
        )

        # Validate configuration
        TestProvider.validate_config(config)

        # Create provider instance
        provider = TestProvider(config)

        # Test basic functionality
        models = provider.get_available_models()
        assert ModelType.FAST in models

        # Test capability discovery
        capability_discovery = ProviderCapabilityDiscovery()
        capabilities = await capability_discovery.discover_provider_capabilities(
            provider
        )
        assert "streaming" in capabilities

        # Test validation
        validator = ProviderValidator()
        errors = validator.validate_provider_class(TestProvider)
        assert len(errors) == 0  # Should be valid

    def test_provider_line_count_requirement(self):
        """Test that providers can be implemented in < 50 lines."""
        # Count lines in the simple provider example
        simple_provider_path = (
            Path(__file__).parent.parent
            / "llm"
            / "provider_framework"
            / "examples"
            / "simple_provider.py"
        )

        if simple_provider_path.exists():
            with open(simple_provider_path, "r") as f:
                lines = f.readlines()

            # Count non-empty, non-comment lines
            code_lines = [
                line
                for line in lines
                if line.strip() and not line.strip().startswith("#")
            ]

            # Should be less than 50 lines
            assert (
                len(code_lines) < 50
            ), f"Simple provider has {len(code_lines)} lines, should be < 50"
