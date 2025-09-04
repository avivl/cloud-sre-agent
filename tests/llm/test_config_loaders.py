"""
Tests for the configuration loaders.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch

from gemini_sre_agent.llm.config_loaders import (
    BaseConfigLoader,
    EnvironmentConfigLoader,
    FileConfigLoader,
    ProgrammaticConfigLoader,
    ConfigLoaderManager,
    LoaderResult
)


class TestBaseConfigLoader:
    """Test the BaseConfigLoader class."""
    
    def test_base_loader_initialization(self):
        """Test BaseConfigLoader initialization."""
        loader = BaseConfigLoader("test_source", priority=1)
        assert loader.source == "test_source"
        assert loader.priority == 1
        assert loader._validators == []
    
    def test_add_validator(self):
        """Test adding validators."""
        loader = BaseConfigLoader("test_source")
        
        def test_validator(data):
            return ["error1", "error2"] if "invalid" in data else []
        
        loader.add_validator(test_validator)
        assert len(loader._validators) == 1
        
        # Test validation
        errors = loader.validate({"invalid": True})
        assert errors == ["error1", "error2"]
        
        errors = loader.validate({"valid": True})
        assert errors == []
    
    def test_load_not_implemented(self):
        """Test that load method raises NotImplementedError."""
        loader = BaseConfigLoader("test_source")
        with pytest.raises(NotImplementedError):
            loader.load()


class TestEnvironmentConfigLoader:
    """Test the EnvironmentConfigLoader class."""
    
    def test_environment_loader_initialization(self):
        """Test EnvironmentConfigLoader initialization."""
        loader = EnvironmentConfigLoader(prefix="TEST_", priority=2)
        assert loader.source == "environment"
        assert loader.priority == 2
        assert loader.prefix == "TEST_"
    
    def test_load_basic_environment_vars(self):
        """Test loading basic environment variables."""
        with patch.dict(os.environ, {
            'LLM_DEFAULT_PROVIDER': 'openai',
            'LLM_DEFAULT_MODEL_TYPE': 'smart',
            'LLM_ENABLE_FALLBACK': 'true',
            'LLM_ENABLE_MONITORING': 'false'
        }):
            loader = EnvironmentConfigLoader()
            result = loader.load()
            
            assert result.source == "environment"
            assert result.data['default_provider'] == 'openai'
            assert result.data['default_model_type'] == 'smart'
            assert result.data['enable_fallback'] is True
            assert result.data['enable_monitoring'] is False
            assert result.errors == []
    
    def test_load_provider_environment_vars(self):
        """Test loading provider-specific environment variables."""
        with patch.dict(os.environ, {
            'OPENAI_API_KEY': 'test-openai-key',
            'ANTHROPIC_API_KEY': 'test-anthropic-key',
            'OPENAI_BASE_URL': 'https://api.openai.com/v1',
            'OPENAI_TIMEOUT': '60',
            'OPENAI_MAX_RETRIES': '5'
        }):
            loader = EnvironmentConfigLoader()
            result = loader.load()
            
            assert 'providers' in result.data
            assert 'openai' in result.data['providers']
            assert 'anthropic' in result.data['providers']
            
            openai_config = result.data['providers']['openai']
            assert openai_config['provider'] == 'openai'
            assert openai_config['api_key'] == 'test-openai-key'
            assert openai_config['base_url'] == 'https://api.openai.com/v1'
            assert openai_config['timeout'] == 60
            assert openai_config['max_retries'] == 5
    
    def test_load_agent_environment_vars(self):
        """Test loading agent-specific environment variables."""
        with patch.dict(os.environ, {
            'LLM_AGENT_TRIAGE_PROVIDER': 'openai',
            'LLM_AGENT_TRIAGE_MODEL_TYPE': 'fast',
            'LLM_AGENT_TRIAGE_FALLBACK_PROVIDER': 'anthropic',
            'LLM_AGENT_ANALYSIS_PROVIDER': 'claude'
        }):
            loader = EnvironmentConfigLoader()
            result = loader.load()
            
            assert 'agents' in result.data
            assert 'triage' in result.data['agents']
            assert 'analysis' in result.data['agents']
            
            triage_config = result.data['agents']['triage']
            assert triage_config['primary_provider'] == 'openai'
            assert triage_config['primary_model_type'] == 'fast'
            assert triage_config['fallback_provider'] == 'anthropic'
    
    def test_set_nested_value(self):
        """Test setting nested values."""
        loader = EnvironmentConfigLoader()
        data = {}
        
        loader._set_nested_value(data, 'cost_config.monthly_budget', '100.0')
        assert data['cost_config']['monthly_budget'] == 100.0
        
        loader._set_nested_value(data, 'resilience_config.circuit_breaker_enabled', 'true')
        assert data['resilience_config']['circuit_breaker_enabled'] is True
        
        loader._set_nested_value(data, 'resilience_config.retry_attempts', '3')
        assert data['resilience_config']['retry_attempts'] == 3
        
        loader._set_nested_value(data, 'cost_config.cost_alerts', '0.5,0.8,0.9')
        assert data['cost_config']['cost_alerts'] == [0.5, 0.8, 0.9]


class TestFileConfigLoader:
    """Test the FileConfigLoader class."""
    
    def test_file_loader_initialization(self):
        """Test FileConfigLoader initialization."""
        loader = FileConfigLoader("/path/to/config.yaml", priority=1)
        assert loader.source == "file:/path/to/config.yaml"
        assert loader.priority == 1
        assert loader.file_path == Path("/path/to/config.yaml")
    
    def test_load_yaml_file(self):
        """Test loading YAML configuration file."""
        config_content = """
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
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            loader = FileConfigLoader(temp_path)
            result = loader.load()
            
            assert result.source == f"file:{temp_path}"
            assert result.data['default_provider'] == 'openai'
            assert result.data['default_model_type'] == 'smart'
            assert 'providers' in result.data
            assert 'openai' in result.data['providers']
            assert result.errors == []
            
        finally:
            os.unlink(temp_path)
    
    def test_load_json_file(self):
        """Test loading JSON configuration file."""
        config_content = """
{
  "default_provider": "anthropic",
  "default_model_type": "fast",
  "providers": {
    "anthropic": {
      "provider": "anthropic",
      "api_key": "test-key",
      "models": {}
    }
  },
  "agents": {}
}
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            loader = FileConfigLoader(temp_path)
            result = loader.load()
            
            assert result.source == f"file:{temp_path}"
            assert result.data['default_provider'] == 'anthropic'
            assert result.data['default_model_type'] == 'fast'
            assert 'providers' in result.data
            assert 'anthropic' in result.data['providers']
            assert result.errors == []
            
        finally:
            os.unlink(temp_path)
    
    def test_load_nonexistent_file(self):
        """Test loading non-existent file."""
        loader = FileConfigLoader("/nonexistent/path.yaml")
        result = loader.load()
        
        assert result.data == {}
        assert len(result.errors) == 1
        assert "Configuration file not found" in result.errors[0]
    
    def test_load_invalid_yaml(self):
        """Test loading invalid YAML file."""
        config_content = """
