
import logging
from typing import Dict, List, Any, Tuple, Optional

from gemini_sre_agent.llm.capabilities.database import CapabilityDatabase
from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability

logger = logging.getLogger(__name__)


class CapabilityComparer:
    """
    Compares capabilities of different LLM models.
    """

    def __init__(self, capability_database: CapabilityDatabase):
        """
        Initialize the CapabilityComparer.

        Args:
            capability_database: The CapabilityDatabase instance.
        """
        self.capability_database = capability_database

    def compare_models(self, model_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Compare capabilities of a list of models.

        Args:
            model_ids: A list of model IDs to compare.

        Returns:
            A dictionary where keys are model IDs and values are dictionaries
            containing their capabilities and comparison metrics.
        """
        comparison_results = {}
        all_capabilities: Dict[str, List[str]] = {}

        # Collect capabilities for all models
        for model_id in model_ids:
            model_caps = self.capability_database.get_capabilities(model_id)
            if model_caps:
                comparison_results[model_id] = {
                    "capabilities": {cap.name: cap.model_dump() for cap in model_caps.capabilities},
                    "summary": {},
                }
                for cap in model_caps.capabilities:
                    if cap.name not in all_capabilities:
                        all_capabilities[cap.name] = []
                    all_capabilities[cap.name].append(model_id)
            else:
                comparison_results[model_id] = {"capabilities": {}, "summary": {"status": "not_found"}}

        # Add comparison metrics
        for model_id, data in comparison_results.items():
            summary = data["summary"]
            if "status" in summary and summary["status"] == "not_found":
                continue

            num_capabilities = len(data["capabilities"])
            summary["num_capabilities"] = num_capabilities

            # Calculate average performance and cost efficiency
            total_performance = sum(c["performance_score"] for c in data["capabilities"].values())
            total_cost_efficiency = sum(c["cost_efficiency"] for c in data["capabilities"].values())

            summary["avg_performance_score"] = total_performance / num_capabilities if num_capabilities > 0 else 0.0
            summary["avg_cost_efficiency"] = total_cost_efficiency / num_capabilities if num_capabilities > 0 else 0.0

            # Identify unique and common capabilities
            unique_capabilities = []
            common_capabilities = []
            for cap_name in data["capabilities"].keys():
                if len(all_capabilities.get(cap_name, [])) == 1:
                    unique_capabilities.append(cap_name)
                elif len(all_capabilities.get(cap_name, [])) == len(model_ids):
                    common_capabilities.append(cap_name)
            summary["unique_capabilities"] = unique_capabilities
            summary["common_capabilities"] = common_capabilities

        return comparison_results

    def find_best_model_for_capabilities(self, required_capabilities: List[str]) -> Optional[Tuple[str, float]]:
        """
        Find the best model that supports all required capabilities.

        Args:
            required_capabilities: A list of capability names required.

        Returns:
            A tuple of (model_id, score) for the best model, or None if no model found.
        """
        best_model_id = None
        best_score = -1.0

        for model_id in self.capability_database.get_all_model_ids():
            model_caps = self.capability_database.get_capabilities(model_id)
            if not model_caps:
                continue
            has_all_required = True
            current_cap_names = {cap.name for cap in model_caps.capabilities}
            for req_cap in required_capabilities:
                if req_cap not in current_cap_names:
                    has_all_required = False
                    break
            
            if has_all_required:
                # Calculate a simple score based on avg performance and cost efficiency
                avg_perf = sum(c.performance_score for c in model_caps.capabilities if c.name in required_capabilities) / len(required_capabilities)
                avg_cost_eff = sum(c.cost_efficiency for c in model_caps.capabilities if c.name in required_capabilities) / len(required_capabilities)
                
                # Simple scoring: higher performance and higher cost efficiency (both 0-1 scores)
                score = (avg_perf * 0.7) + (avg_cost_eff * 0.3) # Example weighting
                
                if score > best_score:
                    best_score = score
                    best_model_id = model_id
        
        if best_model_id:
            return (best_model_id, best_score)
        return None
