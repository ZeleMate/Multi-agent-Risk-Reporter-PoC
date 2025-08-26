"""
Verifier Agent Prompts
Evidence validation and confidence assessment prompts.
"""

from typing import Any

from ..types import FlagItem


def _escape_braces(text: str) -> str:
    return text.replace("{", "{{").replace("}", "}}")


def get_verifier_prompt(candidates: list[FlagItem], full_evidence: list[dict[str, Any]]) -> str:
    """
    Generate verifier prompt for evidence validation - PORTFOLIO HEALTH FOCUS.

    Args:
        candidates: List of candidate risks from analyzer
        full_evidence: Full evidence chunks for validation

    Returns:
        Formatted prompt for verifier agent
    """
    # Format candidates with enhanced detail
    candidates_text = ""
    for i, candidate in enumerate(candidates, 1):
        candidates_text += f"""
CANDIDATE {i}:
Label: {candidate.get('label', 'Unknown')}
Title: {_escape_braces(candidate.get('title', 'Unknown'))}
Reason: {_escape_braces(candidate.get('reason', 'Unknown'))}
Owner: {_escape_braces(candidate.get('owner_hint', 'Unknown'))}
Next Step: {_escape_braces(candidate.get('next_step', 'Unknown'))}
Score: {candidate.get('score', 0)}
Confidence: {_escape_braces(candidate.get('confidence', 'Unknown'))}
Thread ID: {_escape_braces(candidate.get('thread_id', 'Unknown'))}
Evidence Citations: {len(candidate.get('evidence', []))} references


EVIDENCE CITATIONS:
{candidate.get('evidence', [])}

---
"""

    # Format full evidence with comprehensive detail (list input)
    evidence_text = ""
    for idx, chunk in enumerate(full_evidence, 1):
        metadata = chunk.get("metadata", {})
        evidence_text += f"""
EVIDENCE CHUNK {idx}:
File: {_escape_braces(metadata.get('file', 'Unknown'))}
Lines: {metadata.get('line_start', '?')}-{metadata.get('line_end', '?')}
Thread ID: {metadata.get('thread_id', 'Unknown')}
Participants: {', '.join(metadata.get('participants', []))}
Date: {metadata.get('start_date', 'Unknown')}
Subject: {_escape_braces(metadata.get('subject', 'Unknown'))}
Total Emails in Thread: {metadata.get('total_emails', 0)}

CONTENT:
{chunk['text']}

---
"""

    prompt = f"""# EVIDENCE VERIFICATION AUDITOR

Your mission is to ensure that every risk claim presented to a Director of Engineering is backed by evidence. You are the final gatekeeper preventing hallucinated or unsupported risks from reaching executive attention.

## BUSINESS CRITICALITY

You are validating risks for a **Director of Engineering** preparing for **Quarterly Business Review (QBR)**. Your validation directly impacts executive decision-making. False positives waste valuable executive time; false negatives miss critical issues.

**Your Responsibility**: Ensure that only evidence-backed, business-impact risks reach the Director's attention.

## VERIFICATION FRAMEWORK

### **VALIDATION CRITERIA**

#### **1. Evidence Sufficiency Test**
**REQUIRED:**
- **Direct Evidence**: Content must explicitly support the claim (not just imply)
- **Citation Accuracy**: File:line references must be precise and verifiable
- **Content Relevance**: Evidence must directly relate to the risk described
- **Context Preservation**: Email context must support the interpretation

**REJECT ONLY IF:**
- Evidence contradicts the claim or shows resolution
- No citation or relevant quote can be provided from the chunks

#### **2. Business Impact Validation**
**Questions to Answer:**
- Will this actually impact delivery milestones?
- Does this require executive-level intervention?
- Is this a QBR-relevant issue?
- Does this affect multiple stakeholders or projects?

#### **3. Confidence Assessment Scale**
- **high**: Evidence is direct, explicit, and unambiguous
- **mid**: Evidence supports claim but requires reasonable interpretation
- **low**: Evidence is weak, circumstantial, or heavily interpreted

### **DUPLICATE DETECTION & MERGING**
**Identify as duplicates if:**
- Same underlying issue (even if described differently)
- Same thread and similar timeframe
- Same stakeholders and business impact

**Merge Strategy:**
- Combine all evidence citations
- Keep the highest confidence level
- Recalculate score based on strongest evidence
- Preserve most comprehensive description

## HALLUCINATION PREVENTION PROTOCOLS

### **RED FLAGS TO WATCH FOR**
1. **Over-interpretation**: Reading too much into casual comments
2. **Cherry-picking**: Selecting only supporting phrases
3. **Assumption Chains**: Building conclusions on unstated assumptions
4. **Context Blindness**: Ignoring email thread context
5. **Temporal Confusion**: Misinterpreting when issues were raised/resolved

### **VALIDATION CHECKLIST (PRACTICAL)**
For each candidate risk, verify:
- [ ] **Evidence exists** in the provided chunks
- [ ] **Citation is accurate** (file:line matches content)
- [ ] **Content reasonably supports claim** (downgrade confidence if borderline)
- [ ] **Business impact** is stated succinctly or implied by context
- [ ] **No resolution** is evident in the thread
- [ ] **Executive attention** is genuinely required

## ACCEPTANCE GUIDELINES (to avoid over-rejection)

- If evidence is distributed across multiple emails in the same thread but clearly points to the same unresolved ask/blocker, classify as VERIFIED with confidence="mid" and consolidate citations.
- If exact file:line is uncertain but the provided chunk clearly contains the relevant text, provide the closest line range from the chunk metadata (approximate) and include up to two exact quotes.
- Prefer downgrading confidence (high → mid → low) over rejecting plausible, evidence-supported items. Only reject when evidence contradicts the claim or shows resolution.

## OUTPUT SPECIFICATIONS

Return ONLY plain YAML (no code fences) with validated results:

verified:
  - label: uhpai  # "erb", "uhpai", or "none"
    title: Critical path blocked by missing API specs
    reason: Development team cannot proceed with user authentication module due to missing API documentation. Email from 2025-01-15 explicitly states: 'We cannot start development until we receive the API specs.' No response received after 12 days.
    owner_hint: BA
    next_step: Provide complete API specs within 24 hours
    evidence:
      - file: data/raw/Project_Phoenix/email1.txt
        lines: "15-22"
    thread_id: thread_abc123
    timestamp: "2025-01-15T10:30:00"
    confidence: high
    score: 4.7
    validation_notes: Evidence directly supports claim. No resolution visible in thread.
    validation_status: VERIFIED
    rejection_reason: null
  - label: none
    title: Claim rejected - insufficient evidence
    reason: Original claim about SSO complexity not supported by evidence
    validation_notes: Email mentions SSO as 'nice to have' but also states 'we can remove it from scope'. No blocking issue identified.
    validation_status: REJECTED
    rejection_reason: Evidence shows issue is resolved or non-blocking
summary:
  total_candidates: 3
  verified_count: 1
  rejected_count: 2
  merged_count: 0
  validation_timestamp: "2025-01-27T10:30:00"

## CANDIDATES TO VERIFY
{candidates_text}

## FULL EVIDENCE FOR VALIDATION
{evidence_text}

## VERIFICATION EXECUTION

**Your Mission**: Be the ruthless auditor that protects executive time from unsupported claims.

**Validation Process:**
1. **Read Every Citation**: Verify each file:line reference exists and supports the claim
2. **Cross-Reference Content**: Ensure the cited content actually supports the risk
3. **Check for Resolution**: Look for any indication the issue was addressed
4. **Assess Business Impact**: Determine if this truly needs executive attention
5. **Document Reasoning**: Provide clear validation_notes for every decision

**Prefer Downgrade Over Rejection**: When in doubt, select lower confidence instead of rejecting plausible items.

**Executive Mindset**: Ask yourself - "Would a Director fire someone over this issue?"

Execute validation with rigor and return evidence-backed risks that demand executive attention."""

    return _escape_braces(prompt)


def get_verifier_system_prompt() -> str:
    """Get the system prompt for verifier agent."""
    return """You trust but verify: prefer downgrading confidence (high→mid→low) over rejecting plausible items. Reject only when evidence contradicts the claim or shows resolution. Provide precise, concise validation notes and keep useful candidates whenever evidence supports them at least partially."""
