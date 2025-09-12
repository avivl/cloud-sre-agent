"""Performance optimization recommendations engine."""

import asyncio
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union, Callable
from collections import defaultdict

from ..logging import get_logger

logger = get_logger(__name__)


class OptimizationCategory(Enum):
    """Categories of optimization recommendations."""
    
    MEMORY = "memory"
    CPU = "cpu"
    NETWORK = "network"
    DATABASE = "database"
    CACHING = "caching"
    ALGORITHM = "algorithm"
    CONFIGURATION = "configuration"
    ARCHITECTURE = "architecture"


class OptimizationPriority(Enum):
    """Priority levels for optimization recommendations."""
    
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class OptimizationRecommendation:
    """Performance optimization recommendation.
    
    Attributes:
        id: Unique recommendation identifier
        title: Recommendation title
        description: Detailed description of the recommendation
        category: Optimization category
        priority: Recommendation priority
        impact_score: Estimated impact score (0-100)
        effort_score: Estimated effort score (0-100)
        confidence: Confidence level (0-100)
        metrics_affected: List of metrics that would be improved
        implementation_steps: Step-by-step implementation guide
        expected_improvement: Expected performance improvement
        prerequisites: Prerequisites for implementation
        risks: Potential risks or side effects
        created_at: When the recommendation was created
        tags: Additional metadata tags
    """
    
    id: str
    title: str
    description: str
    category: OptimizationCategory
    priority: OptimizationPriority
    impact_score: int = 0
    effort_score: int = 0
    confidence: int = 0
    metrics_affected: List[str] = field(default_factory=list)
    implementation_steps: List[str] = field(default_factory=list)
    expected_improvement: Dict[str, Any] = field(default_factory=dict)
    prerequisites: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class OptimizationConfig:
    """Configuration for performance optimization.
    
    Attributes:
        enable_auto_analysis: Whether to enable automatic analysis
        analysis_interval: Analysis interval in seconds
        min_confidence_threshold: Minimum confidence threshold for recommendations
        max_recommendations: Maximum number of recommendations to generate
        enable_impact_scoring: Whether to enable impact scoring
        enable_effort_scoring: Whether to enable effort scoring
        enable_risk_assessment: Whether to enable risk assessment
    """
    
    enable_auto_analysis: bool = True
    analysis_interval: float = 300.0  # 5 minutes
    min_confidence_threshold: int = 70
    max_recommendations: int = 50
    enable_impact_scoring: bool = True
    enable_effort_scoring: bool = True
    enable_risk_assessment: bool = True


