# Error Handling Integration Examples

This directory contains examples demonstrating how the advanced error handling system is integrated into the source control providers.

## Examples

### `error_handling_integration_example.py`

A comprehensive example that demonstrates:

- **Error Handling Factory**: How to create error handling components for different providers
- **Provider Integration**: How GitHub, GitLab, and Local providers automatically initialize error handling
- **Advanced Features**: Monitoring dashboard and self-healing capabilities
- **Configuration**: How to configure error handling for different providers

## Running the Examples

```bash
# Run the integration example
python examples/error_handling_integration_example.py
```

## What You'll See

The example will show:

1. ✅ Error handling components being created for each provider
2. ✅ Providers automatically initializing error handling systems
3. ✅ Circuit breakers, retry managers, and fallback strategies being set up
4. ✅ Monitoring dashboard providing system health and metrics
5. ✅ Self-healing capabilities analyzing errors and triggering recovery actions

## Key Integration Points

### 1. Automatic Initialization

All providers automatically initialize error handling when they start up:

```python
# In GitHubProvider._setup_client()
self._initialize_error_handling("github", self.repo_config.error_handling.model_dump())

# In GitLabProvider.initialize()
self._initialize_error_handling("gitlab", self.repo_config.error_handling.model_dump())

# In LocalProvider.__init__()
self._initialize_error_handling("local", self.repo_config.error_handling.model_dump())
```

### 2. Operation Wrapping

All critical operations are wrapped with error handling:

```python
async def get_file_content(self, path: str, ref: Optional[str] = None) -> str:
    return await self._execute_with_error_handling(
        "get_file_content", self.operations.get_file_content, path, ref
    )
```

### 3. Graceful Fallback

If advanced error handling fails to initialize, providers fall back to legacy error handling:

```python
async def _execute_with_error_handling(self, operation_name: str, func: Callable, *args, **kwargs) -> Any:
    if self._error_handling_components:
        # Use advanced error handling system
        resilient_manager = self._error_handling_components.get("resilient_manager")
        if resilient_manager:
            return await resilient_manager.execute_resilient_operation(
                operation_name, func, *args, **kwargs
            )
    
    # Fall back to legacy resilient manager
    return await self._execute_resilient_operation(operation_name, func, *args, **kwargs)
```

## Configuration

Each provider can have custom error handling configuration:

```python
config = GitHubRepositoryConfig(
    name="my-repo",
    owner="my-org",
    token="ghp_...",
    error_handling=ErrorHandlingConfig(
        circuit_breaker={
            "failure_threshold": 5,
            "recovery_timeout": 30,
            "expected_exception": "Exception"
        },
        retry={
            "max_attempts": 3,
            "base_delay": 1.0,
            "max_delay": 10.0,
            "exponential_base": 2.0
        }
    )
)
```

## Monitoring

The monitoring dashboard provides real-time insights:

- System health status
- Error handling metrics
- Circuit breaker states
- Recovery action status

## Self-Healing

The self-healing system automatically:

- Analyzes error patterns
- Triggers recovery actions
- Monitors system health
- Provides fallback strategies

This integration ensures that all source control operations are resilient, monitored, and self-healing!
