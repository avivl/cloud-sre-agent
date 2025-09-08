import pytest
from unittest.mock import MagicMock

from gemini_sre_agent.llm.capabilities.comparison import CapabilityComparer
from gemini_sre_agent.llm.capabilities.database import CapabilityDatabase
from gemini_sre_agent.llm.capabilities.models import ModelCapability, ModelCapabilities


@pytest.fixture
def populated_capability_database():
    """Fixture for a populated CapabilityDatabase."""
    db = CapabilityDatabase()
    
    cap_text_gen = ModelCapability(name="text_generation", description="Generates text", performance_score=0.8, cost_efficiency=0.2)
    cap_code_gen = ModelCapability(name="code_generation", description="Generates code", performance_score=0.9, cost_efficiency=0.1)
    cap_image_rec = ModelCapability(name="image_recognition", description="Recognizes images", performance_score=0.7, cost_efficiency=0.3)

    model_caps1 = ModelCapabilities(
        model_id="provider1/model_A", capabilities=[cap_text_gen, cap_code_gen]
    )
    model_caps2 = ModelCapabilities(
        model_id="provider2/model_B", capabilities=[cap_text_gen, cap_image_rec]
    )
    model_caps3 = ModelCapabilities(
        model_id="provider3/model_C", capabilities=[cap_code_gen]
    )
    model_caps4 = ModelCapabilities(
        model_id="provider4/model_D", capabilities=[cap_text_gen]
    )

    db.add_capabilities(model_caps1)
    db.add_capabilities(model_caps2)
    db.add_capabilities(model_caps3)
    db.add_capabilities(model_caps4)
    return db


def test_compare_models(populated_capability_database):
    comparer = CapabilityComparer(populated_capability_database)
    model_ids = ["provider1/model_A", "provider2/model_B", "provider3/model_C"]
    results = comparer.compare_models(model_ids)

    assert len(results) == 3
    assert "provider1/model_A" in results
    assert "provider2/model_B" in results
    assert "provider3/model_C" in results

    # Check provider1/model_A
    model_A_results = results["provider1/model_A"]
    assert "text_generation" in model_A_results["capabilities"]
    assert "code_generation" in model_A_results["capabilities"]
    assert model_A_results["summary"]["num_capabilities"] == 2
    assert model_A_results["summary"]["avg_performance_score"] == (0.8 + 0.9) / 2
    assert model_A_results["summary"]["avg_cost_efficiency"] == (0.2 + 0.1) / 2
    
    

    # Check provider2/model_B
    model_B_results = results["provider2/model_B"]
    assert "text_generation" in model_B_results["capabilities"]
    assert "image_recognition" in model_B_results["capabilities"]
    assert model_B_results["summary"]["num_capabilities"] == 2
    
    assert "image_recognition" in model_B_results["summary"]["unique_capabilities"] # Unique to B among compared

    # Check provider3/model_C
    model_C_results = results["provider3/model_C"]
    assert "code_generation" in model_C_results["capabilities"]
    assert model_C_results["summary"]["num_capabilities"] == 1
    
    assert not model_C_results["summary"]["unique_capabilities"]


def test_find_best_model_for_capabilities(populated_capability_database):
    comparer = CapabilityComparer(populated_capability_database)

    # Test with capabilities supported by multiple models
    best_model = comparer.find_best_model_for_capabilities(["text_generation"])
    assert best_model is not None
    # provider1/model_A (0.8 perf, 0.2 cost) vs provider2/model_B (0.7 perf, 0.3 cost) vs provider4/model_D (0.8 perf, 0.2 cost)
    # Scoring: (perf * 0.7) + ((1 - cost) * 0.3)
    # A: (0.8 * 0.7) + (0.8 * 0.3) = 0.56 + 0.24 = 0.8
    # B: (0.7 * 0.7) + (0.7 * 0.3) = 0.49 + 0.21 = 0.7
    # D: (0.8 * 0.7) + (0.8 * 0.3) = 0.56 + 0.24 = 0.8
    # A and D have same score, so it depends on iteration order.
    # Let's assume provider1/model_A is returned first due to iteration order.
    assert best_model[0] in ["provider1/model_A", "provider4/model_D"]
    assert best_model[1] == pytest.approx(0.8)

    # Test with capabilities supported by only one model
    best_model = comparer.find_best_model_for_capabilities(["image_recognition"])
    assert best_model is not None
    assert best_model[0] == "provider2/model_B"
    assert best_model[1] == pytest.approx((0.7 * 0.7) + (0.7 * 0.3)) # 0.7

    # Test with capabilities not supported by any model
    best_model = comparer.find_best_model_for_capabilities(["video_analysis"])
    assert best_model is None

    # Test with multiple required capabilities
    best_model = comparer.find_best_model_for_capabilities(["text_generation", "code_generation"])
    assert best_model is not None
    assert best_model[0] == "provider1/model_A"
    assert best_model[1] == pytest.approx((((0.8+0.9)/2) * 0.7) + (((1-0.2)+(1-0.1))/2 * 0.3)) # (0.85 * 0.7) + (0.85 * 0.3) = 0.85
