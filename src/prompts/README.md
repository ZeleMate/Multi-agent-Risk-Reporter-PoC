# Prompts Module - PORTFOLIO HEALTH SYSTEM

This module contains all LLM prompts used by the multi-agent risk reporter system, specifically designed for **Portfolio Health Reports** supporting **Director of Engineering QBR preparation**. Each agent has its own prompt file with specialized instructions and templates focused on executive-level decision making.

## Business Context

The system is designed to help a **Director of Engineering** prepare for their **Quarterly Business Review (QBR)** by providing a "Portfolio Health Report" that quickly identifies risks, inconsistencies, and unresolved issues across their entire project portfolio.

## Structure

```
src/prompts/
├── __init__.py          # Module exports
├── analyzer.py          # Risk identification and classification
├── verifier.py          # Evidence validation and quality assurance
├── composer.py          # Executive report composition
└── README.md           # This documentation
```

## Agent Prompts - Detailed Specifications

### 1. Analyzer Agent (`analyzer.py`) - Risk Identification

**Purpose**: Identify and classify critical attention flags from project communications based on real email patterns

**Key Functions**:
- `get_analyzer_prompt()`: Main analysis prompt with portfolio-level focus
- `get_analyzer_system_prompt()`: System prompt for technical program manager expertise

**Critical Features**:
- **UHPAI Detection**: Unresolved High-Priority Action Items (>5 days old)
  - Miscommunications between team members
  - Cross-project confusion and process issues
  - Unanswered technical questions blocking progress
  - Developer-admitted bugs requiring immediate attention

- **ERB Classification**: Emerging Risks/Blockers that could impact delivery
  - Staging environment inconsistencies and anomalies
  - Production code bugs (filename validation, cache issues)
  - Technical blockers affecting user experience
  - Misdiagnosis of bugs (cache issue vs filename validation)

- **Business Impact Scoring**: Role weights, age factors, topic relevance
- **Executive Focus**: Only flags issues requiring Director attention
- **Evidence-Based**: Every claim must have explicit file:line citations

**Scoring Algorithm**:
```
score = role_weight + (age_weight × days_unresolved) + topic_weight + repeat_weight
```

**Rejection Criteria**:
- Social discussions (team lunch planning)
- Routine status updates without action items
- Already resolved issues
- Non-business impacting items
- Insufficient evidence

### 2. Verifier Agent (`verifier.py`) - Quality Assurance

**Purpose**: Validate risk claims and prevent hallucinated or unsupported findings

**Key Functions**:
- `get_verifier_prompt()`: Technical evidence validation
- `get_verifier_system_prompt()`: System prompt for senior technical auditor expertise
- `get_verifier_validation_criteria()`: Validation frameworks by risk type including real-world examples

**Critical Features**:
- **Evidence Cross-Referencing**: Verifies all citations against full email chunks
- **Citation Accuracy**: Validates file:line references match actual email content
- **Context Preservation**: Maintains email thread context and timeline
- **Technical Precision**: Distinguishes between cache issues and actual bugs
- **Business Impact Validation**: Ensures flagged issues truly affect delivery/cost/quality
- **Rejection Protocols**: Clear criteria for rejecting unsupported claims

**Validation Checklist**:
- [ ] Evidence exists in provided chunks and matches citation
- [ ] Content supports claim without over-interpretation or speculation
- [ ] Business impact is clear and significant for QBR preparation
- [ ] No resolution is evident in the email thread
- [ ] Issue genuinely requires executive attention
- [ ] Timeline and context are accurately preserved

**Real-World Validation Examples**:
- **Accept**: "Profile picture upload fails with space-containing filenames" (clear reproduction, business impact)
- **Reject**: "Team lunch planning discussions" (social, not business-critical)
- **Accept**: "Developer admits to introducing bug in recent commit" (explicit admission, clear impact)
- **Reject**: "Vague status update without action items" (insufficient evidence)

### 3. Composer Agent (`composer.py`) - Executive Reporting

**Purpose**: Transform validated risks into compelling QBR narrative based on real project patterns

**Key Functions**:
- `get_composer_prompt()`: Executive report composition with portfolio focus
- `get_composer_system_prompt()`: System prompt for C-suite communications
- `get_composer_report_templates()`: Portfolio health report templates
- `get_composer_formatting_rules()`: Executive formatting guidelines

**Critical Features**:
- **Executive TL;DR**: 3-6 bullets sorted by business impact (production bugs first)
- **Portfolio Table**: Risk details with business context and specific actions
- **Evidence Appendix**: Source citations with actual email quotes
- **QBR Preparation Focus**: Strategic implications and executive actions
- **Business Language**: Impact on delivery, cost, quality, reputation, team efficiency

