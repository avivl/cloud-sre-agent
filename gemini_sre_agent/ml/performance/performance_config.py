# gemini_sre_agent/ml/performance/performance_config.py

"""
Performance configuration for the enhanced code generation system.

This module provides configuration options for caching, analysis depth,
parallel processing, and other performance-related settings.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class CacheConfig:
    """Configuration for the caching system."""
    
    max_size_mb: int = 100
    default_ttl_seconds: int = 3600  # 1 hour
    cleanup_interval_seconds: int = 300  # 5 minutes
    max_entries: int = 1000
    
    # Repository context specific settings
    repo_context_ttl_seconds: int = 7200  # 2 hours
    issue_pattern_ttl_seconds: int = 86400  # 24 hours
    
    # Cache invalidation settings
    enable_auto_invalidation: bool = True
    invalidation_threshold: float = 0.8  # Invalidate when 80% full


@dataclass
class AnalysisConfig:
    """Configuration for repository analysis performance."""
    
    # Analysis depth configurations
    basic_analysis: Dict[str, Any]
    standard_analysis: Dict[str, Any]
    comprehensive_analysis: Dict[str, Any]
    
    # Parallel processing settings
    max_parallel_workers: int = 8
    enable_async_io: bool = True
    enable_parallel_analysis: bool = True
    
    # File processing limits
    max_files_per_analysis: int = 2000
    max_file_size_mb: int = 10
    skip_binary_files: bool = True
    
    def __post_init__(self):
        """Set default analysis configurations if not provided."""
        if self.basic_analysis is None:
            self.basic_analysis = {
                "max_files": 100,
                "max_depth": 2,
                "include_hidden": False,
                "parallel_workers": 2,
                "analysis_timeout": 30
            }
        
        if self.standard_analysis is None:
            self.standard_analysis = {
                "max_files": 500,
                "max_depth": 3,
                "include_hidden": False,
                "parallel_workers": 4,
                "analysis_timeout": 60
            }
        
        if self.comprehensive_analysis is None:
            self.comprehensive_analysis = {
                "max_files": 2000,
                "max_depth": 5,
                "include_hidden": True,
                "parallel_workers": 8,
                "analysis_timeout": 120
            }


@dataclass
class ModelPerformanceConfig:
    """Configuration for AI model performance optimization."""
    
    # Model selection for different tasks
    fast_model: str = "gemini-1.5-flash-001"  # Fast, less accurate
    accurate_model: str = "gemini-1.5-pro-001"  # Slower, more accurate
    
    # Prompt optimization settings
    enable_prompt_caching: bool = True
    prompt_cache_ttl_seconds: int = 1800  # 30 minutes
    max_prompt_length: int = 8000
    
    # Response optimization
    enable_response_caching: bool = True
    response_cache_ttl_seconds: int = 3600  # 1 hour
    max_response_length: int = 16000
    
    # Fallback settings
    enable_fallback_models: bool = True
    fallback_timeout_seconds: int = 30
    max_fallback_attempts: int = 2


@dataclass
class PerformanceConfig:
    """Main performance configuration class."""
    
    cache: CacheConfig
    analysis: AnalysisConfig
    model: ModelPerformanceConfig
    
    # Global performance settings
    enable_performance_monitoring: bool = True
    performance_log_level: str = "INFO"
    enable_metrics_collection: bool = True
    
    # Resource limits
    max_memory_usage_mb: int = 512
    max_cpu_usage_percent: int = 80
    enable_resource_monitoring: bool = True
    
    def __post_init__(self):
        """Set default configurations if not provided."""
        # This method is no longer needed since all fields are required
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "cache": self.cache.__dict__,
            "analysis": self.analysis.__dict__,
            "model": self.model.__dict__,
            "enable_performance_monitoring": self.enable_performance_monitoring,
            "performance_log_level": self.performance_log_level,
            "enable_metrics_collection": self.enable_metrics_collection,
            "max_memory_usage_mb": self.max_memory_usage_mb,
            "max_cpu_usage_percent": self.max_cpu_usage_percent,
            "enable_resource_monitoring": self.enable_resource_monitoring,
        }
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "PerformanceConfig":
        """Create configuration from dictionary."""
        cache_config = CacheConfig(**config_dict.get("cache", {}))
        analysis_config = AnalysisConfig(**config_dict.get("analysis", {}))
        model_config = ModelPerformanceConfig(**config_dict.get("model", {}))
        
        return cls(
            cache=cache_config,
            analysis=analysis_config,
            model=model_config,
            enable_performance_monitoring=config_dict.get("enable_performance_monitoring", True),
            performance_log_level=config_dict.get("performance_log_level", "INFO"),
            enable_metrics_collection=config_dict.get("enable_metrics_collection", True),
            max_memory_usage_mb=config_dict.get("max_memory_usage_mb", 512),
            max_cpu_usage_percent=config_dict.get("max_cpu_usage_percent", 80),
            enable_resource_monitoring=config_dict.get("enable_resource_monitoring", True),
        )
    
    def get_analysis_config(self, depth: str) -> Dict[str, Any]:
        """Get analysis configuration for a specific depth."""
        depth_mapping = {
            "basic": self.analysis.basic_analysis,
            "standard": self.analysis.standard_analysis,
            "comprehensive": self.analysis.comprehensive_analysis
        }
        
        return depth_mapping.get(depth, self.analysis.standard_analysis)
    
    def is_performance_critical(self) -> bool:
        """Check if performance is critical (low resource availability)."""
        # This could be enhanced with actual system monitoring
        return False  # Placeholder for now
