"""
Comprehensive unit tests for GeminiAPIClient.

Tests cover structured output support, error handling, cost tracking,
rate limiting, and performance monitoring.
"""

import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from gemini_sre_agent.ml.adaptive_rate_limiter import AdaptiveRateLimiter
from gemini_sre_agent.ml.cost_tracker import CostTracker
from gemini_sre_agent.ml.gemini_api_client import (
    GeminiAPIClient,
    GeminiRequest,
    GeminiResponse,
)
from gemini_sre_agent.ml.rate_limiter_config import UrgencyLevel


class TestGeminiRequest:
    """Test GeminiRequest model validation."""

    def test_valid_request(self):
        """Test creating valid request."""
        request = GeminiRequest(
            model="gemini-pro",
            messages=[{"role": "user", "content": "test message"}],
            temperature=0.7,
        )
        assert request.model == "gemini-pro"
        assert request.temperature == 0.7
        assert len(request.messages) == 1

    def test_request_with_schema(self):
        """Test request with response schema."""
        schema = {
            "type": "object",
            "properties": {"confidence": {"type": "number"}},
            "required": ["confidence"],
        }
        request = GeminiRequest(
            model="gemini-pro",
            messages=[{"role": "user", "content": "test"}],
            response_schema=schema,
        )
        assert request.response_schema == schema

    def test_invalid_temperature(self):
        """Test validation of temperature parameter."""
        with pytest.raises(ValueError):
            GeminiRequest(
                model="gemini-pro",
                messages=[{"role": "user", "content": "test"}],
                temperature=3.0,  # Invalid: > 2.0
            )


class TestGeminiResponse:
    """Test GeminiResponse model."""

    def test_successful_response(self):
        """Test successful response creation."""
        response = GeminiResponse(
            success=True,
            content="Test response",
            tokens_used=50,
            latency_ms=150.0,
            model_used="gemini-pro",
        )
        assert response.success is True
        assert response.content == "Test response"
        assert response.tokens_used == 50
        assert response.latency_ms == 150.0

    def test_error_response(self):
        """Test error response creation."""
        response = GeminiResponse(
            success=False, error_message="API error", model_used="gemini-pro"
        )
        assert response.success is False
        assert response.error_message == "API error"
        assert response.tokens_used == 0  # Default


class TestGeminiAPIClientInit:
    """Test GeminiAPIClient initialization."""

    @patch("gemini_sre_agent.ml.gemini_api_client.GENAI_AVAILABLE", True)
    @patch("gemini_sre_agent.ml.gemini_api_client.genai")
    def test_successful_init(self, mock_genai):
        """Test successful client initialization."""
        client = GeminiAPIClient(api_key="test_key")

        assert client._request_count == 0
        assert client._total_tokens == 0
        assert client._total_latency == 0.0
        mock_genai.configure.assert_called_once_with(api_key="test_key")

    @patch("gemini_sre_agent.ml.gemini_api_client.GENAI_AVAILABLE", False)
    def test_init_without_genai(self):
        """Test initialization when google-generativeai not available."""
        with pytest.raises(
            ImportError, match="google-generativeai package is required"
        ):
            GeminiAPIClient(api_key="test_key")

    @patch("gemini_sre_agent.ml.gemini_api_client.GENAI_AVAILABLE", True)
    @patch("gemini_sre_agent.ml.gemini_api_client.genai")
    def test_init_with_monitoring_components(self, mock_genai):
        """Test initialization with cost tracker and rate limiter."""
        cost_tracker = Mock(spec=CostTracker)
        rate_limiter = Mock(spec=AdaptiveRateLimiter)

        client = GeminiAPIClient(
            api_key="test_key", cost_tracker=cost_tracker, rate_limiter=rate_limiter
        )

        assert client.cost_tracker is cost_tracker
        assert client.rate_limiter is rate_limiter


