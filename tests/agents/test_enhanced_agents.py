"""Tests for Enhanced Agent Classes with Multi-Provider Support."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from gemini_sre_agent.agents.enhanced_adapter import (
    AgentMigrationHelper,
    BackwardCompatibilityWrapper,
    EnhancedAgentAdapter,
)
from gemini_sre_agent.agents.enhanced_base import EnhancedBaseAgent
from gemini_sre_agent.agents.enhanced_specialized import (
    EnhancedAnalysisAgent,
    EnhancedCodeAgent,
    EnhancedRemediationAgent,
    EnhancedTextAgent,
    EnhancedTriageAgent,
)
from gemini_sre_agent.agents.response_models import AnalysisResponse, CodeResponse, TextResponse
from gemini_sre_agent.llm.base import ModelType, ProviderType
from gemini_sre_agent.llm.config import LLMConfig, LLMProviderConfig
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal


@pytest.fixture
def mock_llm_config():
    """Create mock LLM configuration."""
    from pydantic import HttpUrl
    
    provider_config = LLMProviderConfig(
        provider="gemini",
        api_key="test-key",
        region="us-central1",
        base_url=HttpUrl("https://generativelanguage.googleapis.com/v1beta"),
        timeout=30,
        max_retries=3,
        rate_limit=100,
    )
    
    return LLMConfig(
        providers={"gemini": provider_config},
        default_provider=ProviderType.GEMINI,
        default_model_type=ModelType.SMART,
        enable_fallback=True,
        enable_monitoring=True,
    )


@pytest.fixture
def mock_enhanced_llm_service():
    """Create mock enhanced LLM service."""
    service = MagicMock()
    service.model_registry = MagicMock()
    service.model_registry.get_all_models.return_value = [
        MagicMock(name="gemini-1.5-pro", provider=ProviderType.GEMINI),
        MagicMock(name="gpt-4o", provider=ProviderType.OPENAI),
    ]
    service.providers = {ProviderType.GEMINI: MagicMock(), ProviderType.OPENAI: MagicMock()}
    service.model_scorer = MagicMock()
    return service


@pytest.fixture
def mock_strategy_manager():
    """Create mock strategy manager."""
    manager = MagicMock()
    manager.select_model.return_value = MagicMock(
        selected_model=MagicMock(name="gemini-1.5-pro"),
        strategy_used="quality_optimized",
        reasoning="Selected for quality",
    )
    manager.get_all_performance_metrics.return_value = {
        "cost": {"total_selections": 10, "success_rate": 0.9},
        "quality": {"total_selections": 15, "success_rate": 0.95},
    }
    return manager


class TestEnhancedBaseAgent:
    """Test EnhancedBaseAgent functionality."""

    @patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService')
    @patch('gemini_sre_agent.agents.enhanced_base.StrategyManager')
    def test_initialization(self, mock_strategy_manager_class, mock_llm_service_class, mock_llm_config):
        """Test EnhancedBaseAgent initialization."""
        mock_llm_service_class.return_value = MagicMock()
        mock_strategy_manager_class.return_value = MagicMock()
        
        agent = EnhancedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TextResponse,
            primary_model="gemini-1.5-pro",
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        assert agent.response_model == TextResponse
        assert agent.primary_model == "gemini-1.5-pro"
        assert agent.optimization_goal == OptimizationGoal.QUALITY
        assert agent.max_retries == 2
        assert agent.collect_stats is True

    @patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService')
    @patch('gemini_sre_agent.agents.enhanced_base.StrategyManager')
    async def test_execute_success(self, mock_strategy_manager_class, mock_llm_service_class, mock_llm_config):
        """Test successful execution with enhanced agent."""
        # Setup mocks
        mock_llm_service = MagicMock()
        mock_llm_service.generate_structured = AsyncMock(return_value=TextResponse(
            text="Generated text",
            confidence=0.9
        ))
        mock_llm_service_class.return_value = mock_llm_service
        
        mock_strategy_manager = MagicMock()
        mock_strategy_manager.select_model.return_value = MagicMock(
            selected_model=MagicMock(name="gemini-1.5-pro")
        )
        mock_strategy_manager_class.return_value = mock_strategy_manager
        
        agent = EnhancedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TextResponse,
        )
        
        # Mock the _select_model method
        agent._select_model = AsyncMock(return_value="gemini-1.5-pro")
        
        result = await agent.execute(
            prompt_name="test_prompt",
            prompt_args={"input": "test input"},
        )
        
        assert isinstance(result, TextResponse)
        assert result.text == "Generated text"
        assert result.confidence == 0.9

    @patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService')
    @patch('gemini_sre_agent.agents.enhanced_base.StrategyManager')
    async def test_execute_with_fallback(self, mock_strategy_manager_class, mock_llm_service_class, mock_llm_config):
        """Test execution with fallback model."""
        # Setup mocks
        mock_llm_service = MagicMock()
        mock_llm_service.generate_structured = AsyncMock(
            side_effect=[Exception("Primary failed"), TextResponse(text="Fallback text", confidence=0.8)]
        )
        mock_llm_service_class.return_value = mock_llm_service
        
        mock_strategy_manager = MagicMock()
        mock_strategy_manager_class.return_value = mock_strategy_manager
        
        agent = EnhancedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TextResponse,
            fallback_model="gemini-1.5-flash",
        )
        
        # Mock the _select_model method
        agent._select_model = AsyncMock(return_value="gemini-1.5-pro")
        
        result = await agent.execute(
            prompt_name="test_prompt",
            prompt_args={"input": "test input"},
        )
        
        assert isinstance(result, TextResponse)
        assert result.text == "Fallback text"

    @patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService')
    @patch('gemini_sre_agent.agents.enhanced_base.StrategyManager')
    async def test_model_selection(self, mock_strategy_manager_class, mock_llm_service_class, mock_llm_config):
        """Test intelligent model selection."""
        # Setup mocks
        mock_llm_service = MagicMock()
        mock_llm_service.model_registry = MagicMock()
        mock_llm_service.model_registry.get_all_models.return_value = [
            MagicMock(name="gemini-1.5-pro"),
            MagicMock(name="gpt-4o"),
        ]
        mock_llm_service_class.return_value = mock_llm_service
        
        mock_strategy_manager = MagicMock()
        mock_strategy_manager.select_model.return_value = MagicMock(
            selected_model=MagicMock(name="gpt-4o"),
            strategy_used="cost_optimized",
            reasoning="Selected for cost efficiency",
        )
        mock_strategy_manager_class.return_value = mock_strategy_manager
        
        agent = EnhancedBaseAgent(
            llm_config=mock_llm_config,
            response_model=TextResponse,
            optimization_goal=OptimizationGoal.COST,
        )
        
        selected_model = await agent._select_model()
        
        assert selected_model == "gpt-4o"
        mock_strategy_manager.select_model.assert_called_once()

    def test_conversation_context_management(self, mock_llm_config):
        """Test conversation context management."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService'), \
             patch('gemini_sre_agent.agents.enhanced_base.StrategyManager'):
            
            agent = EnhancedBaseAgent(
                llm_config=mock_llm_config,
                response_model=TextResponse,
            )
            
            # Test initial state
            assert len(agent.get_conversation_context()) == 0
            
            # Test context update
            agent._update_conversation_context(
                "test_prompt",
                {"input": "test"},
                "gemini-1.5-pro",
                TextResponse(text="response", confidence=0.9)
            )
            
            context = agent.get_conversation_context()
            assert len(context) == 1
            assert context[0]["prompt_name"] == "test_prompt"
            assert context[0]["model"] == "gemini-1.5-pro"
            
            # Test context clearing
            agent.clear_conversation_context()
            assert len(agent.get_conversation_context()) == 0

    def test_configuration_updates(self, mock_llm_config):
        """Test configuration update methods."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService'), \
             patch('gemini_sre_agent.agents.enhanced_base.StrategyManager'):
            
            agent = EnhancedBaseAgent(
                llm_config=mock_llm_config,
                response_model=TextResponse,
            )
            
            # Test optimization goal update
            agent.update_optimization_goal(OptimizationGoal.PERFORMANCE)
            assert agent.optimization_goal == OptimizationGoal.PERFORMANCE
            
            # Test provider preference update
            agent.update_provider_preference([ProviderType.OPENAI, ProviderType.GEMINI])
            assert agent.provider_preference == [ProviderType.OPENAI, ProviderType.GEMINI]
            
            # Test cost constraints update
            agent.update_cost_constraints(max_cost=0.01, min_performance=0.8)
            assert agent.max_cost == 0.01
            assert agent.min_performance == 0.8

    def test_stats_summary(self, mock_llm_config):
        """Test comprehensive stats summary."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedLLMService'), \
             patch('gemini_sre_agent.agents.enhanced_base.StrategyManager') as mock_strategy_manager_class:
            
            mock_strategy_manager = MagicMock()
            mock_strategy_manager.get_all_performance_metrics.return_value = {
                "cost": {"total_selections": 10},
                "quality": {"total_selections": 15},
            }
            mock_strategy_manager_class.return_value = mock_strategy_manager
            
            agent = EnhancedBaseAgent(
                llm_config=mock_llm_config,
                response_model=TextResponse,
            )
            
            stats = agent.get_stats_summary()
            
            assert "agent_stats" in stats
            assert "model_selection_stats" in stats
            assert "conversation_length" in stats
            assert "optimization_goal" in stats
            assert "provider_preference" in stats
            assert "constraints" in stats