class PerformanceAnalyzer:
    """Performance analyzer for identifying optimization opportunities.
    
    Analyzes performance metrics to identify bottlenecks,
    inefficiencies, and optimization opportunities.
    """
    
    def __init__(self):
        """Initialize the performance analyzer."""
        self._patterns = {
            "memory_leak": self._detect_memory_leak,
            "cpu_spike": self._detect_cpu_spike,
            "slow_operation": self._detect_slow_operation,
            "high_error_rate": self._detect_high_error_rate,
            "resource_contention": self._detect_resource_contention,
            "inefficient_algorithm": self._detect_inefficient_algorithm,
            "configuration_issue": self._detect_configuration_issue
        }
    
    def analyze_metrics(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """Analyze performance metrics for issues.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            List of detected issue patterns
        """
        detected_patterns = []
        
        for pattern_name, detector in self._patterns.items():
            if detector(metrics, historical_data):
                detected_patterns.append(pattern_name)
        
        return detected_patterns
    
    def _detect_memory_leak(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect memory leak patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if memory leak is detected
        """
        if not historical_data or len(historical_data) < 10:
            return False
        
        memory_values = [
            data.get("memory_usage", 0) for data in historical_data[-10:]
        ]
        
        # Check for consistent upward trend
        if len(memory_values) >= 5:
            trend = self._calculate_trend(memory_values)
            return trend > 0.1  # 10% increase per sample
        
        return False
    
    def _detect_cpu_spike(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect CPU spike patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if CPU spike is detected
        """
        current_cpu = metrics.get("cpu_usage", 0)
        return current_cpu > 80.0  # 80% CPU usage threshold
    
    def _detect_slow_operation(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect slow operation patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if slow operation is detected
        """
        avg_response_time = metrics.get("avg_response_time", 0)
        return avg_response_time > 1000.0  # 1 second threshold
    
    def _detect_high_error_rate(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect high error rate patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if high error rate is detected
        """
        error_rate = metrics.get("error_rate", 0)
        return error_rate > 5.0  # 5% error rate threshold
    
    def _detect_resource_contention(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect resource contention patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if resource contention is detected
        """
        cpu_usage = metrics.get("cpu_usage", 0)
        memory_usage = metrics.get("memory_usage", 0)
        
        # High CPU and memory usage indicates resource contention
        return cpu_usage > 70.0 and memory_usage > 1000000000  # 1GB
    
    def _detect_inefficient_algorithm(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect inefficient algorithm patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if inefficient algorithm is detected
        """
        if not historical_data or len(historical_data) < 5:
            return False
        
        response_times = [
            data.get("avg_response_time", 0) for data in historical_data[-5:]
        ]
        
        # Check for exponential growth in response time
        if len(response_times) >= 3:
            growth_rate = self._calculate_growth_rate(response_times)
            return growth_rate > 0.5  # 50% growth per sample
        
        return False
    
    def _detect_configuration_issue(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """Detect configuration issue patterns.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            True if configuration issue is detected
        """
        # Check for unusually low throughput
        throughput = metrics.get("throughput", 0)
        return throughput < 1.0  # Less than 1 request per second
    
    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate trend of a series of values.
        
        Args:
            values: Series of values
            
        Returns:
            Trend value (positive = increasing, negative = decreasing)
        """
        if len(values) < 2:
            return 0.0
        
        # Simple linear regression slope
        n = len(values)
        x_sum = sum(range(n))
        y_sum = sum(values)
        xy_sum = sum(i * values[i] for i in range(n))
        x2_sum = sum(i * i for i in range(n))
        
        slope = (n * xy_sum - x_sum * y_sum) / (n * x2_sum - x_sum * x_sum)
        return slope
    
    def _calculate_growth_rate(self, values: List[float]) -> float:
        """Calculate growth rate of a series of values.
        
        Args:
            values: Series of values
            
        Returns:
            Growth rate as percentage
        """
        if len(values) < 2:
            return 0.0
        
        first_value = values[0]
        last_value = values[-1]
        
        if first_value == 0:
            return 0.0
        
        return (last_value - first_value) / first_value


class OptimizationEngine:
    """Performance optimization recommendations engine.
    
    Analyzes performance patterns and generates intelligent
    recommendations for system optimization.
    """
    
    def __init__(self, config: Optional[OptimizationConfig] = None):
        """Initialize the optimization engine.
        
        Args:
            config: Optimization configuration
        """
        self._config = config or OptimizationConfig()
        self._analyzer = PerformanceAnalyzer()
        self._recommendations: Dict[str, OptimizationRecommendation] = {}
        self._analysis_task: Optional[asyncio.Task] = None
        self._start_analysis_task()
    
    def _start_analysis_task(self) -> None:
        """Start the background analysis task."""
        if self._config.enable_auto_analysis and self._analysis_task is None:
            self._analysis_task = asyncio.create_task(self._continuous_analysis())
    
    async def _continuous_analysis(self) -> None:
        """Continuous performance analysis."""
        while True:
            try:
                # This would typically get metrics from a metrics collector
                # For now, we'll just sleep and wait for manual analysis
                await asyncio.sleep(self._config.analysis_interval)
                
            except Exception as e:
                logger.error(f"Error in continuous analysis: {e}")
                await asyncio.sleep(60)
    
    def analyze_performance(
        self,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> List[OptimizationRecommendation]:
        """Analyze performance and generate recommendations.
        
        Args:
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            List of optimization recommendations
        """
        # Analyze metrics for issues
        detected_patterns = self._analyzer.analyze_metrics(metrics, historical_data)
        
        # Generate recommendations based on detected patterns
        recommendations = []
        for pattern in detected_patterns:
            pattern_recommendations = self._generate_recommendations_for_pattern(
                pattern, metrics, historical_data
            )
            recommendations.extend(pattern_recommendations)
        
        # Filter by confidence threshold
        recommendations = [
            rec for rec in recommendations
            if rec.confidence >= self._config.min_confidence_threshold
        ]
        
        # Limit number of recommendations
        recommendations = recommendations[:self._config.max_recommendations]
        
        # Store recommendations
        for recommendation in recommendations:
            self._recommendations[recommendation.id] = recommendation
        
        return recommendations
    
    def _generate_recommendations_for_pattern(
        self,
        pattern: str,
        metrics: Dict[str, Any],
        historical_data: Optional[List[Dict[str, Any]]] = None
    ) -> List[OptimizationRecommendation]:
        """Generate recommendations for a specific pattern.
        
        Args:
            pattern: Detected pattern name
            metrics: Current performance metrics
            historical_data: Historical performance data
            
        Returns:
            List of recommendations for the pattern
        """
        recommendations = []
        
        if pattern == "memory_leak":
            recommendations.append(self._create_memory_leak_recommendation(metrics))
        elif pattern == "cpu_spike":
            recommendations.append(self._create_cpu_spike_recommendation(metrics))
        elif pattern == "slow_operation":
            recommendations.append(self._create_slow_operation_recommendation(metrics))
        elif pattern == "high_error_rate":
            recommendations.append(self._create_high_error_rate_recommendation(metrics))
        elif pattern == "resource_contention":
            recommendations.append(self._create_resource_contention_recommendation(metrics))
        elif pattern == "inefficient_algorithm":
            recommendations.append(self._create_inefficient_algorithm_recommendation(metrics))
        elif pattern == "configuration_issue":
            recommendations.append(self._create_configuration_issue_recommendation(metrics))
        
        return recommendations
    
    def _create_memory_leak_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create memory leak optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Memory leak optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"memory_leak_{int(time.time())}",
            title="Fix Memory Leak",
            description="Detected potential memory leak based on increasing memory usage over time",
            category=OptimizationCategory.MEMORY,
            priority=OptimizationPriority.HIGH,
            impact_score=85,
            effort_score=60,
            confidence=80,
            metrics_affected=["memory_usage", "memory_delta"],
            implementation_steps=[
                "Review code for unclosed resources (files, connections, etc.)",
                "Implement proper resource cleanup in finally blocks",
                "Use context managers for resource management",
                "Add memory monitoring and alerting",
                "Consider implementing garbage collection tuning"
            ],
            expected_improvement={
                "memory_usage": "Reduce by 20-50%",
                "stability": "Improve system stability"
            },
            prerequisites=["Code review access", "Memory profiling tools"],
            risks=["Potential performance impact during cleanup", "Code changes required"]
        )
    
    def _create_cpu_spike_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create CPU spike optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            CPU spike optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"cpu_spike_{int(time.time())}",
            title="Optimize CPU Usage",
            description="High CPU usage detected, investigate and optimize CPU-intensive operations",
            category=OptimizationCategory.CPU,
            priority=OptimizationPriority.HIGH,
            impact_score=75,
            effort_score=70,
            confidence=85,
            metrics_affected=["cpu_usage", "response_time"],
            implementation_steps=[
                "Profile CPU usage to identify bottlenecks",
                "Optimize algorithms and data structures",
                "Implement caching for expensive operations",
                "Consider async/await for I/O operations",
                "Scale horizontally if needed"
            ],
            expected_improvement={
                "cpu_usage": "Reduce by 30-60%",
                "response_time": "Improve by 20-40%"
            },
            prerequisites=["CPU profiling tools", "Performance testing"],
            risks=["Code refactoring required", "Potential functionality changes"]
        )
    
    def _create_slow_operation_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create slow operation optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Slow operation optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"slow_operation_{int(time.time())}",
            title="Optimize Slow Operations",
            description="Operations are taking longer than expected, investigate and optimize",
            category=OptimizationCategory.ALGORITHM,
            priority=OptimizationPriority.MEDIUM,
            impact_score=80,
            effort_score=50,
            confidence=75,
            metrics_affected=["avg_response_time", "p95_response_time", "p99_response_time"],
            implementation_steps=[
                "Identify slowest operations using profiling",
                "Optimize database queries and add indexes",
                "Implement connection pooling",
                "Add caching for frequently accessed data",
                "Consider async operations for I/O"
            ],
            expected_improvement={
                "avg_response_time": "Reduce by 40-70%",
                "p95_response_time": "Reduce by 30-60%"
            },
            prerequisites=["Profiling tools", "Database access"],
            risks=["Database schema changes", "Caching complexity"]
        )
    
    def _create_high_error_rate_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create high error rate optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            High error rate optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"high_error_rate_{int(time.time())}",
            title="Reduce Error Rate",
            description="High error rate detected, investigate and fix error sources",
            category=OptimizationCategory.CONFIGURATION,
            priority=OptimizationPriority.CRITICAL,
            impact_score=90,
            effort_score=40,
            confidence=95,
            metrics_affected=["error_rate", "successful_requests"],
            implementation_steps=[
                "Review error logs to identify root causes",
                "Implement proper error handling and validation",
                "Add retry mechanisms with exponential backoff",
                "Improve input validation and sanitization",
                "Add circuit breakers for external dependencies"
            ],
            expected_improvement={
                "error_rate": "Reduce by 80-95%",
                "successful_requests": "Increase by 20-50%"
            },
            prerequisites=["Error logging", "Monitoring tools"],
            risks=["Potential service disruption during fixes"]
        )
    
    def _create_resource_contention_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create resource contention optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Resource contention optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"resource_contention_{int(time.time())}",
            title="Resolve Resource Contention",
            description="High CPU and memory usage detected, optimize resource utilization",
            category=OptimizationCategory.ARCHITECTURE,
            priority=OptimizationPriority.HIGH,
            impact_score=85,
            effort_score=80,
            confidence=80,
            metrics_affected=["cpu_usage", "memory_usage", "throughput"],
            implementation_steps=[
                "Implement horizontal scaling",
                "Optimize resource allocation",
                "Add load balancing",
                "Implement resource pooling",
                "Consider microservices architecture"
            ],
            expected_improvement={
                "cpu_usage": "Reduce by 40-60%",
                "memory_usage": "Reduce by 30-50%",
                "throughput": "Increase by 50-100%"
            },
            prerequisites=["Infrastructure changes", "Load balancer"],
            risks=["Architecture changes", "Deployment complexity"]
        )
    
    def _create_inefficient_algorithm_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create inefficient algorithm optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Inefficient algorithm optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"inefficient_algorithm_{int(time.time())}",
            title="Optimize Algorithm Performance",
            description="Detected inefficient algorithm causing performance degradation",
            category=OptimizationCategory.ALGORITHM,
            priority=OptimizationPriority.MEDIUM,
            impact_score=70,
            effort_score=60,
            confidence=70,
            metrics_affected=["avg_response_time", "cpu_usage"],
            implementation_steps=[
                "Profile algorithms to identify bottlenecks",
                "Replace O(n²) algorithms with O(n log n) or O(n)",
                "Implement memoization for repeated calculations",
                "Use appropriate data structures",
                "Consider parallel processing where applicable"
            ],
            expected_improvement={
                "avg_response_time": "Reduce by 50-80%",
                "cpu_usage": "Reduce by 30-50%"
            },
            prerequisites=["Algorithm analysis", "Performance testing"],
            risks=["Code complexity", "Potential bugs"]
        )
    
    def _create_configuration_issue_recommendation(self, metrics: Dict[str, Any]) -> OptimizationRecommendation:
        """Create configuration issue optimization recommendation.
        
        Args:
            metrics: Current performance metrics
            
        Returns:
            Configuration issue optimization recommendation
        """
        return OptimizationRecommendation(
            id=f"configuration_issue_{int(time.time())}",
            title="Fix Configuration Issues",
            description="Low throughput detected, review and optimize configuration settings",
            category=OptimizationCategory.CONFIGURATION,
            priority=OptimizationPriority.MEDIUM,
            impact_score=60,
            effort_score=30,
            confidence=85,
            metrics_affected=["throughput", "response_time"],
            implementation_steps=[
                "Review connection pool settings",
                "Optimize thread pool configurations",
                "Adjust timeout values",
                "Review resource limits",
                "Check for rate limiting issues"
            ],
            expected_improvement={
                "throughput": "Increase by 100-300%",
                "response_time": "Improve by 20-40%"
            },
            prerequisites=["Configuration access", "Performance testing"],
            risks=["Service disruption during changes"]
        )
    
    def get_recommendations(
        self,
        category: Optional[OptimizationCategory] = None,
        priority: Optional[OptimizationPriority] = None
    ) -> List[OptimizationRecommendation]:
        """Get optimization recommendations.
        
        Args:
            category: Filter by category (optional)
            priority: Filter by priority (optional)
            
        Returns:
            List of optimization recommendations
        """
        recommendations = list(self._recommendations.values())
        
        if category:
            recommendations = [rec for rec in recommendations if rec.category == category]
        
        if priority:
            recommendations = [rec for rec in recommendations if rec.priority == priority]
        
        return sorted(recommendations, key=lambda x: x.priority.value, reverse=True)
    
    def get_recommendation(self, recommendation_id: str) -> Optional[OptimizationRecommendation]:
        """Get a specific optimization recommendation.
        
        Args:
            recommendation_id: ID of the recommendation
            
        Returns:
            Optimization recommendation or None
        """
        return self._recommendations.get(recommendation_id)
    
    def remove_recommendation(self, recommendation_id: str) -> None:
        """Remove an optimization recommendation.
        
        Args:
            recommendation_id: ID of the recommendation to remove
        """
        self._recommendations.pop(recommendation_id, None)
    
    def get_optimization_summary(self) -> Dict[str, Any]:
        """Get optimization summary.
        
        Returns:
            Optimization summary
        """
        recommendations = list(self._recommendations.values())
        
        by_category = defaultdict(int)
        by_priority = defaultdict(int)
        
        for rec in recommendations:
            by_category[rec.category.value] += 1
            by_priority[rec.priority.value] += 1
        
        return {
            "total_recommendations": len(recommendations),
            "by_category": dict(by_category),
            "by_priority": dict(by_priority),
            "avg_impact_score": sum(rec.impact_score for rec in recommendations) / len(recommendations) if recommendations else 0,
            "avg_effort_score": sum(rec.effort_score for rec in recommendations) / len(recommendations) if recommendations else 0,
            "avg_confidence": sum(rec.confidence for rec in recommendations) / len(recommendations) if recommendations else 0,
            "config": {
                "enable_auto_analysis": self._config.enable_auto_analysis,
                "analysis_interval": self._config.analysis_interval,
                "min_confidence_threshold": self._config.min_confidence_threshold,
                "max_recommendations": self._config.max_recommendations
            }
        }
    
    def __enter__(self):
        """Context manager entry.
        
        Returns:
            Self
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.
        
        Args:
            exc_type: Exception type
            exc_val: Exception value
            exc_tb: Exception traceback
        """
        if self._analysis_task and not self._analysis_task.done():
            self._analysis_task.cancel()