class TestGeminiAPIClientGeneration:
    """Test response generation functionality."""

    @pytest.fixture
    def mock_client_setup(self):
        """Setup mock client with dependencies."""
        # Create comprehensive mock for genai module
        mock_genai = Mock()
        mock_genai.configure = Mock()
        mock_model = Mock()
        mock_genai.GenerativeModel = Mock(return_value=mock_model)
        mock_genai.types = Mock()
        mock_genai.types.GenerationConfig = Mock()

        # Patch both GENAI_AVAILABLE and the genai module at import time
        patches = [
            patch("gemini_sre_agent.ml.gemini_api_client.GENAI_AVAILABLE", True),
            patch("gemini_sre_agent.ml.gemini_api_client.genai", mock_genai),
        ]

        for p in patches:
            p.start()

        try:
            cost_tracker = AsyncMock(spec=CostTracker)
            rate_limiter = AsyncMock(spec=AdaptiveRateLimiter)

            client = GeminiAPIClient(
                api_key="test_key", cost_tracker=cost_tracker, rate_limiter=rate_limiter
            )

            yield client, mock_genai, cost_tracker, rate_limiter
        finally:
            for p in patches:
                p.stop()

    @pytest.mark.asyncio
    async def test_successful_generation(self, mock_client_setup):
        """Test successful response generation."""
        client, mock_genai, cost_tracker, rate_limiter = mock_client_setup

        # Setup mocks
        rate_limiter.should_allow_request.return_value = True

        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = "Generated response"

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types.GenerationConfig.return_value = Mock()

        request = GeminiRequest(
            model="gemini-pro", messages=[{"role": "user", "content": "test message"}]
        )

        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = mock_response
            response = await client.generate_response(request)

        assert response.success is True
        assert response.content == "Generated response"
        assert response.tokens_used > 0
        assert response.latency_ms > 0

        # Verify rate limiting was checked
        rate_limiter.should_allow_request.assert_called_once_with(
            UrgencyLevel.MEDIUM, cost_tracker
        )

        # Verify cost tracking
        cost_tracker.record_actual_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limited_request(self, mock_client_setup):
        """Test request blocked by rate limiter."""
        client, mock_genai, cost_tracker, rate_limiter = mock_client_setup

        # Setup rate limiter to block request
        rate_limiter.should_allow_request.return_value = False

        request = GeminiRequest(
            model="gemini-pro", messages=[{"role": "user", "content": "test message"}]
        )

        response = await client.generate_response(request)

        assert response.success is False
        assert response.error_message == "Request blocked by rate limiter"
        assert response.tokens_used == 0

    @pytest.mark.asyncio
    async def test_structured_output_parsing(self, mock_client_setup):
        """Test structured JSON output parsing."""
        client, mock_genai, cost_tracker, rate_limiter = mock_client_setup

        # Setup mocks for structured output
        rate_limiter.should_allow_request.return_value = True

        json_response = {"confidence": 0.85, "pattern_type": "memory_leak"}

        mock_response = Mock()
        mock_response.candidates = [Mock()]
        mock_response.candidates[0].content.parts = [Mock()]
        mock_response.candidates[0].content.parts[0].text = json.dumps(json_response)

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types.GenerationConfig.return_value = Mock()

        schema = {
            "type": "object",
            "properties": {"confidence": {"type": "number"}},
            "required": ["confidence"],
        }

        request = GeminiRequest(
            model="gemini-pro",
            messages=[{"role": "user", "content": "analyze pattern"}],
            response_schema=schema,
        )

        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = mock_response
            response = await client.generate_response(request)

        assert response.success is True
        assert response.parsed_json == json_response
        assert response.parsed_json["confidence"] == 0.85

    @pytest.mark.asyncio
    async def test_api_error_handling(self, mock_client_setup):
        """Test API error handling."""
        client, mock_genai, cost_tracker, rate_limiter = mock_client_setup

        rate_limiter.should_allow_request.return_value = True

        mock_model = Mock()
        mock_model.generate_content.side_effect = Exception("API connection failed")
        mock_genai.GenerativeModel.return_value = mock_model

        request = GeminiRequest(
            model="gemini-pro", messages=[{"role": "user", "content": "test message"}]
        )

        with patch("asyncio.to_thread", side_effect=Exception("API connection failed")):
            response = await client.generate_response(request)

        assert response.success is False
        assert "Gemini API error: API connection failed" in response.error_message
        assert response.latency_ms > 0

        # Verify error tracking
        cost_tracker.record_actual_cost.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_candidates_response(self, mock_client_setup):
        """Test handling when API returns no candidates."""
        client, mock_genai, cost_tracker, rate_limiter = mock_client_setup

        rate_limiter.should_allow_request.return_value = True

        mock_response = Mock()
        mock_response.candidates = []  # No candidates

        mock_model = Mock()
        mock_model.generate_content.return_value = mock_response
        mock_genai.GenerativeModel.return_value = mock_model
        mock_genai.types.GenerationConfig.return_value = Mock()

        request = GeminiRequest(
            model="gemini-pro", messages=[{"role": "user", "content": "test message"}]
        )

        with patch("asyncio.to_thread") as mock_to_thread:
            mock_to_thread.return_value = mock_response
            response = await client.generate_response(request)

        assert response.success is False
        assert response.error_message == "No candidates in API response"


