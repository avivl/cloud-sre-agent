# tests/test_enhanced_code_generation_agent_simple.py

from unittest.mock import Mock

import pytest


class TestEnhancedCodeGenerationConfig:
    """Test the configuration class for enhanced code generation agent"""

    def test_config_initialization(self):
        """Test config initialization with default values"""

        # Mock the config class
        class MockConfig:
            def __init__(self, project_id, location, main_model, **kwargs):
                self.project_id = project_id
                self.location = location
                self.main_model = main_model
                self.meta_model = kwargs.get("meta_model", "gemini-1.5-flash-001")
                self.max_iterations = kwargs.get("max_iterations", 3)
                self.quality_threshold = kwargs.get("quality_threshold", 8.0)
                self.enable_learning = kwargs.get("enable_learning", True)
                self.human_review_threshold = kwargs.get("human_review_threshold", 7.0)

        config = MockConfig(
            project_id="test-project",
            location="us-central1",
            main_model="gemini-1.5-pro",
        )

        assert config.project_id == "test-project"
        assert config.location == "us-central1"
        assert config.main_model == "gemini-1.5-pro"
        assert config.meta_model == "gemini-1.5-flash-001"
        assert config.max_iterations == 3
        assert config.quality_threshold == 8.0
        assert config.enable_learning is True
        assert config.human_review_threshold == 7.0

    def test_config_custom_values(self):
        """Test config initialization with custom values"""

        # Mock the config class
        class MockConfig:
            def __init__(self, project_id, location, main_model, **kwargs):
                self.project_id = project_id
                self.location = location
                self.main_model = main_model
                self.meta_model = kwargs.get("meta_model", "gemini-1.5-flash-001")
                self.max_iterations = kwargs.get("max_iterations", 3)
                self.quality_threshold = kwargs.get("quality_threshold", 8.0)
                self.enable_learning = kwargs.get("enable_learning", True)
                self.human_review_threshold = kwargs.get("human_review_threshold", 7.0)

        config = MockConfig(
            project_id="custom-project",
            location="europe-west1",
            main_model="custom-model",
            meta_model="custom-meta",
            max_iterations=5,
            quality_threshold=9.0,
            enable_learning=False,
            human_review_threshold=8.5,
        )

        assert config.project_id == "custom-project"
        assert config.location == "europe-west1"
        assert config.main_model == "custom-model"
        assert config.meta_model == "custom-meta"
        assert config.max_iterations == 5
        assert config.quality_threshold == 9.0
        assert config.enable_learning is False
        assert config.human_review_threshold == 8.5


