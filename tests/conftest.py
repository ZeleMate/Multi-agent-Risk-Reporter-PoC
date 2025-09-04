"""
Pytest configuration and shared fixtures for the multi-agent risk reporter tests.
"""

import os
import shutil
import tempfile
from unittest.mock import Mock, patch

import pytest

from src.services.config import AppConfig
from src.types import Chunk, EmailData, ThreadData


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    temp_path = tempfile.mkdtemp()
    yield temp_path
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture(scope="session")
def mock_config():
    """Create a mock configuration for testing."""
    config = AppConfig()

    # Override with test-specific values
    config.data_raw = "/tmp/test_data/raw"  # Use absolute path
    config.data_clean = "/tmp/test_data/clean"
    config.vectorstore_dir = "/tmp/test_vectorstore"
    config.report_dir = "/tmp/test_reports"
    config.openai_api_key = "test-key"

    # Test model config
    config.model.chat_model = "gpt-5-mini"
    config.model.temperature = 0.1

    return config


@pytest.fixture(scope="session")
def sample_email_data():
    """Sample email data for testing."""
    return EmailData(
        sender_name="John Doe",
        sender_email="john.doe@company.com",
        sender_role="developer",
        to_recipients=[{"name": "Jane Smith", "email": "jane.smith@company.com"}],
        cc_recipients=[],
        date="2024-01-15 10:30:00",
        date_normalized="2024-01-15T10:30:00",
        subject="Issue with deployment",
        canonical_subject="issue deployment",
        body="We are experiencing issues with the latest deployment. The application is not starting correctly.",
    )


@pytest.fixture(scope="session")
def sample_thread_data(sample_email_data):
    """Sample thread data for testing."""
    return ThreadData(
        thread_id="thread_001",
        file_path="./test_data/raw/sample.txt",
        total_emails=1,
        participants=["john.doe@company.com", "jane.smith@company.com"],
        subject="Issue with deployment",
        canonical_subject="issue deployment",
        start_date="2024-01-15T10:30:00",
        end_date="2024-01-15T10:30:00",
        emails=[sample_email_data],
    )


@pytest.fixture(scope="session")
def sample_chunks():
    """Sample chunks for testing."""
    chunks = []

    # Chunk 1 - ERB type (Emerging Risk/Blocker)
    chunk1 = Chunk(
        id="chunk_001",
        text="The application is completely blocked due to database connectivity issues. We cannot proceed with the deployment until this is resolved.",
        metadata={
            "file": "./test_data/raw/email1.txt",
            "line_start": 1,
            "line_end": 5,
            "thread_id": "thread_001",
            "total_emails": 1,
            "participants": ["john.doe@company.com"],
            "subject": "Database connectivity issue",
            "canonical_subject": "database connectivity issue",
            "start_date": "2024-01-15T10:30:00",
            "end_date": "2024-01-15T10:30:00",
            "chunk_size": 150,
            "sentence_count": 2,
        },
    )

    # Chunk 2 - UHPAI type (Unresolved High-Priority Action Item)
    chunk2 = Chunk(
        id="chunk_002",
        text="The security vulnerability in the payment module needs immediate attention. This is a high priority item that has been unresolved for 10 days.",
        metadata={
            "file": "./test_data/raw/email2.txt",
            "line_start": 1,
            "line_end": 4,
            "thread_id": "thread_002",
            "total_emails": 1,
            "participants": ["jane.smith@company.com"],
            "subject": "Security vulnerability - urgent",
            "canonical_subject": "security vulnerability urgent",
            "start_date": "2024-01-14T14:20:00",
            "end_date": "2024-01-14T14:20:00",
            "chunk_size": 120,
            "sentence_count": 2,
        },
    )

    # Chunk 3 - Neutral chunk (should not be flagged)
    chunk3 = Chunk(
        id="chunk_003",
        text="The team meeting is scheduled for tomorrow at 2 PM. We will discuss the project progress and next steps.",
        metadata={
            "file": "./test_data/raw/email3.txt",
            "line_start": 1,
            "line_end": 3,
            "thread_id": "thread_003",
            "total_emails": 1,
            "participants": ["manager@company.com"],
            "subject": "Team meeting reminder",
            "canonical_subject": "team meeting reminder",
            "start_date": "2024-01-16T09:00:00",
            "end_date": "2024-01-16T09:00:00",
            "chunk_size": 80,
            "sentence_count": 2,
        },
    )

    chunks.extend([chunk1, chunk2, chunk3])
    return chunks


@pytest.fixture(scope="session")
def mock_openai_response():
    """Mock OpenAI response for testing."""
    mock_response = Mock()
    mock_response.content = """
items:
  - label: "erb"
    title: "Database connectivity issue blocking deployment"
    reason: "Application is completely blocked due to database connectivity issues"
    owner_hint: "Database team"
    next_step: "Investigate and resolve database connectivity issue"
    evidence:
      - file: "./test_data/raw/email1.txt"
        lines: "1-5"
    thread_id: "thread_001"
    timestamp: "2024-01-15T10:30:00"
    confidence: "high"
    score: 0.9
"""
    return mock_response


@pytest.fixture(autouse=True)
def mock_env_vars():
    """Mock environment variables for tests."""
    with patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "test-key",
            "DEBUG_LOGS": "false",
            "DATA_RAW": "./test_data/raw",
            "DATA_CLEAN": "./test_data/clean",
            "VECTORSTORE_DIR": "./test_vectorstore",
            "REPORT_DIR": "./test_reports",
        },
    ):
        yield


@pytest.fixture
def mock_langchain_openai(mock_openai_response):
    """Mock LangChain OpenAI for testing."""
    with patch("src.services.config.ChatOpenAI") as mock_chat:
        mock_instance = Mock()
        mock_instance.invoke.return_value = mock_openai_response
        mock_chat.return_value = mock_instance
        yield mock_chat


@pytest.fixture
def mock_chroma_client():
    """Mock ChromaDB client for testing."""
    with patch("src.retrieval.store.chromadb.Client") as mock_client:
        mock_collection = Mock()
        mock_collection.add.return_value = None
        mock_collection.query.return_value = {
            "documents": [["Test document"]],
            "metadatas": [[{"file": "test.txt", "line_start": 1}]],
            "distances": [[0.1]],
            "ids": [["chunk_001"]],
        }

        mock_client_instance = Mock()
        mock_client_instance.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance
        yield mock_client


@pytest.fixture
def mock_huggingface_model():
    """Mock HuggingFace model for testing."""
    with patch("src.retrieval.store.AutoModel") as mock_model_class:
        mock_model = Mock()
        mock_model.eval.return_value = None
        mock_model.cuda.return_value = mock_model
        mock_model.to.return_value = mock_model
        mock_model.__call__.return_value.last_hidden_state = [[[0.1, 0.2, 0.3] * 128]]

        mock_model_class.from_pretrained.return_value = mock_model
        yield mock_model_class


@pytest.fixture
def mock_tokenizer():
    """Mock tokenizer for testing."""
    with patch("src.retrieval.store.AutoTokenizer") as mock_tokenizer_class:
        mock_tokenizer = Mock()
        mock_tokenizer.__call__.return_value = {
            "input_ids": [[1, 2, 3, 4, 5]],
            "attention_mask": [[1, 1, 1, 1, 1]],
        }

        mock_tokenizer_class.from_pretrained.return_value = mock_tokenizer
        yield mock_tokenizer_class
