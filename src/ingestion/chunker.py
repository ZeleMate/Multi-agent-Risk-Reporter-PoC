import hashlib
import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    text: str
    chunk_id: str
    file: str
    line_start: int
    line_end: int
    thread_id: str
    metadata: dict[str, Any]


class EmailChunker:
    """Chunks email threads into smaller pieces."""

    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap

    def estimate_tokens(self, text: str) -> int:
        """Rough token estimation (4 chars ≈ 1 token)."""
        return len(text) // 4

    def split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting by punctuation
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def create_chunks_from_thread(self, thread_data: dict[str, Any]) -> list[Chunk]:
        """Create chunks from an email thread."""
        chunks = []
        thread_id = thread_data.get("thread_id", "unknown")
        file_path = thread_data.get("file_path", "unknown")

        # Build full text from emails
        full_text = ""
        for email in thread_data.get("emails", []):
            email_header = f"From: {email.get('sender_name', 'Unknown')} [{email.get('sender_role', 'Unknown')}]\n"
            email_header += f"To: {', '.join([r.get('name', 'Unknown') for r in email.get('to_recipients', [])])}\n"
            email_header += f"Cc: {', '.join([r.get('name', 'Unknown') for r in email.get('cc_recipients', [])])}\n"
            email_header += f"Date: {email.get('date', 'Unknown')}\n"
            email_header += f"Subject: {email.get('subject', 'Unknown')}\n\n"

            full_text += email_header
            full_text += email.get("body", "") + "\n\n"

        # Split into sentences
        sentences = self.split_into_sentences(full_text)

        # Create chunks
        current_chunk: list[str] = []
        current_tokens = 0
        chunk_index = 0

        for sentence in sentences:
            sentence_tokens = self.estimate_tokens(sentence)

            # Check if adding sentence would exceed chunk size
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                # Create chunk
                chunk_text = " ".join(current_chunk)
                # Deterministic, content-based chunk id (stable across runs)
                digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
                chunk_id = f"{thread_id}_{chunk_index + 1}_{digest}"

                chunk = Chunk(
                    text=chunk_text,
                    chunk_id=chunk_id,
                    file=file_path,
                    line_start=chunk_index * 1000 + 1,  # Approximate line numbers
                    line_end=(chunk_index + 1) * 1000,
                    thread_id=thread_id,
                    metadata={
                        "total_emails": thread_data.get("total_emails", 0),
                        "participants": thread_data.get("participants", []),
                        "subject": thread_data.get("subject", ""),
                        "chunk_size": current_tokens,
                    },
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_count = min(3, len(current_chunk))
                current_chunk = current_chunk[-overlap_count:] + [sentence]
                current_tokens = sum(self.estimate_tokens(s) for s in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            digest = hashlib.sha256(chunk_text.encode("utf-8")).hexdigest()[:16]
            chunk_id = f"{thread_id}_{chunk_index + 1}_{digest}"

            chunk = Chunk(
                text=chunk_text,
                chunk_id=chunk_id,
                file=file_path,
                line_start=chunk_index * 1000 + 1,
                line_end=(chunk_index + 1) * 1000,
                thread_id=thread_id,
                metadata={
                    "total_emails": thread_data.get("total_emails", 0),
                    "participants": thread_data.get("participants", []),
                    "subject": thread_data.get("subject", ""),
                    "chunk_size": current_tokens,
                },
            )
            chunks.append(chunk)

        return chunks

    def chunk_threads(self, threads_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Chunk all threads and return structured data."""
        all_chunks = []

        for thread in threads_data:
            chunks = self.create_chunks_from_thread(thread)

            for chunk in chunks:
                chunk_dict = {
                    "id": chunk.chunk_id,
                    "text": chunk.text,
                    "metadata": {
                        "file": chunk.file,
                        "line_start": chunk.line_start,
                        "line_end": chunk.line_end,
                        "thread_id": chunk.thread_id,
                        **chunk.metadata,
                    },
                }
                all_chunks.append(chunk_dict)

        logger.info(f"Created {len(all_chunks)} chunks from {len(threads_data)} threads")
        return all_chunks


def create_chunks(
    threads_data: list[dict[str, Any]], chunk_size: int = 1000, overlap: int = 100
) -> list[dict[str, Any]]:
    """Convenience function to create chunks from thread data."""
    chunker = EmailChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk_threads(threads_data)