class TestGeminiAPIClientHelpers:
    """Test helper methods."""

    @patch("gemini_sre_agent.ml.gemini_api_client.GENAI_AVAILABLE", True)
    @patch("gemini_sre_agent.ml.gemini_api_client.genai")
    def setUp(self, mock_genai):
        """Setup client for helper tests."""
        self.client = GeminiAPIClient(api_key="test_key")
        return mock_genai

    def test_build_generation_config(self):
        """Test generation config building."""
        self.setUp()

        request = GeminiRequest(
            model="gemini-pro",
            messages=[{"role": "user", "content": "test"}],
            temperature=0.8,
            max_tokens=1000,
        )

        config = self.client._build_generation_config(request)

        assert config["temperature"] == 0.8
        assert config["max_output_tokens"] == 1000
        assert config["candidate_count"] == 1

    def test_build_generation_config_with_schema(self):
        """Test config building with response schema."""
        self.setUp()

        schema = {"type": "object", "properties": {"result": {"type": "string"}}}
        request = GeminiRequest(
            model="gemini-pro",
            messages=[{"role": "user", "content": "test"}],
            response_schema=schema,
        )

        config = self.client._build_generation_config(request)

        assert config["response_mime_type"] == "application/json"
        assert config["response_schema"] == schema

    def test_format_messages(self):
        """Test message formatting."""
        self.setUp()

        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]

        formatted = self.client._format_messages(messages)

        expected = (
            "SYSTEM: You are a helpful assistant\n\n"
            "USER: Hello\n\n"
            "ASSISTANT: Hi there!"
        )
        assert formatted == expected

    def test_parse_structured_output_json(self):
        """Test JSON parsing from structured output."""
        self.setUp()

        json_content = '{"confidence": 0.95, "pattern": "cpu_spike"}'
        schema = {"type": "object", "required": ["confidence"]}

        result = self.client._parse_structured_output(json_content, schema)

        assert result["confidence"] == 0.95
        assert result["pattern"] == "cpu_spike"

    def test_parse_structured_output_markdown(self):
        """Test parsing JSON wrapped in markdown."""
        self.setUp()

        markdown_content = '```json\n{"confidence": 0.75}\n```'
        schema = {"type": "object", "required": ["confidence"]}

        result = self.client._parse_structured_output(markdown_content, schema)

        assert result["confidence"] == 0.75

    def test_parse_structured_output_invalid_json(self):
        """Test handling invalid JSON."""
        self.setUp()

        invalid_content = "Not valid JSON content"
        schema = {"type": "object", "required": ["confidence"]}

        result = self.client._parse_structured_output(invalid_content, schema)

        assert result == {}

    def test_estimate_tokens(self):
        """Test token estimation."""
        self.setUp()

        text = "This is a test message for token estimation"
        tokens = self.client._estimate_tokens(text)

        # Rough estimation: ~4 characters per token
        expected_tokens = len(text) // 4
        assert tokens == expected_tokens
        assert tokens > 0

    def test_performance_stats(self):
        """Test performance statistics."""
        self.setUp()

        # Simulate some requests
        self.client._request_count = 5
        self.client._total_tokens = 250
        self.client._total_latency = 750.0

        stats = self.client.get_performance_stats()

        assert stats["total_requests"] == 5
        assert stats["total_tokens"] == 250
        assert stats["total_latency_ms"] == 750.0
        assert stats["average_latency_ms"] == 150.0
        assert stats["average_tokens_per_request"] == 50.0
