#!/usr/bin/env python3
"""
Configuration validation script for the log ingestion system.

This script validates ingestion configuration files and provides
detailed feedback on any issues found.
"""

import sys
from pathlib import Path
from typing import List

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_sre_agent.config.ingestion_config import (
    ConfigError,
    IngestionConfigManager,
)


def validate_config_file(config_path: Path) -> List[str]:
    """Validate a single configuration file."""
    errors = []

    try:
        # Load configuration
        config_manager = IngestionConfigManager()
        config = config_manager.load_config(config_path)

        # Validate configuration
        validation_errors = config_manager.validate_config()
        errors.extend(validation_errors)

        if not errors:
            print(f"✅ {config_path.name}: Valid configuration")
            print(f"   - Schema version: {config.schema_version}")
            print(f"   - Sources: {len(config.sources)}")
            print(f"   - Enabled sources: {len(config.get_enabled_sources())}")
            print(f"   - Buffer strategy: {config.global_config.buffer_strategy}")
            print(
                f"   - Max throughput: {config.global_config.max_throughput} logs/sec"
            )
        else:
            print(f"❌ {config_path.name}: Configuration errors found")
            for error in errors:
                print(f"   - {error}")

    except ConfigError as e:
        print(f"❌ {config_path.name}: Configuration error - {e}")
        errors.append(str(e))
    except Exception as e:
        print(f"❌ {config_path.name}: Unexpected error - {e}")
        errors.append(f"Unexpected error: {e}")

    return errors


def main():
    """Main validation function."""
    print("🔍 Log Ingestion Configuration Validator")
    print("=" * 50)

    # Get the examples directory
    examples_dir = Path(__file__).parent / "ingestion_configs"

    if not examples_dir.exists():
        print(f"❌ Examples directory not found: {examples_dir}")
        return 1

    # Find all configuration files
    config_files = []
    for pattern in ["*.json", "*.yaml", "*.yml"]:
        config_files.extend(examples_dir.glob(pattern))

    if not config_files:
        print(f"❌ No configuration files found in {examples_dir}")
        return 1

    print(f"Found {len(config_files)} configuration files:")
    for config_file in config_files:
        print(f"  - {config_file.name}")
    print()

    # Validate each configuration file
    all_errors = []
    valid_count = 0

    for config_file in sorted(config_files):
        errors = validate_config_file(config_file)
        if not errors:
            valid_count += 1
        all_errors.extend(errors)
        print()

    # Summary
    print("=" * 50)
    print("Validation Summary:")
    print(f"  - Total files: {len(config_files)}")
    print(f"  - Valid files: {valid_count}")
    print(f"  - Invalid files: {len(config_files) - valid_count}")
    print(f"  - Total errors: {len(all_errors)}")

    if all_errors:
        print("\nAll Errors:")
        for i, error in enumerate(all_errors, 1):
            print(f"  {i}. {error}")
        return 1
    else:
        print("\n✅ All configuration files are valid!")
        return 0


if __name__ == "__main__":
    sys.exit(main())