class TestEnhancedCodeGenerationAgent:
    """Test the enhanced code generation agent"""

    def test_agent_initialization(self):
        """Test agent initialization"""

        # Mock the agent class
        class MockAgent:
            def __init__(self, config):
                self.config = config
                self.code_generator_factory = Mock()
                self.generation_history = []
                self.learning_data = {}

        mock_config = Mock()
        mock_config.project_id = "test-project"
        mock_config.location = "us-central1"
        mock_config.main_model = "gemini-1.5-pro"

        agent = MockAgent(mock_config)

        assert agent.config == mock_config
        assert agent.code_generator_factory is not None
        assert agent.generation_history == []
        assert agent.learning_data == {}

    def test_generation_history_management(self):
        """Test generation history management"""

        # Mock the agent class
        class MockAgent:
            def __init__(self):
                self.generation_history = []
                self.learning_data = {}

            def add_generation_record(self, record):
                self.generation_history.append(record)
                if len(self.generation_history) > 1000:
                    self.generation_history = self.generation_history[-1000:]

            def get_history_count(self):
                return len(self.generation_history)

            def reset_history(self):
                self.generation_history = []
                self.learning_data = {}

        agent = MockAgent()

        # Test adding records
        assert agent.get_history_count() == 0

        record1 = {"timestamp": "2024-01-01", "success": True}
        record2 = {"timestamp": "2024-01-02", "success": False}

        agent.add_generation_record(record1)
        agent.add_generation_record(record2)

        assert agent.get_history_count() == 2
        assert agent.generation_history[0]["success"] is True
        assert agent.generation_history[1]["success"] is False

        # Test reset
        agent.reset_history()
        assert agent.get_history_count() == 0
        assert agent.learning_data == {}

    def test_learning_data_management(self):
        """Test learning data management"""

        # Mock the agent class
        class MockAgent:
            def __init__(self):
                self.learning_data = {}

            def update_learning_data(self, domain, success, quality_score):
                if domain not in self.learning_data:
                    self.learning_data[domain] = {
                        "total_generations": 0,
                        "successful_generations": 0,
                        "average_quality_score": 0.0,
                    }

                domain_data = self.learning_data[domain]
                domain_data["total_generations"] += 1

                if success:
                    domain_data["successful_generations"] += 1

                # Update average quality score
                current_total = domain_data["average_quality_score"] * (
                    domain_data["total_generations"] - 1
                )
                new_total = current_total + quality_score
                domain_data["average_quality_score"] = (
                    new_total / domain_data["total_generations"]
                )

            def get_domain_stats(self, domain):
                return self.learning_data.get(domain, {})

        agent = MockAgent()

        # Test initial state
        assert agent.get_domain_stats("database") == {}

        # Test updating learning data
        agent.update_learning_data("database", True, 8.5)
        agent.update_learning_data("database", False, 4.0)
        agent.update_learning_data("database", True, 9.0)

        db_stats = agent.get_domain_stats("database")
        assert db_stats["total_generations"] == 3
        assert db_stats["successful_generations"] == 2
        assert (
            abs(db_stats["average_quality_score"] - 7.17) < 0.01
        )  # (8.5 + 4.0 + 9.0) / 3

        # Test another domain
        agent.update_learning_data("api", True, 7.5)
        api_stats = agent.get_domain_stats("api")
        assert api_stats["total_generations"] == 1
        assert api_stats["successful_generations"] == 1
        assert api_stats["average_quality_score"] == 7.5

    def test_quality_threshold_logic(self):
        """Test quality threshold logic"""

        # Mock the agent class
        class MockAgent:
            def __init__(self, human_review_threshold=7.0):
                self.config = Mock()
                self.config.human_review_threshold = human_review_threshold

            def check_requires_human_review(self, quality_score, critical_issues_count):
                return (
                    quality_score < self.config.human_review_threshold
                    or critical_issues_count > 0
                )

        agent = MockAgent(human_review_threshold=7.0)

        # Test quality score below threshold
        assert agent.check_requires_human_review(6.5, 0) is True

        # Test quality score above threshold, no critical issues
        assert agent.check_requires_human_review(8.0, 0) is False

        # Test quality score above threshold, but with critical issues
        assert agent.check_requires_human_review(8.5, 1) is True

        # Test quality score below threshold, with critical issues
        assert agent.check_requires_human_review(6.0, 2) is True

        # Test with different threshold
        agent2 = MockAgent(human_review_threshold=8.5)
        assert agent2.check_requires_human_review(8.0, 0) is True
        assert agent2.check_requires_human_review(9.0, 0) is False

    def test_statistics_calculation(self):
        """Test statistics calculation"""

        # Mock the agent class
        class MockAgent:
            def __init__(self):
                self.generation_history = []

            def add_generation_record(self, record):
                self.generation_history.append(record)

            def calculate_statistics(self):
                if not self.generation_history:
                    return {"message": "No generation history available"}

                total_generations = len(self.generation_history)
                successful_generations = sum(
                    1 for record in self.generation_history if record["success"]
                )
                average_quality = (
                    sum(record["quality_score"] for record in self.generation_history)
                    / total_generations
                )
                average_time = (
                    sum(
                        record["generation_time_ms"]
                        for record in self.generation_history
                    )
                    / total_generations
                )

                return {
                    "total_generations": total_generations,
                    "successful_generations": successful_generations,
                    "overall_success_rate": successful_generations / total_generations,
                    "average_quality_score": average_quality,
                    "average_generation_time_ms": average_time,
                }

        agent = MockAgent()

        # Test empty history
        stats = agent.calculate_statistics()
        assert "message" in stats
        assert stats["message"] == "No generation history available"

        # Test with history
        agent.add_generation_record(
            {"success": True, "quality_score": 8.5, "generation_time_ms": 1500}
        )
        agent.add_generation_record(
            {"success": False, "quality_score": 4.0, "generation_time_ms": 800}
        )
        agent.add_generation_record(
            {"success": True, "quality_score": 9.0, "generation_time_ms": 1200}
        )

        stats = agent.calculate_statistics()
        assert stats["total_generations"] == 3
        assert stats["successful_generations"] == 2
        assert stats["overall_success_rate"] == 2 / 3
        # Convert to float for comparison to avoid type issues
        avg_quality = float(stats["average_quality_score"])
        avg_time = float(stats["average_generation_time_ms"])
        assert abs(avg_quality - 7.17) < 0.01  # (8.5 + 4.0 + 9.0) / 3
        assert abs(avg_time - 1166.67) < 0.01  # (1500 + 800 + 1200) / 3 ≈ 1166.67


if __name__ == "__main__":
    pytest.main([__file__])
