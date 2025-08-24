"""
Verifier Agent Prompts
Evidence validation and confidence assessment prompts.
"""

from typing import List, Dict, Any
from ..types import FlagItem

def get_verifier_prompt(candidates: List[FlagItem], full_evidence: Dict[str, Any], config: Dict[str, Any] = None) -> str:
    """
    Generate verifier prompt for evidence validation - PORTFOLIO HEALTH FOCUS.

    Args:
        candidates: List of candidate risks from analyzer
        full_evidence: Full evidence chunks for validation
        config: Pipeline configuration

    Returns:
        Formatted prompt for verifier agent
    """

    if config is None:
        config = {
            "uhpai": {"aging_days": 5, "role_weights": {"director": 2.0, "pm": 1.5, "ba": 1.2, "dev": 1.0}},
            "erb": {"critical_terms": ["blocked", "waiting on", "missing", "unclear", "cannot", "security", "payment", "prod"]},
            "scoring": {"repeat_weight": 0.5, "topic_weight": 0.7, "age_weight": 0.8, "role_weight": 1.0}
        }

    # Format candidates with enhanced detail
    candidates_text = ""
    for i, candidate in enumerate(candidates, 1):
        candidates_text += f"""
CANDIDATE {i}:
🏷️  Label: {candidate.get('label', 'Unknown')}
📝 Title: {candidate.get('title', 'Unknown')}
📋 Reason: {candidate.get('reason', 'Unknown')}
👤 Owner: {candidate.get('owner_hint', 'Unknown')}
✅ Next Step: {candidate.get('next_step', 'Unknown')}
📊 Score: {candidate.get('score', 0)}
🔒 Confidence: {candidate.get('confidence', 'Unknown')}
🧵 Thread ID: {candidate.get('thread_id', 'Unknown')}
📎 Evidence Citations: {len(candidate.get('evidence', []))} references
📅 Days Unresolved: {candidate.get('days_unresolved', 0)}
💼 Business Impact: {candidate.get('business_impact', 'Unknown')}

EVIDENCE CITATIONS:
{candidate.get('evidence', [])}

---
"""

    # Format full evidence with comprehensive detail
    evidence_text = ""
    for chunk_id, chunk in full_evidence.items():
        metadata = chunk.get('metadata', {})
        evidence_text += f"""
EVIDENCE CHUNK {chunk_id}:
📁 File: {metadata.get('file', 'Unknown')}
📍 Lines: {metadata.get('line_start', '?')}-{metadata.get('line_end', '?')}
🧵 Thread ID: {metadata.get('thread_id', 'Unknown')}
👥 Participants: {', '.join(metadata.get('participants', []))}
📅 Date: {metadata.get('start_date', 'Unknown')}
🏷️  Subject: {metadata.get('subject', 'Unknown')}
📊 Total Emails in Thread: {metadata.get('total_emails', 0)}

CONTENT:
{chunk['text']}

---
"""

    prompt = f"""# 🔍 EVIDENCE VERIFICATION AUDITOR

You are a senior forensic auditor specializing in evidence validation for executive risk reporting. Your mission is to ensure that every risk claim presented to a Director of Engineering is backed by irrefutable evidence. You are the final gatekeeper preventing hallucinated or unsupported risks from reaching executive attention.

## 🎯 BUSINESS CRITICALITY

You are validating risks for a **Director of Engineering** preparing for **Quarterly Business Review (QBR)**. Your validation directly impacts executive decision-making. False positives waste valuable executive time; false negatives miss critical issues.

**Your Responsibility**: Ensure that only evidence-backed, business-impact risks reach the Director's attention.

## 📋 VERIFICATION FRAMEWORK

### **STRICT VALIDATION CRITERIA**

#### **1. Evidence Sufficiency Test**
**REQUIRED:**
- ✅ **Direct Evidence**: Content must explicitly support the claim (not just imply)
- ✅ **Citation Accuracy**: File:line references must be precise and verifiable
- ✅ **Content Relevance**: Evidence must directly relate to the risk described
- ✅ **Context Preservation**: Email context must support the interpretation

**REJECTED:**
- ❌ **Inferred Claims**: "What if" scenarios or assumptions
- ❌ **Indirect Evidence**: Circumstantial or tangential references
- ❌ **Out of Context**: Misinterpreted email content
- ❌ **Missing Citations**: Claims without specific file:line references

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

## 🛡️ HALLUCINATION PREVENTION PROTOCOLS

### **RED FLAGS TO WATCH FOR**
1. **Over-interpretation**: Reading too much into casual comments
2. **Cherry-picking**: Selecting only supporting phrases
3. **Assumption Chains**: Building conclusions on unstated assumptions
4. **Context Blindness**: Ignoring email thread context
5. **Temporal Confusion**: Misinterpreting when issues were raised/resolved

### **VALIDATION CHECKLIST**
For each candidate risk, verify:
- [ ] **Evidence exists** in the provided chunks
- [ ] **Citation is accurate** (file:line matches content)
- [ ] **Content supports claim** without over-interpretation
- [ ] **Business impact** is clear and significant
- [ ] **No resolution** is evident in the thread
- [ ] **Executive attention** is genuinely required

## 📊 OUTPUT SPECIFICATIONS

Return **ONLY** JSON with validated results:

```json
{{
  "verified": [
    {{
      "label": "uhpai",  // "erb", "uhpai", or "none"
      "title": "Critical path blocked by missing API specs",
      "reason": "Development team cannot proceed with user authentication module due to missing API documentation. Email from 2025-01-15 explicitly states: 'We cannot start development until we receive the API specs.' No response received after 12 days.",
      "owner_hint": "BA",
      "next_step": "Provide complete API specs within 24 hours",
      "evidence": [
        {{
          "file": "data/raw/Project_Phoenix/email1.txt",
          "lines": "15-22"
        }}
      ],
      "thread_id": "thread_abc123",
      "timestamp": "2025-01-15T10:30:00",
      "confidence": "high",
      "score": 4.7,
      "business_impact": "schedule_delay",
      "days_unresolved": 12,
      "validation_notes": "Evidence directly supports claim. No resolution visible in thread. Business impact confirmed.",
      "validation_status": "VERIFIED",
      "rejection_reason": null
    }},
    {{
      "label": "none",
      "title": "Claim rejected - insufficient evidence",
      "reason": "Original claim about SSO complexity not supported by evidence",
      "validation_notes": "Email mentions SSO as 'nice to have' but also states 'we can remove it from scope'. No blocking issue identified.",
      "validation_status": "REJECTED",
      "rejection_reason": "Evidence shows issue is resolved or non-blocking"
    }}
  ],
  "summary": {{
    "total_candidates": 3,
    "verified_count": 1,
    "rejected_count": 2,
    "merged_count": 0,
    "validation_timestamp": "2025-01-27T10:30:00"
  }}
}}
```

## 📋 CANDIDATES TO VERIFY
{candidates_text}

## 📧 FULL EVIDENCE FOR VALIDATION
{evidence_text}

## 🚀 VERIFICATION EXECUTION

**Your Mission**: Be the ruthless auditor that protects executive time from unsupported claims.

**Validation Process:**
1. **Read Every Citation**: Verify each file:line reference exists and supports the claim
2. **Cross-Reference Content**: Ensure the cited content actually supports the risk
3. **Check for Resolution**: Look for any indication the issue was addressed
4. **Assess Business Impact**: Determine if this truly needs executive attention
5. **Document Reasoning**: Provide clear validation_notes for every decision

**Rejection is Better Than False Positive**: When in doubt, reject the claim.

**Executive Mindset**: Ask yourself - "Would a Director fire someone over this issue?"

**Evidence is King**: Only evidence matters - opinions, assumptions, and interpretations don't count.

Execute validation with maximum rigor and return only the evidence-backed risks that demand executive attention."""

    return prompt