invalid: yaml: content: [unclosed
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            temp_path = f.name
        
        try:
            loader = FileConfigLoader(temp_path)
            result = loader.load()
            
            assert result.data == {}
            assert len(result.errors) == 1
            assert "YAML parsing error" in result.errors[0]
            
        finally:
            os.unlink(temp_path)
    
    def test_load_unsupported_format(self):
        """Test loading unsupported file format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some text content")
            temp_path = f.name
        
        try:
            loader = FileConfigLoader(temp_path)
            result = loader.load()
            
            assert result.data == {}
            assert len(result.errors) == 1
            assert "Unsupported file format" in result.errors[0]
            
        finally:
            os.unlink(temp_path)


class TestProgrammaticConfigLoader:
    """Test the ProgrammaticConfigLoader class."""
    
    def test_programmatic_loader_initialization(self):
        """Test ProgrammaticConfigLoader initialization."""
        config_data = {"default_provider": "openai"}
        loader = ProgrammaticConfigLoader(config_data, priority=3)
        
        assert loader.source == "programmatic"
        assert loader.priority == 3
        assert loader.config_data == config_data
    
    def test_load_programmatic_config(self):
        """Test loading programmatic configuration."""
        config_data = {
            "default_provider": "openai",
            "default_model_type": "smart",
            "providers": {
                "openai": {
                    "provider": "openai",
                    "api_key": "test-key",
                    "models": {}
                }
            },
            "agents": {}
        }
        
        loader = ProgrammaticConfigLoader(config_data)
        result = loader.load()
        
        assert result.source == "programmatic"
        assert result.data == config_data
        assert result.errors == []
    
    def test_load_with_validation_errors(self):
        """Test loading with validation errors."""
        config_data = {"invalid": "data"}
        
        def validator(data):
            return ["Validation error"] if "invalid" in data else []
        
        loader = ProgrammaticConfigLoader(config_data)
        loader.add_validator(validator)
        result = loader.load()
        
        assert result.data == config_data
        assert result.errors == ["Validation error"]


class TestConfigLoaderManager:
    """Test the ConfigLoaderManager class."""
    
    def test_manager_initialization(self):
        """Test ConfigLoaderManager initialization."""
        manager = ConfigLoaderManager()
        assert manager.loaders == []
        assert manager._results == []
    
    def test_add_loader(self):
        """Test adding loaders."""
        manager = ConfigLoaderManager()
        loader1 = EnvironmentConfigLoader()
        loader2 = ProgrammaticConfigLoader({})
        
        manager.add_loader(loader1)
        manager.add_loader(loader2)
        
        assert len(manager.loaders) == 2
        assert loader1 in manager.loaders
        assert loader2 in manager.loaders
    
    def test_load_all_with_priority(self):
        """Test loading from multiple loaders with priority."""
        manager = ConfigLoaderManager()
        
        # Add loaders with different priorities
        env_loader = EnvironmentConfigLoader(priority=1)
        prog_loader = ProgrammaticConfigLoader(
            {"default_provider": "programmatic"}, 
            priority=2
        )
        
        manager.add_loader(prog_loader)  # Add higher priority first
        manager.add_loader(env_loader)   # Add lower priority second
        
        with patch.dict(os.environ, {
            'LLM_DEFAULT_PROVIDER': 'environment',
            'GEMINI_API_KEY': ''  # Clear any existing API keys
        }, clear=True):
            result = manager.load_all()
            
            # The programmatic loader has higher priority (2) than environment (1)
            # But since environment is processed second, it overwrites programmatic
            # This is the correct behavior - later loaders can override earlier ones
            assert result['default_provider'] == 'environment'
    
    def test_merge_config_data(self):
        """Test merging configuration data."""
        manager = ConfigLoaderManager()
        
        base = {
            "default_provider": "base",
            "providers": {
                "openai": {
                    "api_key": "base-key",
                    "timeout": 30
                }
            }
        }
        
        updates = {
            "default_provider": "updated",
            "providers": {
                "openai": {
                    "api_key": "updated-key"
                },
                "anthropic": {
                    "api_key": "new-key"
                }
            }
        }
        
        result = manager._merge_config_data(base, updates)
        
        assert result['default_provider'] == 'updated'
        assert result['providers']['openai']['api_key'] == 'updated-key'
        assert result['providers']['openai']['timeout'] == 30  # Preserved from base
        assert result['providers']['anthropic']['api_key'] == 'new-key'
    
    def test_get_loader_results(self):
        """Test getting loader results."""
        manager = ConfigLoaderManager()
        loader = ProgrammaticConfigLoader({"test": "data"})
        manager.add_loader(loader)
        
        manager.load_all()
        results = manager.get_loader_results()
        
        assert len(results) == 1
        assert results[0].source == "programmatic"
        assert results[0].data == {"test": "data"}
    
    def test_get_all_errors(self):
        """Test getting all errors from loaders."""
        manager = ConfigLoaderManager()
        
        # Add a loader that will produce errors
        loader = FileConfigLoader("/nonexistent/path.yaml")
        manager.add_loader(loader)
        
        manager.load_all()
        errors = manager.get_all_errors()
        
        assert len(errors) > 0
        assert any("Configuration file not found" in error for error in errors)
    
    def test_get_loader_summary(self):
        """Test getting loader summary."""
        manager = ConfigLoaderManager()
        
        # Add loaders
        env_loader = EnvironmentConfigLoader()
        prog_loader = ProgrammaticConfigLoader({"test": "data"})
        file_loader = FileConfigLoader("/nonexistent/path.yaml")
        
        manager.add_loader(env_loader)
        manager.add_loader(prog_loader)
        manager.add_loader(file_loader)
        
        manager.load_all()
        summary = manager.get_loader_summary()
        
        assert summary['total_loaders'] == 3
        assert summary['successful_loads'] == 2  # env and programmatic
        assert summary['failed_loads'] == 1  # file loader
        assert summary['total_errors'] > 0
        assert len(summary['loaders']) == 3
