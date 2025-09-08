import pytest

from gemini_sre_agent.llm.capabilities.database import CapabilityDatabase
from gemini_sre_agent.llm.capabilities.models import ModelCapabilities, ModelCapability


@pytest.fixture
def capability_database():
    """Fixture for an empty CapabilityDatabase."""
    return CapabilityDatabase()


@pytest.fixture
def sample_model_capabilities():
    """Fixture for sample ModelCapabilities objects."""
    cap1 = ModelCapability(name="text_generation", description="Generates text")
    cap2 = ModelCapability(name="code_generation", description="Generates code")
    cap3 = ModelCapability(name="image_recognition", description="Recognizes images")

    model_caps1 = ModelCapabilities(
        model_id="provider1/model_A", capabilities=[cap1, cap2]
    )
    model_caps2 = ModelCapabilities(
        model_id="provider2/model_B", capabilities=[cap1, cap3]
    )
    model_caps3 = ModelCapabilities(model_id="provider3/model_C", capabilities=[cap2])
    return [model_caps1, model_caps2, model_caps3]


def test_add_capabilities(capability_database, sample_model_capabilities):
    for caps in sample_model_capabilities:
        capability_database.add_capabilities(caps)
    assert len(capability_database) == 3
    assert "provider1/model_A" in capability_database
    assert (
        capability_database.get_capabilities("provider1/model_A")
        == sample_model_capabilities[0]
    )


def test_get_capabilities(capability_database, sample_model_capabilities):
    capability_database.add_capabilities(sample_model_capabilities[0])
    retrieved_caps = capability_database.get_capabilities("provider1/model_A")
    assert retrieved_caps == sample_model_capabilities[0]
    assert capability_database.get_capabilities("non_existent_model") is None


def test_query_capabilities_by_name(capability_database, sample_model_capabilities):
    for caps in sample_model_capabilities:
        capability_database.add_capabilities(caps)

    text_gen_models = capability_database.query_capabilities(
        capability_name="text_generation"
    )
    assert len(text_gen_models) == 2
    assert any(mc.model_id == "provider1/model_A" for mc in text_gen_models)
    assert any(mc.model_id == "provider2/model_B" for mc in text_gen_models)

    code_gen_models = capability_database.query_capabilities(
        capability_name="code_generation"
    )
    assert len(code_gen_models) == 2
    assert any(mc.model_id == "provider1/model_A" for mc in code_gen_models)
    assert any(mc.model_id == "provider3/model_C" for mc in code_gen_models)

    image_rec_models = capability_database.query_capabilities(
        capability_name="image_recognition"
    )
    assert len(image_rec_models) == 1
    assert any(mc.model_id == "provider2/model_B" for mc in image_rec_models)

    non_existent_caps = capability_database.query_capabilities(
        capability_name="video_analysis"
    )
    assert len(non_existent_caps) == 0


def test_query_all_capabilities(capability_database, sample_model_capabilities):
    for caps in sample_model_capabilities:
        capability_database.add_capabilities(caps)
    all_caps = capability_database.query_capabilities()
    assert len(all_caps) == 3
    # Ensure all original capabilities are present
    assert all(c in all_caps for c in sample_model_capabilities)


def test_clear_database(capability_database, sample_model_capabilities):
    for caps in sample_model_capabilities:
        capability_database.add_capabilities(caps)
    assert len(capability_database) > 0
    capability_database.clear()
    assert len(capability_database) == 0
    assert "provider1/model_A" not in capability_database