class TestEnhancedSpecializedAgents:
    """Test enhanced specialized agent classes."""

    @patch('gemini_sre_agent.agents.enhanced_specialized.EnhancedBaseAgent.__init__')
    def test_enhanced_text_agent(self, mock_init, mock_llm_config):
        """Test EnhancedTextAgent initialization."""
        mock_init.return_value = None
        
        EnhancedTextAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[1]["response_model"] == TextResponse
        assert call_args[1]["optimization_goal"] == OptimizationGoal.QUALITY

    @patch('gemini_sre_agent.agents.enhanced_specialized.EnhancedBaseAgent.__init__')
    def test_enhanced_analysis_agent(self, mock_init, mock_llm_config):
        """Test EnhancedAnalysisAgent initialization."""
        mock_init.return_value = None
        
        EnhancedAnalysisAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[1]["response_model"] == AnalysisResponse
        assert call_args[1]["optimization_goal"] == OptimizationGoal.QUALITY

    @patch('gemini_sre_agent.agents.enhanced_specialized.EnhancedBaseAgent.__init__')
    def test_enhanced_code_agent(self, mock_init, mock_llm_config):
        """Test EnhancedCodeAgent initialization."""
        mock_init.return_value = None
        
        EnhancedCodeAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[1]["response_model"] == CodeResponse
        assert call_args[1]["optimization_goal"] == OptimizationGoal.QUALITY

    @patch('gemini_sre_agent.agents.enhanced_specialized.EnhancedBaseAgent.__init__')
    def test_enhanced_triage_agent(self, mock_init, mock_llm_config):
        """Test EnhancedTriageAgent initialization."""
        mock_init.return_value = None
        
        EnhancedTriageAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.PERFORMANCE,
        )
        
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[1]["response_model"] == AnalysisResponse
        assert call_args[1]["optimization_goal"] == OptimizationGoal.PERFORMANCE

    @patch('gemini_sre_agent.agents.enhanced_specialized.EnhancedBaseAgent.__init__')
    def test_enhanced_remediation_agent(self, mock_init, mock_llm_config):
        """Test EnhancedRemediationAgent initialization."""
        mock_init.return_value = None
        
        EnhancedRemediationAgent(
            llm_config=mock_llm_config,
            optimization_goal=OptimizationGoal.QUALITY,
        )
        
        mock_init.assert_called_once()
        call_args = mock_init.call_args
        assert call_args[1]["response_model"] == AnalysisResponse
        assert call_args[1]["optimization_goal"] == OptimizationGoal.QUALITY


