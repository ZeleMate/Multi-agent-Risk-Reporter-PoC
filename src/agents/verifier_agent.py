import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.state import OverallState
from src.prompts.verifier import get_verifier_prompt, get_verifier_system_prompt
from src.services.config import get_config
from src.types import VerifierResponse

logger = logging.getLogger(__name__)


def verifier_agent(state: OverallState) -> VerifierResponse:
    """Verifier agent."""
    config = get_config()
    model = ChatOpenAI(
        model=config.model.chat_model,
        temperature=config.model.temperature,
    )

    # Generate prompt and get response
    prompt = get_verifier_prompt(state.get("candidates", []), state.get("chunks", []))
    system_prompt = get_verifier_system_prompt()

    # Optional debug: persist verifier prompts
    try:
        if getattr(config, "debug_logs", False):
            import os
            os.makedirs(config.report_dir, exist_ok=True)
            with open(os.path.join(config.report_dir, "verifier_system_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(system_prompt)
            with open(os.path.join(config.report_dir, "verifier_prompt.txt"), "w", encoding="utf-8") as f:
                f.write(prompt)
    except Exception as e:
        logger.warning(f"Failed to write verifier debug prompts: {e}")

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt),
    ]

    response_msg = model.invoke(messages)
    response_text = getattr(response_msg, "content", response_msg)

    # Parse YAML response
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(response_text)
    except Exception as e:
        logger.warning(f"Failed to parse YAML response: {e}, using raw text")
        data = response_text

    # Extract verified items
    if isinstance(data, dict) and "verified" in data:
        verified = data["verified"]
    elif isinstance(data, list):
        verified = data
    elif isinstance(data, dict):
        verified = [data]
    else:
        verified = []

    return VerifierResponse(verified=verified)
