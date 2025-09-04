# Provider Addition Framework

The Provider Addition Framework is a comprehensive system designed to make adding new LLM providers to the Gemini SRE Agent as simple as possible. The framework provides templates, auto-registration, validation, and plugin capabilities to minimize the code required for new provider implementations.

## Overview

The framework consists of several key components:

- **Templates**: Pre-built base classes for common provider patterns
- **Auto-Registry**: Automatic discovery and registration of providers
- **Validation**: Tools to verify provider implementations
- **Plugin Architecture**: Support for external provider modules
- **Capability Discovery**: System for discovering and cataloging provider capabilities

## Quick Start

### Creating a Simple Provider

The easiest way to add a new provider is to use one of the pre-built templates:

```python
from gemini_sre_agent.llm.provider_framework.templates import HTTPAPITemplate
from gemini_sre_agent.llm.base import ModelType
from gemini_sre_agent.llm.config import LLMProviderConfig, ProviderType

class MyProvider(HTTPAPITemplate):
    def _get_model_mapping(self):
        return {
            ModelType.FAST: "my-fast-model",
            ModelType.SMART: "my-smart-model"
        }

    def _get_api_endpoint(self):
        return "/v1/chat/completions"

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}

# Usage
config = LLMProviderConfig(
    provider=ProviderType.CUSTOM,
    api_key="your-api-key",
    base_url="https://api.myprovider.com"
)

provider = MyProvider(config)
```

That's it! Your provider is ready to use with just a few lines of code.

## Templates

### HTTPAPITemplate

For providers that use HTTP APIs with JSON requests/responses:

```python
class MyHTTPProvider(HTTPAPITemplate):
    def _get_model_mapping(self):
        return {ModelType.FAST: "fast-model"}

    def _get_api_endpoint(self):
        return "/chat/completions"

    def _get_headers(self):
        return {"Authorization": f"Bearer {self.api_key}"}
```

### OpenAICompatibleTemplate

For providers that follow OpenAI's API format:

```python
class MyOpenAIProvider(OpenAICompatibleTemplate):
    def _get_model_mapping(self):
        return {ModelType.FAST: "gpt-3.5-turbo"}

    def _get_api_endpoint(self):
        return "/v1/chat/completions"
```

### RESTAPITemplate

For providers with custom REST API formats:

```python
class MyRESTProvider(RESTAPITemplate):
    def _get_model_mapping(self):
        return {ModelType.FAST: "custom-model"}

    def _build_request_payload(self, request):
        return {
            "messages": request.messages,
            "model": request.model,
            "max_tokens": request.max_tokens
        }

    def _parse_response(self, response_data):
        return LLMResponse(
            content=response_data["response"],
            model=response_data["model"],
            usage=response_data.get("usage", {}),
            finish_reason="stop"
        )
```

### StreamingTemplate

For providers that support streaming responses:

```python
class MyStreamingProvider(StreamingTemplate):
    def _get_model_mapping(self):
        return {ModelType.FAST: "streaming-model"}

    async def _stream_response(self, request):
        # Implement streaming logic
        async for chunk in self._make_streaming_request(request):
            yield chunk
```

## Auto-Registration

The framework automatically discovers and registers providers:

```python
from gemini_sre_agent.llm.provider_framework import ProviderAutoRegistry

# Discover built-in providers
registry = ProviderAutoRegistry()
registry.discover_builtin_providers()

# Register discovered providers
registry.register_discovered_providers()

# Get provider information
info = registry.get_provider_info("my_provider")
```

## Validation

Validate your provider implementation:

```python
from gemini_sre_agent.llm.provider_framework import ProviderValidator

validator = ProviderValidator()
errors = validator.validate_provider_class(MyProvider)

if not errors:
    print("Provider is valid!")
else:
    print("Validation errors:", errors)
```

## Plugin Architecture

Load external provider plugins:

```python
from gemini_sre_agent.llm.provider_framework import ProviderPluginLoader

loader = ProviderPluginLoader()
loader.add_plugin_path("/path/to/plugins")

# Discover and load plugins
plugins = loader.discover_plugins(["/path/to/plugins"])

# Load a specific plugin
provider_class = loader.load_plugin("my_plugin")
```

## Capability Discovery

Discover what capabilities your provider supports:

```python
from gemini_sre_agent.llm.provider_framework import ProviderCapabilityDiscovery

discovery = ProviderCapabilityDiscovery()
capabilities = await discovery.discover_provider_capabilities(provider)

print("Streaming support:", capabilities["streaming"].supported)
print("Tools support:", capabilities["tools"].supported)
```

## Advanced Usage

### Custom Provider Implementation

For providers that don't fit the templates, implement the base interface directly:

```python
from gemini_sre_agent.llm.provider_framework.base_template import BaseProviderTemplate
from gemini_sre_agent.llm.base import LLMRequest, LLMResponse

class CustomProvider(BaseProviderTemplate):
    async def _make_api_request(self, request: LLMRequest) -> dict:
        # Custom API request logic
        return await self._custom_api_call(request)

    def _parse_response(self, response_data: dict) -> LLMResponse:
        # Custom response parsing
        return LLMResponse(
            content=response_data["custom_field"],
            model=request.model,
            usage=response_data.get("usage", {}),
            finish_reason="stop"
        )

    def _get_model_mapping(self) -> dict:
        return {ModelType.FAST: "custom-model"}
```

### Configuration Validation

Add custom configuration validation:

