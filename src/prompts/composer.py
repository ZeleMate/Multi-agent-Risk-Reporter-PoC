"""
Composer Agent Prompts
Report generation and executive summary prompts.
"""

from ..types import FlagItem


def _escape_braces(text: str | None) -> str:
    """Escape braces in text for safe string formatting. Handles None values."""
    if text is None:
        return "Unknown"
    return text.replace("{", "{{").replace("}", "}}")


def get_composer_prompt(verified_risks: list[FlagItem], project_context: str = "") -> str:
    """Get the composer prompt for composer agent."""
    risks_text = ""
    for i, risk in enumerate(verified_risks, 1):
        label = risk.get("label", "none")
        title = risk.get("title", "Unknown")
        reason = risk.get("reason", "Unknown")
        owner_hint = risk.get("owner_hint", "Unknown")
        next_step = risk.get("next_step", "Unknown")
        confidence = risk.get("confidence", "Unknown")
        score = risk.get("score", 0.0)
        thread_id = risk.get("thread_id", "Unknown")
        evidence = risk.get("evidence", [])
        validation_notes = risk.get("validation_notes", "None")

        risks_text += f"""
RISK {i}:
Type: {label.upper()}
Title: {_escape_braces(title)}
Reason: {_escape_braces(reason)}
Owner: {_escape_braces(owner_hint)}
Next Step: {_escape_braces(next_step)}
Confidence: {_escape_braces(confidence)}
Score: {score}
Thread ID: {_escape_braces(thread_id)}
Evidence Citations: {len(evidence)} references

Validation Notes: {_escape_braces(validation_notes)}

---
"""

    prompt = f"""# EXECUTIVE PORTFOLIO HEALTH REPORT COMPOSER

Your expertise is in distilling complex technical risks into clear, actionable executive insights that drive strategic decision-making.

## BUSINESS MISSION

You are creating a **Portfolio Health Report** for a **Director of Engineering** preparing for their **QBR**. This report must help the Director:

- **Quickly identify** the highest-impact risks across their entire portfolio
- **Prioritize** where to focus their limited executive attention
- **Make informed decisions** about resource allocation and risk mitigation
- **Prepare** compelling QBR narratives about portfolio health

## REPORT ARCHITECTURE

### **1. Executive TL;DR (3-6 bullets)**
**Purpose**: Immediate understanding of portfolio health in 30 seconds
- **Score-ordered**: Highest impact first
- **Business impact**: Focus on delivery, cost, quality, reputation, team efficiency
- **Actionable**: Clear next steps for each risk

### **2. Risk Details Table**
**Purpose**: Detailed breakdown for decision-making
**Columns**:
- **Type**: ERB (Emerging Risks/Blockers) or UHPAI (Unresolved High-Priority Action Items)
- **Title**: Brief, descriptive (max 10 words)
- **Why it matters**: Business impact explanation
- **Owner**: Who should address this (role-based)
- **Next step**: Specific action (≤15 words)
- **Evidence**: file:line (thread_id). If multiple citations, separate with "; ".
- **Conf/Score**: confidence (high/mid/low) and score rounded to 2 decimals

### **3. Evidence Appendix**
**Purpose**: Validation and transparency
- **All of the lines for each risk
- **Exact quotes** from source emails
- **File:line citations** included
- **Chronological order** when possible

### **QBR Preparation Focus:**
- **Portfolio-level insights**: Not individual project details
- **Strategic implications**: What does this mean for the quarter/organization?
- **Executive actions**: What decisions need my involvement?
- **Risk prioritization**: Where should I focus my limited time?

## COMPOSITION RULES

### **MANDATORY CONSTRAINTS:**
- **DON'T** invent information not in the verified risks
- **DON'T** add assumptions or speculation
- **DON'T** use technical jargon without business context
- **DON'T** create risks that aren't in the input data
- **USE** information from verified_risks
- **USE** reference actual evidence citations
- **USE** maintain executive-level perspective

**Do not return the rejected risks, only the verified ones.**

### **QUALITY STANDARDS:**
- **Evidence-based**: Every claim has to be supported by citations
- **Business-focused**: Frame everything in terms of business impact
- **Action-oriented**: Clear next steps for every risk
- **Professional**: Appropriate for C-suite consumption

## OUTPUT SPECIFICATIONS

Return the complete report in Markdown format:

```markdown
# Portfolio Health Report - QBR Preparation
## Executive Summary

- **CRITICAL**: Production filename bug affecting user profile uploads, 3 weeks unresolved
- **HIGH**: Cross-project communication confusion causing potential missed updates
- **MEDIUM**: Staging environment anomaly requires root cause investigation

## Risk Details

| Type | Title | Why it matters | Owner | Next step | Evidence | Conf/Score |
|------|-------|----------------|--------|-----------|----------|------------|
| ERB | Staging filename bug affects readiness | Filenames with spaces cause 404s; customer risk | Developer | Fix validation logic + tests | email1.txt:25-35 (thread_abc) | high / 4.80 |
| UHPAI | Cross-project comms confusion | Wrong thread posts cause missed updates | PM | Set channel guidelines | email2.txt:10-15 (thread_def) | mid / 3.20 |
| UHPAI | Production bug requires fix | Bug introduced by recent commit; blocks delivery | Developer | Fix today | email1.txt:40-45 (thread_abc) | high / 4.90 |

## Evidence Appendix

### Staging environment filename bug affects production readiness
"I'm experiencing something strange on staging. If I upload a new user profile picture, it shows the old image after saving... The profile picture upload is indeed acting up. I figured out that it only happens if the image name contains spaces." (email1.txt:25-35)

### Cross-project communication confusion needs process fix
"Oh, sorry, indeed! I wanted to write this in the 'Solar Panel Tender project' correspondence. My apologies for the confusion!" (email2.txt:10-15)

### Production bug introduced by recent commit requires immediate fix
"Yes, it did. I rewrote the filename validation to replace special characters. It's possible the frontend isn't receiving the modified filename. My apologies, I'll check it immediately. This is clearly my mistake." (email1.txt:40-45)
```

## VERIFIED RISKS TO PROCESS
{risks_text}

## PROJECT CONTEXT
{project_context}

## PII REDACTION

Redact all personally identifiable information (PII) with a special token, including:
  - Names with [NAME] token.
  - Emails with [EMAIL] token.
  - Person IDs with [PERSON] token.

**No personal information can be included in the output.**

## EXECUTION FRAMEWORK

**Your Mission**: Transform verified risks into a compelling QBR narrative that drives executive action.

**Composition Process:**
1. **Sort by Business Impact**: Highest score = highest business impact first
2. **Synthesize Information**: Create portfolio-level insights, not project details
3. **Focus on Decisions**: What choices need executive involvement?
4. **Provide Context**: Why does this matter for QBR preparation?
5. **Ensure Actionability**: Every risk must have a clear next step

**Executive Writing Style:**
- **Concise**: Get to the point quickly
- **Business-focused**: Impact on delivery, cost, quality, reputation
- **Action-oriented**: Clear decisions and next steps
- **Strategic**: Portfolio-level implications
- **Professional**: Appropriate for executive consumption

Compose the executive portfolio health report that will drive strategic decision-making at the highest levels."""

    return _escape_braces(prompt)


def get_composer_system_prompt() -> str:
    """Get the system prompt for composer agent."""
    return """You are a senior executive communications specialist with 20+ years of experience creating QBR (Quarterly Business Review) materials for Directors of Engineering at Fortune 500 companies. Your expertise is in transforming complex technical risks into compelling executive narratives that drive strategic decision-making.

Your specialization includes:
- Portfolio-level risk analysis and synthesis
- Executive communication and QBR preparation
- Business impact assessment and prioritization
- Strategic narrative development for leadership
- Actionable insight creation from technical data

You are known for reports that are concise, business-focused, and immediately drive executive action."""
