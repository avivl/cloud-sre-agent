# Quality Gates System

A comprehensive code quality validation system for the Gemini SRE Agent project.

## Overview

The Quality Gates system provides automated validation of code quality across multiple dimensions:

- **Static Analysis**: Type checking with Pyright and linting with Ruff
- **Test Coverage**: Automated test coverage validation
- **Security**: Vulnerability scanning with Bandit and dependency checks
- **Performance**: Resource usage and performance metrics validation
- **Documentation**: Docstring coverage and documentation quality checks
- **Style**: Code formatting and style consistency validation

## Quick Start

### Using the CLI

```bash
# Run all quality gates
python -m gemini_sre_agent.core.quality.cli run

# Run specific gates
python -m gemini_sre_agent.core.quality.cli run --gates=static_analysis,security

# Generate HTML report
python -m gemini_sre_agent.core.quality.cli run --output=report.html --format=html

# Run with custom configuration
python -m gemini_sre_agent.core.quality.cli run --min-coverage=90 --max-line-length=120
```

### Using Make

```bash
# Quick quality check (static analysis only)
make quality-gates-quick

# Full quality gates
make quality-gates-full

# All quality gates with console output
make quality-gates
```

### Using Pre-commit Hooks

```bash
# Install pre-commit hooks
make install-hooks

# Run hooks on all files
make pre-commit-all
```

## Configuration

### Quality Gate Configuration

Create a configuration file to customize quality gate behavior:

```python
from gemini_sre_agent.core.quality import QualityGateConfig

config = QualityGateConfig(
    # Static analysis
    enable_pyright=True,
    enable_ruff=True,
    pyright_strict=True,
    ruff_strict=True,
    
    # Test coverage
    enable_coverage=True,
    min_coverage=80.0,
    
    # Security
    enable_security=True,
    security_tools=["bandit", "safety"],
    
    # Performance
    enable_performance=True,
    max_memory_mb=512,
    max_cpu_percent=80.0,
    
    # Documentation
    enable_docs=True,
    min_docstring_coverage=90.0,
    
    # Style
    enable_style=True,
    max_line_length=100,
    
    # General
    fail_on_warning=False,
    parallel_execution=True,
    timeout_seconds=300
)
```

### Ruff Configuration

The project includes a `ruff.toml` configuration file with optimized settings:

```toml
line-length = 100
target-version = "py312"

[lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM", "TCH", "TID", "Q", "RUF"]
ignore = ["E501", "B008", "C901"]

[lint.per-file-ignores]
"tests/**/*.py" = ["S101", "S106", "S108"]
"**/__init__.py" = ["F401"]
```

### Pyright Configuration

Type checking is configured via `pyrightconfig.json`:

```json
{
  "venvPath": ".",
  "venv": ".venv",
  "include": ["gemini_sre_agent", "main.py"],
  "exclude": ["**/__pycache__", "**/.pytest_cache", "**/tests"],
  "reportMissingImports": true,
  "reportUndefinedVariable": true,
  "reportPossiblyUnboundVariable": true,
  "reportArgumentType": true,
  "reportAttributeAccessIssue": true
}
```

## Quality Gates

### Static Analysis Gate

Validates code using static analysis tools:

- **Pyright**: Type checking with strict mode
- **Ruff**: Linting and code style validation

```python
from gemini_sre_agent.core.quality.validators import StaticAnalysisGate

gate = StaticAnalysisGate()
result = await gate.check(config)
```

### Test Coverage Gate

Ensures adequate test coverage:

- Minimum coverage percentage validation
- Coverage report generation
- Integration with pytest-cov

```python
from gemini_sre_agent.core.quality.validators import TestCoverageGate

gate = TestCoverageGate()
result = await gate.check(config)
```

### Security Gate

Scans for security vulnerabilities:

- **Bandit**: Security issue detection
- **Safety**: Dependency vulnerability scanning

```python
from gemini_sre_agent.core.quality.validators import SecurityGate

gate = SecurityGate()
result = await gate.check(config)
```

### Performance Gate

Monitors performance metrics:

- Memory usage validation
- CPU usage monitoring
- Resource threshold enforcement

```python
from gemini_sre_agent.core.quality.validators import PerformanceGate

gate = PerformanceGate()
result = await gate.check(config)
```

### Documentation Gate

Validates documentation quality:

- Docstring coverage analysis
- Documentation completeness checks
- Quality metrics validation

```python
from gemini_sre_agent.core.quality.validators import DocumentationGate

gate = DocumentationGate()
result = await gate.check(config)
```

### Style Gate

