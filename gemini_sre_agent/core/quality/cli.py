# gemini_sre_agent/core/quality/cli.py
"""
Command-line interface for quality gates.

This module provides a CLI tool for running quality gates and generating reports.
"""

import asyncio
from pathlib import Path
import sys

import click

from ..logging import get_logger
from .exceptions import QualityGateError
from .gates import QualityGateConfig, QualityGateManager
from .reports import QualityReportFormatter, QualityReportGenerator, ReportFormat
from .validators import (
    DocumentationGate,
    PerformanceGate,
    SecurityGate,
    StaticAnalysisGate,
    StyleGate,
    TestCoverageGate,
)

logger = get_logger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--config", "-c", type=click.Path(exists=True), help="Path to configuration file")
@click.pass_context
def cli(ctx, verbose: bool, config: str | None):
    """Quality gate management CLI."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["config"] = config


@cli.command()
@click.option("--pyright/--no-pyright", default=True, help="Enable/disable pyright checks")
@click.option("--ruff/--no-ruff", default=True, help="Enable/disable ruff checks")
@click.option("--coverage/--no-coverage", default=True, help="Enable/disable coverage checks")
@click.option("--security/--no-security", default=True, help="Enable/disable security checks")
@click.option(
    "--performance/--no-performance", 
    default=True, 
    help="Enable/disable performance checks"
)
@click.option("--docs/--no-docs", default=True, help="Enable/disable documentation checks")
@click.option("--style/--no-style", default=True, help="Enable/disable style checks")
@click.option("--min-coverage", default=80.0, help="Minimum test coverage percentage")
@click.option("--max-line-length", default=100, help="Maximum line length")
@click.option("--fail-on-warning", is_flag=True, help="Fail on warnings")
@click.option("--parallel/--no-parallel", default=True, help="Run gates in parallel")
@click.option("--timeout", default=300, help="Timeout in seconds")
@click.option("--output", "-o", type=click.Path(), help="Output file for report")
@click.option(
    "--format", 
    "output_format", 
    type=click.Choice(["json", "html", "markdown", "console"]),
    default="console", 
    help="Output format"
)
@click.option("--gates", help="Comma-separated list of gates to run (default: all)")
def run(
    pyright: bool,
    ruff: bool,
    coverage: bool,
    security: bool,
    performance: bool,
    docs: bool,
    style: bool,
    min_coverage: float,
    max_line_length: int,
    fail_on_warning: bool,
    parallel: bool,
    timeout: int,
    output: str | None,
    output_format: str,
    gates: str | None
):
    """Run quality gates."""
    asyncio.run(_run_quality_gates(
        pyright=pyright,
        ruff=ruff,
        coverage=coverage,
        security=security,
        performance=performance,
        docs=docs,
        style=style,
        min_coverage=min_coverage,
        max_line_length=max_line_length,
        fail_on_warning=fail_on_warning,
        parallel=parallel,
        timeout=timeout,
        output=output,
        output_format=output_format,
        gates=gates
    ))


async def _run_quality_gates(
    pyright: bool,
    ruff: bool,
    coverage: bool,
    security: bool,
    performance: bool,
    docs: bool,
    style: bool,
    min_coverage: float,
    max_line_length: int,
    fail_on_warning: bool,
    parallel: bool,
    timeout: int,
    output: str | None,
    output_format: str,
    gates: str | None
):
    """Run quality gates with the specified configuration."""
    try:
        # Create configuration
        config = QualityGateConfig(
            enable_pyright=pyright,
            enable_ruff=ruff,
            enable_coverage=coverage,
            enable_security=security,
            enable_performance=performance,
            enable_docs=docs,
            enable_style=style,
            min_coverage=min_coverage,
            max_line_length=max_line_length,
            fail_on_warning=fail_on_warning,
            parallel_execution=parallel,
            timeout_seconds=timeout
        )

        # Create quality gate manager
        manager = QualityGateManager(config)

        # Register gates
        manager.register_gate("static_analysis", StaticAnalysisGate())
        manager.register_gate("test_coverage", TestCoverageGate())
        manager.register_gate("security", SecurityGate())
        manager.register_gate("performance", PerformanceGate())
        manager.register_gate("documentation", DocumentationGate())
        manager.register_gate("style", StyleGate())

        # Filter gates if specified
        if gates:
            gate_names = [name.strip() for name in gates.split(",")]
            manager.gates = {
                name: manager.gates[name] 
                for name in gate_names if name in manager.gates
            }

        # Run gates
        logger.info("Starting quality gate execution")
        start_time = asyncio.get_event_loop().time()

        results = await manager.run_all_gates()

        duration = asyncio.get_event_loop().time() - start_time

        # Generate report
        report_generator = QualityReportGenerator()
        report = report_generator.generate_report(results, duration)

        # Format and display report
        formatter = QualityReportFormatter()
        format_type = ReportFormat(output_format)
        report_content = formatter.format_report(report, format_type)

        if output:
            output_path = Path(output)
            formatter.save_report(report, output_path, format_type)
            click.echo(f"Report saved to {output_path}")
        else:
            click.echo(report_content)

        # Check if build should fail
        if manager.should_fail_build(results):
            click.echo("❌ Quality gates failed - build should not proceed", err=True)
            sys.exit(1)
        else:
            click.echo("✅ All quality gates passed")
            sys.exit(0)

    except QualityGateError as e:
        click.echo(f"❌ Quality gate error: {e.message}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Unexpected error: {e!s}", err=True)
        logger.exception("Unexpected error in quality gate execution")
        sys.exit(1)


@cli.command()
@click.option("--output", "-o", type=click.Path(), help="Output file for configuration")
def init_config(output: str | None):
    """Initialize a quality gate configuration file."""
    config = QualityGateConfig()

    config_content = f"""# Quality Gate Configuration
