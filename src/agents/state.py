from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from src.types import FlagItem


class OverallState(TypedDict):
    messages: Annotated[list[str], add_messages]
    chunks: list[dict[str, Any]]
    project_context: str
    candidates: list[FlagItem]
    verified: list[FlagItem]
    report: str