Enforces code style consistency:

- Line length validation
- Formatting consistency checks
- Style rule enforcement

```python
from gemini_sre_agent.core.quality.validators import StyleGate

gate = StyleGate()
result = await gate.check(config)
```

## Programmatic Usage

### Basic Usage

```python
import asyncio
from gemini_sre_agent.core.quality import QualityGateManager, QualityGateConfig
from gemini_sre_agent.core.quality.validators import (
    StaticAnalysisGate,
    TestCoverageGate,
    SecurityGate
)

async def run_quality_gates():
    # Create configuration
    config = QualityGateConfig(
        min_coverage=85.0,
        max_line_length=100,
        fail_on_warning=True
    )
    
    # Create manager
    manager = QualityGateManager(config)
    
    # Register gates
    manager.register_gate("static_analysis", StaticAnalysisGate())
    manager.register_gate("test_coverage", TestCoverageGate())
    manager.register_gate("security", SecurityGate())
    
    # Run all gates
    results = await manager.run_all_gates()
    
    # Check results
    failed_gates = manager.get_failed_gates(results)
    if failed_gates:
        print(f"Failed gates: {[r.gate_name for r in failed_gates]}")
        return False
    
    print("All quality gates passed!")
    return True

# Run the gates
asyncio.run(run_quality_gates())
```

### Custom Gates

Create custom quality gates by implementing the `QualityGate` protocol:

```python
from gemini_sre_agent.core.quality.gates import QualityGate, QualityGateResult, QualityGateStatus

class CustomGate:
    async def check(self, config: QualityGateConfig) -> QualityGateResult:
        # Your custom validation logic here
        if self._custom_validation():
            return QualityGateResult(
                gate_name="custom_gate",
                status=QualityGateStatus.PASSED,
                message="Custom validation passed"
            )
        else:
            return QualityGateResult(
                gate_name="custom_gate",
                status=QualityGateStatus.FAILED,
                message="Custom validation failed"
            )
    
    def _custom_validation(self) -> bool:
        # Implement your validation logic
        return True
```

## Reporting

### Report Formats

The system supports multiple report formats:

- **JSON**: Machine-readable format for CI/CD integration
- **HTML**: Rich visual reports for web viewing
- **Markdown**: Documentation-friendly format
- **Console**: Human-readable terminal output

### Generating Reports

```python
from gemini_sre_agent.core.quality.reports import (
    QualityReportGenerator,
    QualityReportFormatter,
    ReportFormat
)

# Generate report
generator = QualityReportGenerator()
report = generator.generate_report(results, duration)

# Format report
formatter = QualityReportFormatter()
json_report = formatter.format_report(report, ReportFormat.JSON)
html_report = formatter.format_report(report, ReportFormat.HTML)

# Save report
formatter.save_report(report, Path("quality-report.html"), ReportFormat.HTML)
```

## CI/CD Integration

### GitHub Actions

The project includes a GitHub Actions workflow (`.github/workflows/quality-gates.yml`) that:

- Runs quality gates on every push and PR
- Generates reports and uploads artifacts
- Comments on PRs with quality gate results
- Fails the build if quality gates fail

### Pre-commit Hooks

Pre-commit hooks (`.pre-commit-config.yaml`) ensure code quality before commits:

- Ruff linting and formatting
- Pyright type checking
- Bandit security scanning
- Custom quality gate validation

### Makefile

The included `Makefile` provides convenient commands:

```bash
make quality-gates          # Run all quality gates
make quality-gates-quick    # Quick check (static analysis only)
make quality-gates-full     # Full check with all validations
make dev-check             # Quick development check
make ci                    # Full CI pipeline simulation
```

## Troubleshooting

### Common Issues

1. **Pyright not found**: Install with `pip install pyright`
2. **Ruff not found**: Install with `pip install ruff`
3. **Bandit not found**: Install with `pip install bandit`
4. **Coverage too low**: Increase test coverage or adjust `min_coverage` setting

### Debug Mode

Enable verbose logging for debugging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Custom Configuration

Override default settings by creating a custom configuration:

```python
config = QualityGateConfig(
    enable_pyright=True,
    pyright_strict=False,  # Less strict type checking
    min_coverage=70.0,     # Lower coverage requirement
    fail_on_warning=False  # Don't fail on warnings
)
```

## Contributing

When contributing to the quality gates system:

1. Follow the existing code style and patterns
2. Add appropriate tests for new functionality
3. Update documentation for new features
4. Ensure all quality gates pass before submitting PRs

## License

This quality gates system is part of the Gemini SRE Agent project and follows the same license terms.
