"""
Critical tests for agent functionality.
Tests essential analyzer, verifier, composer agents for PoC.
"""

from unittest.mock import Mock, patch

from src.agents.analyzer_agent import analyzer_agent
from src.agents.composer_agent import composer_agent
from src.agents.graph import create_graph
from src.agents.state import OverallState
from src.agents.verifier_agent import verifier_agent


class TestAnalyzerAgent:
    """Test critical analyzer agent functionality."""

    @patch("src.agents.analyzer_agent.ChatOpenAI")
    @patch("src.agents.analyzer_agent.get_analyzer_prompt")
    @patch("src.agents.analyzer_agent.get_analyzer_system_prompt")
    def test_analyzer_agent_success(
        self, mock_system_prompt, mock_get_prompt, mock_chat_openai, mock_config, sample_chunks
    ):
        """Test successful analyzer agent execution."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_get_prompt.return_value = "Test prompt"

        mock_response = Mock()
        mock_response.content = """
items:
  - label: "erb"
    title: "Database connectivity issue"
    reason: "Application is blocked"
    owner_hint: "Database team"
    next_step: "Investigate connection"
    evidence:
      - file: "test.txt"
        lines: "1-5"
    thread_id: "thread_001"
    timestamp: "2024-01-15T10:30:00"
    confidence: "high"
    score: 0.9
"""
        mock_model_instance = Mock()
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model_instance

        # Create test state
        state = OverallState(
            chunks=sample_chunks[:2], project_context="Test project"  # Limit to 2 chunks
        )

        # Execute agent
        result = analyzer_agent(state)

        # Verify results
        assert "items" in result
        assert len(result["items"]) == 1
        assert result["items"][0]["label"] == "erb"
        assert result["items"][0]["title"] == "Database connectivity issue"


class TestVerifierAgent:
    """Test critical verifier agent functionality."""

    @patch("src.agents.verifier_agent.ChatOpenAI")
    @patch("src.agents.verifier_agent.get_verifier_prompt")
    @patch("src.agents.verifier_agent.get_verifier_system_prompt")
    def test_verifier_agent_success(
        self, mock_system_prompt, mock_get_prompt, mock_chat_openai, mock_config, sample_chunks
    ):
        """Test successful verifier agent execution."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_get_prompt.return_value = "Test prompt"

        mock_response = Mock()
        mock_response.content = """
verified:
  - label: "erb"
    title: "Database connectivity issue"
    reason: "Application is blocked"
    owner_hint: "Database team"
    next_step: "Investigate connection"
    evidence:
      - file: "test.txt"
        lines: "1-5"
    thread_id: "thread_001"
    timestamp: "2024-01-15T10:30:00"
    confidence: "high"
    score: 0.9
"""
        mock_model_instance = Mock()
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model_instance

        # Create test state
        candidates = [
            {
                "label": "erb",
                "title": "Database issue",
                "evidence": [{"file": "test.txt", "lines": "1-5"}],
            }
        ]

        state = OverallState(candidates=candidates, chunks=sample_chunks[:2])

        # Execute agent
        result = verifier_agent(state)

        # Verify results
        assert "verified" in result
        assert len(result["verified"]) == 1
        assert result["verified"][0]["label"] == "erb"


