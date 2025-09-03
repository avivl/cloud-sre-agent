#!/usr/bin/env python3
"""
Example script demonstrating how to use the enhanced configuration management system.
"""

import os
import sys
from pathlib import Path

# Add the parent directory to the path so we can import the config module
sys.path.insert(0, str(Path(__file__).parent.parent))

from gemini_sre_agent.config import (
    AppConfig,
    ConfigError,
    ConfigManager,
    Environment,
    MLConfig,
)


def main():
    """Demonstrate configuration system usage."""
    print("🔧 Enhanced Configuration Management System Demo")
    print("=" * 50)

    # Example 1: Create a basic configuration
    print("\n1. Creating a basic configuration...")

    # Create required models for MLConfig
    from gemini_sre_agent.config.app_config import ServiceConfig
    from gemini_sre_agent.config.ml_config import ModelConfig, ModelType

    required_models = {
        ModelType.TRIAGE: ModelConfig(
            name="gemini-pro",
            type=ModelType.TRIAGE,
            max_tokens=1000,
            temperature=0.7,
            cost_per_1k_tokens=0.001,
        ),
        ModelType.ANALYSIS: ModelConfig(
            name="gemini-pro",
            type=ModelType.ANALYSIS,
            max_tokens=1000,
            temperature=0.7,
            cost_per_1k_tokens=0.001,
        ),
        ModelType.CLASSIFICATION: ModelConfig(
            name="gemini-pro",
            type=ModelType.CLASSIFICATION,
            max_tokens=1000,
            temperature=0.7,
            cost_per_1k_tokens=0.001,
        ),
    }

    config = AppConfig(
        environment=Environment.DEVELOPMENT,
        debug=True,
        log_level="DEBUG",
        app_name="demo-app",
        app_version="1.0.0",
        ml=MLConfig(models=required_models),
        services=[
            ServiceConfig(
                name="demo-service",
                project_id="demo-project",
                location="us-central1",
                subscription_id="demo-subscription",
            )
        ],
    )

    print(f"   Environment: {config.environment}")
    print(f"   Debug mode: {config.debug}")
    print(f"   Log level: {config.log_level}")
    print(f"   App name: {config.app_name}")
    print(f"   App version: {config.app_version}")
    print(f"   Schema version: {config.schema_version}")

    # Example 2: Load configuration from file
    print("\n2. Loading configuration from file...")
    config_file = Path(__file__).parent / "config_example.yaml"

    if config_file.exists():
        try:
            # Create a temporary config directory for the manager
            import shutil
            import tempfile

            config_dir = tempfile.mkdtemp()
            config_dir_path = Path(config_dir)
            config_dir_path.mkdir(exist_ok=True)

            # Copy the config file to the config directory
            shutil.copy2(config_file, config_dir_path / "config.yaml")

            manager = ConfigManager(str(config_dir))
            loaded_config = manager.reload_config()  # Force initial load

            print(f"   ✅ Successfully loaded config from {config_file}")
            print(f"   Environment: {loaded_config.environment}")
            print(f"   Debug mode: {loaded_config.debug}")
            print(f"   ML models configured: {len(loaded_config.ml.models)}")
            print(f"   Services configured: {len(loaded_config.services)}")

            # Example 3: Access nested configuration
            print("\n3. Accessing nested configuration...")
            if loaded_config.services:
                print(f"   First service: {loaded_config.services[0].name}")
                print(f"   Service project: {loaded_config.services[0].project_id}")
            if loaded_config.ml.models:
                triage_model = loaded_config.ml.models.get(ModelType.TRIAGE)
                if triage_model:
                    print(f"   Triage model: {triage_model.name}")
                    print(f"   Max tokens: {triage_model.max_tokens}")
                    print(f"   Temperature: {triage_model.temperature}")

            # Clean up
            shutil.rmtree(config_dir)

            # Example 4: Configuration validation
            print("\n4. Configuration validation...")
            checksum = loaded_config.calculate_checksum()
            loaded_config.validation_checksum = checksum
            is_valid = loaded_config.validate_checksum()
            print(f"   Configuration checksum: {checksum[:16]}...")
            print(f"   Configuration is valid: {is_valid}")

        except ConfigError as e:
            print(f"   ❌ Error loading config: {e}")
    else:
        print(f"   ⚠️  Config file not found: {config_file}")
        print("   Please create the example config file first.")

    # Example 5: Environment variable integration
    print("\n5. Environment variable integration...")
    print("   Setting environment variables...")

    # Set some environment variables
    os.environ["GEMINI_API_KEY"] = "AIzaSyTest123456789"
    os.environ["ML_PRIMARY_MODEL_NAME"] = "gemini-pro-vision"
    os.environ["ML_PRIMARY_MODEL_MAX_TOKENS"] = "2000"
    os.environ["ML_PRIMARY_MODEL_TEMPERATURE"] = "0.5"

    try:
        # Create a new manager to pick up environment variables
        env_manager = ConfigManager()

        # Create a minimal config file for testing
        minimal_config = {
            "environment": "development",
            "debug": True,
            "log_level": "DEBUG",
            "app_name": "env-test-app",
            "app_version": "1.0.0",
        }

        import tempfile

        import yaml

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(minimal_config, f)
            temp_config_file = f.name

        try:
            env_config = env_manager.reload_config()

            print("   ✅ Environment variables integrated successfully")
            print(f"   Environment: {env_config.environment}")
            print(f"   Debug mode: {env_config.debug}")
            print(f"   App name: {env_config.app_name}")

        finally:
            os.unlink(temp_config_file)

    except Exception as e:
        print(f"   ❌ Error with environment variables: {e}")

    # Example 6: Configuration hot reloading
    print("\n6. Configuration hot reloading...")
    print(
        "   This feature allows the configuration to be reloaded without restarting the application."
    )
    print(
        "   The ConfigManager monitors file changes and can automatically reload when needed."
    )

    print("\n✅ Configuration system demo completed!")
    print("\nNext steps:")
    print("   - Create your own configuration file based on the example")
    print("   - Set environment variables for sensitive data")
    print("   - Use ConfigManager in your application for hot reloading")
    print("   - Run the CLI tools for validation and migration")


if __name__ == "__main__":
    main()