class TestEnhancedAgentAdapter:
    """Test EnhancedAgentAdapter functionality."""

    def test_adapter_initialization(self, mock_llm_config):
        """Test adapter initialization."""
        # Create a mock legacy agent
        legacy_agent = MagicMock()
        legacy_agent.response_model = TextResponse
        legacy_agent.primary_model = "gemini-1.5-pro"
        legacy_agent.fallback_model = "gemini-1.5-flash"
        legacy_agent.__class__.__name__ = "TextAgent"
        
        with patch('gemini_sre_agent.agents.enhanced_adapter.EnhancedTextAgent'):
            adapter = EnhancedAgentAdapter(
                legacy_agent=legacy_agent,
                llm_config=mock_llm_config,
            )
            
            assert adapter.legacy_agent == legacy_agent
            assert adapter.llm_config == mock_llm_config
            assert adapter.enable_enhancements is True

    @patch('gemini_sre_agent.agents.enhanced_adapter.EnhancedTextAgent')
    async def test_adapter_execute_enhanced(self, mock_enhanced_agent_class, mock_llm_config):
        """Test adapter execution with enhanced features enabled."""
        # Create a mock legacy agent
        legacy_agent = MagicMock()
        legacy_agent.response_model = TextResponse
        legacy_agent.primary_model = "gemini-1.5-pro"
        legacy_agent.fallback_model = "gemini-1.5-flash"
        legacy_agent.__class__.__name__ = "TextAgent"
        
        # Create mock enhanced agent
        mock_enhanced_agent = MagicMock()
        mock_enhanced_agent.execute = AsyncMock(return_value=TextResponse(text="Enhanced response", confidence=0.9))
        mock_enhanced_agent_class.return_value = mock_enhanced_agent
        
        adapter = EnhancedAgentAdapter(
            legacy_agent=legacy_agent,
            llm_config=mock_llm_config,
            enable_enhancements=True,
        )
        
        result = await adapter.execute(
            prompt_name="test_prompt",
            prompt_args={"input": "test"},
        )
        
        assert isinstance(result, TextResponse)
        assert result.text == "Enhanced response"
        mock_enhanced_agent.execute.assert_called_once()

    @patch('gemini_sre_agent.agents.enhanced_adapter.EnhancedTextAgent')
    async def test_adapter_execute_legacy(self, mock_enhanced_agent_class, mock_llm_config):
        """Test adapter execution with enhanced features disabled."""
        # Create a mock legacy agent
        legacy_agent = MagicMock()
        legacy_agent.response_model = TextResponse
        legacy_agent.primary_model = "gemini-1.5-pro"
        legacy_agent.fallback_model = "gemini-1.5-flash"
        legacy_agent.__class__.__name__ = "TextAgent"
        legacy_agent.execute = AsyncMock(return_value=TextResponse(text="Legacy response", confidence=0.8))
        
        # Create mock enhanced agent
        mock_enhanced_agent = MagicMock()
        mock_enhanced_agent_class.return_value = mock_enhanced_agent
        
        adapter = EnhancedAgentAdapter(
            legacy_agent=legacy_agent,
            llm_config=mock_llm_config,
            enable_enhancements=False,
        )
        
        result = await adapter.execute(
            prompt_name="test_prompt",
            prompt_args={"input": "test"},
        )
        
        assert isinstance(result, TextResponse)
        assert result.text == "Legacy response"
        legacy_agent.execute.assert_called_once()

    def test_adapter_feature_toggle(self, mock_llm_config):
        """Test enabling/disabling enhanced features."""
        # Create a mock legacy agent
        legacy_agent = MagicMock()
        legacy_agent.response_model = TextResponse
        legacy_agent.primary_model = "gemini-1.5-pro"
        legacy_agent.fallback_model = "gemini-1.5-flash"
        legacy_agent.__class__.__name__ = "TextAgent"
        
        with patch('gemini_sre_agent.agents.enhanced_adapter.EnhancedTextAgent'):
            adapter = EnhancedAgentAdapter(
                legacy_agent=legacy_agent,
                llm_config=mock_llm_config,
            )
            
            # Test enabling features
            adapter.enable_enhanced_features()
            assert adapter.enable_enhancements is True
            
            # Test disabling features
            adapter.disable_enhanced_features()
            assert adapter.enable_enhancements is False


