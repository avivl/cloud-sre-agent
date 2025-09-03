# Development Guide

This guide provides essential information for developers working on the Gemini SRE Agent project. It covers setting up your development environment, running tests, and understanding code quality practices.

## Development Environment Setup

Assuming you have completed the [Setup and Installation Guide](SETUP_INSTALLATION.md), your development environment should be ready. Key tools for development include:

- **Python 3.12+**
- **`uv`**: For dependency management.
- **`pytest`**: For running tests.
- **`gcloud` CLI**: For GCP authentication and interaction.

## Running the Agent Locally

To run the agent in your local development environment:

```bash
python main.py
```

This will start the agent, which will attempt to load configurations from `config/config.yaml` and set up log monitoring for the defined services. Ensure your GCP credentials and GitHub token are correctly configured as per the [Setup and Installation Guide](SETUP_INSTALLATION.md).

## Testing

Comprehensive unit tests are provided to ensure the correctness and reliability of the agent's components.

### Running Unit Tests

To execute all unit tests, navigate to the project root and run:

```bash
uv run pytest
```

Alternatively, if you have `pytest` installed globally or in your virtual environment:

```bash
pytest
```

### Test Structure

Tests are located in the `tests/` directory, mirroring the structure of the `gemini_sre_agent/` package. Each core module (e.g., `triage_agent.py`, `analysis_agent.py`) has a corresponding test file (e.g., `test_triage_agent.py`, `test_analysis_agent.py`).

- **`pytest-asyncio`**: Used for testing asynchronous functions and methods.
- **Mocking:** `unittest.mock.patch` is used extensively to mock external dependencies (like GCP Vertex AI API calls or GitHub API calls) to ensure tests are isolated, fast, and do not require live credentials.

### Integration Testing

Integration tests verify the end-to-end functionality of the agent by making live calls to GCP and GitHub services. These tests are located in `tests/integration/`.

To run integration tests, you need to:

1.  **Configure your GCP project:** Ensure Vertex AI API is enabled, models are available, and your service account has necessary permissions.
2.  **Configure a dedicated GitHub repository:** For the `RemediationAgent` to create test branches and PRs.
3.  **Set `GITHUB_TOKEN` environment variable.**

Run integration tests using the `integration` marker:

```bash
uv run pytest -m integration
# or
pytest -m integration
```

## Code Quality

Maintaining high code quality is crucial for the project's long-term maintainability and reliability.

### Type Hinting

The codebase extensively uses [Python type hints](https://docs.python.org/3/library/typing.html) to improve code readability, enable static analysis, and reduce runtime errors. Developers are expected to adhere to existing type hinting conventions when contributing new code or modifying existing sections. Pydantic models are also used for robust data validation and clear data structures, further enhancing type safety and code quality.

### Enhanced Configuration System

The project now uses a modern, type-safe configuration system built on Pydantic and `pydantic-settings`. This system provides:

- **Type-safe configuration** with comprehensive validation
- **Environment variable integration** for sensitive data
- **Hot reloading** capabilities for development
- **CLI tools** for validation, migration, and management
- **Schema versioning** for compatibility tracking

#### Using the Configuration System

```python
from gemini_sre_agent.config import ConfigManager

# Initialize configuration manager
config_manager = ConfigManager("config/config.yaml")

# Load configuration
config = config_manager.reload_config()

# Access configuration with type safety
services = config.services
ml_config = config.ml
performance_config = config.performance
```

#### Configuration CLI Tools

The system includes powerful CLI tools for configuration management:

```bash
# Validate configuration
python -m gemini_sre_agent.config.cli_tools validate config/config.yaml

# Generate configuration template
python -m gemini_sre_agent.config.cli_tools generate_template --output config/template.yaml

# Migrate from legacy format
python -m gemini_sre_agent.config.cli_tools migrate --input old_config.yaml --output new_config.yaml

# Compare configurations
python -m gemini_sre_agent.config.cli_tools diff config1.yaml config2.yaml
```

For more details, see the [Configuration Guide](CONFIGURATION.md) and [Configuration Migration Guide](CONFIG_MIGRATION_GUIDE.md).

### Linting and Formatting

The project uses `ruff` for linting and `black` for automatic code formatting to ensure consistent style across the codebase.

- **`ruff`**: Used for linting and checking code for common errors and style violations.
  ```bash
  uv pip install ruff # If not already installed
  ruff check .
  ```
- **`black`**: Used for automatic code formatting to ensure consistent style across the codebase.
  ```bash
  uv pip install black # If not already installed
  black .
  ```

### Static Type Checking

`pyright` is used for static type checking to catch type-related errors before runtime.

- **`pyright`**:
  ```bash
  uv pip install pyright # If not already installed
  pyright
  ```
  Ensure `pyrightconfig.json` is configured in the project root.

### Resilience Implementation

The agent incorporates robust resilience patterns using the `hyx` library (for circuit breakers, retries, bulkheads, rate limiting) and `asyncio.wait_for()` for explicit timeout handling. When developing, consider how new components or external interactions can benefit from these patterns to ensure the agent's stability under adverse conditions. The `tenacity` library is also used for simpler retry mechanisms on specific operations.

## Contributing

We welcome contributions to the Gemini SRE Agent! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes, ensuring they adhere to the project's code quality standards and include comprehensive tests.
4.  Submit a Pull Request to the `main` branch of the upstream repository.

When submitting a Pull Request, please ensure:

- Your code passes all existing tests.
- New features or bug fixes are accompanied by appropriate unit and/or integration tests.
- Your code is well-documented with docstrings and comments where necessary.
- Your commit messages are clear and descriptive.

## IDE Setup

### VS Code Configuration

For VS Code users, it's recommended to install the following extensions:

- **Python** (ms-python.python): Provides rich support for Python development.
- **Pylance** (ms-python.vscode-pylance): Enhances Python language server with type checking and intelligent code completion.
- **ruff** (charliermarsh.ruff): Integrates the `ruff` linter.
- **Black Formatter** (ms-python.black-formatter): Integrates the `black` formatter.

Ensure your VS Code settings are configured to use `ruff` as the linter and `black` as the formatter. You might also need to configure your Python interpreter to point to your project's virtual environment.

### PyCharm Configuration

For PyCharm users, ensure your project interpreter is set to the project's virtual environment. PyCharm typically auto-detects `ruff` and `black` if they are installed in the environment. You can also configure them manually in `Settings/Preferences > Tools > External Tools` or `Settings/Preferences > Editor > Code Style > Python`.

## Debugging

### Local Debugging Setup

You can debug the agent locally using your IDE's debugging features.

**VS Code:**

1.  Open the `main.py` file.
2.  Set breakpoints by clicking in the gutter next to the line numbers.
3.  Go to the Run and Debug view (Ctrl+Shift+D or Cmd+Shift+D).
4.  Click "Run and Debug" and select "Python File" or configure a `launch.json` for more advanced debugging scenarios.

**PyCharm:**

1.  Open the `main.py` file.
2.  Set breakpoints by clicking in the gutter next to the line numbers.
3.  Right-click on the `main.py` file and select "Debug 'main'".

### Log Analysis

The agent uses structured logging. When debugging, pay attention to the log levels (`DEBUG`, `INFO`, `WARN`, `ERROR`) and the `extra` fields in JSON logs for contextual information.

```bash
# Example of filtering logs for a specific service in a JSON log file
cat /var/log/gemini-sre-agent.log | grep "billing-service" | jq .
```