```python
class MyProvider(HTTPAPITemplate):
    @classmethod
    def validate_config(cls, config):
        super().validate_config(config)

        # Custom validation
        if not config.custom_field:
            raise ValueError("custom_field is required")

    def _get_model_mapping(self):
        return {ModelType.FAST: "my-model"}
```

### Error Handling

Implement custom error handling:

```python
class MyProvider(HTTPAPITemplate):
    async def _make_api_request(self, request: LLMRequest) -> dict:
        try:
            return await super()._make_api_request(request)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Handle rate limiting
                await asyncio.sleep(1)
                return await self._make_api_request(request)
            raise

    def _get_model_mapping(self):
        return {ModelType.FAST: "my-model"}
```

## Best Practices

### 1. Use Templates When Possible

Templates provide the most functionality with the least code:

```python
# Good: Use template
class MyProvider(HTTPAPITemplate):
    def _get_model_mapping(self):
        return {ModelType.FAST: "my-model"}

# Avoid: Reimplementing everything
class MyProvider(BaseProviderTemplate):
    # Lots of boilerplate code...
```

### 2. Implement Required Methods

Always implement the three required abstract methods:

```python
class MyProvider(BaseProviderTemplate):
    async def _make_api_request(self, request: LLMRequest) -> dict:
        # API request logic
        pass

    def _parse_response(self, response_data: dict) -> LLMResponse:
        # Response parsing logic
        pass

    def _get_model_mapping(self) -> dict:
        # Model mapping logic
        pass
```

### 3. Validate Configuration

Always validate provider-specific configuration:

```python
@classmethod
def validate_config(cls, config):
    super().validate_config(config)

    # Provider-specific validation
    if not hasattr(config, 'custom_field'):
        raise ValueError("custom_field is required")
```

### 4. Handle Errors Gracefully

Implement proper error handling:

```python
async def _make_api_request(self, request: LLMRequest) -> dict:
    try:
        # API call
        pass
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 429:
            # Rate limiting
            await asyncio.sleep(1)
            return await self._make_api_request(request)
        raise
```

### 5. Test Your Provider

Write tests for your provider:

```python
import pytest
from unittest.mock import AsyncMock, patch

class TestMyProvider:
    @pytest.fixture
    def provider(self):
        config = LLMProviderConfig(
            provider=ProviderType.CUSTOM,
            api_key="test-key",
            base_url="https://api.test.com"
        )
        return MyProvider(config)

    @pytest.mark.asyncio
    async def test_generate(self, provider):
        with patch.object(provider, '_make_api_request') as mock_request:
            mock_request.return_value = {
                "choices": [{"message": {"content": "test"}}],
                "model": "test-model",
                "usage": {"total_tokens": 10}
            }

            request = LLMRequest(
                messages=[{"role": "user", "content": "Hello"}],
                model="test-model"
            )

            response = await provider.generate(request)
            assert response.content == "test"
```

## Examples

See the `examples/` directory for complete working examples:

- `simple_provider.py`: Basic provider using HTTPAPITemplate
- `custom_provider.py`: Custom provider with advanced features

## Troubleshooting

### Common Issues

1. **Provider not discovered**: Ensure your provider class is in the correct module and follows naming conventions.

2. **Validation errors**: Check that all required methods are implemented and configuration is valid.

3. **API errors**: Verify your API endpoint, headers, and request format are correct.

4. **Import errors**: Make sure all required dependencies are installed.

### Getting Help

1. Check the examples in the `examples/` directory
2. Run the validation tools to identify issues
3. Use the capability discovery to understand what your provider supports
4. Review the test files for usage patterns

## API Reference

### BaseProviderTemplate

Base class for all provider templates.

#### Methods

- `generate(request: LLMRequest) -> LLMResponse`: Generate a response
- `health_check() -> bool`: Check provider health
- `get_available_models() -> dict`: Get available models
- `supports_streaming() -> bool`: Check streaming support
- `supports_tools() -> bool`: Check tools support
- `token_count(text: str) -> int`: Count tokens
- `cost_estimate(input_tokens: int, output_tokens: int) -> float`: Estimate cost

#### Abstract Methods

- `_make_api_request(request: LLMRequest) -> dict`: Make API request
- `_parse_response(response_data: dict) -> LLMResponse`: Parse response
- `_get_model_mapping() -> dict`: Get model mapping

### ProviderAutoRegistry

Automatic provider discovery and registration.

#### Methods

- `discover_builtin_providers()`: Discover built-in providers
- `register_discovered_providers()`: Register discovered providers
- `get_provider_info(name: str) -> dict`: Get provider information
- `validate_discovered_providers() -> dict`: Validate providers

### ProviderValidator

Provider implementation validation.

#### Methods

- `validate_provider_class(provider_class) -> list`: Validate provider class
- `generate_validation_report(provider_class) -> dict`: Generate validation report

### ProviderPluginLoader

Plugin loading and management.

#### Methods

- `add_plugin_path(path: str)`: Add plugin path
- `discover_plugins(paths: list) -> dict`: Discover plugins
- `load_plugin(name: str)`: Load plugin
- `list_loaded_plugins() -> list`: List loaded plugins

### ProviderCapabilityDiscovery

Provider capability discovery and analysis.

#### Methods

- `discover_provider_capabilities(provider) -> dict`: Discover capabilities
- `find_providers_with_capability(capability: str) -> list`: Find providers with capability
- `validate_provider_for_use_case(provider: str, use_case: str) -> dict`: Validate for use case
- `export_capability_report() -> dict`: Export capability report
