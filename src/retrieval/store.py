"""
Vector Store Module for ChromaDB integration.
Handles storing chunks with embeddings for retrieval.
"""

import argparse
import hashlib
import json
import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import chromadb
import torch
from chromadb.config import Settings
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)


class VectorStore:
    """
    ChromaDB-based vector store for email chunks.
    """

    def __init__(
        self, collection_name: str = "email_chunks", persist_directory: str = ".vectorstore"
    ):
        self.collection_name = collection_name
        self.persist_directory = persist_directory
        self.client = None
        self.collection = None
        self.embedding_model = None

    def initialize(self):
        """Initialize ChromaDB client and embedding model."""
        try:
            # Initialize ChromaDB client with persistence
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

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"},  # Use cosine similarity
            )

            logger.info(f"Vector store initialized at {self.persist_directory}")
            logger.info(f"Collection '{self.collection_name}' ready with model {model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    def load_chunks(self, chunks_file: str) -> list[dict[str, Any]]:
        """Load chunks from JSON file."""
        try:
            with open(chunks_file, encoding="utf-8") as f:
                chunks = json.load(f)
            logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
            return chunks
        except Exception as e:
            logger.error(f"Failed to load chunks from {chunks_file}: {e}")
            raise

    def generate_embeddings(
        self, texts: list[str], embed_batch_size: int = 32
    ) -> list[list[float]]:
        """Generate embeddings for text chunks using Qwen model with micro-batching."""
        try:
            all_embeddings: list[list[float]] = []

            for i in range(0, len(texts), embed_batch_size):
                sub_texts = texts[i : i + embed_batch_size]

                # Tokenize the batch
                inputs = self.tokenizer(
                    sub_texts,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=512,
                )

                # Move inputs to same device as model
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                elif torch.backends.mps.is_available():
                    inputs = {k: v.to("mps") for k, v in inputs.items()}

                # Generate embeddings for the batch
                with torch.no_grad():
                    outputs = self.embedding_model(**inputs)
                    # Average pooling over sequence length
                    batch_embeddings = outputs.last_hidden_state.mean(dim=1).cpu().numpy()

                # Extend with each vector as list[float]
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
                # Convert lists to comma-separated strings
                if key == "participants":
                    prepared[key] = ", ".join(str(item) for item in value)
                else:
                    prepared[key] = ", ".join(str(item) for item in value)
            elif isinstance(value, str | int | float | bool) or value is None:
                prepared[key] = value
            else:
                # Convert other types to string
                prepared[key] = str(value)
        return prepared

    @staticmethod
    def compute_chunk_hash(chunk: dict[str, Any]) -> str:
        """Compute a stable hash for a chunk based on text and normalized metadata."""
        text = chunk.get("text") or ""
        metadata = chunk.get("metadata") or {}
        try:
            # Normalize metadata to stable string
            meta_str = json.dumps(metadata, sort_keys=True, ensure_ascii=False)
        except Exception:
            meta_str = str(metadata)
        h = hashlib.sha256()
        h.update(text.encode("utf-8"))
        h.update(b"|")
        h.update(meta_str.encode("utf-8"))
        return h.hexdigest()

    def upsert_batch(
        self,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
        embeddings: list[list[float]],
    ):
        """Upsert a batch into the collection, falling back to add if upsert not available."""
        try:
            # Some versions of chromadb support upsert
            if hasattr(self.collection, "upsert"):
                self.collection.upsert(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids,
                )
            else:
                self.collection.add(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids,
                )
        except Exception:
            # Fallback: try add (best effort)
            self.collection.add(
                documents=texts,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids,
            )

    def store_chunks(
        self, chunks: list[dict[str, Any]], batch_size: int = 100, embed_batch_size: int = 32
    ):
        """Store chunks with embeddings in ChromaDB."""
        try:
            total_chunks = len(chunks)
            logger.info(f"Starting to store {total_chunks} chunks...")

            for i in range(0, total_chunks, batch_size):
                batch = chunks[i : i + batch_size]
                texts = [chunk["text"] for chunk in batch]
                ids = [chunk["id"] for chunk in batch]

                # Prepare metadata for ChromaDB
                metadatas = [self._prepare_metadata(chunk["metadata"]) for chunk in batch]

                # Generate embeddings for batch
                embeddings = self.generate_embeddings(texts, embed_batch_size=embed_batch_size)

                # Upsert into collection
                self.upsert_batch(ids=ids, texts=texts, metadatas=metadatas, embeddings=embeddings)

                logger.info(
                    f"Stored batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}"
                )

            logger.info(f"Successfully stored {total_chunks} chunks in vector store")

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise

    def get_collection_info(self) -> dict[str, Any]:
        """Get information about the collection."""
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

    def get_all_chunk_ids(self) -> list[str]:
        """Get all chunk IDs from the collection."""
        if not self.collection:
            raise ValueError("Vector store not initialized")

        try:
            # Get all documents without limit to retrieve IDs
            result = self.collection.get(include=["documents"])
            return result.get("ids", [])
        except Exception as e:
            logger.error(f"Failed to get chunk IDs: {e}")
            return []


def process_chunks_to_vectorstore(
    input_dir: str,
    vectorstore_dir: str,
    collection_name: str = "email_chunks",
    batch_size: int = 100,
    embed_batch_size: int = 32,
    incremental: bool = True,
    prune_missing: bool = False,
):
    """
    Process chunks from input directory and store in vector database.

    Args:
        input_dir: Directory containing chunks.json
        vectorstore_dir: Directory for vector store persistence
        collection_name: Name of the ChromaDB collection
        batch_size: Batch size for processing
    """
    try:
        # Create vector store directory if it doesn't exist
        os.makedirs(vectorstore_dir, exist_ok=True)

        # Initialize vector store
        store = VectorStore(collection_name=collection_name, persist_directory=vectorstore_dir)
        store.initialize()

        # Find chunks file
        chunks_file = Path(input_dir) / "chunks.json"
        if not chunks_file.exists():
            raise FileNotFoundError(f"chunks.json not found in {input_dir}")

        # Load chunks
        chunks = store.load_chunks(str(chunks_file))

        # Incremental manifest path
        manifest_path = Path(vectorstore_dir) / f"{collection_name}_manifest.json"
        manifest: dict[str, Any] = {"version": 1, "items": {}}
        if incremental and manifest_path.exists():
            try:
                with open(manifest_path, encoding="utf-8") as f:
                    manifest = json.load(f) or manifest
            except Exception:
                manifest = {"version": 1, "items": {}}

        # Build plan: new or changed chunks
        items_manifest: dict[str, Any] = manifest.get("items", {})
        to_upsert: list[dict[str, Any]] = []
        for ch in chunks:
            cid = ch.get("id")
            if not cid:
                continue
            ch_hash = VectorStore.compute_chunk_hash(ch)
            prev = items_manifest.get(cid)
            if (not incremental) or (prev is None) or (prev.get("hash") != ch_hash):
                to_upsert.append(ch)

        # Optional prune of missing ids
        to_delete_ids: list[str] = []
        if incremental and prune_missing:
            current_ids = {ch.get("id") for ch in chunks if ch.get("id")}
            for mid in list(items_manifest.keys()):
                if mid not in current_ids:
                    to_delete_ids.append(mid)

        # Execute upserts
        if to_upsert:
            store.store_chunks(to_upsert, batch_size=batch_size, embed_batch_size=embed_batch_size)
        else:
            logger.info("No new or updated chunks to store (incremental up-to-date)")

        # Execute deletes (best effort)
        if to_delete_ids:
            try:
                store.collection.delete(ids=to_delete_ids)
                logger.info(f"Pruned {len(to_delete_ids)} missing chunks from collection")
            except Exception as e:
                logger.warning(f"Failed to prune some missing ids: {e}")

        # Update and persist manifest
        now_iso = datetime.now(UTC).isoformat()
        for ch in chunks:
            cid = ch.get("id")
            if not cid:
                continue
            items_manifest[cid] = {
                "hash": VectorStore.compute_chunk_hash(ch),
                "updated_at": now_iso,
            }
        manifest["items"] = items_manifest
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Failed to write manifest {manifest_path}: {e}")

        # Get final info
        info = store.get_collection_info()
        logger.info(f"Vector store creation completed: {info}")

        return info

    except Exception as e:
        logger.error(f"Vector store processing failed: {e}")
        raise


def main():
    """CLI entry point for vector store creation."""
    parser = argparse.ArgumentParser(description="Create ChromaDB vector store from email chunks")
    parser.add_argument(
        "--input-dir", type=str, default="./data/clean", help="Directory containing chunks.json"
    )
    parser.add_argument(
        "--vectorstore-dir",
        type=str,
        default=".vectorstore",
        help="Directory for vector store persistence",
    )
    parser.add_argument(
        "--collection-name",
        type=str,
        default="email_chunks",
        help="Name of the ChromaDB collection",
    )
    parser.add_argument(
        "--batch-size", type=int, default=100, help="Batch size (chunks per add call)"
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=32,
        help="Embedding micro-batch size (texts per forward pass)",
    )
    parser.add_argument(
        "--no-incremental",
        action="store_true",
        help="Disable incremental upsert (process all chunks)",
    )
    parser.add_argument(
        "--prune-missing",
        action="store_true",
        help="Delete entries from collection that are missing from chunks.json",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    try:
        info = process_chunks_to_vectorstore(
            input_dir=args.input_dir,
            vectorstore_dir=args.vectorstore_dir,
            collection_name=args.collection_name,
            batch_size=args.batch_size,
            embed_batch_size=args.embed_batch_size,
            incremental=not args.no_incremental,
            prune_missing=args.prune_missing,
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
