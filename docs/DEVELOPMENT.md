# Development Guide

This guide provides essential information for developers working on the Gemini SRE Agent project. It covers setting up your development environment, running tests, and understanding code quality practices.

## Development Environment Setup

Assuming you have completed the [Setup and Installation Guide](SETUP_INSTALLATION.md), your development environment should be ready. Key tools for development include:

*   **Python 3.12+**
*   **`uv`**: For dependency management.
*   **`pytest`**: For running tests.
*   **`gcloud` CLI**: For GCP authentication and interaction.

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

Tests are located in the `tests/` directory, mirroring the structure of the `src/` directory. Each core module (e.g., `triage_agent.py`, `analysis_agent.py`) has a corresponding test file (e.g., `test_triage_agent.py`, `test_analysis_agent.py`).

*   **`pytest-asyncio`**: Used for testing asynchronous functions and methods.
*   **Mocking:** `unittest.mock.patch` is used extensively to mock external dependencies (like GCP Vertex AI API calls or GitHub API calls) to ensure tests are isolated, fast, and do not require live credentials.

## Code Quality

Maintaining high code quality is crucial for the project's long-term maintainability and reliability.

### Type Hinting

The codebase extensively uses [Python type hints](https://docs.python.org/3/library/typing.html) to improve code readability, enable static analysis, and reduce runtime errors. Developers are expected to adhere to existing type hinting conventions when contributing new code or modifying existing sections. Pydantic models are also used for robust data validation and clear data structures, further enhancing type safety and code quality.

### Linting and Formatting

(Instructions for linting and formatting tools like `ruff` and `black` would go here. Example commands below are placeholders.)

*   **`ruff`**: Used for linting and checking code for common errors and style violations.
    ```bash
    # Install ruff (if not already installed via uv sync)
    # uv pip install ruff
    ruff check .
    ```
*   **`black`**: Used for automatic code formatting to ensure consistent style across the codebase.
    ```bash
    # Install black (if not already installed via uv sync)
    # uv pip install black
    black .
    ```

### Resilience Implementation

The agent incorporates robust resilience patterns using the `hyx` library (for circuit breakers, retries, bulkheads, rate limiting) and `asyncio.wait_for()` for explicit timeout handling. When developing, consider how new components or external interactions can benefit from these patterns to ensure the agent's stability under adverse conditions. The `tenacity` library is also used for simpler retry mechanisms on specific operations.

## Contributing

We welcome contributions to the Gemini SRE Agent! To contribute:

1.  Fork the repository.
2.  Create a new branch for your feature or bug fix.
3.  Implement your changes, ensuring they adhere to the project's code quality standards and include comprehensive tests.
4.  Submit a Pull Request to the `main` branch of the upstream repository.

When submitting a Pull Request, please ensure:
*   Your code passes all existing tests.
*   New features or bug fixes are accompanied by appropriate unit and/or integration tests.
*   Your code is well-documented with docstrings and comments where necessary.
*   Your commit messages are clear and descriptive.