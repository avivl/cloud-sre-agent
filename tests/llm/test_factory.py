# tests/llm/test_factory.py

"""
Tests for the LLM provider factory pattern.
"""

import pytest
from unittest.mock import Mock, patch
from gemini_sre_agent.llm.factory import LLMProviderFactory
from gemini_sre_agent.llm.base import LLMProvider, LLMProviderError, ProviderType
from gemini_sre_agent.llm.config import LLMProviderConfig


class MockProvider(LLMProvider):
    """Mock provider for testing."""
    
    async def generate(self, request):
        return Mock()
    
    async def generate_stream(self, request):
        yield Mock()
    
    async def health_check(self) -> bool:
        return True
    
    def supports_streaming(self) -> bool:
        return True
    
    def supports_tools(self) -> bool:
        return False
    
    def get_available_models(self):
        return {}
    
    @classmethod
    def validate_config(cls, config):
        pass


class TestLLMProviderFactory:
    """Test LLMProviderFactory functionality."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Clear any existing registrations
        LLMProviderFactory._providers.clear()
        LLMProviderFactory._instances.clear()
    
    def teardown_method(self):
        """Clean up after tests."""
        LLMProviderFactory._providers.clear()
        LLMProviderFactory._instances.clear()
    
    def test_register_provider(self):
        """Test provider registration."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        assert "test" in LLMProviderFactory._providers
        assert LLMProviderFactory._providers["test"] == MockProvider
    
    def test_register_invalid_provider(self):
        """Test registration of invalid provider."""
        with pytest.raises(ValueError, match="Provider class must inherit from LLMProvider"):
            LLMProviderFactory.register_provider("invalid", str)
    
    def test_unregister_provider(self):
        """Test provider unregistration."""
        LLMProviderFactory.register_provider("test", MockProvider)
        assert "test" in LLMProviderFactory._providers
        
        LLMProviderFactory.unregister_provider("test")
        assert "test" not in LLMProviderFactory._providers
    
    def test_list_providers(self):
        """Test listing registered providers."""
        LLMProviderFactory.register_provider("test1", MockProvider)
        LLMProviderFactory.register_provider("test2", MockProvider)
        
        providers = LLMProviderFactory.list_providers()
        assert "test1" in providers
        assert "test2" in providers
    
    def test_create_provider_success(self):
        """Test successful provider creation."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        provider = LLMProviderFactory.create_provider("test-provider", config)
        
        assert isinstance(provider, MockProvider)
        assert "test-provider:test:test-model" in LLMProviderFactory._instances
    
    def test_create_provider_unsupported(self):
        """Test creation of unsupported provider."""
        config = Mock()
        config.provider = "unsupported"
        
        with pytest.raises(LLMProviderError, match="Unsupported provider type"):
            LLMProviderFactory.create_provider("test", config)
    
    def test_create_provider_caching(self):
        """Test provider instance caching."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        # Create first instance
        provider1 = LLMProviderFactory.create_provider("test-provider", config)
        
        # Create second instance with same config
        provider2 = LLMProviderFactory.create_provider("test-provider", config)
        
        # Should return the same instance
        assert provider1 is provider2
    
    def test_get_provider(self):
        """Test getting existing provider."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        # Create provider
        LLMProviderFactory.create_provider("test-provider", config)
        
        # Get provider
        provider = LLMProviderFactory.get_provider("test-provider:test:test-model")
        
        assert isinstance(provider, MockProvider)
    
    def test_get_provider_not_found(self):
        """Test getting non-existent provider."""
        provider = LLMProviderFactory.get_provider("non-existent")
        
        assert provider is None
    
    def test_list_instances(self):
        """Test listing provider instances."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        LLMProviderFactory.create_provider("test-provider", config)
        
        instances = LLMProviderFactory.list_instances()
        assert "test-provider:test:test-model" in instances
    
    def test_clear_instances(self):
        """Test clearing all instances."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        LLMProviderFactory.create_provider("test-provider", config)
        assert len(LLMProviderFactory._instances) > 0
        
        LLMProviderFactory.clear_instances()
        assert len(LLMProviderFactory._instances) == 0
    
    def test_health_check_all(self):
        """Test health check on all instances."""
        LLMProviderFactory.register_provider("test", MockProvider)
        
        config = Mock()
        config.provider = "test"
        config.model = "test-model"
        config.max_retries = 3
        
        LLMProviderFactory.create_provider("test-provider", config)
        
        health_status = LLMProviderFactory.health_check_all()
        
        assert "test-provider:test:test-model" in health_status
        assert health_status["test-provider:test:test-model"] is True
