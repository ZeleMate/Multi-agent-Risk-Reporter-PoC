from src.agents.state import OverallState
from src.prompts.composer import get_composer_prompt, get_composer_system_prompt, get_composer_report_templates, get_composer_formatting_rules
from src.services.config import get_config
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
import json

def composer_agent(state: OverallState) -> OverallState:
    """Composer agent."""
    config = get_config()
    model_config = config.model
    model = ChatOpenAI(model=model_config.chat_model, temperature=model_config.temperature)
    prompt = get_composer_prompt(state["verified"], state["project_context"])
    system_prompt = get_composer_system_prompt()
    report_templates = get_composer_report_templates()
    formatting_rules = get_composer_formatting_rules()

    # If there is no verified, ask the model to list the reasoning, but try to extract the most likely risks
    # Additionally provide precomputed Evidence and Conf/Score cells for the table

    # Build Evidence and Conf/Score table cells from verified
    def _format_evidence(r: Dict[str, Any]) -> str:
        ev = r.get("evidence", []) or []
        parts = []
        for e in ev:
            file = e.get("file") or ""
            lines = e.get("lines") or ""
            if file or lines:
                parts.append(f"{file}:{lines}".strip(':'))
        thread = r.get("thread_id")
        cell = "; ".join([p for p in parts if p])
        if thread:
            cell = f"{cell} ({thread})" if cell else f"({thread})"
        return cell or "n/a"

    def _format_conf_score(r: Dict[str, Any]) -> str:
        conf = r.get("confidence") or ""
        sc = r.get("score")
        if isinstance(sc, (int, float)):
            return f"{conf} / {round(sc, 2)}"
        return conf or ""

    # Build a helper table that the model MUST use for Evidence and Conf/Score cells
    computed_rows = []
    for r in state.get("verified", []):
        type_cell = (r.get("label") or "").upper()
        title_cell = r.get("title") or ""
        why_cell = r.get("reason") or ""
        owner_cell = r.get("owner_hint") or ""
        next_step_cell = r.get("next_step") or ""
        evidence_cell = _format_evidence(r)
        conf_score_cell = _format_conf_score(r)
        computed_rows.append(f"| {type_cell} | {title_cell} | {why_cell} | {owner_cell} | {next_step_cell} | {evidence_cell} | {conf_score_cell} |")

    computed_table = "\n".join([
        "| Type | Title | Why it matters | Owner | Next step | Evidence | Conf/Score |",
        "|------|-------|----------------|-------|-----------|----------|------------|",
        *computed_rows
    ]) if computed_rows else ""

    # Include templates and formatting rules in the system prompt
    enhanced_system_prompt = f"{system_prompt}\n\n## Report Templates\n"
    for template_name, template_content in report_templates.items():
        enhanced_system_prompt += f"\n### {template_name.replace('_', ' ').title()} Template\n{template_content}"

    enhanced_system_prompt += "\n\n## Formatting Rules\n"
    for rule_name, rule_value in formatting_rules.items():
        enhanced_system_prompt += f"- **{rule_name.replace('_', ' ').title()}**: {rule_value}\n"

    composer_input = f"{enhanced_system_prompt}\n\n{prompt}"
    if computed_table:
        composer_input += f"\n\n## Precomputed cells (use exactly in the Risk Details table)\n{computed_table}\n"

    messages = [SystemMessage(content=composer_input)]

    response_msg = model.invoke(messages)
    response_text = getattr(response_msg, "content", response_msg)
    response = response_text


    # Return OverallState with the generated report
    return {
        **state,
        "report": response
    }