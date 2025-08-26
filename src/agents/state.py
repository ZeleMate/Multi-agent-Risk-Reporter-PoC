from typing import TypedDict, Annotated, List, Dict, Any
from langgraph.graph.message import add_messages
from src.types import FlagItem

class OverallState(TypedDict):
    messages: Annotated[List[str], add_messages]
    chunks: List[Dict[str, Any]]
    project_context: str
    candidates: List[FlagItem]
    verified: List[FlagItem]
    report: str
    