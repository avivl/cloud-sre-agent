"""
Performance Benchmark for Enhanced Multi-Provider LLM System.

This script benchmarks the performance of different optimization strategies
and provides insights into cost, quality, and speed trade-offs.
"""

import asyncio
import time
import statistics
from typing import Dict, List, Tuple
import logging

from gemini_sre_agent.agents.enhanced_triage_agent import EnhancedTriageAgent
from gemini_sre_agent.llm.config_manager import ConfigManager
from gemini_sre_agent.llm.strategy_manager import OptimizationGoal
from gemini_sre_agent.llm.monitoring.llm_metrics import get_llm_metrics_collector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceBenchmark:
    """Benchmark the enhanced LLM system performance."""
    
    def __init__(self, config_path: str = "examples/llm_configs/multi_provider_config.yaml"):
        """Initialize the benchmark."""
        self.config_manager = ConfigManager(config_path)
        self.llm_config = self.config_manager.get_config()
        self.metrics_collector = get_llm_metrics_collector()
        
        # Test data
        self.test_logs = [
            ["ERROR: Database connection timeout after 30s"],
            ["CRITICAL: Service crashed with OutOfMemoryError"],
            ["WARN: High CPU usage detected (95%)", "ERROR: Request timeout"],
            ["INFO: Service started", "ERROR: Configuration file not found"],
            ["DEBUG: Processing request", "WARN: Slow query detected", "ERROR: Database deadlock"],
        ]
    
    async def benchmark_optimization_strategies(self) -> Dict[str, Dict[str, float]]:
        """Benchmark different optimization strategies."""
        logger.info("Starting optimization strategy benchmark...")
        
        strategies = [
            ("Cost Effective", OptimizationGoal.COST_EFFECTIVE, {"max_cost": 0.005}),
            ("Quality Focused", OptimizationGoal.QUALITY, {"min_quality": 0.9}),
            ("Hybrid", OptimizationGoal.HYBRID, {"max_cost": 0.01, "min_quality": 0.8}),
            ("Speed Focused", OptimizationGoal.COST_EFFECTIVE, {"max_cost": 0.002}),
        ]
        
        results = {}
        
        for strategy_name, goal, params in strategies:
            logger.info(f"Benchmarking {strategy_name} strategy...")
            
            agent = EnhancedTriageAgent(
                llm_config=self.llm_config,
                optimization_goal=goal,
                collect_stats=True,
                **params
            )
            
            # Benchmark this strategy
            strategy_results = await self._benchmark_agent(agent, strategy_name)
            results[strategy_name] = strategy_results
            
            logger.info(f"{strategy_name} results: {strategy_results}")
        
        return results
    
    async def _benchmark_agent(self, agent: EnhancedTriageAgent, strategy_name: str) -> Dict[str, float]:
        """Benchmark a specific agent configuration."""
        response_times = []
        costs = []
        quality_scores = []
        success_count = 0
        
        for i, logs in enumerate(self.test_logs):
            try:
                start_time = time.time()
                
                # Process logs
                response = await agent.analyze_logs(logs, f"{strategy_name}_test_{i}")
                
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to ms
                
                response_times.append(response_time)
                success_count += 1
                
                # Simulate cost and quality metrics
                # In a real implementation, these would come from the actual LLM responses
                estimated_cost = len(" ".join(logs)) * 0.00001  # Rough estimate
                costs.append(estimated_cost)
                
                # Quality score based on response completeness
                quality_score = min(1.0, len(response.description) / 100.0)
                quality_scores.append(quality_score)
                
            except Exception as e:
                logger.error(f"Error in {strategy_name} test {i}: {e}")
        
        # Calculate statistics
        return {
            "avg_response_time_ms": statistics.mean(response_times) if response_times else 0,
            "median_response_time_ms": statistics.median(response_times) if response_times else 0,
            "avg_cost": statistics.mean(costs) if costs else 0,
            "total_cost": sum(costs),
            "avg_quality": statistics.mean(quality_scores) if quality_scores else 0,
            "success_rate": success_count / len(self.test_logs),
            "total_requests": len(self.test_logs),
        }
    
    async def benchmark_model_comparison(self) -> Dict[str, Dict[str, float]]:
        """Compare performance across different models."""
        logger.info("Starting model comparison benchmark...")
        
        models_to_test = [
            ("llama3.2:1b", "Fast Model"),
            ("llama3.2:3b", "Balanced Model"),
            # Add more models as available
        ]
        
        results = {}
        
        for model_name, description in models_to_test:
            logger.info(f"Benchmarking {description} ({model_name})...")
            
            try:
                agent = EnhancedTriageAgent(
                    llm_config=self.llm_config,
                    primary_model=model_name,
                    optimization_goal=OptimizationGoal.HYBRID,
                    collect_stats=True,
                )
                
                model_results = await self._benchmark_agent(agent, model_name)
                results[f"{description} ({model_name})"] = model_results
                
            except Exception as e:
                logger.error(f"Error benchmarking {model_name}: {e}")
                results[f"{description} ({model_name})"] = {"error": str(e)}
        
        return results
    
    async def benchmark_load_testing(self, concurrent_requests: int = 5) -> Dict[str, float]:
        """Perform load testing with concurrent requests."""
        logger.info(f"Starting load test with {concurrent_requests} concurrent requests...")
        
        agent = EnhancedTriageAgent(
            llm_config=self.llm_config,
            optimization_goal=OptimizationGoal.HYBRID,
            collect_stats=True,
        )
        
        async def process_request(request_id: int) -> Tuple[float, bool]:
            """Process a single request and return response time and success status."""
            try:
                start_time = time.time()
                logs = self.test_logs[request_id % len(self.test_logs)]
                await agent.analyze_logs(logs, f"load_test_{request_id}")
                end_time = time.time()
                return (end_time - start_time) * 1000, True
            except Exception as e:
                logger.error(f"Load test request {request_id} failed: {e}")
                return 0, False
        
        # Create concurrent tasks
        tasks = [process_request(i) for i in range(concurrent_requests)]
        
        start_time = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()
        
        # Process results
        response_times = []
        success_count = 0
        
        for result in results:
            if isinstance(result, tuple):
                response_time, success = result
                if success:
                    response_times.append(response_time)
                    success_count += 1
        
        total_time = (end_time - start_time) * 1000  # Convert to ms
        
        return {
            "total_time_ms": total_time,
            "avg_response_time_ms": statistics.mean(response_times) if response_times else 0,
            "max_response_time_ms": max(response_times) if response_times else 0,
            "min_response_time_ms": min(response_times) if response_times else 0,
            "success_rate": success_count / concurrent_requests,
            "requests_per_second": concurrent_requests / (total_time / 1000) if total_time > 0 else 0,
            "concurrent_requests": concurrent_requests,
        }
    
    def generate_report(self, results: Dict[str, Dict]) -> str:
        """Generate a comprehensive benchmark report."""
        report = []
        report.append("=" * 80)
        report.append("ENHANCED MULTI-PROVIDER LLM SYSTEM - PERFORMANCE BENCHMARK REPORT")
        report.append("=" * 80)
        report.append("")
        
        # Optimization strategies results
        if "optimization_strategies" in results:
            report.append("OPTIMIZATION STRATEGIES COMPARISON")
            report.append("-" * 40)
            
            strategies = results["optimization_strategies"]
            
            # Create comparison table
            headers = ["Strategy", "Avg Time (ms)", "Avg Cost", "Avg Quality", "Success Rate"]
            report.append(f"{headers[0]:<20} {headers[1]:<15} {headers[2]:<12} {headers[3]:<12} {headers[4]:<12}")
            report.append("-" * 80)
            
            for strategy, metrics in strategies.items():
                report.append(
                    f"{strategy:<20} "
                    f"{metrics.get('avg_response_time_ms', 0):<15.2f} "
                    f"{metrics.get('avg_cost', 0):<12.6f} "
                    f"{metrics.get('avg_quality', 0):<12.3f} "
                    f"{metrics.get('success_rate', 0):<12.2%}"
                )
            report.append("")
        
        # Model comparison results
        if "model_comparison" in results:
            report.append("MODEL COMPARISON")
            report.append("-" * 40)
            
            models = results["model_comparison"]
            
            for model, metrics in models.items():
                if "error" in metrics:
                    report.append(f"{model}: ERROR - {metrics['error']}")
                else:
                    report.append(f"{model}:")
                    report.append(f"  Average Response Time: {metrics.get('avg_response_time_ms', 0):.2f} ms")
                    report.append(f"  Average Cost: ${metrics.get('avg_cost', 0):.6f}")
                    report.append(f"  Average Quality: {metrics.get('avg_quality', 0):.3f}")
                    report.append(f"  Success Rate: {metrics.get('success_rate', 0):.2%}")
                    report.append("")
        
        # Load testing results
        if "load_testing" in results:
            report.append("LOAD TESTING RESULTS")
            report.append("-" * 40)
            
            load_metrics = results["load_testing"]
            report.append(f"Concurrent Requests: {load_metrics.get('concurrent_requests', 0)}")
            report.append(f"Total Time: {load_metrics.get('total_time_ms', 0):.2f} ms")
            report.append(f"Average Response Time: {load_metrics.get('avg_response_time_ms', 0):.2f} ms")
            report.append(f"Min Response Time: {load_metrics.get('min_response_time_ms', 0):.2f} ms")
            report.append(f"Max Response Time: {load_metrics.get('max_response_time_ms', 0):.2f} ms")
            report.append(f"Success Rate: {load_metrics.get('success_rate', 0):.2%}")
            report.append(f"Requests per Second: {load_metrics.get('requests_per_second', 0):.2f}")
            report.append("")
        
        # Recommendations
        report.append("RECOMMENDATIONS")
        report.append("-" * 40)
        
        if "optimization_strategies" in results:
            strategies = results["optimization_strategies"]
            
            # Find best strategy for each metric
            best_speed = min(strategies.items(), key=lambda x: x[1].get('avg_response_time_ms', float('inf')))
            best_cost = min(strategies.items(), key=lambda x: x[1].get('avg_cost', float('inf')))
            best_quality = max(strategies.items(), key=lambda x: x[1].get('avg_quality', 0))
            
            report.append(f"• For fastest response: Use '{best_speed[0]}' strategy")
            report.append(f"• For lowest cost: Use '{best_cost[0]}' strategy")
            report.append(f"• For highest quality: Use '{best_quality[0]}' strategy")
            report.append("")
        
        report.append("SYSTEM METRICS")
        report.append("-" * 40)
        
        # Get overall system metrics
        system_metrics = self.metrics_collector.get_metrics_summary()
        for key, value in system_metrics.items():
            if isinstance(value, float):
                report.append(f"{key.replace('_', ' ').title()}: {value:.4f}")
            else:
                report.append(f"{key.replace('_', ' ').title()}: {value}")
        
        report.append("")
        report.append("=" * 80)
        
        return "\\n".join(report)


async def main():
    """Run the complete benchmark suite."""
    logger.info("Starting Enhanced Multi-Provider LLM System Benchmark")
    
    benchmark = PerformanceBenchmark()
    all_results = {}
    
    try:
        # Run optimization strategies benchmark
        logger.info("Running optimization strategies benchmark...")
        optimization_results = await benchmark.benchmark_optimization_strategies()
        all_results["optimization_strategies"] = optimization_results
        
        # Run model comparison benchmark
        logger.info("Running model comparison benchmark...")
        model_results = await benchmark.benchmark_model_comparison()
        all_results["model_comparison"] = model_results
        
        # Run load testing
        logger.info("Running load testing...")
        load_results = await benchmark.benchmark_load_testing(concurrent_requests=10)
        all_results["load_testing"] = load_results
        
        # Generate and display report
        report = benchmark.generate_report(all_results)
        print(report)
        
        # Save report to file
        with open("benchmark_report.txt", "w") as f:
            f.write(report)
        
        logger.info("Benchmark completed successfully! Report saved to benchmark_report.txt")
        
    except Exception as e:
        logger.error(f"Benchmark failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())