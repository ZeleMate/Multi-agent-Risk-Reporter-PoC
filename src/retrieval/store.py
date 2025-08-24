"""
Vector Store Module for ChromaDB integration.
Handles storing chunks with embeddings for retrieval.
"""

import json
import logging
import os
from typing import List, Dict, Any, Optional
import argparse
from pathlib import Path

import chromadb
from chromadb.config import Settings
import torch
from transformers import AutoModel, AutoTokenizer

logger = logging.getLogger(__name__)

class VectorStore:
    """
    ChromaDB-based vector store for email chunks.
    """

    def __init__(self, collection_name: str = "email_chunks", persist_directory: str = ".vectorstore"):
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
                path=self.persist_directory,
                settings=Settings(anonymized_telemetry=False)
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
                self.embedding_model = self.embedding_model.to('mps')

            # Get or create collection
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )

            logger.info(f"Vector store initialized at {self.persist_directory}")
            logger.info(f"Collection '{self.collection_name}' ready with model {model_name}")

        except Exception as e:
            logger.error(f"Failed to initialize vector store: {e}")
            raise

    def load_chunks(self, chunks_file: str) -> List[Dict[str, Any]]:
        """Load chunks from JSON file."""
        try:
            with open(chunks_file, 'r', encoding='utf-8') as f:
                chunks = json.load(f)
            logger.info(f"Loaded {len(chunks)} chunks from {chunks_file}")
            return chunks
        except Exception as e:
            logger.error(f"Failed to load chunks from {chunks_file}: {e}")
            raise

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for text chunks using Qwen model."""
        try:
            embeddings = []

            for text in texts:
                # Tokenize the text
                inputs = self.tokenizer(text, return_tensors='pt', padding=True, truncation=True, max_length=512)

                # Move inputs to same device as model
                if torch.cuda.is_available():
                    inputs = {k: v.cuda() for k, v in inputs.items()}
                elif torch.backends.mps.is_available():
                    inputs = {k: v.to('mps') for k, v in inputs.items()}

                # Generate embeddings
                with torch.no_grad():
                    outputs = self.embedding_model(**inputs)
                    # Use the last hidden state and average pooling for sentence embedding
                    embedding = outputs.last_hidden_state.mean(dim=1).squeeze().cpu().numpy()

                embeddings.append(embedding.tolist())

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate embeddings: {e}")
            raise

    def _prepare_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare metadata for ChromaDB storage."""
        prepared = {}
        for key, value in metadata.items():
            if isinstance(value, list):
                # Convert lists to comma-separated strings
                if key == 'participants':
                    prepared[key] = ', '.join(str(item) for item in value)
                else:
                    prepared[key] = ', '.join(str(item) for item in value)
            elif isinstance(value, (str, int, float, bool)) or value is None:
                prepared[key] = value
            else:
                # Convert other types to string
                prepared[key] = str(value)
        return prepared

    def store_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 100):
        """Store chunks with embeddings in ChromaDB."""
        try:
            total_chunks = len(chunks)
            logger.info(f"Starting to store {total_chunks} chunks...")

            for i in range(0, total_chunks, batch_size):
                batch = chunks[i:i + batch_size]
                texts = [chunk['text'] for chunk in batch]
                ids = [chunk['id'] for chunk in batch]

                # Prepare metadata for ChromaDB
                metadatas = [self._prepare_metadata(chunk['metadata']) for chunk in batch]

                # Generate embeddings for batch
                embeddings = self.generate_embeddings(texts)

                # Add to collection
                self.collection.add(
                    documents=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )

                logger.info(f"Stored batch {i//batch_size + 1}/{(total_chunks + batch_size - 1)//batch_size}")

            logger.info(f"Successfully stored {total_chunks} chunks in vector store")

        except Exception as e:
            logger.error(f"Failed to store chunks: {e}")
            raise

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            count = self.collection.count()
            return {
                "collection_name": self.collection_name,
                "total_chunks": count,
                "persist_directory": self.persist_directory
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}


def process_chunks_to_vectorstore(
    input_dir: str,
    vectorstore_dir: str,
    collection_name: str = "email_chunks",
    batch_size: int = 100
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
        store = VectorStore(
            collection_name=collection_name,
            persist_directory=vectorstore_dir
        )
        store.initialize()

        # Find chunks file
        chunks_file = Path(input_dir) / "chunks.json"
        if not chunks_file.exists():
            raise FileNotFoundError(f"chunks.json not found in {input_dir}")

        # Load and store chunks
        chunks = store.load_chunks(str(chunks_file))
        store.store_chunks(chunks, batch_size=batch_size)

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
    parser.add_argument("--input-dir", type=str, default="./data/clean",
                       help="Directory containing chunks.json")
    parser.add_argument("--vectorstore-dir", type=str, default=".vectorstore",
                       help="Directory for vector store persistence")
    parser.add_argument("--collection-name", type=str, default="email_chunks",
                       help="Name of the ChromaDB collection")
    parser.add_argument("--batch-size", type=int, default=100,
                       help="Batch size for processing")

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    try:
        info = process_chunks_to_vectorstore(
            input_dir=args.input_dir,
            vectorstore_dir=args.vectorstore_dir,
            collection_name=args.collection_name,
            batch_size=args.batch_size
        )

        print("✅ Vector store creation successful!")
        print(f"   Collection: {info['collection_name']}")
        print(f"   Total chunks: {info['total_chunks']}")
        print(f"   Location: {info['persist_directory']}")

    except Exception as e:
        print(f"❌ Vector store creation failed: {e}")
        exit(1)


if __name__ == "__main__":
    main()
