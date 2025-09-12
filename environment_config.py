#!/usr/bin/env python3
"""
Environment-Specific Configuration Management

This script provides environment-specific configuration management for the enhanced LLM system.
"""

import os
import json
import yaml
from typing import Dict, Any, Optional
from pathlib import Path
import logging

from gemini_sre_agent.llm.config import LLMConfig

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EnvironmentConfigManager:
    """Manages environment-specific configurations for the enhanced LLM system."""
    
    def __init__(self, config_dir: str = "config") -> None:
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(exist_ok=True)
        self.current_env = os.getenv('ENVIRONMENT', 'development')
        
    def get_environment_config(self, environment: str : Optional[str] = None) -> Dict[str, Any]:
        """Get configuration for a specific environment."""
        if environment is None:
            environment = self.current_env
            
        config_file = self.config_dir / f"{environment}.yaml"
        
        if not config_file.exists():
            logger.warning(f"Config file {config_file} not found, using defaults")
            return self._get_default_config(environment)
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Override with environment variables
        config = self._apply_env_overrides(config)
        
        return config
    
    def _get_default_config(self, environment: str) -> Dict[str, Any]:
        """Get default configuration for an environment."""
        defaults = {
            'development': {
                'llm': {
                    'providers': {
                        'gemini': {
                            'provider': 'gemini',
                            'api_key': os.getenv('GEMINI_API_KEY', 'dev-key'),
                            'timeout': 30,
                            'max_retries': 3,
                            'models': {
                                'gemini-1.5-flash': {
                                    'name': 'gemini-1.5-flash',
                                    'model_type': 'fast',
                                    'cost_per_1k_tokens': 0.000075,
                                    'max_tokens': 1000000,
                                    'capabilities': ['text', 'json']
                                }
                            }
                        }
                    },
                    'default_model_type': 'fast',
                    'optimization_goal': 'cost',
                    'max_cost': 10.0,
                    'min_performance': 0.7,
                    'min_quality': 0.8
                },
                'monitoring': {
                    'retention_hours': 24,
                    'alert_thresholds': {
                        'success_rate': 0.95,
                        'max_latency_ms': 5000,
                        'max_cost_per_hour': 5.0
                    }
                },
                'logging': {
                    'level': 'DEBUG',
                    'format': 'detailed'
                }
            },
            'staging': {
                'llm': {
                    'providers': {
                        'gemini': {
                            'provider': 'gemini',
                            'api_key': os.getenv('GEMINI_API_KEY'),
                            'timeout': 30,
                            'max_retries': 3,
                            'models': {
                                'gemini-1.5-flash': {
                                    'name': 'gemini-1.5-flash',
                                    'model_type': 'fast',
                                    'cost_per_1k_tokens': 0.000075,
                                    'max_tokens': 1000000,
                                    'capabilities': ['text', 'json']
                                },
                                'gemini-1.5-pro': {
                                    'name': 'gemini-1.5-pro',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.00125,
                                    'max_tokens': 1000000,
                                    'capabilities': ['text', 'json', 'vision']
                                }
                            }
                        },
                        'openai': {
                            'provider': 'openai',
                            'api_key': os.getenv('OPENAI_API_KEY', '***REMOVED***'),
                            'timeout': 30,
                            'max_retries': 3,
                            'models': {
                                'gpt-4o-mini': {
                                    'name': 'gpt-4o-mini',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.00015,
                                    'max_tokens': 128000,
                                    'capabilities': ['text', 'json']
                                }
                            }
                        }
                    },
                    'default_model_type': 'smart',
                    'optimization_goal': 'balanced',
                    'max_cost': 50.0,
                    'min_performance': 0.8,
                    'min_quality': 0.9
                },
                'monitoring': {
                    'retention_hours': 72,
                    'alert_thresholds': {
                        'success_rate': 0.98,
                        'max_latency_ms': 3000,
                        'max_cost_per_hour': 20.0
                    }
                },
                'logging': {
                    'level': 'INFO',
                    'format': 'structured'
                }
            },
            'production': {
                'llm': {
                    'providers': {
                        'gemini': {
                            'provider': 'gemini',
                            'api_key': os.getenv('GEMINI_API_KEY'),
                            'timeout': 30,
                            'max_retries': 5,
                            'rate_limit': 1000,
                            'models': {
                                'gemini-1.5-flash': {
                                    'name': 'gemini-1.5-flash',
                                    'model_type': 'fast',
                                    'cost_per_1k_tokens': 0.000075,
                                    'max_tokens': 1000000,
                                    'capabilities': ['text', 'json']
                                },
                                'gemini-1.5-pro': {
                                    'name': 'gemini-1.5-pro',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.00125,
                                    'max_tokens': 1000000,
                                    'capabilities': ['text', 'json', 'vision']
                                }
                            }
                        },
                        'openai': {
                            'provider': 'openai',
                            'api_key': os.getenv('OPENAI_API_KEY', '***REMOVED***'),
                            'timeout': 30,
                            'max_retries': 5,
                            'rate_limit': 500,
                            'models': {
                                'gpt-4o-mini': {
                                    'name': 'gpt-4o-mini',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.00015,
                                    'max_tokens': 128000,
                                    'capabilities': ['text', 'json']
                                },
                                'gpt-4o': {
                                    'name': 'gpt-4o',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.005,
                                    'max_tokens': 128000,
                                    'capabilities': ['text', 'json', 'vision']
                                }
                            }
                        },
                        'anthropic': {
                            'provider': 'anthropic',
                            'api_key': os.getenv('ANTHROPIC_API_KEY', 'production-key'),
                            'timeout': 30,
                            'max_retries': 5,
                            'rate_limit': 300,
                            'models': {
                                'claude-3-5-sonnet-20241022': {
                                    'name': 'claude-3-5-sonnet-20241022',
                                    'model_type': 'smart',
                                    'cost_per_1k_tokens': 0.003,
                                    'max_tokens': 200000,
                                    'capabilities': ['text', 'json']
                                }
                            }
                        }
                    },
                    'default_model_type': 'smart',
                    'optimization_goal': 'quality',
                    'max_cost': 200.0,
                    'min_performance': 0.9,
                    'min_quality': 0.95,
                    'business_hours_only': True
                },
                'monitoring': {
                    'retention_hours': 168,  # 1 week
                    'alert_thresholds': {
                        'success_rate': 0.99,
                        'max_latency_ms': 2000,
                        'max_cost_per_hour': 50.0
                    }
                },
                'logging': {
                    'level': 'WARNING',
                    'format': 'json'
                }
            }
        }
        
        return defaults.get(environment, defaults['development'])
    
    def _apply_env_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply environment variable overrides to configuration."""
        # Override API keys
        if 'llm' in config and 'providers' in config['llm']:
            for provider_name, provider_config in config['llm']['providers'].items():
                env_key = f"{provider_name.upper()}_API_KEY"
                if env_key in os.environ:
                    provider_config['api_key'] = os.environ[env_key]
        
        # Override other settings
        if 'GEMINI_PROJECT' in os.environ:
            config.setdefault('gemini', {})['project'] = os.environ['GEMINI_PROJECT']
        
        if 'GEMINI_LOCATION' in os.environ:
            config.setdefault('gemini', {})['location'] = os.environ['GEMINI_LOCATION']
        
        return config
    
    def create_environment_configs(self) -> None:
        """Create configuration files for all environments."""
        environments = ['development', 'staging', 'production']
        
        for env in environments:
            config = self._get_default_config(env)
            config_file = self.config_dir / f"{env}.yaml"
            
            with open(config_file, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, indent=2)
            
            logger.info(f"Created configuration file: {config_file}")
    
    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate configuration structure."""
        try:
            # Try to create LLMConfig from the configuration
            if 'llm' in config:
                LLMConfig(**config['llm'])
            return True
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False
    
    def get_llm_config(self, environment: str : Optional[str] = None) -> LLMConfig:
        """Get LLM configuration for a specific environment."""
        env_config = self.get_environment_config(environment)
        
        if 'llm' not in env_config:
            raise ValueError(f"No LLM configuration found for environment: {environment}")
        
        return LLMConfig(**env_config['llm'])
    
    def print_environment_summary(self, environment: str : Optional[str] = None) -> None:
        """Print a summary of environment configuration."""
        if environment is None:
            environment = self.current_env
        
        config = self.get_environment_config(environment)
        
        print(f"🔧 Environment Configuration: {environment.upper()}")
        print("=" * 60)
        
        # LLM Configuration
        if 'llm' in config:
            llm_config = config['llm']
            print(f"🤖 LLM Configuration:")
            print(f"   Default Model Type: {llm_config.get('default_model_type', 'N/A')}")
            print(f"   Optimization Goal: {llm_config.get('optimization_goal', 'N/A')}")
            print(f"   Max Cost: ${llm_config.get('max_cost', 'N/A')}")
            print(f"   Min Performance: {llm_config.get('min_performance', 'N/A')}")
            print(f"   Min Quality: {llm_config.get('min_quality', 'N/A')}")
            
            providers = llm_config.get('providers', {})
            print(f"   Providers: {len(providers)}")
            for provider_name, provider_config in providers.items():
                models = provider_config.get('models', {})
                print(f"     - {provider_name}: {len(models)} models")
        
        # Monitoring Configuration
        if 'monitoring' in config:
            monitoring_config = config['monitoring']
            print(f"📊 Monitoring Configuration:")
            print(f"   Retention Hours: {monitoring_config.get('retention_hours', 'N/A')}")
            thresholds = monitoring_config.get('alert_thresholds', {})
            print(f"   Alert Thresholds:")
            for key, value in thresholds.items():
                print(f"     - {key}: {value}")
        
        # Logging Configuration
        if 'logging' in config:
            logging_config = config['logging']
            print(f"📝 Logging Configuration:")
            print(f"   Level: {logging_config.get('level', 'N/A')}")
            print(f"   Format: {logging_config.get('format', 'N/A')}")
        
        print("=" * 60)

def main() -> None:
    """Main function to demonstrate environment configuration management."""
    print("🚀 Environment Configuration Management Demo")
    print("=" * 60)
    
    # Create config manager
    config_manager = EnvironmentConfigManager()
    
    # Create configuration files for all environments
    print("📁 Creating environment configuration files...")
    config_manager.create_environment_configs()
    print("✅ Configuration files created")
    print()
    
    # Show configuration for each environment
    environments = ['development', 'staging', 'production']
    
    for env in environments:
        config_manager.print_environment_summary(env)
        print()
    
    # Validate configurations
    print("🔍 Validating configurations...")
    for env in environments:
        config = config_manager.get_environment_config(env)
        is_valid = config_manager.validate_config(config)
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"   {env}: {status}")
    
    print()
    print("🎯 Environment Configuration Management Complete!")
    print("   - Configuration files created for all environments")
    print("   - Environment-specific settings configured")
    print("   - API key overrides supported via environment variables")
    print("   - Validation system in place")

if __name__ == "__main__":
    main()
