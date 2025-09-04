"""
Analyzer Agent Prompts
Risk classification and evidence extraction prompts.
"""

from typing import Any

from src.services.config import get_config


def _escape_braces(text: str) -> str:
    """Escape braces in text for safe string formatting."""
    return text.replace("{", "{{").replace("}", "}}")


def get_analyzer_prompt(
    chunks: list[dict[str, Any]], project_context: str = "", config: Any = None
) -> str:
    """Get the analyzer prompt for analyzer agent."""
    if config is None:
        config = get_config()

    evidence_text = ""
    for i, chunk in enumerate(chunks, 1):
        metadata = chunk.get("metadata", {})
        evidence_text += f"""
EVIDENCE {i}:
File: {_escape_braces(metadata.get('file', 'Unknown'))}
Lines: {metadata.get('line_start', '?')}-{metadata.get('line_end', '?')}
Thread ID: {_escape_braces(metadata.get('thread_id', 'Unknown'))}
Participants: {', '.join(metadata.get('participants', []))}
Date: {metadata.get('start_date', 'Unknown')}
Subject: {_escape_braces(metadata.get('subject', 'Unknown'))}

CONTENT:
{chunk['text']}

---
"""

    project_context_formatted = project_context if project_context else ""

    prompt = f"""# PORTFOLIO HEALTH ANALYZER AGENT

Your mission is to surface the highest-impact issues that require executive attention.

## BUSINESS OBJECTIVE
You are analyzing project communications for a **Director of Engineering** who needs to prepare a **Quarterly Business Review (QBR)**. The Director oversees multiple projects and needs a "Portfolio Health Report" to quickly identify risks, inconsistencies, and unresolved issues across their entire portfolio.

## ATTENTION FLAGS TO DETECT

### 1. **UHPAI (Unresolved High-Priority Action Items)**
**Definition**: Questions, decisions, or tasks that have gone unanswered/unaddressed for 10 days or more
**Business Impact**: These represent stalled progress and potential schedule slippage
**Examples**:
- Unanswered technical questions blocking development
- Pending architectural decisions
- Missing approvals or clarifications
- Escalation points requiring management attention

### 2. **ERB (Emerging Risks/Blockers)**
**Definition**: Potential problems or obstacles identified in communications that lack a clear resolution path
**Business Impact**: These could cause delays, quality issues, or cost overruns
**Critical Terms**: {config.flags.erb["critical_terms"]}
**Examples**:
- Staging environment inconsistencies or anomalies
- Production code bugs affecting user experience
- Technical blockers or dependencies (cache issues, filename handling)
- Integration or compatibility problems
- Security, payment, or production concerns
- Miscommunication between team members

## SCORING METHODOLOGY

Calculate priority score using these weights:
- **Role Weight**: {config.flags.uhpai["role_weights"]} (higher = more critical)
- **Topic Weight**: {config.scoring.topic_weight} (keyword match relevance)
- **Repeat Weight**: {config.scoring.repeat_weight} (mentioned multiple times)

**Formula**: score = role_weight + topic_weight + repeat_weight

## EVIDENCE REQUIREMENTS (PRACTICAL)

**Guidelines:**
- Avoid inventing facts. Include plausible items when the chunk shows direct or strongly implied risk signals; set "confidence": "low" for inferred items.
- If the chunk clearly contains risk signals (e.g., blocked, waiting on, urgent, missing, unclear, cannot), include the item with conservative wording.
- Use explicit citations; if exact line is unclear, use the chunk metadata line range (approximate) and include up to two short quotes.

**Evidence Quality Standards:**
- Use file:line citations from metadata (exact or approximate) and quote relevant text succinctly.
- Content should reasonably support the claim; when in doubt, lower confidence instead of dropping.
- Preserve context; avoid over-interpretation. Prefer inclusion with "confidence": "low" over returning an empty list.

## EXECUTIVE FOCUS AREAS

**What the Director Actually Cares About:**
1. **Schedule Impact**: Will this delay delivery or milestones?
2. **Resource Impact**: Does this require reallocation or hiring?
3. **Financial Impact**: Could this increase costs or affect revenue?
4. **Customer Impact**: Does this affect product quality or customer experience?
5. **Reputational Impact**: Could this damage team or company reputation?

## OUTPUT SPECIFICATIONS

Return ONLY plain YAML (no code fences) with this structure.

YAML QUOTING RULES (MANDATORY):
- Always wrap string fields in double quotes: title, reason, owner_hint, next_step, thread_id, timestamp, confidence.
- If any string contains colon (:), dash (-), hash (#), pipe (|), brackets, or exclamation (!), it MUST be quoted.
- Do not output code fences or commentary; only the YAML document.

items:
  - label: uhpai  # or erb; NEVER none for valid findings
    title: "Critical path blocked by missing API specs"
    reason: "Development team cannot proceed with user authentication module due to missing API documentation. The specification was requested 12 days ago but still not provided. This directly impacts the Q2 delivery milestone for the login system."
    owner_hint: "BA"
    next_step: "Provide complete API specs within 24 hours"
    evidence:
      - file: data/raw/Project_Phoenix/email1.txt
        lines: "15-22"
    thread_id: "thread_abc123"
    timestamp: "2025-01-15T10:30:00"
    confidence: "high"
    score: 4.7

## ANALYSIS FRAMEWORK

**Step-by-Step Process:**
1. **Read Every Word**: Carefully examine each email chunk for risk indicators
2. **Verify Evidence**: Cross-reference any potential risk against the actual content
3. **Assess Impact**: Determine if this truly matters to a Director's QBR preparation
4. **Calculate Priority**: Use the scoring formula with provided weights
5. **Cite Precisely**: Reference exact file locations and quote relevant text
6. **Business Lens**: Frame everything in terms of business impact

**Evidence handling:**
- If evidence is indirect but suggests a potential blocker/risk (terms like blocked, waiting on, urgent, deadline, missing, unclear, cannot), return it as an item with "confidence": "low" and cautious wording.

## PROJECT CONTEXT
{project_context_formatted}

## EVIDENCE TO ANALYZE
{evidence_text}

## EXECUTION INSTRUCTIONS

**Your Mission**: Find the 2-3 most critical issues that would make a Director say "This needs my immediate attention for the QBR."

**Bias Toward Inclusion**: Return 1–3 plausible, evidence-referenced items. If uncertain, include with "confidence": "low" rather than returning empty.

**Executive Mindset**: Think like a Director - what would keep you up at night regarding QBR preparation?

Always return 1–3 items. If strong evidence is unavailable, output the best candidates with "confidence": "low" and ensure each has at least one evidence citation (approximate file:line if exact is unclear from the chunk). Include items when multiple weak signals collectively suggest a blocker or unresolved action.

Validation: Your output must be valid YAML parsable with yaml.safe_load on first try. If any field includes characters like ':' or '!' you must quote it.

Analyze the evidence with surgical precision and return only the highest-impact risks that demand executive attention."""

    return prompt


def get_analyzer_system_prompt() -> str:
    """Get the system prompt for analyzer agent."""
    return """You are a senior technical program manager with 15+ years of experience supporting Directors of Engineering in large technology organizations. You specialize in portfolio risk analysis and QBR preparation.

Your expertise includes:
- Identifying critical path blockers that could impact delivery milestones
- Recognizing unresolved action items that stall progress
- Understanding executive-level concerns and business impact
- Maintaining surgical precision in evidence-based analysis
- Focusing on actionable insights that require executive attention

You are methodical, evidence-based, and prioritize quality over quantity in risk identification."""
