"""
Tests for the configuration management system.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open

from gemini_sre_agent.llm.config_manager import ConfigManager, ConfigSource, get_config_manager, initialize_config
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig, ModelConfig, AgentLLMConfig


class TestConfigManager:
    """Test the ConfigManager class."""
    
    def test_config_manager_initialization(self):
        """Test ConfigManager initialization."""
        manager = ConfigManager()
        assert manager._config is not None
        assert isinstance(manager._config, LLMConfig)
    
    def test_config_manager_with_file_path(self):
        """Test ConfigManager initialization with file path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
default_provider: "openai"
default_model_type: "smart"
providers:
  openai:
    provider: "openai"
    api_key: "test-key"
    models:
      gpt-4:
        name: "gpt-4"
        model_type: "smart"
        max_tokens: 4000
agents: {}
""")
            temp_path = f.name
        
        try:
            manager = ConfigManager(temp_path)
            config = manager.get_config()
            assert config.default_provider == "openai"
            assert config.default_model_type == "smart"
            assert "openai" in config.providers
        finally:
            os.unlink(temp_path)
    
    def test_load_from_environment(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            'LLM_DEFAULT_PROVIDER': 'anthropic',
            'LLM_DEFAULT_MODEL_TYPE': 'fast',
            'OPENAI_API_KEY': 'test-openai-key',
            'ANTHROPIC_API_KEY': 'test-anthropic-key'
        }):
            manager = ConfigManager()
            config = manager.get_config()
            
            assert config.default_provider == "anthropic"
            assert config.default_model_type == "fast"
            assert config.providers["openai"].api_key == "test-openai-key"
            assert config.providers["anthropic"].api_key == "test-anthropic-key"
    
    def test_get_provider_config(self):
        """Test getting provider-specific configuration."""
        manager = ConfigManager()
        
        # Test with non-existing provider (since default config has no providers)
        provider_config = manager.get_provider_config("openai")
        assert provider_config is None
        
        # Test with non-existing provider
        provider_config = manager.get_provider_config("nonexistent")
        assert provider_config is None
    
    def test_get_agent_config(self):
        """Test getting agent-specific configuration."""
        manager = ConfigManager()
        
        # Test with non-existing agent (since default config has no agents)
        agent_config = manager.get_agent_config("triage")
        assert agent_config is None
        
        # Test with non-existing agent
        agent_config = manager.get_agent_config("nonexistent")
        assert agent_config is None
    
    def test_update_config(self):
        """Test updating configuration programmatically."""
        manager = ConfigManager()
        
        # Update default provider
        manager.update_config({"default_provider": "anthropic"})
        config = manager.get_config()
        assert config.default_provider == "anthropic"
        
        # Update provider configuration
        manager.update_config({
            "providers": {
                "openai": {
                    "provider": "openai",
                    "api_key": "new-api-key",
                    "models": {
                        "gpt-4": {
                            "name": "gpt-4",
                            "model_type": "smart",
                            "max_tokens": 8000
                        }
                    }
                }
            }
        })
        config = manager.get_config()
        assert config.providers["openai"].api_key == "new-api-key"
        assert config.providers["openai"].models["gpt-4"].max_tokens == 8000
    
    def test_reload_config(self):
        """Test reloading configuration."""
        manager = ConfigManager()
        original_provider = manager.get_config().default_provider
        
        # Update configuration
        manager.update_config({"default_provider": "anthropic"})
        assert manager.get_config().default_provider == "anthropic"
        
        # Reload should restore original
        manager.reload_config()
        assert manager.get_config().default_provider == original_provider
    
    def test_config_callbacks(self):
        """Test configuration change callbacks."""
        manager = ConfigManager()
        callback_called = False
        callback_config = None
        
        def test_callback(config):
            nonlocal callback_called, callback_config
            callback_called = True
            callback_config = config
        
        manager.add_callback(test_callback)
        
        # Update configuration should trigger callback
        manager.update_config({"default_provider": "anthropic"})
        
        assert callback_called
        assert callback_config is not None
        assert callback_config.default_provider == "anthropic"
    
    def test_validate_config(self):
        """Test configuration validation."""
        manager = ConfigManager()
        
        # Valid configuration should have no errors
        errors = manager.validate_config()
        assert isinstance(errors, list)
        
        # Test with invalid configuration - this should fail during update_config
        with pytest.raises(Exception):  # Should raise ValidationError
            manager.update_config({
                "providers": {
                    "openai": {
                        "provider": "openai",
                        "api_key": "",  # Invalid: empty API key
                        "models": {
                            "gpt-4": {
                                "name": "gpt-4",
                                "model_type": "smart",
                                "max_tokens": -1  # Invalid: negative max_tokens
                            }
                        }
                    }
                }
            })
    
    def test_get_config_summary(self):
        """Test getting configuration summary."""
        manager = ConfigManager()
        summary = manager.get_config_summary()
        
        assert isinstance(summary, dict)
        assert "default_provider" in summary
        assert "default_model_type" in summary
        assert "providers" in summary
        assert "agents" in summary
        assert "sources" in summary
    
    def test_export_config_yaml(self):
        """Test exporting configuration to YAML."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            manager.export_config(temp_path, format='yaml')
            
            # Verify file was created and contains expected content
            assert Path(temp_path).exists()
            with open(temp_path, 'r') as f:
                content = f.read()
                assert "default_provider" in content
                assert "providers" in content
        
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)
    
    def test_export_config_json(self):
        """Test exporting configuration to JSON."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name
        
        try:
            manager.export_config(temp_path, format='json')
            
            # Verify file was created and contains expected content
            assert Path(temp_path).exists()
            with open(temp_path, 'r') as f:
                content = f.read()
                assert "default_provider" in content
                assert "providers" in content
        
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)
    
    def test_export_config_invalid_format(self):
        """Test exporting configuration with invalid format."""
        manager = ConfigManager()
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            temp_path = f.name
        
        try:
            with pytest.raises(ValueError, match="Unsupported format"):
                manager.export_config(temp_path, format='txt')
        
        finally:
            if Path(temp_path).exists():
                os.unlink(temp_path)


class TestConfigSource:
    """Test the ConfigSource dataclass."""
    
    def test_config_source_creation(self):
        """Test ConfigSource creation."""
        source = ConfigSource(
            source_type='file',
            path='/path/to/config.yaml',
            priority=1,
            metadata={'format': 'yaml'}
        )
        
        assert source.source_type == 'file'
        assert source.path == '/path/to/config.yaml'
        assert source.priority == 1
        assert source.metadata == {'format': 'yaml'}
    
    def test_config_source_defaults(self):
        """Test ConfigSource with default values."""
        source = ConfigSource(source_type='env')
        
        assert source.source_type == 'env'
        assert source.path is None
        assert source.priority == 0
        assert source.metadata == {}


class TestGlobalConfigManager:
    """Test global configuration manager functions."""
    
    def test_get_config_manager(self):
        """Test getting the global configuration manager."""
        manager = get_config_manager()
        assert isinstance(manager, ConfigManager)
        
        # Should return the same instance
        manager2 = get_config_manager()
        assert manager is manager2
    
    def test_initialize_config(self):
        """Test initializing the global configuration manager."""
        manager = initialize_config()
        assert isinstance(manager, ConfigManager)
        
        # Should return the same instance
        manager2 = get_config_manager()
        assert manager is manager2
    
    def test_initialize_config_with_path(self):
        """Test initializing the global configuration manager with path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write("""
default_provider: "anthropic"
default_model_type: "fast"
providers: {}
agents: {}
""")
            temp_path = f.name
        
        try:
            manager = initialize_config(temp_path)
            assert isinstance(manager, ConfigManager)
            
            config = manager.get_config()
            assert config.default_provider == "anthropic"
            assert config.default_model_type == "fast"
        
        finally:
            os.unlink(temp_path)
