# tests/llm/test_model_registry.py

"""
Unit tests for the ModelRegistry class.
"""

import tempfile
import yaml
from pathlib import Path

from gemini_sre_agent.llm.model_registry import (
    ModelRegistry,
    ModelRegistryConfig,
    ModelInfo,
    ModelCapability
)
from gemini_sre_agent.llm.base import ModelType, ProviderType


class TestModelRegistry:
    """Test the ModelRegistry class."""
    
    def test_model_registry_initialization(self):
        """Test ModelRegistry initialization with default config."""
        registry = ModelRegistry()
        assert registry.config is not None
        assert len(registry._models) == 0
        assert len(registry._semantic_mappings) == 0
    
    def test_model_registry_with_config(self):
        """Test ModelRegistry initialization with custom config."""
        config = ModelRegistryConfig(
            config_file="test.yaml",
            auto_reload=True,
            cache_ttl=600
        )
        registry = ModelRegistry(config)
        assert registry.config.config_file == "test.yaml"
        assert registry.config.auto_reload is True
        assert registry.config.cache_ttl == 600
    
    def test_register_model(self):
        """Test registering a model."""
        registry = ModelRegistry()
        model_info = ModelInfo(
            name="test-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST,
            capabilities={ModelCapability.STREAMING},
            cost_per_1k_tokens=0.001,
            performance_score=0.8,
            reliability_score=0.9
        )
        
        registry.register_model(model_info)
        assert registry.is_model_registered("test-model")
        assert registry.get_model("test-model") == model_info
    
    def test_unregister_model(self):
        """Test unregistering a model."""
        registry = ModelRegistry()
        model_info = ModelInfo(
            name="test-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST
        )
        
        registry.register_model(model_info)
        assert registry.is_model_registered("test-model")
        
        result = registry.unregister_model("test-model")
        assert result is True
        assert not registry.is_model_registered("test-model")
        
        # Test unregistering non-existent model
        result = registry.unregister_model("non-existent")
        assert result is False
    
    def test_get_models_by_semantic_type(self):
        """Test getting models by semantic type."""
        registry = ModelRegistry()
        
        # Register models of different types
        fast_model = ModelInfo(
            name="fast-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST
        )
        smart_model = ModelInfo(
            name="smart-model",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.SMART
        )
        
        registry.register_model(fast_model)
        registry.register_model(smart_model)
        
        fast_models = registry.get_models_by_semantic_type(ModelType.FAST)
        assert len(fast_models) == 1
        assert fast_models[0].name == "fast-model"
        
        smart_models = registry.get_models_by_semantic_type(ModelType.SMART)
        assert len(smart_models) == 1
        assert smart_models[0].name == "smart-model"
    
    def test_get_models_by_provider(self):
        """Test getting models by provider."""
        registry = ModelRegistry()
        
        openai_model = ModelInfo(
            name="openai-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST
        )
        claude_model = ModelInfo(
            name="claude-model",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.SMART
        )
        
        registry.register_model(openai_model)
        registry.register_model(claude_model)
        
        openai_models = registry.get_models_by_provider(ProviderType.OPENAI)
        assert len(openai_models) == 1
        assert openai_models[0].name == "openai-model"
        
        claude_models = registry.get_models_by_provider(ProviderType.CLAUDE)
        assert len(claude_models) == 1
        assert claude_models[0].name == "claude-model"
    
    def test_get_models_by_capability(self):
        """Test getting models by capability."""
        registry = ModelRegistry()
        
        streaming_model = ModelInfo(
            name="streaming-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST,
            capabilities={ModelCapability.STREAMING}
        )
        tools_model = ModelInfo(
            name="tools-model",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.SMART,
            capabilities={ModelCapability.TOOLS}
        )
        both_model = ModelInfo(
            name="both-model",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.SMART,
            capabilities={ModelCapability.STREAMING, ModelCapability.TOOLS}
        )
        
        registry.register_model(streaming_model)
        registry.register_model(tools_model)
        registry.register_model(both_model)
        
        streaming_models = registry.get_models_by_capability(ModelCapability.STREAMING)
        assert len(streaming_models) == 2
        model_names = {m.name for m in streaming_models}
        assert model_names == {"streaming-model", "both-model"}
        
        tools_models = registry.get_models_by_capability(ModelCapability.TOOLS)
        assert len(tools_models) == 2
        model_names = {m.name for m in tools_models}
        assert model_names == {"tools-model", "both-model"}
    
    def test_get_fallback_chain(self):
        """Test getting fallback chain for a model."""
        registry = ModelRegistry()
        
        primary_model = ModelInfo(
            name="primary",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST,
            fallback_models=["fallback1", "fallback2"]
        )
        fallback1_model = ModelInfo(
            name="fallback1",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.FAST
        )
        fallback2_model = ModelInfo(
            name="fallback2",
            provider=ProviderType.GEMINI,
            semantic_type=ModelType.FAST
        )
        
        registry.register_model(primary_model)
        registry.register_model(fallback1_model)
        registry.register_model(fallback2_model)
        
        chain = registry.get_fallback_chain("primary")
        assert len(chain) == 3
        assert chain[0].name == "primary"
        assert chain[1].name == "fallback1"
        assert chain[2].name == "fallback2"
    
    def test_query_models(self):
        """Test querying models with multiple criteria."""
        registry = ModelRegistry()
        
        # Register test models
        models = [
            ModelInfo(
                name="fast-openai",
                provider=ProviderType.OPENAI,
                semantic_type=ModelType.FAST,
                capabilities={ModelCapability.STREAMING},
                cost_per_1k_tokens=0.001,
                performance_score=0.7,
                reliability_score=0.8
            ),
            ModelInfo(
                name="smart-claude",
                provider=ProviderType.CLAUDE,
                semantic_type=ModelType.SMART,
                capabilities={ModelCapability.TOOLS},
                cost_per_1k_tokens=0.003,
                performance_score=0.9,
                reliability_score=0.9
            ),
            ModelInfo(
                name="fast-gemini",
                provider=ProviderType.GEMINI,
                semantic_type=ModelType.FAST,
                capabilities={ModelCapability.STREAMING, ModelCapability.VISION},
                cost_per_1k_tokens=0.0005,
                performance_score=0.8,
                reliability_score=0.8
            )
        ]
        
        for model in models:
            registry.register_model(model)
        
        # Test query by semantic type
        fast_models = registry.query_models(semantic_type=ModelType.FAST)
        assert len(fast_models) == 2
        model_names = {m.name for m in fast_models}
        assert model_names == {"fast-openai", "fast-gemini"}
        
        # Test query by provider
        openai_models = registry.query_models(provider=ProviderType.OPENAI)
        assert len(openai_models) == 1
        assert openai_models[0].name == "fast-openai"
        
        # Test query by capabilities
        streaming_models = registry.query_models(capabilities=[ModelCapability.STREAMING])
        assert len(streaming_models) == 2
        model_names = {m.name for m in streaming_models}
        assert model_names == {"fast-openai", "fast-gemini"}
        
        # Test query by cost
        cheap_models = registry.query_models(max_cost=0.001)
        assert len(cheap_models) == 2
        model_names = {m.name for m in cheap_models}
        assert model_names == {"fast-openai", "fast-gemini"}
        
        # Test query by performance
        high_perf_models = registry.query_models(min_performance=0.8)
        assert len(high_perf_models) == 2
        model_names = {m.name for m in high_perf_models}
        assert model_names == {"smart-claude", "fast-gemini"}
        
        # Test combined query
        combined = registry.query_models(
            semantic_type=ModelType.FAST,
            capabilities=[ModelCapability.STREAMING],
            max_cost=0.001
        )
        assert len(combined) == 2  # Both fast-openai and fast-gemini meet criteria
        model_names = {m.name for m in combined}
        assert model_names == {"fast-openai", "fast-gemini"}
    
    def test_load_from_config_file_not_found(self):
        """Test loading from non-existent config file."""
        registry = ModelRegistry()
        # Should not raise exception, just log warning
        registry.load_from_config("non-existent.yaml")
        assert len(registry._models) == 0
    
    def test_load_from_config_yaml(self):
        """Test loading from YAML config file."""
        config_data = {
            'models': {
                'test-model': {
                    'provider': 'openai',
                    'semantic_type': 'fast',
                    'capabilities': ['streaming'],
                    'cost_per_1k_tokens': 0.001,
                    'performance_score': 0.8,
                    'reliability_score': 0.9
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name
        
        try:
            registry = ModelRegistry()
            registry.load_from_config(config_path)
            
            assert registry.is_model_registered("test-model")
            model = registry.get_model("test-model")
            assert model is not None
            assert model.provider == ProviderType.OPENAI
            assert model.semantic_type == ModelType.FAST
            assert ModelCapability.STREAMING in model.capabilities
            assert model.cost_per_1k_tokens == 0.001
        finally:
            Path(config_path).unlink()
    
    def test_should_reload(self):
        """Test cache reload logic."""
        config = ModelRegistryConfig(auto_reload=True, cache_ttl=1, config_file="test.yaml")
        registry = ModelRegistry(config)
        
        # Should reload if never loaded
        assert registry.should_reload() is True
        
        # Should not reload if auto_reload is False
        config.auto_reload = False
        assert registry.should_reload() is False
        
        # Should not reload if no config file
        config.auto_reload = True
        config.config_file = None
        assert registry.should_reload() is False
    
    def test_get_model_count(self):
        """Test getting model count."""
        registry = ModelRegistry()
        assert registry.get_model_count() == 0
        
        model_info = ModelInfo(
            name="test-model",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST
        )
        registry.register_model(model_info)
        assert registry.get_model_count() == 1
    
    def test_get_all_models(self):
        """Test getting all models."""
        registry = ModelRegistry()
        assert len(registry.get_all_models()) == 0
        
        model1 = ModelInfo(
            name="model1",
            provider=ProviderType.OPENAI,
            semantic_type=ModelType.FAST
        )
        model2 = ModelInfo(
            name="model2",
            provider=ProviderType.CLAUDE,
            semantic_type=ModelType.SMART
        )
        
        registry.register_model(model1)
        registry.register_model(model2)
        
        all_models = registry.get_all_models()
        assert len(all_models) == 2
        model_names = {m.name for m in all_models}
        assert model_names == {"model1", "model2"}
