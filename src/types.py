"""Type definitions for multi-agent risk reporter."""

from typing import Any, Literal, TypedDict

Label = Literal["erb", "uhpai", "none"]
Confidence = Literal["low", "mid", "high"]


class EvidenceSpan(TypedDict):
    file: str
    lines: str


class FlagItem(TypedDict, total=False):
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


class Chunk(TypedDict):
    """Text chunk with metadata."""

    id: str
    text: str
    metadata: dict[str, Any]


class EmailData(TypedDict, total=False):
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
    thread_id: str
    file_path: str
    total_emails: int
    participants: list[str]
    subject: str
    canonical_subject: str
    start_date: str
    end_date: str
    emails: list[EmailData]


class SearchResult(TypedDict):
    id: str
    text: str
    metadata: dict[str, Any]
    score: float
    rank: int


class PipelineState(TypedDict, total=False):
    chunks: list[Chunk]
    candidates: list[FlagItem]
    verified: list[FlagItem]
    report: str
    config: dict[str, Any]


# Agent response types
class AnalyzerResponse(TypedDict):
    items: list[FlagItem]


class VerifierResponse(TypedDict):
    verified: list[FlagItem]


class ComposerResponse(TypedDict):
    report: str


# Configuration types
class ModelConfig(TypedDict, total=False):
    provider: str
    chat_model: str
    temperature: float
    max_output_tokens: int


class PipelineConfig(TypedDict, total=False):
    retrieval: dict[str, Any]
    flags: dict[str, Any]
    scoring: dict[str, Any]
    report: dict[str, Any]
