"""Retrieval module for hybrid search over email chunks."""

import logging
import os
from typing import Any

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
import chromadb
import torch
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


class HybridRetriever:
    """Hybrid retriever with keyword prefiltering and vector search."""

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
            "urgent",
            "deadline",
            "error",
            "bug",
            "missing",
        ]

        self.client: Any | None = None
        self.collection: Any | None = None
        self.embedding_model: Any | None = None

    def initialize(self) -> None:
        """Initialize ChromaDB client and embedding model."""
        try:
            self.client = chromadb.PersistentClient(
                path=self.persist_directory, settings=Settings(anonymized_telemetry=False)
            )

            # Load model
            try:
                from src.services.config import get_config

                config = get_config()
                model_name = config.embedding.model_name
            except ImportError:
                model_name = "Qwen/Qwen3-Embedding-0.6B"

            self.tokenizer = AutoTokenizer.from_pretrained(
                model_name,
                trust_remote_code=False,
                revision="c54f2e6e80b2d7b7de06f51cec4959f6b3e03418",
            )
            self.embedding_model = AutoModel.from_pretrained(
                model_name,
                trust_remote_code=False,
                revision="c54f2e6e80b2d7b7de06f51cec4959f6b3e03418",
            )
            self.embedding_model.eval()

            # GPU/MPS support
            if torch.cuda.is_available():
                self.embedding_model.cuda()
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self.embedding_model.to("mps")

            self.collection = self.client.get_collection(name=self.collection_name)
            logger.info(f"Retriever initialized: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to initialize retriever: {e}")
            raise

    def keyword_prefilter(self, query: str) -> list[str]:
        """Perform keyword-based prefiltering."""
        try:
            if self.collection is None:
                logger.error("Collection not initialized. Call initialize() first.")
                return []
            results = self.collection.get(include=["documents"])
            if not results["documents"]:
                return []

            relevant_ids = []
            query_lower = query.lower()

            for doc_id, document in zip(results["ids"], results["documents"], strict=False):
                doc_lower = document.lower()

                # Check for query terms or prefilter keywords
                has_match = any(term in doc_lower for term in query_lower.split()) or any(
                    keyword in doc_lower for keyword in self.prefilter_keywords
                )

                if has_match:
                    relevant_ids.append(doc_id)

            logger.info(f"Prefilter found {len(relevant_ids)} chunks")
            return relevant_ids

        except Exception as e:
            logger.error(f"Prefilter failed: {e}")
            return []

    def generate_query_embedding(self, query: str) -> list[float]:
        try:
            if self.embedding_model is None:
                raise RuntimeError("Embedding model not initialized. Call initialize() first.")
            inputs = self.tokenizer(query, return_tensors="pt", truncation=True, max_length=512)

            # Move to device
            if torch.cuda.is_available():
                inputs = {k: v.cuda() for k, v in inputs.items()}
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                inputs = {k: v.to("mps") for k, v in inputs.items()}

            with torch.no_grad():
                outputs = self.embedding_model(**inputs)
                embedding = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()

            return embedding.tolist()  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise

    def semantic_search(
        self, query: str, candidate_ids: list[str] | None = None, top_k: int = 10
    ) -> list[dict[str, Any]]:
        if self.collection is None:
            logger.error("Collection not initialized. Call initialize() first.")
            return []

        try:
            query_embedding = self.generate_query_embedding(query)

            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )

            # Filter by candidate IDs if provided
            if candidate_ids:
                ids = results.get("ids", [[]])[0]
                filtered_indices = [i for i, doc_id in enumerate(ids) if doc_id in candidate_ids]

                if filtered_indices:
                    for key in ["ids", "documents", "metadatas", "distances"]:
                        if key in results and results[key]:
                            results[key][0] = [results[key][0][i] for i in filtered_indices[:top_k]]
                else:
                    # No matches, return empty
                    for key in ["ids", "documents", "metadatas", "distances"]:
                        if key in results:
                            results[key][0] = []

            # Format results
            formatted_results = []
            for i, (doc_id, document, metadata, distance) in enumerate(
                zip(
                    results.get("ids", [[]])[0],
                    results.get("documents", [[]])[0],
                    results.get("metadatas", [[]])[0],
                    results.get("distances", [[]])[0],
                    strict=False,
                )
            ):
                formatted_results.append(
                    {
                        "id": doc_id,
                        "text": document,
                        "metadata": metadata,
                        "score": 1 - distance,
                        "rank": i + 1,
                    }
                )

            logger.info(f"Semantic search: {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def retrieve(self, query: str, top_k: int | None = None) -> list[dict[str, Any]]:
        try:
            k = top_k or self.top_k

            # Keyword prefiltering
            candidate_ids = None
            if self.prefilter_keywords:
                candidate_ids = self.keyword_prefilter(query)
                if not candidate_ids:
                    logger.info("No prefilter candidates, using semantic search only")

            # Semantic search
            results = self.semantic_search(query, candidate_ids=candidate_ids, top_k=k)
            results.sort(key=lambda x: x["score"], reverse=True)

            logger.info(f"Retrieval: {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []

    def get_collection_stats(self) -> dict[str, Any]:
        if self.collection is None:
            return {
                "collection_name": self.collection_name,
                "total_chunks": 0,
            }

        try:
            return {
                "collection_name": self.collection_name,
                "total_chunks": self.collection.count(),
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}


def create_retriever(
    vectorstore_dir: str = ".vectorstore",
    collection_name: str = "email_chunks",
    top_k: int = 10,
    prefilter_keywords: list[str] | None = None,
) -> HybridRetriever:
    retriever = HybridRetriever(
        collection_name=collection_name,
        persist_directory=vectorstore_dir,
        top_k=top_k,
        prefilter_keywords=prefilter_keywords,
    )
    retriever.initialize()
    return retriever


def test_retrieval() -> None:
    """Test retriever with sample queries."""
    try:
        retriever = create_retriever()
        queries = ["risks", "blockers", "login page"]

        for query in queries:
            print(f"\n{query}:")
            results = retriever.retrieve(query, top_k=2)
            for result in results[:2]:
                print(f"  {result['score']:.2f} - {result['text'][:60]}...")

    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_retrieval()
