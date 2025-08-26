"""
Critical tests for vector store and retrieval functionality.
Tests the essential VectorStore and HybridRetriever classes for PoC.
"""

from unittest.mock import Mock, patch

from src.retrieval.retriever import HybridRetriever
from src.retrieval.store import VectorStore


class TestVectorStore:
    """Test critical VectorStore functionality."""

    def test_vector_store_initialization(self):
        """Test VectorStore initialization."""
        store = VectorStore(collection_name="test_collection", persist_directory="/tmp/test")
        assert store.collection_name == "test_collection"
        assert store.persist_directory == "/tmp/test"

    @patch("src.retrieval.store.chromadb.PersistentClient")
    @patch("src.retrieval.store.AutoTokenizer")
    @patch("src.retrieval.store.AutoModel")
    def test_vector_store_initialize_success(
        self, mock_auto_model, mock_tokenizer, mock_chroma_client
    ):
        """Test successful VectorStore initialization."""
        # Setup mocks
        mock_collection = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_or_create_collection.return_value = mock_collection

        mock_model_instance = Mock()
        mock_model_instance.eval.return_value = mock_model_instance

        mock_chroma_client.return_value = mock_client_instance
        mock_auto_model.from_pretrained.return_value = mock_model_instance
        mock_tokenizer.from_pretrained.return_value = Mock()

        # Test initialization
        store = VectorStore()
        store.initialize()

        assert store.client is not None
        assert store.collection is not None
        assert store.embedding_model is not None

    def test_compute_chunk_hash(self):
        """Test chunk hash computation."""
        store = VectorStore()
        chunk = {
            "text": "Test chunk text",
            "metadata": {"file": "test.txt", "line_start": 1, "line_end": 10},
        }

        hash1 = store.compute_chunk_hash(chunk)
        hash2 = store.compute_chunk_hash(chunk)

        # Same chunk should produce same hash
        assert hash1 == hash2
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 produces 64 character hex string

    def test_get_all_chunk_ids_empty_collection(self):
        """Test getting chunk IDs from empty collection."""
        store = VectorStore()
        store.collection = Mock()
        store.collection.get.return_value = {"ids": []}

        result = store.get_all_chunk_ids()
        assert result == []


class TestHybridRetriever:
    """Test critical HybridRetriever functionality."""

    def test_hybrid_retriever_initialization(self):
        """Test HybridRetriever initialization."""
        retriever = HybridRetriever(
            collection_name="test_collection",
            persist_directory="/tmp/test",
            top_k=5,
            prefilter_keywords=["blocker", "urgent"],
        )

        assert retriever.collection_name == "test_collection"
        assert retriever.top_k == 5
        assert "blocker" in retriever.prefilter_keywords

    @patch("src.retrieval.retriever.chromadb.PersistentClient")
    @patch("src.retrieval.retriever.AutoTokenizer")
    @patch("src.retrieval.retriever.AutoModel")
    def test_hybrid_retriever_initialize_success(
        self, mock_auto_model, mock_tokenizer, mock_chroma_client
    ):
        """Test successful HybridRetriever initialization."""
        # Setup mocks
        mock_collection = Mock()
        mock_client_instance = Mock()
        mock_client_instance.get_collection.return_value = mock_collection

        mock_model_instance = Mock()
        mock_model_instance.eval.return_value = mock_model_instance

        mock_chroma_client.return_value = mock_client_instance
        mock_auto_model.from_pretrained.return_value = mock_model_instance
        mock_tokenizer.from_pretrained.return_value = Mock()

        # Test initialization
        retriever = HybridRetriever()
        retriever.initialize()

        assert retriever.client is not None
        assert retriever.collection is not None

    def test_keyword_prefilter_with_matches(self):
        """Test keyword prefiltering with matching keywords."""
        retriever = HybridRetriever(prefilter_keywords=["blocker", "urgent"])
        retriever.collection = Mock()

        # Mock documents with keyword matches
        mock_docs = ["This is a blocker issue", "This is urgent", "This is normal"]
        mock_ids = ["chunk_1", "chunk_2", "chunk_3"]
        mock_metadatas = [{"file": "test1.txt"}, {"file": "test2.txt"}, {"file": "test3.txt"}]

        retriever.collection.get.return_value = {
            "documents": mock_docs,
            "ids": mock_ids,
            "metadatas": mock_metadatas,
        }

        result = retriever.keyword_prefilter("find issues")
        assert len(result) > 0

    def test_retrieve_with_prefilter(self):
        """Test retrieve method with keyword prefiltering."""
        retriever = HybridRetriever(prefilter_keywords=["blocker"])

        # Mock the internal methods
        retriever.keyword_prefilter = Mock(return_value=["chunk_1", "chunk_2"])
        retriever.semantic_search = Mock(
            return_value=[
                {
                    "id": "chunk_1",
                    "text": "Blocker issue",
                    "metadata": {"file": "test.txt"},
                    "score": 0.9,
                }
            ]
        )

        result = retriever.retrieve("find blockers", top_k=5)

        assert len(result) == 1
        assert result[0]["id"] == "chunk_1"
