import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.state import OverallState
from src.prompts.analyzer import get_analyzer_prompt, get_analyzer_system_prompt
from src.services.config import get_config
from src.types import AnalyzerResponse, FlagItem

logger = logging.getLogger(__name__)


def analyzer_agent(state: OverallState) -> AnalyzerResponse:
    """Analyzer agent."""
    config = get_config()
    model = ChatOpenAI(
        model=config.model.chat_model,
        temperature=config.model.temperature,
    )
    system_prompt = get_analyzer_system_prompt()

    # Use hybrid retrieval selected chunks or limit to config top_k
    all_chunks = state.get("chunks", [])
    max_chunks = getattr(config.retrieval, "top_k", 15) or 15

    # If chunks are already from hybrid retrieval (have score field), use as-is
    # Otherwise limit to top_k to reduce token usage
    if all_chunks and isinstance(all_chunks[0], dict) and "score" in all_chunks[0]:
        # Already filtered by hybrid retrieval, use all
        chunks = all_chunks
        logger.info(f"Using {len(chunks)} hybrid retrieval selected chunks")
    else:
        # Limit to max_chunks to reduce token usage
        chunks = all_chunks[:max_chunks]
        logger.info(f"Limited to {len(chunks)} chunks (max {max_chunks})")

    # Generate prompt and get response
    prompt_text = get_analyzer_prompt(chunks, state["project_context"], config)
    # Optional debug: persist analyzer prompts
    try:
        if getattr(config, "debug_logs", False):
            import os

            os.makedirs(config.report_dir, exist_ok=True)
            with open(
                os.path.join(config.report_dir, "analyzer_system_prompt.txt"), "w", encoding="utf-8"
            ) as f:
                f.write(system_prompt)
            with open(
                os.path.join(config.report_dir, "analyzer_prompt.txt"), "w", encoding="utf-8"
            ) as f:
                f.write(prompt_text)
    except Exception as e:
        logger.warning(f"Failed to write analyzer debug prompts: {e}")
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt_text),
    ]
    response_msg = model.invoke(messages)
    response_text = getattr(response_msg, "content", response_msg)

    # Parse YAML response
    try:
        import yaml  # type: ignore[import-untyped]

        response = yaml.safe_load(response_text)
    except Exception as e:
        logger.warning(f"Failed to parse YAML response: {e}, using raw text")
        response = response_text

    # Extract items from response
    items: list[dict[str, Any]] = []
    if isinstance(response, dict) and "items" in response:
        items = response["items"] or []
    elif isinstance(response, list):
        items = response
    elif isinstance(response, dict):
        items = [response]

    # Basic deduplication by title
    seen_titles = set()
    unique_items = []
    for item in items:
        title = (item.get("title") or "").strip().lower()
        if title not in seen_titles:
            seen_titles.add(title)
            unique_items.append(item)

    from typing import cast

    return AnalyzerResponse(items=cast(list[FlagItem], unique_items))
