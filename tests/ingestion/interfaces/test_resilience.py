# tests/ingestion/interfaces/test_resilience.py

"""
Tests for the resilience system using circuitbreaker and tenacity.
"""

import pytest
import asyncio
from unittest.mock import Mock
from gemini_sre_agent.ingestion.interfaces.resilience import (
    HyxResilientClient,
    create_resilience_config,
    ResilienceConfig,
)


class TestResilienceConfig:
    """Test the ResilienceConfig dataclass."""
    
    def test_resilience_config_creation(self):
        """Test creating a ResilienceConfig instance."""
        config = ResilienceConfig(
            retry={"max_attempts": 3, "initial_delay": 1},
            circuit_breaker={"failure_threshold": 5, "recovery_timeout": 60.0},
            timeout=30,
            bulkhead={"limit": 10, "queue": 5},
            rate_limit={"requests_per_second": 100, "burst_limit": 200}
        )
        
        assert config.retry["max_attempts"] == 3
        assert config.circuit_breaker["failure_threshold"] == 5
        assert config.timeout == 30
        assert config.bulkhead["limit"] == 10
        assert config.rate_limit["requests_per_second"] == 100


class TestHyxResilientClient:
    """Test the HyxResilientClient integration."""
    
    def test_client_creation(self):
        """Test creating a HyxResilientClient instance."""
        config = ResilienceConfig(
            retry={"max_attempts": 3, "initial_delay": 1},
            circuit_breaker={"failure_threshold": 5, "recovery_timeout": 60.0},
            timeout=30,
            bulkhead={"limit": 10, "queue": 5},
            rate_limit={"requests_per_second": 100, "burst_limit": 200}
        )
        
        client = HyxResilientClient(config)
        assert client.config == config
        assert hasattr(client, '_stats')
    
    @pytest.mark.asyncio
    async def test_execute_with_resilience(self):
        """Test executing an operation with all resilience patterns."""
        config = ResilienceConfig(
            retry={"max_attempts": 2, "initial_delay": 0.1},
            circuit_breaker={"failure_threshold": 3, "recovery_timeout": 1.0},
            timeout=1,
            bulkhead={"limit": 5, "queue": 2},
            rate_limit={"requests_per_second": 100, "burst_limit": 200}
        )
        
        client = HyxResilientClient(config)
        
        async def test_operation():
            return "success"
        
        result = await client.execute(test_operation)
        assert result == "success"
        
        # Check that stats were updated
        assert client._stats["total_operations"] == 1
        assert client._stats["successful_operations"] == 1
    
    @pytest.mark.asyncio
    async def test_execute_with_failure(self):
        """Test executing an operation that fails."""
        config = ResilienceConfig(
            retry={"max_attempts": 2, "initial_delay": 0.1},
            circuit_breaker={"failure_threshold": 3, "recovery_timeout": 1.0},
            timeout=1,
            bulkhead={"limit": 5, "queue": 2},
            rate_limit={"requests_per_second": 100, "burst_limit": 200}
        )
        
        client = HyxResilientClient(config)
        
        async def failing_operation():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError, match="Test error"):
            await client.execute(failing_operation)
        
        # Check that stats were updated
        assert client._stats["total_operations"] == 1
        assert client._stats["failed_operations"] == 1


class TestCreateResilienceConfig:
    """Test the create_resilience_config utility function."""
    
    def test_create_default_config(self):
        """Test creating a default resilience config."""
        config = create_resilience_config()
        
        assert isinstance(config, ResilienceConfig)
        assert "max_attempts" in config.retry
        assert "failure_threshold" in config.circuit_breaker
        assert config.timeout > 0
        assert "limit" in config.bulkhead
        assert "requests_per_second" in config.rate_limit
    
    def test_create_production_config(self):
        """Test creating a production resilience config."""
        config = create_resilience_config("production")
        
        assert config.retry["max_attempts"] == 3
        assert config.circuit_breaker["failure_threshold"] == 3
        assert config.timeout == 30
        assert config.bulkhead["limit"] == 10
        assert config.rate_limit["requests_per_second"] == 8
    
    def test_create_staging_config(self):
        """Test creating a staging resilience config."""
        config = create_resilience_config("staging")
        
        assert config.retry["max_attempts"] == 3
        assert config.circuit_breaker["failure_threshold"] == 4
        assert config.timeout == 25
        assert config.bulkhead["limit"] == 8
        assert config.rate_limit["requests_per_second"] == 10


if __name__ == "__main__":
    pytest.main([__file__])
