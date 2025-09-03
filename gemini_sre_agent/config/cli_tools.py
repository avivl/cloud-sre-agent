# gemini_sre_agent/config/cli_tools.py

"""
CLI tools and development utilities for configuration management.
"""


import click
import yaml

from .app_config import AppConfig
from .dev_utils import ConfigDevUtils
from .errors import ConfigFileError, ConfigValidationError
from .manager import ConfigManager


@click.group()
def config_cli():
    """Gemini SRE Agent Configuration Management CLI."""
    pass


@config_cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option(
    "--environment", "-e", default="development", help="Environment to validate against"
)
def validate(config_file: str, environment: str):
    """Validate configuration file against schema."""
    try:
        manager = ConfigManager()
        config = manager.loader.load_config(
            AppConfig, config_file=config_file, environment=environment
        )

        click.echo("✅ Configuration validation successful!")
        click.echo(f"   Environment: {config.environment}")
        click.echo(f"   Schema version: {config.schema_version}")
        click.echo(f"   Services configured: {len(config.services)}")

        # Validate checksum if present
        if config.validation_checksum:
            if config.validate_checksum():
                click.echo("✅ Configuration checksum validation passed")
            else:
                click.echo(
                    "⚠️  Configuration checksum validation failed - possible drift detected"
                )

    except ConfigValidationError as e:
        click.echo("❌ Configuration validation failed:")
        click.echo(e.format_errors())
        raise click.Abort() from e
    except ConfigFileError as e:
        click.echo(f"❌ Configuration file error: {e}")
        raise click.Abort() from e


@config_cli.command()
@click.argument("old_config_file", type=click.Path(exists=True))
@click.argument("new_config_file", type=click.Path())
@click.option("--backup/--no-backup", default=True, help="Create backup of old config")
def migrate(old_config_file: str, new_config_file: str, backup: bool):
    """Migrate old configuration format to new format."""
    try:
        # Load old configuration
        with open(old_config_file, "r") as f:
            old_config = yaml.safe_load(f)

        # Migrate to new format
        new_config = ConfigDevUtils.migrate_old_config(old_config)

        # Create backup if requested
        if backup:
            backup_file = f"{old_config_file}.backup"
            click.echo(f"Creating backup: {backup_file}")
            with open(backup_file, "w") as f:
                yaml.dump(old_config, f, default_flow_style=False)

        # Write new configuration
        with open(new_config_file, "w") as f:
            yaml.dump(new_config, f, default_flow_style=False, sort_keys=False)

        click.echo("✅ Migration completed successfully!")
        click.echo(f"   Old config: {old_config_file}")
        click.echo(f"   New config: {new_config_file}")

    except Exception as e:
        click.echo(f"❌ Migration failed: {e}")
        raise click.Abort() from e


@config_cli.command()
@click.option(
    "--environment",
    "-e",
    default="production",
    help="Environment to generate template for",
)
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def generate_template(environment: str, output: str):
    """Generate configuration template for specified environment."""
    try:
        template = ConfigDevUtils.generate_config_template(AppConfig, environment)

        if output:
            with open(output, "w") as f:
                f.write(template)
            click.echo(f"✅ Template generated: {output}")
        else:
            click.echo(template)

    except Exception as e:
        click.echo(f"❌ Template generation failed: {e}")
        raise click.Abort() from e


@config_cli.command()
@click.argument("config_file1", type=click.Path(exists=True))
@click.argument("config_file2", type=click.Path(exists=True))
@click.option(
    "--format", "output_format", type=click.Choice(["yaml", "json"]), default="yaml"
)
def diff(config_file1: str, config_file2: str, output_format: str):
    """Compare two configuration files and show differences."""
    try:
        with open(config_file1, "r") as f:
            config1 = yaml.safe_load(f)

        with open(config_file2, "r") as f:
            config2 = yaml.safe_load(f)

        diff_result = ConfigDevUtils.diff_configs(config1, config2, output_format)
        click.echo(diff_result)

    except Exception as e:
        click.echo(f"❌ Configuration diff failed: {e}")
        raise click.Abort() from e


@config_cli.command()
@click.argument("config_file", type=click.Path(exists=True))
@click.option("--output", "-o", type=click.Path(), help="Output file path")
def export_env(config_file: str, output: str):
    """Export configuration as environment variables."""
    try:
        manager = ConfigManager()
        config = manager.loader.load_config(AppConfig, config_file=config_file)

        env_vars = ConfigDevUtils.export_config_to_env(config)

        if output:
            with open(output, "w") as f:
                for key, value in env_vars.items():
                    f.write(f"{key}={value}\n")
            click.echo(f"✅ Environment variables exported to: {output}")
        else:
            for key, value in env_vars.items():
                click.echo(f"{key}={value}")

    except Exception as e:
        click.echo(f"❌ Export failed: {e}")
        raise click.Abort() from e


if __name__ == "__main__":
    config_cli()
