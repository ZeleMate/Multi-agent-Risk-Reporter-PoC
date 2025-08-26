import re
import logging
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

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
    metadata: Dict[str, Any]

class EmailChunker:
    """
    Chunks email threads according to AGENTS.md specification.
    - Chunk at thread scope (≈800–1200 tokens, with 80–120 overlap)
    - Preserve sentence IDs and file:line_start-line_end for citations
    """
    
    def __init__(self, chunk_size: int = 1000, overlap: int = 100):
        self.chunk_size = chunk_size
        self.overlap = overlap
        
    def estimate_tokens(self, text: str) -> int:
        """
        Rough token estimation (4 chars ≈ 1 token).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        return len(text) // 4
    
    def split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into sentences while preserving email structure.
        
        Args:
            text: Input text
            
        Returns:
            List of sentences
        """
        # Split by sentence endings, but preserve email headers
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Handle email-specific patterns
        result = []
        for sentence in sentences:
            # Don't split email headers
            if re.match(r'^(From|To|Cc|Date|Subject):', sentence):
                result.append(sentence)
            else:
                # Split long sentences if needed
                if len(sentence) > 200:
                    # Split by commas or other natural breaks
                    sub_sentences = re.split(r',\s+', sentence)
                    result.extend(sub_sentences)
                else:
                    result.append(sentence)
        
        return [s.strip() for s in result if s.strip()]
    
    def create_chunks_from_thread(self, thread_data: Dict[str, Any]) -> List[Chunk]:
        """
        Create chunks from an email thread with accurate line ranges.

        Args:
            thread_data: Thread data dictionary

        Returns:
            List of Chunk objects with accurate file:line citations
        """
        chunks = []
        thread_id = thread_data.get('thread_id', 'unknown')
        file_path = thread_data.get('file_path', 'unknown')

        # Read original file to get accurate line numbers
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                original_lines = f.readlines()
                original_content = ''.join(original_lines)
        except FileNotFoundError:
            logger.warning(f"Original file {file_path} not found, using approximate line numbers")
            original_lines = []
            original_content = ""

        # Find email boundaries in original file
        email_boundaries = []
        current_email_start = None

        for i, line in enumerate(original_lines):
            if line.startswith('From:'):
                if current_email_start is not None:
                    email_boundaries.append((current_email_start, i-1))
                current_email_start = i

        # Add last email
        if current_email_start is not None:
            email_boundaries.append((current_email_start, len(original_lines)-1))

        # Process emails with their original line ranges
        full_text = ""
        current_line_offset = 0
        email_line_mappings = []  # Track which lines belong to which email

        for i, email in enumerate(thread_data.get('emails', [])):
            if i < len(email_boundaries):
                email_start_line, email_end_line = email_boundaries[i]
            else:
                email_start_line = 0
                email_end_line = len(original_lines) - 1

            # Record line mapping for this email
            email_line_mappings.append({
                'email_index': i,
                'start_line': email_start_line,
                'end_line': email_end_line,
                'content_start': current_line_offset
            })

            # Add email header with line tracking
            email_header = f"From: {email.get('sender_name', 'Unknown')} [{email.get('sender_role', 'Unknown')}]\n"
            email_header += f"To: {', '.join([r.get('name', 'Unknown') for r in email.get('to_recipients', [])])}\n"
            email_header += f"Date: {email.get('date', 'Unknown')}\n"
            email_header += f"Subject: {email.get('subject', 'Unknown')}\n\n"

            full_text += email_header
            current_line_offset += 5  # Header lines + empty line

            # Add email body with line tracking
            body = email.get('body', '')
            full_text += body + "\n\n"
            current_line_offset += len(body.split('\n')) + 2

        # Split into sentences
        sentences = self.split_into_sentences(full_text)

        # Create chunks with accurate line mapping
        current_chunk = []
        current_tokens = 0
        chunk_start_line = 1

        def map_content_position_to_original_line(content_position):
            """Map content position to original file line using email mappings."""
            for mapping in email_line_mappings:
                if content_position >= mapping['content_start']:
                    # Calculate relative position within this email
                    relative_pos = content_position - mapping['content_start']
                    # Map to original file lines
                    return mapping['start_line'] + relative_pos
            return 1  # fallback

        for i, sentence in enumerate(sentences):
            sentence_tokens = self.estimate_tokens(sentence)

            # If adding this sentence would exceed chunk size
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk:
                # Create chunk with accurate line range
                chunk_text = ' '.join(current_chunk)
                chunk_id = f"{thread_id}_chunk_{len(chunks) + 1}"

                # Map chunk positions to original file lines using email mappings
                chunk_start_pos = sum(len(' '.join(sentences[:current_chunk_start])) + 1
                                    for current_chunk_start in range(len(current_chunk)))
                chunk_end_pos = chunk_start_pos + len(chunk_text)

                chunk_start_line = map_content_position_to_original_line(chunk_start_pos)
                chunk_end_line = map_content_position_to_original_line(chunk_end_pos)

                chunk = Chunk(
                    text=chunk_text,
                    chunk_id=chunk_id,
                    file=file_path,
                    line_start=chunk_start_line,
                    line_end=chunk_end_line,
                    thread_id=thread_id,
                    metadata={
                        'total_emails': thread_data.get('total_emails', 0),
                        'participants': thread_data.get('participants', []),
                        'subject': thread_data.get('subject', ''),
                        'canonical_subject': thread_data.get('canonical_subject', ''),
                        'start_date': thread_data.get('start_date', ''),
                        'end_date': thread_data.get('end_date', ''),
                        'chunk_size': current_tokens,
                        'sentence_count': len(current_chunk)
                    }
                )
                chunks.append(chunk)

                # Start new chunk with overlap
                overlap_sentences = current_chunk[-3:] if len(current_chunk) >= 3 else current_chunk
                current_chunk = overlap_sentences + [sentence]
                current_tokens = sum(self.estimate_tokens(s) for s in current_chunk)

                # Update line start for next chunk using email mappings
                overlap_start_pos = sum(len(' '.join(sentences[:len(current_chunk) - len(overlap_sentences)])) + 1
                                      for _ in range(len(overlap_sentences)))
                chunk_start_line = map_content_position_to_original_line(overlap_start_pos)
            else:
                current_chunk.append(sentence)
                current_tokens += sentence_tokens

        # Add final chunk if there's content
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            chunk_id = f"{thread_id}_chunk_{len(chunks) + 1}"

            # Map final chunk positions using email mappings
            final_chunk_start_pos = sum(len(' '.join(sentences[:len(sentences) - len(current_chunk)])) + 1
                                      for _ in range(len(current_chunk)))
            final_chunk_end_pos = final_chunk_start_pos + len(chunk_text)

            chunk_start_line = map_content_position_to_original_line(final_chunk_start_pos)
            chunk_end_line = map_content_position_to_original_line(final_chunk_end_pos)

            chunk = Chunk(
                text=chunk_text,
                chunk_id=chunk_id,
                file=file_path,
                line_start=chunk_start_line,
                line_end=chunk_end_line,
                thread_id=thread_id,
                metadata={
                    'total_emails': thread_data.get('total_emails', 0),
                    'participants': thread_data.get('participants', []),
                    'subject': thread_data.get('subject', ''),
                    'canonical_subject': thread_data.get('canonical_subject', ''),
                    'start_date': thread_data.get('start_date', ''),
                    'end_date': thread_data.get('end_date', ''),
                    'chunk_size': current_tokens,
                    'sentence_count': len(current_chunk)
                }
            )
            chunks.append(chunk)

        return chunks
    
    def chunk_threads(self, threads_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunk all threads and return structured data.
        
        Args:
            threads_data: List of thread data dictionaries
            
        Returns:
            List of chunk dictionaries ready for vector store
        """
        all_chunks = []
        
        for thread in threads_data:
            chunks = self.create_chunks_from_thread(thread)
            
            for chunk in chunks:
                chunk_dict = {
                    'id': chunk.chunk_id,
                    'text': chunk.text,
                    'metadata': {
                        'file': chunk.file,
                        'line_start': chunk.line_start,
                        'line_end': chunk.line_end,
                        'thread_id': chunk.thread_id,
                        **chunk.metadata
                    }
                }
                all_chunks.append(chunk_dict)
        
        logger.info(f"Created {len(all_chunks)} chunks from {len(threads_data)} threads")
        return all_chunks

def create_chunks(threads_data: List[Dict[str, Any]], chunk_size: int = 1000, overlap: int = 100) -> List[Dict[str, Any]]:
    """
    Convenience function to create chunks from thread data.
    
    Args:
        threads_data: List of thread data dictionaries
        chunk_size: Target chunk size in tokens
        overlap: Overlap size in tokens
        
    Returns:
        List of chunk dictionaries
    """
    chunker = EmailChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk_threads(threads_data)
