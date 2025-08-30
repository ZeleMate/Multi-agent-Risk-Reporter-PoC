from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.state import OverallState
from src.prompts.composer import get_composer_prompt, get_composer_system_prompt
from src.services.config import get_config
from src.types import ComposerResponse


def composer_agent(state: OverallState) -> ComposerResponse:
    """Composer agent."""
    config = get_config()
    model = ChatOpenAI(
        model=config.model.chat_model,
        temperature=config.model.temperature,
    )
    prompt = get_composer_prompt(state["verified"], state["project_context"])
    system_prompt = get_composer_system_prompt()

    # Combine system prompt and user prompt
    full_prompt = f"{system_prompt}\n\n{prompt}"

    messages = [SystemMessage(content=full_prompt)]
    response_msg = model.invoke(messages)
    response_text = getattr(response_msg, "content", response_msg)

    return ComposerResponse(report=response_text)
