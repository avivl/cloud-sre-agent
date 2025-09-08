import pytest

from gemini_sre_agent.llm.capabilities.requirements import CapabilityRequirements
from gemini_sre_agent.llm.common.enums import ModelType


def test_capability_requirements_initialization():
    reqs = CapabilityRequirements(
        task_name="Summarization",
        required_capabilities=["text_generation"],
        preferred_model_type=ModelType.SMART,
        min_performance_score=0.7,
        max_cost_per_1k_tokens=0.005,
        latency_tolerance_ms=500,
        custom_criteria={"domain": "finance"},
    )

    assert reqs.task_name == "Summarization"
    assert reqs.required_capabilities == ["text_generation"]
    assert reqs.preferred_model_type == ModelType.SMART
    assert reqs.min_performance_score == 0.7
    assert reqs.max_cost_per_1k_tokens == 0.005
    assert reqs.latency_tolerance_ms == 500
    assert reqs.custom_criteria == {"domain": "finance"}


def test_capability_requirements_defaults():
    reqs = CapabilityRequirements(task_name="DefaultTask")
    assert reqs.required_capabilities == []
    assert reqs.preferred_model_type is None
    assert reqs.min_performance_score == 0.0
    assert reqs.max_cost_per_1k_tokens is None
    assert reqs.latency_tolerance_ms is None
    assert reqs.custom_criteria == {}


def test_capability_requirements_validation():
    with pytest.raises(ValueError):
        # min_performance_score out of range
        CapabilityRequirements(task_name="Invalid", min_performance_score=1.5)

    with pytest.raises(ValueError):
        # max_cost_per_1k_tokens negative
        CapabilityRequirements(task_name="Invalid", max_cost_per_1k_tokens=-0.001)

    with pytest.raises(ValueError):
        # latency_tolerance_ms negative
        CapabilityRequirements(task_name="Invalid", latency_tolerance_ms=-100)
