from langchain_core.messages import SystemMessage
from typing import Any
from langchain_openai import ChatOpenAI
from openai import BadRequestError

from src.agents.state import OverallState
from src.prompts.composer import get_composer_prompt, get_composer_system_prompt
from src.services.config import get_config
from src.types import ComposerResponse


def composer_agent(state: OverallState) -> ComposerResponse:
    """Composer agent."""
    config = get_config()
    # Always use alternative model for composer (gpt-5)
    alt = config.alternative_model
    # Prefer explicit reasoning_effort per latest docs, with graceful fallback if unsupported.
    try:
        model = ChatOpenAI(
            model=alt.chat_model,
            reasoning_effort=alt.reasoning_effort,
            temperature=alt.temperature,
        )
    except TypeError:
        # If this SDK version doesn't accept reasoning_effort, fall back without it
        model = ChatOpenAI(
            model=alt.chat_model,
            temperature=alt.temperature,
        )
        print("Fallback to without reasoning_effort")
    prompt = get_composer_prompt(state["verified"], state["project_context"])
    system_prompt = get_composer_system_prompt()

    # Combine system prompt and user prompt
    full_prompt = f"{system_prompt}\n\n{prompt}"

    messages = [SystemMessage(content=full_prompt)]
    try:
        response_msg = model.invoke(messages)
        print("Response received with reasoning_effort")
    except BadRequestError as e:
        # If API rejects reasoning_effort, retry once without it
        if "Unknown parameter" in str(e) or "reasoning_effort" in str(e):
            model = ChatOpenAI(
                model=alt.chat_model,
                temperature=alt.temperature,
            )
            response_msg = model.invoke(messages)
            print("Fallback to without reasoning_effort")
        else:
            raise

    response_text = str(getattr(response_msg, "content", response_msg))

    return ComposerResponse(report=response_text)