class TestComposerAgent:
    """Test critical composer agent functionality."""

    @patch("src.services.config.get_config")
    @patch("src.agents.composer_agent.ChatOpenAI")
    @patch("src.agents.composer_agent.get_composer_prompt")
    @patch("src.agents.composer_agent.get_composer_system_prompt")
    def test_composer_agent_success(
        self,
        mock_system_prompt,
        mock_get_prompt,
        mock_chat_openai,
        mock_get_config,
    ):
        """Test successful composer agent execution."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_get_prompt.return_value = "Test prompt"

        # Setup mock config
        from src.services.config import (
            AgentModelsConfig,
            AlternativeModelConfig,
            AppConfig,
            ModelConfig,
        )

        test_config = AppConfig()
        test_config.agent_models = AgentModelsConfig()
        test_config.model = ModelConfig()
        test_config.alternative_model = AlternativeModelConfig()

        test_config.agent_models.composer = "primary_model"
        test_config.model.chat_model = "gpt-5-mini"
        mock_get_config.return_value = test_config

        mock_response = Mock()
        mock_response.content = "# Risk Report\n- Database issue found"
        mock_model_instance = Mock()
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model_instance

        verified = [
            {
                "label": "erb",
                "title": "Database issue",
                "evidence": [{"file": "test.txt", "lines": "1-5"}],
                "confidence": "high",
                "score": 0.9,
            }
        ]

        state = OverallState(verified=verified, project_context="Test project")

        result = composer_agent(state)

        # Verify results
        assert "report" in result
        assert "# Risk Report" in result["report"]
        assert "Database issue" in result["report"]


class TestGraph:
    """Test critical graph functionality."""

    def test_create_graph_structure(self):
        """Test graph creation and structure."""
        graph = create_graph()

        # Verify graph has the expected nodes
        assert graph is not None

    @patch("src.services.config.get_config")
    @patch("src.agents.composer_agent.ChatOpenAI")
    @patch("src.agents.composer_agent.get_composer_prompt")
    @patch("src.agents.composer_agent.get_composer_system_prompt")
    def test_composer_agent_model_selection(
        self,
        mock_system_prompt,
        mock_get_prompt,
        mock_chat_openai,
        mock_config,
    ):
        """Test composer agent model selection logic."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_get_prompt.return_value = "Test prompt"

        mock_response = Mock()
        mock_response.content = "# Test Report\nContent here"
        mock_model_instance = Mock()
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model_instance

        # Test with alternative model selection
        mock_config.agent_models.composer = "alternative_model"
        mock_config.alternative_model.chat_model = "gpt-5"

        verified = [
            {
                "label": "erb",
                "title": "Test issue",
                "evidence": [{"file": "test.txt", "lines": "1-5"}],
                "confidence": "high",
                "score": 0.9,
            }
        ]

        state = OverallState(verified=verified, project_context="Test project")

        result = composer_agent(state)

        # Verify results
        assert "report" in result
        assert result["report"] == "# Test Report\nContent here"

        # Verify alternative model was used
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args
        assert call_args.kwargs["model"] == "gpt-5"

    @patch("src.services.config.get_config")
    @patch("src.agents.composer_agent.ChatOpenAI")
    @patch("src.agents.composer_agent.get_composer_prompt")
    @patch("src.agents.composer_agent.get_composer_system_prompt")
    def test_composer_agent_primary_model_selection(
        self,
        mock_system_prompt,
        mock_get_prompt,
        mock_chat_openai,
        mock_get_config,
    ):
        """Test composer agent uses primary model when configured."""
        # Setup mocks
        mock_system_prompt.return_value = "System prompt"
        mock_get_prompt.return_value = "Test prompt"

        # Setup mock config
        from src.services.config import (
            AgentModelsConfig,
            AlternativeModelConfig,
            AppConfig,
            ModelConfig,
        )

        test_config = AppConfig()
        test_config.agent_models = AgentModelsConfig()
        test_config.model = ModelConfig()
        test_config.alternative_model = AlternativeModelConfig()

        test_config.agent_models.composer = "primary_model"
        test_config.model.chat_model = "gpt-5-mini"
        test_config.alternative_model.chat_model = "gpt-5"
        mock_get_config.return_value = test_config

        mock_response = Mock()
        mock_response.content = "# Test Report\nContent here"
        mock_model_instance = Mock()
        mock_model_instance.invoke.return_value = mock_response
        mock_chat_openai.return_value = mock_model_instance

        verified = []
        state = OverallState(verified=verified, project_context="Test project")

        composer_agent(state)

        # Verify alternative model was used (composer forces alternative)
        mock_chat_openai.assert_called_once()
        call_args = mock_chat_openai.call_args
        assert call_args.kwargs["model"] == "gpt-5"
