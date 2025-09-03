# gemini_sre_agent/ml/enhanced_code_generation_learning.py

"""
Learning and statistics functionality for enhanced code generation.

This module handles the learning data management, generation history tracking,
and statistical analysis for the enhanced code generation agent.
"""

from datetime import datetime
from typing import Any, Dict, List


class EnhancedCodeGenerationLearning:
    """Handles learning data management and statistics for code generation"""

    def __init__(self):
        self.generation_history: List[Dict[str, Any]] = []
        self.learning_data: Dict[str, Any] = {}

    def record_generation_history(
        self, issue_context, code_generation_result, start_time: float
    ):
        """Record generation history for analysis and learning"""
        generation_record = {
            "timestamp": datetime.now().isoformat(),
            "issue_type": issue_context.issue_type.value,
            "complexity_score": getattr(issue_context, "complexity_score", 5),
            "severity_level": issue_context.severity_level,
            "generation_success": code_generation_result.get("success", False),
            "quality_score": code_generation_result.get("quality_score", 0.0),
            "generation_time_ms": code_generation_result.get("generation_time_ms", 0),
            "iteration_count": code_generation_result.get("iteration_count", 1),
            "validation_passed": (
                code_generation_result.get("validation_result", {}).get(
                    "is_valid", False
                )
            ),
            "validation_score": (
                code_generation_result.get("validation_result", {}).get(
                    "overall_score", 0.0
                )
            ),
            "critical_issues_count": (
                len(
                    [
                        issue
                        for issue in code_generation_result.get(
                            "validation_result", {}
                        ).get("issues", [])
                        if issue.get("level") == "critical"
                    ]
                )
            ),
            "domain": issue_context.issue_type.value.split("_")[0],
            "affected_files_count": len(issue_context.affected_files),
        }

        self.generation_history.append(generation_record)

        # Keep only last 1000 records to prevent memory issues
        if len(self.generation_history) > 1000:
            self.generation_history = self.generation_history[-1000:]

    def update_learning_data(self, issue_context, code_generation_result):
        """Update learning data based on generation results"""
        domain = issue_context.issue_type.value.split("_")[0]

        if domain not in self.learning_data:
            self.learning_data[domain] = {
                "total_generations": 0,
                "successful_generations": 0,
                "average_quality_score": 0.0,
                "average_validation_score": 0.0,
                "common_patterns": {},
                "validation_issues": {},
                "successful_patterns": {},
                "failed_patterns": {},
            }

        domain_data = self.learning_data[domain]
        domain_data["total_generations"] += 1

        if code_generation_result.get("success", False):
            domain_data["successful_generations"] += 1

        # Update average quality score
        quality_score = code_generation_result.get("quality_score", 0.0)
        current_total = domain_data["average_quality_score"] * (
            domain_data["total_generations"] - 1
        )
        new_total = current_total + quality_score
        domain_data["average_quality_score"] = (
            new_total / domain_data["total_generations"]
        )

        # Update average validation score
        validation_score = code_generation_result.get("validation_result", {}).get(
            "overall_score", 0.0
        )
        current_validation_total = domain_data["average_validation_score"] * (
            domain_data["total_generations"] - 1
        )
        new_validation_total = current_validation_total + validation_score
        domain_data["average_validation_score"] = (
            new_validation_total / domain_data["total_generations"]
        )

        # Track validation issues
        validation_result = code_generation_result.get("validation_result", {})
        if validation_result:
            for issue in validation_result.get("issues", []):
                issue_key = (
                    f"{issue.get('type', 'unknown')}_{issue.get('level', 'unknown')}"
                )
                if issue_key not in domain_data["validation_issues"]:
                    domain_data["validation_issues"][issue_key] = 0
                domain_data["validation_issues"][issue_key] += 1

        # Track successful and failed patterns for learning
        if code_generation_result.get("success", False) and validation_result.get(
            "is_valid", False
        ):
            # Record successful patterns
            pattern_key = (
                f"{issue_context.issue_type.value}_{len(issue_context.affected_files)}"
            )
            if pattern_key not in domain_data["successful_patterns"]:
                domain_data["successful_patterns"][pattern_key] = 0
            domain_data["successful_patterns"][pattern_key] += 1
        else:
            # Record failed patterns for improvement
            pattern_key = (
                f"{issue_context.issue_type.value}_{len(issue_context.affected_files)}"
            )
            if pattern_key not in domain_data["failed_patterns"]:
                domain_data["failed_patterns"][pattern_key] = 0
            domain_data["failed_patterns"][pattern_key] += 1

    def get_generation_statistics(self) -> Dict[str, Any]:
        """Get statistics about code generation performance"""
        if not self.generation_history:
            return {"message": "No generation history available"}

        total_generations = len(self.generation_history)
        successful_generations = sum(
            1 for record in self.generation_history if record["generation_success"]
        )
        average_quality = (
            sum(record["quality_score"] for record in self.generation_history)
            / total_generations
        )
        average_time = (
            sum(record["generation_time_ms"] for record in self.generation_history)
            / total_generations
        )

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
            domain_data["success_rate"] = (
                domain_data["success_rate"] / domain_data["count"]
            )

            domain_records = [
                r for r in self.generation_history if r["domain"] == domain
            ]
            domain_data["avg_quality"] = sum(
                r["quality_score"] for r in domain_records
            ) / len(domain_records)

        return {
            "total_generations": total_generations,
            "successful_generations": successful_generations,
            "overall_success_rate": successful_generations / total_generations,
            "average_quality_score": average_quality,
            "average_generation_time_ms": average_time,
            "domain_statistics": domain_stats,
            "learning_data": self.learning_data,
        }

    def reset_learning_data(self):
        """Reset learning data (useful for testing or starting fresh)"""
        self.learning_data = {}
        self.generation_history = []

    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from learning data to improve generation"""
        insights = {
            "improvement_areas": [],
            "successful_patterns": {},
            "common_issues": {},
            "recommendations": [],
        }

        for domain, data in self.learning_data.items():
            # Identify improvement areas
            success_rate = (
                data["successful_generations"] / data["total_generations"]
                if data["total_generations"] > 0
                else 0
            )
            if success_rate < 0.8:
                insights["improvement_areas"].append(
                    {
                        "domain": domain,
                        "success_rate": success_rate,
                        "issue": "Low success rate",
                        "recommendation": f"Review {domain} generator patterns and validation rules",
                    }
                )

            # Track successful patterns
            if data["successful_patterns"]:
                insights["successful_patterns"][domain] = data["successful_patterns"]

            # Track common issues
            if data["validation_issues"]:
                insights["common_issues"][domain] = data["validation_issues"]

            # Generate recommendations
            if data["average_validation_score"] < 0.7:
                insights["recommendations"].append(
                    {
                        "domain": domain,
                        "type": "validation_improvement",
                        "message": f"Improve validation rules for {domain} issues",
                        "priority": "high",
                    }
                )

        return insights

    def get_feedback_for_generator(self, generator_type: str) -> Dict[str, Any]:
        """Get specific feedback for a generator type"""
        domain = (
            generator_type.split("_")[0] if "_" in generator_type else generator_type
        )

        if domain not in self.learning_data:
            return {"message": f"No learning data available for {domain}"}

        data = self.learning_data[domain]

        return {
            "domain": domain,
            "total_generations": data["total_generations"],
            "success_rate": (
                data["successful_generations"] / data["total_generations"]
                if data["total_generations"] > 0
                else 0
            ),
            "average_quality_score": data["average_quality_score"],
            "average_validation_score": data["average_validation_score"],
            "most_common_issues": sorted(
                data["validation_issues"].items(), key=lambda x: x[1], reverse=True
            )[:5],
            "successful_patterns": data["successful_patterns"],
            "failed_patterns": data["failed_patterns"],
            "recommendations": self._generate_domain_recommendations(domain, data),
        }

    def _generate_domain_recommendations(
        self, domain: str, data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate specific recommendations for a domain"""
        recommendations = []

        success_rate = (
            data["successful_generations"] / data["total_generations"]
            if data["total_generations"] > 0
            else 0
        )

        if success_rate < 0.7:
            recommendations.append(
                {
                    "type": "success_rate",
                    "message": f"Success rate for {domain} is {success_rate:.1%}",
                    "suggestion": "Review and improve generation patterns",
                    "priority": "high",
                }
            )

        if data["average_validation_score"] < 0.6:
            recommendations.append(
                {
                    "type": "validation",
                    "message": f"Validation score for {domain} is {data['average_validation_score']:.2f}",
                    "suggestion": "Enhance validation rules and patterns",
                    "priority": "medium",
                }
            )

        # Check for specific validation issues
        critical_issues = [
            issue
            for issue in data["validation_issues"].items()
            if "critical" in issue[0]
        ]
        if critical_issues:
            recommendations.append(
                {
                    "type": "critical_issues",
                    "message": f"Found {len(critical_issues)} types of critical validation issues",
                    "suggestion": "Address critical validation issues immediately",
                    "priority": "high",
                    "issues": critical_issues,
                }
            )

        return recommendations

    def export_learning_data(self, generator_info: Dict[str, Any]) -> Dict[str, Any]:
        """Export learning data for external analysis"""
        return {
            "learning_data": self.learning_data,
            "generation_history": self.generation_history,
            "statistics": self.get_generation_statistics(),
            "insights": self.get_learning_insights(),
            "generator_info": generator_info,
            "export_timestamp": datetime.now().isoformat(),
        }
