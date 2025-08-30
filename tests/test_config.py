"""
Critical tests for configuration management.
Tests the essential ConfigManager and AppConfig functionality for PoC.
"""

import os

from src.services.config import ConfigManager


class TestConfigManager:
    """Test critical ConfigManager functionality."""

    def test_load_from_yaml_valid_file(self, temp_dir):
        """Test loading configuration from a valid YAML file."""
        yaml_content = """
primary_model:
  provider: openai
  chat_model: gpt-5-mini
  temperature: 0.5
  max_output_tokens: 1000

embedding_model:
  model_name: "Qwen/Qwen3-Embedding-0.6B"
"""

        yaml_path = os.path.join(temp_dir, "test_config.yaml")
        with open(yaml_path, "w") as f:
            f.write(yaml_content)

        result = ConfigManager.load_from_yaml(yaml_path)

        assert result is not None
        assert result["primary_model"]["chat_model"] == "gpt-5-mini"
        assert result["embedding_model"]["model_name"] == "Qwen/Qwen3-Embedding-0.6B"

    def test_load_from_yaml_missing_file(self):
        """Test loading configuration from a non-existent file."""
        result = ConfigManager.load_from_yaml("/nonexistent/path.yaml")
        assert result == {}

    def test_load_complete_config(self, temp_dir):
        """Test loading complete configuration from YAML files."""
        # Create mock YAML files
        model_yaml = """
primary_model:
  provider: openai
  chat_model: gpt-5-mini
  temperature: 0.5
  max_output_tokens: 1000

embedding_model:
  model_name: "Qwen/Qwen3-Embedding-0.6B"

agent_models:
  analyzer: "primary_model"
  verifier: "primary_model"
  composer: "alternative_model"
"""

        pipeline_yaml = """
retrieval:
  top_k: 15
  prefilter_keywords: ["blocker", "risk", "urgent"]

chunking:
  chunk_size: 1000
  overlap: 100

scoring:
  repeat_weight: 0.5
  topic_weight: 0.7
  role_weight: 1.0

flags:
  uhpai:
    aging_days: 5
    role_weights: {"director": 2.0, "pm": 1.5, "ba": 1.2, "dev": 1.0}
  erb:
    critical_terms: ["blocked", "waiting on", "missing", "urgent"]

report:
  top_n_per_project: 5
"""

        # Write files
        model_path = os.path.join(temp_dir, "model.yaml")
        pipeline_path = os.path.join(temp_dir, "pipeline.yaml")

        with open(model_path, "w") as f:
            f.write(model_yaml)
        with open(pipeline_path, "w") as f:
            f.write(pipeline_yaml)

        # Load config
        config = ConfigManager.load_config(
            config_dir=temp_dir,
            model_config_file="model.yaml",
            pipeline_config_file="pipeline.yaml",
        )

        # Verify critical settings
        assert config.model.chat_model == "gpt-5-mini"
        assert config.embedding.model_name == "Qwen/Qwen3-Embedding-0.6B"
        assert config.agent_models.analyzer == "primary_model"
        assert config.retrieval.top_k == 10
        assert config.chunking.chunk_size == 1000
        assert "blocker" in config.retrieval.prefilter_keywords
