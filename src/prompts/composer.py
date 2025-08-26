"""
Composer Agent Prompts
Report generation and executive summary prompts.
"""

from typing import List, Dict, Any
from ..types import FlagItem

def _escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")

def get_composer_prompt(verified_risks: List[FlagItem], project_context: str = "") -> str:
    """
    Generate composer prompt for executive report creation - PORTFOLIO HEALTH FOCUS.

    Args:
        verified_risks: List of verified risks from verifier
        project_context: Additional project context

    Returns:
        Formatted prompt for composer agent
    """

    # Format verified risks with enhanced detail
    risks_text = ""
    for i, risk in enumerate(verified_risks, 1):
        risks_text += f"""
RISK {i}:
Type: {risk.get('label', 'Unknown').upper()}
Title: {_escape_braces(risk.get('title', 'Unknown'))}
Reason: {_escape_braces(risk.get('reason', 'Unknown'))}
Owner: {_escape_braces(risk.get('owner_hint', 'Unknown'))}
Next Step: {_escape_braces(risk.get('next_step', 'Unknown'))}
Confidence: {_escape_braces(risk.get('confidence', 'Unknown'))}
Score: {risk.get('score', 0)}
Thread ID: {_escape_braces(risk.get('thread_id', 'Unknown'))}
Evidence Citations: {len(risk.get('evidence', []))} references
 
Validation Notes: {risk.get('validation_notes', 'None')}

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

def get_composer_report_templates() -> Dict[str, str]:
    """Get report templates for different scenarios."""
    return {
        "executive_summary": """
## Executive Summary

{bullet_points}

**Overall Risk Assessment:** {risk_level}
**Immediate Actions Required:** {action_count}
**Timeline Impact:** {timeline_impact}
""",

        "risk_table": """## Risk Details

| Type | Title | Why it matters | Owner | Next step | Evidence |
|------|-------|----------------|--------|-----------|----------|
{rows}
""",

        "evidence_section": """## Evidence Appendix

{evidence_entries}
""",

        "empty_report": """# Portfolio Health Report - QBR Preparation

## Executive Summary

**No critical risks identified** in the current portfolio analysis.

**Overall Risk Assessment:** Low
**Immediate Actions Required:** None
**Timeline Impact:** No significant impact on QBR objectives

## Risk Details

No risks requiring executive attention were identified in the email analysis.

## Analysis Notes

- All project communications reviewed across portfolio
- No staging environment issues or production bugs found
- No unresolved action items or miscommunications detected
- Standard project communication patterns observed
- Portfolio health is strong for QBR preparation
- Continue monitoring for any emerging issues
"""
    }

def get_composer_formatting_rules() -> Dict[str, Any]:
    """Get formatting and style rules for reports."""
    return {
        "max_title_length": 10,
        "max_next_step_length": 15,
        "max_evidence_lines": 2,
        "executive_bullets": "3-6",
        "table_columns": [
            "Type", "Title", "Why it matters", "Owner", "Next step", "Evidence"
        ],
        "markdown_syntax": {
            "header1": "#",
            "header2": "##",
            "header3": "###",
            "bold": "**",
            "italic": "*",
            "table_separator": "|"
        }
    }
