from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.state import OverallState
from src.prompts.composer import get_composer_prompt, get_composer_system_prompt
from src.services.config import get_config
from src.types import ComposerResponse


def composer_agent(state: OverallState) -> ComposerResponse:
    """Composer agent."""
    config = get_config()
    # Always use alternative model for composer (gpt-5)
    alt = config.alternative_model
    model = ChatOpenAI(
        model=alt.chat_model,
        temperature=alt.temperature,
    )
    prompt = get_composer_prompt(state["verified"], state["project_context"])
    system_prompt = get_composer_system_prompt()

    # Combine system prompt and user prompt
    full_prompt = f"{system_prompt}\n\n{prompt}"

    messages = [SystemMessage(content=full_prompt)]
    response_msg = model.invoke(messages)
    response_text = str(getattr(response_msg, "content", response_msg))

    return ComposerResponse(report=response_text)
