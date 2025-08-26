"""
Type definitions for the multi-agent risk reporter.
"""

from dataclasses import dataclass
from typing import Any, Literal, TypedDict

# Core type aliases
Label = Literal["erb", "uhpai", "none"]
Confidence = Literal["low", "mid", "high"]


class EvidenceSpan(TypedDict):
    """Evidence citation span."""

    file: str
    lines: str  # Format: "12-24"


class FlagItem(TypedDict, total=False):
    """Individual risk flag item."""

    label: Label
    title: str
    reason: str
    owner_hint: str
    next_step: str
    evidence: list[EvidenceSpan]
    thread_id: str
    timestamp: str
    confidence: Confidence
    score: float
    # Optional validation fields (set by verifier)
    validation_status: str  # e.g., "VERIFIED", "REJECTED"
    validation_notes: str
    rejection_reason: str


class ChunkMetadata(TypedDict, total=False):
    """Metadata for text chunks."""

    file: str
    line_start: int
    line_end: int
    thread_id: str
    total_emails: int
    participants: list[str]
    subject: str
    canonical_subject: str
    start_date: str
    end_date: str
    chunk_size: int
    sentence_count: int


class Chunk(TypedDict):
    """Text chunk with metadata."""

    id: str
    text: str
    metadata: ChunkMetadata


class EmailData(TypedDict, total=False):
    """Parsed email data structure."""

    sender_name: str
    sender_email: str
    sender_role: str
    to_recipients: list[dict[str, str]]
    cc_recipients: list[dict[str, str]]
    date: str
    date_normalized: str
    subject: str
    canonical_subject: str
    body: str


class ThreadData(TypedDict, total=False):
    """Email thread data structure."""

    thread_id: str
    file_path: str
    total_emails: int
    participants: list[str]
    subject: str
    canonical_subject: str
    start_date: str
    end_date: str
    emails: list[EmailData]


class ColleaguesData(TypedDict):
    """Colleagues data structure."""

    person_id: str
    name: str
    role: str
    email_redacted: str


class SearchResult(TypedDict):
    """Search result from retrieval."""

    id: str
    text: str
    metadata: ChunkMetadata
    score: float
    rank: int


class AgentMessage(TypedDict):
    """Message structure for agent communication."""

    role: str
    content: str
    metadata: dict[str, Any] | None


class PipelineState(TypedDict, total=False):
    """State for the LangGraph pipeline."""

    chunks: list[Chunk]
    candidates: list[FlagItem]
    verified: list[FlagItem]
    report: str
    config: dict[str, Any]


# Dataclasses for better structure
@dataclass
class RetrievalResult:
    """Structured result from retrieval system."""

    query: str
    results: list[SearchResult]
    total_found: int
    search_time: float
    filters_applied: dict[str, Any] | None = None


@dataclass
class ProcessingStats:
    """Statistics for data processing."""

    total_threads: int = 0
    total_emails: int = 0
    total_chunks: int = 0
    total_participants: int = 0
    processing_time: float = 0.0
    date_processed: str | None = None


# Response types for agents
class AnalyzerResponse(TypedDict):
    """Response from analyzer agent."""

    items: list[FlagItem]


class VerifierResponse(TypedDict):
    """Response from verifier agent."""

    verified: list[FlagItem]


class ComposerResponse(TypedDict):
    """Response from composer agent."""

    report: str


# Configuration types (used by config.py)
class ModelSettings(TypedDict, total=False):
    """Model configuration settings."""

    provider: str
    chat_model: str
    temperature: float
    max_output_tokens: int


class RetrievalSettings(TypedDict, total=False):
    """Retrieval configuration settings."""

    top_k: int
    prefilter_keywords: list[str]


class ChunkingSettings(TypedDict, total=False):
    """Chunking configuration settings."""

    chunk_size: int
    overlap: int


class FlagSettings(TypedDict, total=False):
    """Flag configuration settings."""

    uhpai: dict[str, Any]
    erb: dict[str, Any]


class ScoringSettings(TypedDict, total=False):
    """Scoring configuration settings."""

    repeat_weight: float
    topic_weight: float
    role_weight: float


class ReportSettings(TypedDict, total=False):
    """Report configuration settings."""

    top_n_per_project: int
