# Test Structure Migration Guide

## Overview
The test structure has been reorganized to follow the new modular architecture.

## New Structure
- `tests/core/` - Core module tests (exceptions, types, interfaces, protocols)
- `tests/agents/` - Agent module tests (models, specialized agents)
- `tests/llm/` - LLM module tests (providers, factory, config, services)
- `tests/ml/` - ML module tests (workflow, code generation)
- `tests/pattern_detector/` - Pattern detection tests
- `tests/source_control/` - Source control tests
- `tests/ingestion/` - Ingestion system tests
- `tests/metrics/` - Metrics and monitoring tests
- `tests/resilience/` - Resilience and error handling tests
- `tests/security/` - Security and compliance tests
- `tests/integration/` - Integration and end-to-end tests
- `tests/performance/` - Performance and benchmark tests
- `tests/config/` - Configuration tests

## Migration Steps
1. Move existing test files to appropriate new directories
2. Update import statements to match new module structure
3. Update test class names and docstrings
4. Ensure all tests follow the new naming conventions
5. Run tests to verify functionality

## Templates
Use the provided templates in `tests/templates/` as starting points for new tests.
