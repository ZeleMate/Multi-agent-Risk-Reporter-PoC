"""Vector store module for ChromaDB integration."""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import chromadb
import torch
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB-based vector store for email chunks."""

    def __init__(
        self, collection_name: str = "email_chunks", persist_directory: str = ".vectorstore"
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
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
            elif torch.backends.mps.is_available():
                self.embedding_model.to("mps")

            self.collection = self.client.get_or_create_collection(
                name=self.collection_name, metadata={"hnsw:space": "cosine"}
            )

            logger.info(f"Vector store initialized: {self.collection_name}")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    def load_chunks(self, chunks_file: str) -> list[dict[str, Any]]:
        """Load chunks from JSON file."""
        try:
            with open(chunks_file, encoding="utf-8") as f:
                chunks = json.load(f)
            if isinstance(chunks, list):
                logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
                return chunks
            else:
                logger.warning(f"Loaded data is not a list: {type(chunks)}")
                return []
        except Exception as e:
            logger.error(f"Failed to load chunks from {chunks_file}: {e}")
            raise

    def generate_embeddings(
        self, texts: list[str], embed_batch_size: int = 32
    ) -> list[list[float]]:
        try:
            all_embeddings = []

            for i in range(0, len(texts), embed_batch_size):
                sub_texts = texts[i : i + embed_batch_size]
                inputs = self.tokenizer(
                    sub_texts, return_tensors="pt", padding=True, truncation=True, max_length=512
                )

                # Move to device
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                elif torch.backends.mps.is_available():  # type: ignore[attr-defined]
                    inputs = {k: v.to("mps") for k, v in inputs.items()}

                with torch.no_grad():
                    outputs = self.embedding_model(**inputs)
                    batch_embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()

                all_embeddings.extend([vec.tolist() for vec in batch_embeddings])

            return all_embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def _prepare_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        """Prepare metadata for ChromaDB storage."""
        prepared = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                prepared[key] = ", ".join(str(item) for item in value)
            else:
                prepared[key] = value
        return prepared

    @staticmethod
    def compute_chunk_hash(chunk: dict[str, Any]) -> str:
        """Compute hash for chunk."""
        text = chunk.get("text", "")
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def upsert_batch(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert batch into collection."""
        if self.collection is None:
            raise RuntimeError("Collection not initialized. Call initialize() first.")

        try:
            if hasattr(self.collection, "upsert"):
                self.collection.upsert(
                    documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
                )
            else:
                self.collection.add(
                    documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
                )
        except Exception as e:
            logger.warning(f"Upsert failed, falling back to add: {e}")
            self.collection.add(
                documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids
            )

    def store_chunks(
        self, chunks: list[dict[str, Any]], batch_size: int = 100, embed_batch_size: int = 32
    ) -> None:
        """Store chunks with embeddings in ChromaDB."""
        try:
            total_chunks = len(chunks)
            logger.info(f"Storing {total_chunks} chunks...")

            for i in range(0, total_chunks, batch_size):
                batch = chunks[i : i + batch_size]
                texts = [chunk["text"] for chunk in batch]
                ids = [chunk["id"] for chunk in batch]
                metadatas = [self._prepare_metadata(chunk["metadata"]) for chunk in batch]
                embeddings = self.generate_embeddings(texts, embed_batch_size=embed_batch_size)

                self.upsert_batch(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)
                logger.info(f"Stored batch {i//batch_size + 1}")

            logger.info(f"Stored {total_chunks} chunks")

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise

    def get_collection_info(self) -> dict[str, Any]:
        if self.collection is None:
            return {
                "collection_name": self.collection_name,
                "total_chunks": 0,
                "persist_directory": self.persist_directory,
            }

        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "persist_directory": self.persist_directory,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}


def process_chunks_to_vectorstore(
    input_dir: str,
    vectorstore_dir: str,
    collection_name: str = "email_chunks",
    batch_size: int = 100,
) -> dict[str, Any]:
    """Process chunks from input directory and store in vector database."""
    try:
        os.makedirs(vectorstore_dir, exist_ok=True)

        # Initialize vector store
        store = VectorStore(collection_name=collection_name, persist_directory=vectorstore_dir)
        store.initialize()

        # Load chunks
        chunks_file = Path(input_dir) / "chunks.json"
        if not chunks_file.exists():
            raise FileNotFoundError(f"chunks.json not found in {input_dir}")

        chunks = store.load_chunks(str(chunks_file))

        # Store all chunks
        if chunks:
            store.store_chunks(chunks, batch_size=batch_size)
            logger.info(f"Stored {len(chunks)} chunks")
        else:
            logger.info("No chunks to store")

        info = store.get_collection_info()
        logger.info(f"Vector store completed: {info}")
        return info

    except Exception as e:
        logger.error(f"Vector store processing failed: {e}")
        raise


def main() -> None:
    """CLI entry point for vector store creation."""
    parser = argparse.ArgumentParser(description="Create ChromaDB vector store from email chunks")
    parser.add_argument(
        "--input-dir", type=str, default="./data/clean", help="Directory containing chunks.json"
    )
    parser.add_argument(
        "--vectorstore-dir", type=str, default=".vectorstore", help="Directory for vector store"
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    try:
        info = process_chunks_to_vectorstore(
            input_dir=args.input_dir,
            vectorstore_dir=args.vectorstore_dir,
        )

        print("Vector store creation successful!")
        print(f"   Collection: {info['collection_name']}")
        print(f"   Total chunks: {info['total_chunks']}")
        print(f"   Location: {info['persist_directory']}")

    except Exception as e:
        print(f"Vector store creation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