# Generated by gemini-sre-agent quality gates

[quality_gates]
# Static analysis
enable_pyright = {str(config.enable_pyright).lower()}
enable_ruff = {str(config.enable_ruff).lower()}
pyright_strict = {str(config.pyright_strict).lower()}
ruff_strict = {str(config.ruff_strict).lower()}

# Test coverage
enable_coverage = {str(config.enable_coverage).lower()}
min_coverage = {config.min_coverage}
coverage_file = "{config.coverage_file}"

# Security
enable_security = {str(config.enable_security).lower()}
security_tools = {config.security_tools}

# Performance
enable_performance = {str(config.enable_performance).lower()}
max_memory_mb = {config.max_memory_mb}
max_cpu_percent = {config.max_cpu_percent}

# Documentation
enable_docs = {str(config.enable_docs).lower()}
require_docstrings = {str(config.require_docstrings).lower()}
min_docstring_coverage = {config.min_docstring_coverage}

# Style
enable_style = {str(config.enable_style).lower()}
max_line_length = {config.max_line_length}
require_type_hints = {str(config.require_type_hints).lower()}

# General
fail_on_warning = {str(config.fail_on_warning).lower()}
parallel_execution = {str(config.parallel_execution).lower()}
timeout_seconds = {config.timeout_seconds}
"""

    if output:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            f.write(config_content)
        click.echo(f"Configuration saved to {output_path}")
    else:
        click.echo(config_content)


@cli.command()
@click.option(
    "--format", 
    "output_format", 
    type=click.Choice(["json", "html", "markdown", "console"]),
    default="console", 
    help="Output format"
)
def list_gates(output_format: str):
    """List available quality gates."""
    gates_info = [
        {
            "name": "static_analysis",
            "description": "Static analysis using pyright and ruff",
            "tools": ["pyright", "ruff"]
        },
        {
            "name": "test_coverage",
            "description": "Test coverage validation",
            "tools": ["pytest", "coverage"]
        },
        {
            "name": "security",
            "description": "Security vulnerability scanning",
            "tools": ["bandit", "safety"]
        },
        {
            "name": "performance",
            "description": "Performance metrics validation",
            "tools": ["psutil", "custom benchmarks"]
        },
        {
            "name": "documentation",
            "description": "Documentation quality checks",
            "tools": ["pydocstyle", "custom checks"]
        },
        {
            "name": "style",
            "description": "Code style validation",
            "tools": ["ruff", "custom checks"]
        }
    ]

    if output_format == "json":
        import json
        click.echo(json.dumps(gates_info, indent=2))
    elif output_format == "html":
        html = "<html><body><h1>Available Quality Gates</h1><ul>"
        for gate in gates_info:
            html += (
                f"<li><strong>{gate['name']}</strong>: {gate['description']} "
                f"(Tools: {', '.join(gate['tools'])})</li>"
            )
        html += "</ul></body></html>"
        click.echo(html)
    elif output_format == "markdown":
        md = "# Available Quality Gates\n\n"
        for gate in gates_info:
            md += f"## {gate['name']}\n"
            md += f"**Description:** {gate['description']}\n"
            md += f"**Tools:** {', '.join(gate['tools'])}\n\n"
        click.echo(md)
    else:
        click.echo("Available Quality Gates:")
        click.echo("=" * 40)
        for gate in gates_info:
            click.echo(f"• {gate['name']}: {gate['description']}")
            click.echo(f"  Tools: {', '.join(gate['tools'])}")
            click.echo()


if __name__ == "__main__":
    cli()
