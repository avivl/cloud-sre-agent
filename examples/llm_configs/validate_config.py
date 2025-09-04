#!/usr/bin/env python3
"""
LLM Configuration Validation Tool

This script validates LLM configuration files and tests provider connections.
It can be used to verify configurations before deployment.

Usage:
    python validate_config.py <config_file>
    python validate_config.py <config_file> --test-providers
    python validate_config.py <config_file> --verbose
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from gemini_sre_agent.llm.config import LLMConfig
from gemini_sre_agent.llm.providers import ProviderHandlerFactory


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )


def load_config_file(config_path: Path) -> Dict[str, Any]:
    """Load configuration from YAML or JSON file."""
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        if config_path.suffix.lower() in [".yaml", ".yml"]:
            return yaml.safe_load(f)
        elif config_path.suffix.lower() == ".json":
            return json.load(f)
        else:
            raise ValueError(f"Unsupported file format: {config_path.suffix}")


def validate_config_structure(config_data: Dict[str, Any]) -> List[str]:
    """Validate the basic structure of the configuration."""
    errors = []

    # Check required top-level fields
    required_fields = ["default_provider", "providers", "agents"]
    for field in required_fields:
        if field not in config_data:
            errors.append(f"Missing required field: {field}")

    # Validate providers
    if "providers" in config_data:
        providers = config_data["providers"]
        if not isinstance(providers, dict):
            errors.append("'providers' must be a dictionary")
        else:
            for provider_name, provider_config in providers.items():
                if not isinstance(provider_config, dict):
                    errors.append(
                        f"Provider '{provider_name}' configuration must be a dictionary"
                    )
                    continue

                # Check required provider fields
                required_provider_fields = ["provider", "models"]
                for field in required_provider_fields:
                    if field not in provider_config:
                        errors.append(
                            f"Provider '{provider_name}' missing required field: {field}"
                        )

                # Validate models
                if "models" in provider_config:
                    models = provider_config["models"]
                    if not isinstance(models, dict):
                        errors.append(
                            f"Provider '{provider_name}' models must be a dictionary"
                        )
                    else:
                        for model_name, model_config in models.items():
                            if not isinstance(model_config, dict):
                                errors.append(
                                    f"Model '{model_name}' in provider '{provider_name}' must be a dictionary"
                                )
                                continue

                            # Check required model fields
                            required_model_fields = [
                                "name",
                                "model_type",
                                "cost_per_1k_tokens",
                            ]
                            for field in required_model_fields:
                                if field not in model_config:
                                    errors.append(
                                        f"Model '{model_name}' in provider '{provider_name}' missing required field: {field}"
                                    )

    # Validate agents
    if "agents" in config_data:
        agents = config_data["agents"]
        if not isinstance(agents, dict):
            errors.append("'agents' must be a dictionary")
        else:
            for agent_name, agent_config in agents.items():
                if not isinstance(agent_config, dict):
                    errors.append(
                        f"Agent '{agent_name}' configuration must be a dictionary"
                    )
                    continue

                # Check required agent fields
                required_agent_fields = ["primary_provider", "fallback_providers"]
                for field in required_agent_fields:
                    if field not in agent_config:
                        errors.append(
                            f"Agent '{agent_name}' missing required field: {field}"
                        )

    return errors


def validate_with_pydantic(config_data: Dict[str, Any]) -> List[str]:
    """Validate configuration using Pydantic models."""
    errors = []

    try:
        # Create LLMConfig instance
        config = LLMConfig(**config_data)

        # Additional validation
        if config.default_provider not in config.providers:
            errors.append(
                f"Default provider '{config.default_provider}' not found in providers"
            )

        # Validate agent provider references
        for agent_name, agent_config in config.agents.items():
            if agent_config.primary_provider not in config.providers:
                errors.append(
                    f"Agent '{agent_name}' primary provider '{agent_config.primary_provider}' not found in providers"
                )

            # Check if fallback_providers attribute exists and is not None
            fallback_providers = getattr(agent_config, "fallback_providers", None)
            if fallback_providers:
                for fallback_provider in fallback_providers:
                    if fallback_provider not in config.providers:
                        errors.append(
                            f"Agent '{agent_name}' fallback provider '{fallback_provider}' not found in providers"
                        )

    except Exception as e:
        errors.append(f"Pydantic validation error: {str(e)}")

    return errors


def test_provider_connections(config: LLMConfig) -> Dict[str, Any]:
    """Test connections to all configured providers."""
    results = {}

    for provider_name, provider_config in config.providers.items():
        try:
            # Create provider handler
            handler = ProviderHandlerFactory.create_handler(provider_config)

            # Test connection
            is_valid, message = handler.validate_credentials()

            results[provider_name] = {
                "status": "success" if is_valid else "failed",
                "message": message,
                "capabilities": (
                    handler.get_capabilities().__dict__ if is_valid else None
                ),
            }

        except Exception as e:
            results[provider_name] = {
                "status": "error",
                "message": f"Connection test failed: {str(e)}",
                "capabilities": None,
            }

    return results


def print_validation_results(
    errors: List[str], warnings: Optional[List[str]] = None
) -> None:
    """Print validation results in a formatted way."""
    if warnings is None:
        warnings = []

    if not errors and not warnings:
        print("✅ Configuration validation passed!")
        return

    if errors:
        print("❌ Configuration validation failed:")
        for error in errors:
            print(f"  • {error}")

    if warnings:
        print("⚠️  Configuration warnings:")
        for warning in warnings:
            print(f"  • {warning}")


def print_provider_test_results(results: Dict[str, Any]) -> None:
    """Print provider connection test results."""
    print("\n🔌 Provider Connection Tests:")

    for provider_name, result in results.items():
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"  {status_icon} {provider_name}: {result['message']}")

        if result["capabilities"]:
            capabilities = result["capabilities"]
            print(f"    • Models: {len(capabilities.get('models', []))}")
            print(f"    • Max tokens: {capabilities.get('max_tokens', 'Unknown')}")
            print(
                f"    • Supports streaming: {capabilities.get('supports_streaming', False)}"
            )
            print(f"    • Supports tools: {capabilities.get('supports_tools', False)}")


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Validate LLM configuration files")
    parser.add_argument("config_file", type=Path, help="Path to configuration file")
    parser.add_argument(
        "--test-providers", action="store_true", help="Test provider connections"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable verbose output"
    )
    parser.add_argument("--output", "-o", type=Path, help="Output results to file")

    args = parser.parse_args()

    # Set up logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    try:
        # Load configuration file
        logger.info(f"Loading configuration from {args.config_file}")
        config_data = load_config_file(args.config_file)

        # Validate structure
        logger.info("Validating configuration structure...")
        structure_errors = validate_config_structure(config_data)

        # Validate with Pydantic
        logger.info("Validating with Pydantic models...")
        pydantic_errors = validate_with_pydantic(config_data)

        # Combine errors
        all_errors = structure_errors + pydantic_errors

        # Print validation results
        print_validation_results(all_errors)

        # Test provider connections if requested
        if args.test_providers and not all_errors:
            logger.info("Testing provider connections...")
            config = LLMConfig(**config_data)
            provider_results = test_provider_connections(config)
            print_provider_test_results(provider_results)

        # Output to file if requested
        if args.output:
            provider_tests = None
            if args.test_providers and not all_errors:
                config = LLMConfig(**config_data)
                provider_tests = test_provider_connections(config)

            output_data = {
                "config_file": str(args.config_file),
                "validation_errors": all_errors,
                "provider_tests": provider_tests,
            }

            with open(args.output, "w") as f:
                json.dump(output_data, f, indent=2)

            print(f"\n📄 Results saved to {args.output}")

        # Exit with appropriate code
        sys.exit(1 if all_errors else 0)

    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        print(f"❌ Validation failed: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