class TestAgentMigrationHelper:
    """Test AgentMigrationHelper functionality."""

    def test_create_enhanced_agent_from_legacy(self, mock_llm_config):
        """Test creating enhanced agent from legacy agent."""
        # Create a mock legacy agent
        legacy_agent = MagicMock()
        legacy_agent.response_model = TextResponse
        legacy_agent.primary_model = "gemini-1.5-pro"
        legacy_agent.fallback_model = "gemini-1.5-flash"
        legacy_agent.max_retries = 3
        legacy_agent.collect_stats = True
        legacy_agent.__class__.__name__ = "TextAgent"
        
        with patch('gemini_sre_agent.agents.enhanced_adapter.EnhancedTextAgent') as mock_enhanced_class:
            AgentMigrationHelper.create_enhanced_agent_from_legacy(
                legacy_agent=legacy_agent,
                llm_config=mock_llm_config,
            )
            
            mock_enhanced_class.assert_called_once()
            call_args = mock_enhanced_class.call_args
            assert call_args[1]["llm_config"] == mock_llm_config
            assert call_args[1]["primary_model"] == "gemini-1.5-pro"
            assert call_args[1]["fallback_model"] == "gemini-1.5-flash"
            assert call_args[1]["max_retries"] == 3
            assert call_args[1]["collect_stats"] is True

    def test_validate_migration_compatibility(self, mock_llm_config):
        """Test migration compatibility validation."""
        # Create a compatible legacy agent
        compatible_agent = MagicMock()
        compatible_agent.response_model = TextResponse
        compatible_agent.llm_service = MagicMock()
        compatible_agent._prompts = {}
        
        # Create an incompatible legacy agent
        incompatible_agent = MagicMock()
        # Missing required attributes
        
        # Test compatible agent
        result = AgentMigrationHelper.validate_migration_compatibility(
            compatible_agent, mock_llm_config
        )
        assert result["compatible"] is True
        
        # Test incompatible agent
        result = AgentMigrationHelper.validate_migration_compatibility(
            incompatible_agent, mock_llm_config
        )
        assert result["compatible"] is False
        assert len(result["required_changes"]) > 0

    def test_generate_migration_report(self, mock_llm_config):
        """Test migration report generation."""
        # Create mock agents
        compatible_agent = MagicMock()
        compatible_agent.response_model = TextResponse
        compatible_agent.llm_service = MagicMock()
        compatible_agent._prompts = {}
        compatible_agent.__class__.__name__ = "TextAgent"
        
        incompatible_agent = MagicMock()
        incompatible_agent.__class__.__name__ = "AnalysisAgent"
        # Missing required attributes
        
        # Cast to proper type for testing
        from typing import List, cast
        from gemini_sre_agent.agents.base import BaseAgent
        agents = cast(List[BaseAgent], [compatible_agent, incompatible_agent])
        
        report = AgentMigrationHelper.generate_migration_report(agents, mock_llm_config)
        
        assert report["total_agents"] == 2
        assert report["compatible_agents"] == 1
        assert report["incompatible_agents"] == 1
        assert len(report["agent_details"]) == 2
        assert len(report["overall_recommendations"]) > 0