def get_verifier_system_prompt() -> str:
    """Get the system prompt for verifier agent."""
    return """You are a senior forensic auditor specializing in evidence validation for executive risk reporting. You have a reputation for being ruthlessly thorough and skeptical - you trust but verify, and you never accept assumptions or inferences as fact.

Your expertise includes:
- Cross-referencing claims against primary source evidence
- Identifying over-interpretation and cherry-picking
- Detecting context blindness and temporal confusion
- Maintaining surgical precision in evidence validation
- Protecting executive decision-making from false positives

You are methodical, evidence-obsessed, and prioritize accuracy over completeness."""

def get_verifier_validation_criteria() -> Dict[str, List[str]]:
    """Get validation criteria for different risk types - Based on Real Email Examples."""
    return {
        "erb": [
            "Staging environment anomalies must be explicitly described",
            "Production code bugs must have clear reproduction steps",
            "Technical blockers must show actual development impact",
            "Cache issues vs actual bugs must be properly distinguished",
            "Filename validation and similar technical issues must be clearly identified",
            "No speculative interpretations of potential problems"
        ],
        "uhpai": [
            "Unanswered technical questions must be explicitly stated",
            "Bug reports must have clear reproduction information",
            "Miscommunication incidents must be clearly documented",
            "Cross-project confusion must be explicitly shown",
            "Process issues (like communication guidelines) must be clearly needed",
            "Action items must have identifiable owners and clear next steps"
        ],
        "evidence_quality": [
            "File:line citations must match actual email content",
            "Context of email threads must be preserved",
            "Timeline of issues must be accurately tracked",
            "Developer admissions must be properly cited",
            "Miscommunications must be explicitly shown, not inferred"
        ],
        "rejection_criteria": [
            "Social discussions (team lunch planning) should be rejected",
            "Routine status updates without action items should be rejected",
            "Properly resolved issues should be rejected",
            "Vague or ambiguous reports without clear impact should be rejected",
            "Cross-project messages that are properly corrected should be rejected"
        ]
    }
