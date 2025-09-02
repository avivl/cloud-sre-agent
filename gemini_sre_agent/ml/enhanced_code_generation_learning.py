# gemini_sre_agent/ml/enhanced_code_generation_learning.py

"""
Learning and statistics functionality for enhanced code generation.

This module handles the learning data management, generation history tracking,
and statistical analysis for the enhanced code generation agent.
"""

from typing import Dict, Any, List
from datetime import datetime


class EnhancedCodeGenerationLearning:
    """Handles learning data management and statistics for code generation"""
    
    def __init__(self):
        self.generation_history: List[Dict[str, Any]] = []
        self.learning_data: Dict[str, Any] = {}
    
    def record_generation_history(
        self, 
        issue_context, 
        code_generation_result,
        start_time: float
    ):
        """Record generation history for analysis and learning"""
        generation_record = {
            "timestamp": datetime.now().isoformat(),
            "issue_type": issue_context.issue_type.value,
            "complexity_score": issue_context.complexity_score,
            "severity_level": issue_context.severity_level,
            "generation_success": code_generation_result.success,
            "quality_score": code_generation_result.quality_score,
            "generation_time_ms": code_generation_result.generation_time_ms,
            "iteration_count": code_generation_result.iteration_count,
            "validation_passed": (
                code_generation_result.validation_result.is_valid 
                if code_generation_result.validation_result else False
            ),
            "critical_issues_count": (
                len(code_generation_result.validation_result.get_critical_issues())
                if code_generation_result.validation_result else 0
            ),
            "domain": issue_context.issue_type.value.split("_")[0],
            "affected_files_count": len(issue_context.affected_files)
        }
        
        self.generation_history.append(generation_record)
        
        # Keep only last 1000 records to prevent memory issues
        if len(self.generation_history) > 1000:
            self.generation_history = self.generation_history[-1000:]
    
    def update_learning_data(
        self, 
        issue_context, 
        code_generation_result
    ):
        """Update learning data based on generation results"""
        domain = issue_context.issue_type.value.split("_")[0]
        
        if domain not in self.learning_data:
            self.learning_data[domain] = {
                "total_generations": 0,
                "successful_generations": 0,
                "average_quality_score": 0.0,
                "common_patterns": {},
                "validation_issues": {}
            }
        
        domain_data = self.learning_data[domain]
        domain_data["total_generations"] += 1
        
        if code_generation_result.success:
            domain_data["successful_generations"] += 1
        
        # Update average quality score
        current_total = domain_data["average_quality_score"] * (domain_data["total_generations"] - 1)
        new_total = current_total + code_generation_result.quality_score
        domain_data["average_quality_score"] = new_total / domain_data["total_generations"]
        
        # Track validation issues
        if code_generation_result.validation_result:
            for issue in code_generation_result.validation_result.issues:
                issue_key = f"{issue.category}_{issue.severity.value}"
                if issue_key not in domain_data["validation_issues"]:
                    domain_data["validation_issues"][issue_key] = 0
                domain_data["validation_issues"][issue_key] += 1
    
    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get statistics about code generation performance"""
        if not self.generation_history:
            return {"message": "No generation history available"}
        
        total_generations = len(self.generation_history)
        successful_generations = sum(1 for record in self.generation_history if record["generation_success"])
        average_quality = sum(record["quality_score"] for record in self.generation_history) / total_generations
        average_time = sum(record["generation_time_ms"] for record in self.generation_history) / total_generations
        
        # Domain breakdown
        domain_stats = {}
        for record in self.generation_history:
            domain = record["domain"]
            if domain not in domain_stats:
                domain_stats[domain] = {"count": 0, "success_rate": 0, "avg_quality": 0}
            
            domain_stats[domain]["count"] += 1
            if record["generation_success"]:
                domain_stats[domain]["success_rate"] += 1
        
        # Calculate success rates and average quality per domain
        for domain in domain_stats:
            domain_data = domain_stats[domain]
            domain_data["success_rate"] = domain_data["success_rate"] / domain_data["count"]
            
            domain_records = [r for r in self.generation_history if r["domain"] == domain]
            domain_data["avg_quality"] = sum(r["quality_score"] for r in domain_records) / len(domain_records)
        
        return {
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "overall_success_rate": successful_generations / total_generations,
            "average_quality_score": average_quality,
            "average_generation_time_ms": average_time,
            "domain_statistics": domain_stats,
            "learning_data": self.learning_data
        }
    
    def reset_learning_data(self):
        """Reset learning data (useful for testing or starting fresh)"""
        self.learning_data = {}
        self.generation_history = []
    
    def export_learning_data(self, generator_info: Dict[str, Any]) -> Dict[str, Any]:
        """Export learning data for external analysis"""
        return {
            "learning_data": self.learning_data,
            "generation_history": self.generation_history,
            "statistics": self.get_generation_statistics(),
            "generator_info": generator_info,
            "export_timestamp": datetime.now().isoformat()
        }