class TestBackwardCompatibilityWrapper:
    """Test BackwardCompatibilityWrapper functionality."""

    def test_wrapper_initialization(self, mock_llm_config):
        """Test wrapper initialization."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedBaseAgent') as mock_enhanced_class:
            mock_enhanced_agent = MagicMock()
            mock_enhanced_agent.llm_service = MagicMock()
            mock_enhanced_agent.response_model = TextResponse
            mock_enhanced_agent.primary_model = "gemini-1.5-pro"
            mock_enhanced_agent.fallback_model = "gemini-1.5-flash"
            mock_enhanced_agent.max_retries = 2
            mock_enhanced_agent.collect_stats = True
            mock_enhanced_agent.stats = MagicMock()
            mock_enhanced_agent._prompts = {}
            mock_enhanced_class.return_value = mock_enhanced_agent
            
            wrapper = BackwardCompatibilityWrapper(mock_enhanced_agent)
            
            # Test that legacy attributes are exposed
            assert wrapper.llm_service == mock_enhanced_agent.llm_service
            assert wrapper.response_model == TextResponse
            assert wrapper.primary_model == "gemini-1.5-pro"
            assert wrapper.fallback_model == "gemini-1.5-flash"
            assert wrapper.max_retries == 2
            assert wrapper.collect_stats is True
            assert wrapper.stats == mock_enhanced_agent.stats
            assert wrapper._prompts == {}

    async def test_wrapper_execute(self, mock_llm_config):
        """Test wrapper execute method."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedBaseAgent') as mock_enhanced_class:
            mock_enhanced_agent = MagicMock()
            mock_enhanced_agent.execute = AsyncMock(return_value=TextResponse(text="Wrapped response", confidence=0.9))
            mock_enhanced_agent.llm_service = MagicMock()
            mock_enhanced_agent.response_model = TextResponse
            mock_enhanced_agent.primary_model = "gemini-1.5-pro"
            mock_enhanced_agent.fallback_model = "gemini-1.5-flash"
            mock_enhanced_agent.max_retries = 2
            mock_enhanced_agent.collect_stats = True
            mock_enhanced_agent.stats = MagicMock()
            mock_enhanced_agent._prompts = {}
            mock_enhanced_class.return_value = mock_enhanced_agent
            
            wrapper = BackwardCompatibilityWrapper(mock_enhanced_agent)
            
            result = await wrapper.execute(
                prompt_name="test_prompt",
                prompt_args={"input": "test"},
            )
            
            assert isinstance(result, TextResponse)
            assert result.text == "Wrapped response"
            mock_enhanced_agent.execute.assert_called_once()

    def test_wrapper_stats_summary(self, mock_llm_config):
        """Test wrapper stats summary method."""
        with patch('gemini_sre_agent.agents.enhanced_base.EnhancedBaseAgent') as mock_enhanced_class:
            mock_enhanced_agent = MagicMock()
            mock_enhanced_agent.get_stats_summary.return_value = {"enhanced": "stats"}
            mock_enhanced_agent.llm_service = MagicMock()
            mock_enhanced_agent.response_model = TextResponse
            mock_enhanced_agent.primary_model = "gemini-1.5-pro"
            mock_enhanced_agent.fallback_model = "gemini-1.5-flash"
            mock_enhanced_agent.max_retries = 2
            mock_enhanced_agent.collect_stats = True
            mock_enhanced_agent.stats = MagicMock()
            mock_enhanced_agent._prompts = {}
            mock_enhanced_class.return_value = mock_enhanced_agent
            
            wrapper = BackwardCompatibilityWrapper(mock_enhanced_agent)
            
            stats = wrapper.get_stats_summary()
            
            assert stats == {"enhanced": "stats"}
            mock_enhanced_agent.get_stats_summary.assert_called_once()
