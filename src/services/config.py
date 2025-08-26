"""
Configuration management for the multi-agent risk reporter.
Loads settings from YAML files and environment variables.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

@dataclass
class ModelConfig:
    """Configuration for LLM models."""
    provider: str = "openai"
    chat_model: str = "gpt-5-mini"
    temperature: float = 0.7
    max_output_tokens: int = 50000
    json_response: bool = True

@dataclass
class EmbeddingConfig:
    """Configuration for embedding models."""
    provider: str = "qwen"
    model_name: str = "Qwen/Qwen3-Embedding-0.6B"
    dimensions: int = 1024

@dataclass
class AgentModelsConfig:
    """Configuration for agent-specific models."""
    analyzer: str = "primary_model"    # Risk classification
    verifier: str = "primary_model"    # Evidence validation
    composer: str = "alternative_model" # Report generation (can use more capable model)

@dataclass
class AlternativeModelConfig:
    """Configuration for alternative model."""
    provider: str = "openai"
    chat_model: str = "gpt-5"
    temperature: float = 0.7
    max_output_tokens: int = 50000
    json_response: bool = True

@dataclass
class RetrievalConfig:
    """Configuration for retrieval system."""
    top_k: int = 10
    prefilter_keywords: List[str] = field(default_factory=lambda: [
        "blocker", "risk", "delayed", "waiting", "asap", "urgent", "deadline",
        "unresolved", "issue", "problem", "critical", "high priority", "error",
        "bug", "missing", "incomplete", "clarification", "question", "help"
    ])

@dataclass
class ChunkingConfig:
    """Configuration for text chunking."""
    chunk_size: int = 1000  # Target tokens per chunk
    overlap: int = 100      # Overlap tokens between chunks

@dataclass
class FlagsConfig:
    """Configuration for risk flags."""
    uhpai: Dict[str, Any] = field(default_factory=lambda: {
        "aging_days": 5,
        "role_weights": {
            "director": 2.0,
            "pm": 1.5,
            "ba": 1.2,
            "dev": 1.0
        }
    })
    erb: Dict[str, Any] = field(default_factory=lambda: {
        "critical_terms": [
            "blocked", "waiting on", "missing", "unclear", "cannot",
            "security", "payment", "prod", "critical", "urgent"
        ]
    })

@dataclass
class ScoringConfig:
    """Configuration for scoring system."""
    repeat_weight: float = 0.5
    topic_weight: float = 0.7
    age_weight: float = 0.8
    role_weight: float = 1.0

@dataclass
class ReportConfig:
    """Configuration for report generation."""
    top_n_per_project: int = 5

@dataclass
class AppConfig:
    """Main application configuration."""
    # Paths
    data_raw: str = "./data/raw"
    data_clean: str = "./data/clean"
    vectorstore_dir: str = ".vectorstore"
    report_dir: str = "./data/report"

    # API Keys
    openai_api_key: Optional[str] = None

    # Components
    model: ModelConfig = field(default_factory=ModelConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    alternative_model: AlternativeModelConfig = field(default_factory=AlternativeModelConfig)
    agent_models: AgentModelsConfig = field(default_factory=AgentModelsConfig)
    retrieval: RetrievalConfig = field(default_factory=RetrievalConfig)
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    flags: FlagsConfig = field(default_factory=FlagsConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    # Debug
    debug_logs: bool = False

    def __post_init__(self):
        """Load API key from environment."""
        self.openai_api_key = os.getenv("OPENAI_API_KEY")

class ConfigManager:
    """Manages configuration loading and validation."""

    @staticmethod
    def load_from_yaml(yaml_path: str) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Configuration file {yaml_path} not found, using defaults")
            return {}
        except Exception as e:
            logger.error(f"Failed to load configuration from {yaml_path}: {e}")
            return {}

    @classmethod
    def load_config(
        cls,
        config_dir: str = "./configs",
        model_config_file: str = "model.yaml",
        pipeline_config_file: str = "pipeline.yaml"
    ) -> AppConfig:
        """Load complete application configuration."""
        try:
            # Start with default configuration
            config = AppConfig()

            # Load model configuration
            model_path = Path(config_dir) / model_config_file
            if model_path.exists():
                model_data = cls.load_from_yaml(str(model_path))
                if model_data:
                    # Load primary model config
                    if "primary_model" in model_data:
                        primary_data = model_data["primary_model"]
                        config.model = ModelConfig(**primary_data)

                    # Load embedding config
                    if "embedding_model" in model_data:
                        embedding_data = model_data["embedding_model"]
                        config.embedding = EmbeddingConfig(**embedding_data)

                    # Load alternative model config
                    if "alternative_model" in model_data:
                        alt_data = model_data["alternative_model"]
                        config.alternative_model = AlternativeModelConfig(**alt_data)

                    # Load agent models config
                    if "agent_models" in model_data:
                        agent_data = model_data["agent_models"]
                        config.agent_models = AgentModelsConfig(**agent_data)

            # Load pipeline configuration
            pipeline_path = Path(config_dir) / pipeline_config_file
            if pipeline_path.exists():
                pipeline_data = cls.load_from_yaml(str(pipeline_path))

                if pipeline_data:
                    # Update retrieval config
                    if "retrieval" in pipeline_data:
                        ret_data = pipeline_data["retrieval"]
                        config.retrieval = RetrievalConfig(**ret_data)

                    # Update chunking config
                    if "chunking" in pipeline_data:
                        chunk_data = pipeline_data["chunking"]
                        config.chunking = ChunkingConfig(**chunk_data)

                    # Update flags config
                    if "flags" in pipeline_data:
                        flags_data = pipeline_data["flags"]
                        config.flags = FlagsConfig(**flags_data)

                    # Update scoring config
                    if "scoring" in pipeline_data:
                        scoring_data = pipeline_data["scoring"]
                        config.scoring = ScoringConfig(**scoring_data)

                    # Update report config
                    if "report" in pipeline_data:
                        report_data = pipeline_data["report"]
                        config.report = ReportConfig(**report_data)

            # Override with environment variables
            config.openai_api_key = os.getenv("OPENAI_API_KEY")
            config.data_raw = os.getenv("DATA_RAW", config.data_raw)
            config.data_clean = os.getenv("DATA_CLEAN", config.data_clean)
            config.vectorstore_dir = os.getenv("VECTORSTORE_DIR", config.vectorstore_dir)
            config.report_dir = os.getenv("REPORT_DIR", config.report_dir)
            # Debug flag
            debug_env = os.getenv("DEBUG_LOGS")
            if isinstance(debug_env, str):
                config.debug_logs = debug_env.lower() in ("1", "true", "yes", "on")

            logger.info("Configuration loaded successfully")
            return config

        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            # Return default config as fallback
            return AppConfig()

    @staticmethod
    def validate_config(config: AppConfig) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Check required API key
        if not config.openai_api_key:
            issues.append("OPENAI_API_KEY is required but not set")

        # Check paths exist
        if not Path(config.data_raw).exists():
            issues.append(f"Data raw directory does not exist: {config.data_raw}")

        # Check model configuration
        if config.model.temperature < 0 or config.model.temperature > 2:
            issues.append("Model temperature should be between 0 and 2")

        # Check chunking configuration
        if config.chunking.chunk_size <= config.chunking.overlap:
            issues.append("Chunk size should be greater than overlap")

        # Check retrieval configuration
        if config.retrieval.top_k <= 0:
            issues.append("Retrieval top_k should be positive")

        return issues

# Global configuration instance
_app_config: Optional[AppConfig] = None

def get_config() -> AppConfig:
    """Get the global application configuration."""
    global _app_config
    if _app_config is None:
        _app_config = ConfigManager.load_config()
    return _app_config

def reload_config() -> AppConfig:
    """Reload configuration from files."""
    global _app_config
    _app_config = ConfigManager.load_config()
    return _app_config

def validate_current_config() -> List[str]:
    """Validate the current configuration."""
    config = get_config()
    return ConfigManager.validate_config(config)
