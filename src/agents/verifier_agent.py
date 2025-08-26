from src.agents.state import OverallState
from src.prompts.verifier import get_verifier_prompt, get_verifier_system_prompt, get_verifier_validation_criteria
from src.services.config import get_config
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.types import FlagItem
import json

def verifier_agent(state: OverallState) -> OverallState:
    """Verifier agent."""
    config = get_config()
    report_dir = getattr(config, "report_dir", "report")
    model_config = config.model
    model = ChatOpenAI(
        model=model_config.chat_model,
        temperature=max(0.7, model_config.temperature),
    )

    # The full_evidence comes from the chunks field
    prompt = get_verifier_prompt(state.get("candidates", []), state.get("chunks", []))
    system_prompt = get_verifier_system_prompt()
    validation_criteria = get_verifier_validation_criteria()

    # Single system message with full instructions
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response_msg = model.invoke(messages)
    response_text = getattr(response_msg, "content", response_msg)

    # Parse YAML
    try:
        import yaml
        data = yaml.safe_load(response_text)
    except Exception:
        data = response_text

    if isinstance(data, dict) and "verified" in data:
        verified = data["verified"]
    elif isinstance(data, list):
        verified = data
    elif isinstance(data, dict):
        verified = [data]
    else:
        verified = []


    # Debug: save only when enabled
    if getattr(config, "debug_logs", False):
        try:
            import os, json
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "verified.json"), "w", encoding="utf-8") as f:
                json.dump({"count": len(verified), "items": verified}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Return OverallState with the validated results
    return {
        **state,
        "verified": verified
    }