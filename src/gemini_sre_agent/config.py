import yaml
from pydantic import BaseModel, Field, field_validator # Updated to field_validator
from typing import Dict, List, Optional

class ModelSelection(BaseModel):
    """
    Configuration model for selecting Gemini models for different tasks.
    """
    triage_model: str
    analysis_model: str
    classification_model: str

class GitHubConfig(BaseModel):
    """
    Configuration model for GitHub repository details.
    """
    repository: str
    base_branch: str

class LoggingConfig(BaseModel):
    """
    Configuration model for logging settings.
    """
    log_level: str = "INFO"
    json_format: bool = False
    log_file: Optional[str] = None

class ServiceMonitorConfig(BaseModel): # Renamed from GeminiCloudLogMonitorConfig
    """
    Configuration model for a single service to be monitored.
    """
    service_name: str = Field(min_length=1, max_length=50) # Added validation
    project_id: str = Field(pattern=r'^[a-z][a-z0-9-]*[a-z0-9]$') # Added validation
    location: str = Field(pattern=r'^[a-z0-9-]+$') # Added validation
    subscription_id: str = Field(min_length=1) # Added validation
    model_selection: Optional[ModelSelection] = None
    github: Optional[GitHubConfig] = None

    @field_validator('project_id') # Updated to field_validator
    @classmethod
    def validate_project_id(cls, v):
        if len(v) < 6 or len(v) > 30:
            raise ValueError('Project ID must be 6-30 characters')
        return v

class GlobalConfig(BaseModel):
    """
    Global configuration settings for the Gemini Cloud Log Monitor application.
    """
    default_model_selection: ModelSelection
    default_github_config: GitHubConfig
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    services: List[ServiceMonitorConfig]

class Config(BaseModel):
    """
    Root configuration model.
    """
    gemini_cloud_log_monitor: GlobalConfig

def load_config(path: str = "config/config.yaml") -> Config:
    """
    Loads the application configuration from a YAML file.

    Args:
        path (str): The path to the configuration YAML file.

    Returns:
        Config: The loaded configuration object.
    """
    with open(path, "r") as f:
        config_data = yaml.safe_load(f)
    return Config(**config_data)

# Example usage:
# config = load_config()
# print(config.gemini_cloud_log_monitor.services[0].service_name)