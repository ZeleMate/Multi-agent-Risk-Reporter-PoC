import json
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.state import OverallState
from src.prompts.analyzer import get_analyzer_prompt, get_analyzer_system_prompt
from src.services.config import get_config
from src.types import AnalyzerResponse


def analyzer_agent(state: OverallState) -> AnalyzerResponse:
    """Analyzer agent."""
    config = get_config()
    report_dir = getattr(config, "report_dir", "report")
    model_config = config.model
    model = ChatOpenAI(
        model=model_config.chat_model,
        temperature=model_config.temperature,
    )
    system_prompt = get_analyzer_system_prompt()

    # Process a limited number of chunks to reduce token usage (enforce max 6)
    base_chunks = state.get("chunks", [])
    max_evidence = min(6, getattr(config.retrieval, "top_k", 6) or 6)
    if isinstance(base_chunks, list) and len(base_chunks) > max_evidence:
        base_chunks = base_chunks[:max_evidence]
    # Debug: optional file logging
    if getattr(config, "debug_logs", False):
        try:
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "chunks_debug.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "total_chunks": len(base_chunks) if isinstance(base_chunks, list) else 0,
                        "sample_ids": [
                            ch.get("id")
                            for ch in (base_chunks[:5] if isinstance(base_chunks, list) else [])
                        ],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except Exception:
            pass
    chunk_windows = [base_chunks] if isinstance(base_chunks, list) and base_chunks else []

    aggregated: list[dict[str, Any]] = []

    for idx, win in enumerate(chunk_windows):
        prompt_text = get_analyzer_prompt(win, state["project_context"], config)
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=prompt_text),
        ]
        response_msg = model.invoke(messages)
        response_text = getattr(response_msg, "content", response_msg)
        # Parse YAML (no code fences expected)
        try:
            import yaml

            response = yaml.safe_load(response_text)
        except Exception:
            response = response_text

        # Debug: save only when enabled
        if getattr(config, "debug_logs", False):
            try:
                import pathlib

                pathlib.Path(report_dir).mkdir(parents=True, exist_ok=True)
                with open(
                    os.path.join(report_dir, f"analyzer_window_{idx}.json"), "w", encoding="utf-8"
                ) as f:
                    f.write(
                        response_text
                        if isinstance(response_text, str)
                        else json.dumps(response, ensure_ascii=False, indent=2)
                    )
                with open(
                    os.path.join(report_dir, f"analyzer_prompt_{idx}.txt"), "w", encoding="utf-8"
                ) as f:
                    f.write(prompt_text)
            except Exception:
                pass

        items: list[dict[str, Any]] = []
        if isinstance(response, dict) and "items" in response:
            items = response["items"] or []
        elif isinstance(response, list):
            items = response
        elif isinstance(response, dict):
            items = [response]

        # basic dedup by (thread_id, title)
        for it in items:
            key = (it.get("thread_id"), (it.get("title") or "").strip().lower())
            if not any(
                (x.get("thread_id"), (x.get("title") or "").strip().lower()) == key
                for x in aggregated
            ):
                aggregated.append(it)

    candidates = aggregated

    # Debug: save candidates only when enabled
    if getattr(config, "debug_logs", False):
        try:
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "candidates.json"), "w", encoding="utf-8") as f:
                json.dump(
                    {"count": len(candidates), "items": candidates}, f, ensure_ascii=False, indent=2
                )
        except Exception:
            pass

    # Return OverallState with the identified candidates
    return AnalyzerResponse(items=candidates)
