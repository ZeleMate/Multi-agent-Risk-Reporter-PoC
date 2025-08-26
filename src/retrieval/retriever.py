"""
Retrieval Module for hybrid search over email chunks.
Combines keyword-based prefiltering with vector similarity search.
"""

import logging
import os
import re
from typing import Any

# Disable parallelism in tokenizers BEFORE importing transformers to avoid fork warnings/deadlocks
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import chromadb
import torch
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Hybrid retriever combining BM25 keyword prefiltering with vector similarity search.
    """

    def __init__(
        self,
        collection_name: str = "email_chunks",
        persist_directory: str = ".vectorstore",
        top_k: int = 10,
        prefilter_keywords: list[str] | None = None,
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.top_k = top_k
        self.prefilter_keywords = prefilter_keywords or [
            "blocker",
            "risk",
            "delayed",
            "waiting",
            "asap",
            "urgent",
            "deadline",
            "unresolved",
            "issue",
            "problem",
            "critical",
            "high priority",
            "error",
            "bug",
            "missing",
            "incomplete",
            "clarification",
            "question",
            "help",
        ]

        self.client = None
        self.collection = None
        self.embedding_model = None

    def initialize(self):
        """Initialize ChromaDB client and embedding model."""
        try:
            # Avoid tokenizers parallelism + fork warnings/deadlocks
            os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
            # Initialize ChromaDB client
            self.client = chromadb.PersistentClient(
                path=self.persist_directory, settings=Settings(anonymized_telemetry=False)
            )

            # Load embedding model from config
            try:
                from src.services.config import get_config

                config = get_config()
                model_name = config.embedding.model_name
            except ImportError:
                # Fallback to default if config not available
                model_name = "Qwen/Qwen3-Embedding-0.6B"

            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.embedding_model = AutoModel.from_pretrained(model_name)

            # Set model to evaluation mode
            self.embedding_model.eval()

            # Move to GPU if available
            if torch.cuda.is_available():
                self.embedding_model = self.embedding_model.cuda()
            elif torch.backends.mps.is_available():
                self.embedding_model = self.embedding_model.to("mps")

            # Get collection
            self.collection = self.client.get_collection(name=self.collection_name)

            logger.info(
                f"Retriever initialized with collection '{self.collection_name}' and model {model_name}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize retriever: {e}")
            raise

    def keyword_prefilter(self, query: str) -> list[str]:
        """
        Perform keyword-based prefiltering to identify relevant chunks.

        Args:
            query: Search query

        Returns:
            List of chunk IDs that match keywords
        """
        try:
            # Get all documents from collection
            results = self.collection.get(include=["documents", "metadatas"])

            if not results["documents"]:
                return []

            relevant_ids = []

            # Check each document for keyword matches
            for doc_id, document, _metadatas in zip(
                results["ids"], results["documents"], results["metadatas"], strict=False
            ):
                # Check if document contains any prefilter keywords
                doc_lower = document.lower()

                # Check query terms
                query_terms = set(re.findall(r"\b\w+\b", query.lower()))
                keyword_matches = query_terms.intersection(set(self.prefilter_keywords))

                # Check if document contains query terms or prefilter keywords
                has_query_terms = any(term in doc_lower for term in query_terms)
                has_prefilter_keywords = any(
                    keyword in doc_lower for keyword in self.prefilter_keywords
                )

                if has_query_terms or has_prefilter_keywords or keyword_matches:
                    relevant_ids.append(doc_id)

            logger.info(f"Keyword prefiltering found {len(relevant_ids)} relevant chunks")
            return relevant_ids

        except Exception as e:
            logger.error(f"Keyword prefiltering failed: {e}")
            return []

    def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for query using Qwen model."""
        try:
            # Tokenize the query
            inputs = self.tokenizer(
                query, return_tensors="pt", padding=True, truncation=True, max_length=512
            )

            # Move inputs to same device as model
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            elif torch.backends.mps.is_available():
                inputs = {k: v.to("mps") for k, v in inputs.items()}

            # Generate embedding
            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
                # Use the last hidden state and average pooling for sentence embedding
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()

            return embedding.tolist()

        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            raise

    def semantic_search(
        self, query: str, candidate_ids: list[str] | None = None, top_k: int = 10
    ) -> list[dict[str, Any]]:
        """
        Perform semantic search using vector similarity.

        Args:
            query: Search query
            candidate_ids: Candidate chunk IDs from prefiltering
            top_k: Number of top results to return

        Returns:
            List of search results with metadata
        """
        try:
            # Generate query embedding using Qwen model
            query_embedding = self.generate_query_embedding(query)

            # Search in collection with candidate IDs
            # Note: For now, let's try without the where clause to see if that works
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            # Normalize result structure to lists-of-lists (Chroma may return flat lists)
            if isinstance(results, dict):
                for key in ["ids", "documents", "metadatas", "distances"]:
                    if key in results and isinstance(results[key], list) and results[key]:
                        if not isinstance(results[key][0], list):
                            results[key] = [results[key]]

            # If we have candidate IDs, filter the results
            if candidate_ids:
                filtered_indices = []
                ids0 = results.get("ids", [])
                ids0 = ids0[0] if isinstance(ids0, list) and ids0 else []
                for i, doc_id in enumerate(ids0):
                    if doc_id in candidate_ids:
                        filtered_indices.append(i)
                if filtered_indices:
                    for key in ["ids", "documents", "metadatas", "distances"]:
                        val = results.get(key)
                        if isinstance(val, list) and val:
                            seq = val[0]
                            if isinstance(seq, list):
                                results[key][0] = [seq[i] for i in filtered_indices][
                                    : min(len(filtered_indices), top_k)
                                ]
                else:
                    # No overlap with candidate_ids; fall back to empty filtered result lists
                    for key in ["ids", "documents", "metadatas", "distances"]:
                        val = results.get(key)
                        if isinstance(val, list) and val:
                            results[key][0] = []

            # Format results
            formatted_results = []
            for i, (doc_id, document, metadata, distance) in enumerate(
                zip(
                    results["ids"][0] if results["ids"] else [],
                    results["documents"][0] if results["documents"] else [],
                    results["metadatas"][0] if results["metadatas"] else [],
                    results["distances"][0] if results["distances"] else [], strict=False,
                )
            ):
                formatted_results.append(
                    {
                        "id": doc_id,
                        "text": document,
                        "metadata": metadata,
                        "score": 1 - distance,  # Convert distance to similarity score
                        "rank": i + 1,
                    }
                )

            logger.info(f"Semantic search found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        """
        Perform hybrid retrieval combining keyword prefiltering and semantic search.

        Args:
            query: Search query
            top_k: Number of results to return (overrides instance default)

        Returns:
            List of retrieved chunks with metadata and scores
        """
        try:
            k = top_k or self.top_k

            # Step 1: Keyword-based prefiltering (optional)
            candidate_ids: list[str] | None
            if self.prefilter_keywords:
                candidate_ids = self.keyword_prefilter(query)
                if not candidate_ids:
                    logger.info(
                        "No candidates from keyword prefiltering; falling back to pure semantic search"
                    )
                    candidate_ids = None
            else:
                candidate_ids = None

            # Step 2: Semantic search
            results = self.semantic_search(query, candidate_ids=candidate_ids, top_k=k)

            # Sort by score (highest first)
            results.sort(key=lambda x: x["score"], reverse=True)

            logger.info(f"Hybrid retrieval completed: {len(results)} results for query '{query}'")
            return results

        except Exception as e:
            logger.error(f"Hybrid retrieval failed: {e}")
            return []

    def retrieve_with_metadata_filter(
        self,
        query: str,
        metadata_filters: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retrieve with additional metadata filters.

        Args:
            query: Search query
            metadata_filters: Metadata filters (e.g., {"thread_id": "thread_123"})
            top_k: Number of results to return

        Returns:
            Filtered retrieval results
        """
        try:
            # Get base results
            results = self.retrieve(query, top_k=top_k)

            if not metadata_filters:
                return results

            # Apply metadata filters
            filtered_results = []
            for result in results:
                metadata = result.get("metadata", {})
                match = True

                for key, value in metadata_filters.items():
                    if key not in metadata or metadata[key] != value:
                        match = False
                        break

                if match:
                    filtered_results.append(result)

            logger.info(f"Metadata filtering: {len(results)} -> {len(filtered_results)} results")
            return filtered_results

        except Exception as e:
            logger.error(f"Metadata filtering failed: {e}")
            return []

    def get_collection_stats(self) -> dict[str, Any]:
        """Get statistics about the collection."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "prefilter_keywords": self.prefilter_keywords,
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {}


def create_retriever(
    vectorstore_dir: str = ".vectorstore",
    collection_name: str = "email_chunks",
    top_k: int = 10,
    prefilter_keywords: list[str] | None = None,
) -> HybridRetriever:
    """
    Factory function to create and initialize a HybridRetriever.

    Args:
        vectorstore_dir: Path to vector store directory
        collection_name: Name of the ChromaDB collection
        top_k: Default number of results to return
        prefilter_keywords: Keywords for prefiltering

    Returns:
        Initialized HybridRetriever instance
    """
    retriever = HybridRetriever(
        collection_name=collection_name,
        persist_directory=vectorstore_dir,
        top_k=top_k,
        prefilter_keywords=prefilter_keywords,
    )
    retriever.initialize()
    return retriever


def test_retrieval():
    """Simple test function for the retriever."""
    try:
        retriever = create_retriever()

        # Test queries
        test_queries = [
            "What are the main risks in the project?",
            "Are there any blockers or urgent issues?",
            "What is the status of the login page specification?",
        ]

        for query in test_queries:
            print(f"\nQuery: {query}")
            results = retriever.retrieve(query, top_k=3)

            for i, result in enumerate(results, 1):
                print(f"{i}. Score: {result['score']:.3f}")
                print(f"   Thread: {result['metadata'].get('thread_id', 'N/A')}")
                print(f"   File: {result['metadata'].get('file', 'N/A')}")
                print(f"   Text preview: {result['text'][:100]}...")

    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    test_retrieval()