**Report Structure**:
```markdown
# 📊 Portfolio Health Report - QBR Preparation
## Executive Summary

- **CRITICAL**: Production filename bug affecting user profile uploads, 3 weeks unresolved
- **HIGH**: Cross-project communication confusion causing potential missed updates
- **MEDIUM**: Staging environment anomaly requires root cause investigation

## Risk Details

| Type | Title | Why it matters | Owner | Next step | Evidence |
|------|-------|----------------|--------|-----------|----------|
| ERB | Staging environment filename bug affects production readiness | Profile picture uploads fail when filenames contain spaces, initially misdiagnosed as cache issue, affects user experience | Developer | Fix filename validation logic immediately | email1.txt:25-35 |
| UHPAI | Cross-project communication confusion needs process fix | Design updates posted in wrong project correspondence, leading to confusion and potential missed updates | PM | Establish clear project communication guidelines | email2.txt:10-15 |
| UHPAI | Production bug introduced by recent commit requires immediate fix | Developer admitted to introducing filename validation bug through recent changes, needs immediate attention | Developer | Fix filename validation bug today | email1.txt:40-45 |

## Evidence Appendix

### Staging environment filename bug affects production readiness
"I'm experiencing something strange on staging. If I upload a new user profile picture, it shows the old image after saving... The profile picture upload is indeed acting up. I figured out that it only happens if the image name contains spaces." (email1.txt:25-35)

### Cross-project communication confusion needs process fix
"Oh, sorry, indeed! I wanted to write this in the 'Solar Panel Tender project' correspondence. My apologies for the confusion!" (email2.txt:10-15)

### Production bug introduced by recent commit requires immediate fix
"Yes, it did. I rewrote the filename validation to replace special characters. It's possible the frontend isn't receiving the modified filename. My apologies, I'll check it immediately. This is clearly my mistake." (email1.txt:40-45)
```

## Prompt Design Principles

### 1. **Business-First Approach**
- All prompts frame technical issues in business terms
- Focus on Director's QBR preparation needs
- Prioritize executive decision-making

### 2. **Evidence-Driven**
- Every claim requires explicit evidence citations
- File:line references must be accurate and verifiable
- No assumptions or inferences allowed

### 3. **Executive Mindset**
- Think like a Director: "What would I present to the CEO?"
- Focus on: "What decisions need my involvement?"
- Prioritize: "Where should I focus my limited time?"

### 4. **QBR Preparation**
- Portfolio-level insights, not project details
- Strategic implications for the quarter/organization
- Actionable insights that drive executive decisions

## Usage Examples

```python
from src.prompts import get_analyzer_prompt, get_verifier_prompt, get_composer_prompt

# Risk identification for QBR preparation
chunks = load_email_chunks()
analysis_prompt = get_analyzer_prompt(
    chunks,
    project_context="Q2 2025 delivery planning"
)

# Evidence validation for quality assurance
candidates = get_risk_candidates()
verification_prompt = get_verifier_prompt(
    candidates,
    full_evidence=evidence_chunks
)

# Executive report composition
verified_risks = get_verified_risks()
report_prompt = get_composer_prompt(
    verified_risks,
    project_context="Portfolio review for upcoming QBR"
)
```

## Configuration Integration

```yaml
# model.yaml
primary_model:
  provider: openai
  chat_model: "gpt-5-mini"  # Cost-effective for analysis
  temperature: 0.1

alternative_model:
  provider: openai
  chat_model: "gpt-5"       # Higher capability for composition
  temperature: 0.1

agent_models:
  analyzer: "primary_model"    # Precision-focused
  verifier: "primary_model"    # Consistency-focused
  composer: "alternative_model" # Creativity-focused
```

## Testing and Validation

Each prompt is designed with:
- **Edge Cases**: Empty inputs, malformed data, ambiguous evidence
- **Business Scenarios**: Various project contexts and risk patterns
- **Executive Review**: Would a Director accept this analysis?
- **QBR Alignment**: Does this support quarterly planning?

## Future Enhancements

Potential improvements:
- **Multi-language Support**: International portfolio management
- **Industry-Specific Templates**: Finance, healthcare, manufacturing
- **Dynamic Prompt Generation**: Context-aware prompt adaptation
- **Interactive Reports**: Drill-down capabilities for executives
- **Integration with QBR Tools**: Automated slide generation

## Prompt Design Principles

### 1. Evidence-Based
- All claims must be supported by explicit evidence
- Citations must be accurate and verifiable
- No assumptions or inferences beyond provided data

### 2. Structured Output
- Consistent JSON schemas for agent communication
- Markdown templates for report formatting
- Clear field requirements and constraints

### 3. Role-Specific Language
- **Analyzer**: Technical risk analysis terminology
- **Verifier**: Legal/forensic auditing language
- **Composer**: Executive business communication

### 4. Context Awareness
- Prompts include project context when available
- Consider email thread relationships
- Maintain conversation flow and context

## Usage Examples

```python
from src.prompts import get_analyzer_prompt, get_verifier_prompt, get_composer_prompt

# Risk analysis
chunks = load_email_chunks()
analysis_prompt = get_analyzer_prompt(chunks, "Project Phoenix context")

# Evidence verification
candidates = load_risk_candidates()
verification_prompt = get_verifier_prompt(candidates, full_evidence)

# Report composition
verified_risks = load_verified_risks()
report_prompt = get_composer_prompt(verified_risks, "Q1 2025 planning")
```

## Configuration Integration

Prompts integrate with the configuration system:

```python
from src.services.config import get_config

config = get_config()
# Agent models can be configured:
# - analyzer: "primary_model" (gpt-5-mini)
# - verifier: "primary_model" (gpt-5-mini)
# - composer: "alternative_model" (gpt-5)
```

## Testing and Validation

Each prompt should be tested with:
- Edge cases (empty input, malformed data)
- Various project contexts
- Different email thread structures
- Boundary conditions for scoring and validation

## Future Enhancements

Potential improvements:
- Multi-language support
- Domain-specific prompt variants
- Dynamic prompt generation based on project type
- Integration with prompt engineering frameworks
- A/B testing of alternative prompt formulations
