# Portfolio Health Report System — Final Blueprint

## Introduction
A Director of Engineering needs a high‑signal “Portfolio Health Report” to prepare for Quarterly Business Review (QBR). This blueprint defines a practical, production‑minded architecture and a working PoC: the system ingests project communications, retrieves high‑signal evidence with a hybrid retriever, identifies and verifies executive‑relevant risks via a multi‑agent LangGraph pipeline, and composes an executive‑ready report. The implementation is configuration‑driven, performs PII redaction up‑front, and is optimized for low token usage.

---

## 1) Data Ingestion & Initial Processing

### Approach
- Parse plain‑text emails into normalized records (From/To/Cc/Date/Subject; date normalization, subject canonicalization).
- Deterministic PII redaction with regex before any LLM step (context‑preserving placeholders).
- Reconstruct threads using canonical subjects and participant metadata.
- Thread‑scope chunking with rich metadata (file, line_start, line_end, thread_id, date, roles) for precise citations.

```mermaid
graph TD
  A[Raw Email Files] --> B[Header Parsing]
  B --> C[PII Redaction]
  C --> D[Thread Reconstruction]
  D --> E[Chunking + Metadata]
  E --> F[Embeddings (Qwen)]
  F --> G[ChromaDB]
  G --> H[Hybrid Retrieval]
```

### Scalability
- Parallel ingestion and incremental updates; partition by project/thread prefix.
- Persistent vector store (Chroma) to avoid recomputation.
- Configurable chunk size/overlap; predictable resource and token usage.

### Security & Privacy
- PII redaction happens pre‑LLM; only redacted text reaches models.
- Simple, auditable rules; no secrets in code.

Deliverable: implemented in `src/ingestion/`, configuration in `configs/`.

---

## 2) The Analytical Engine (Multi‑Step AI Logic)

### Attention Flags (executive‑relevant)
- **UHPAI** — Unresolved High‑Priority Action Items (e.g., unanswered > 5 days, missing clarifications/approvals).
- **ERB** — Emerging Risks/Blockers (e.g., security/payment/production issues, critical blockers, unclear ownership).

### Pipeline
```mermaid
graph TD
  A[Chunks via Hybrid Retrieval] --> B[Analyzer Agent]
  B --> C[Candidates (YAML, citations)]
  C --> D[Verifier Agent]
  D --> E[Verified (YAML, merged, confidence)]
  E --> F[Composer Agent]
  F --> G[Executive Markdown Report]
```

### Retrieval (Hybrid)
1) Lightweight keyword prefilter (configurable) narrows candidate IDs.
2) Vector similarity (top‑k) over Chroma embeddings; if prefilter is empty, vector‑only.
3) Graceful fallback: on retrieval issues, proceed with available chunks to keep the pipeline running.

### Models (current configuration)
- Analyzer: `gpt‑5‑mini`
- Verifier: `gpt‑5‑mini`
- Composer: `gpt‑5` (always)

### Scoring (deterministic)
`score = role_weight + topic_weight + repeat_weight`  
Weights/keywords come from `configs/pipeline.yaml` (no hard‑coding).

### Hallucination Prevention & Contracts
- **No‑evidence → No‑claim**: each item must cite at least one `file:lines` span from chunk metadata.
- Verifier merges duplicates and assigns `confidence: high|mid|low`.
- Agents exchange plain YAML; runtime parsing validates structure.

### Engineered Prompts — Excerpts
- **Analyzer (user)**: UHPAI/ERB rules, critical terms, scoring weights, strict evidence constraints; output: YAML `items`.
- **Verifier (user)**: explicit evidence check, duplicate merge, confidence; output: YAML `verified` (no unused summary/status fields).
- **Composer (user)**: Markdown with 1) Executive TL;DR (3–6 bullets), 2) Risk Table (Type/Title/Why/Owner/Next step/Evidence), 3) Evidence Appendix (≤ 2 lines per item, with citations).

### Runnable Code
- Orchestrator: `src/agents/graph.py`
- Retrieval: `src/retrieval/` (Chroma + hybrid search)
- Agents/Prompts: `src/agents/`, `src/prompts/`

Run locally:
```
make ingest
make index
make run   # writes data/report/portfolio_health.md
```

---

## 3) Cost & Robustness Considerations

### Robustness
- Multi‑stage verification with explicit citations; deterministic scoring for consistency.
- Hybrid retrieval reduces noise; top‑k caps token usage.
- Fallback behavior keeps the pipeline functional under partial failures.

### Cost Management
- Tiered models: `gpt‑5‑mini` for Analyzer/Verifier, `gpt‑5` for Composer only.
- Token budgets: compact prompts, ≤ 15‑word next steps, top‑k evidence.
- Local embeddings (Qwen) → zero embedding API cost.

---

## 4) Monitoring & Trust
- **Evidence Accuracy**: % of items with valid `file:line` citations (target 100%).
- **Hallucination Rate**: % of items rejected by Verifier (target ≤ 5%).
- **Retrieval Hit‑Rate**, **tokens per run**, **stage latency** p50/p95.
- **Executive usefulness**: qualitative feedback loop for continuous tuning.

PoC hooks: structured logs, smoke test (`tests/ci_smoke.py`), unit tests for agents and prompt conformance.

---

## 5) Architectural Risk & Mitigation
- **Primary risk**: evidence quality degradation at scale (ambiguous threads, weak citations).
- **Mitigation**: stronger prefilter/metadata filters; stricter Verifier rules; duplicate merge; confidence downgrades; optional quote‑match corroboration; route low‑confidence items to human review; monitor hallucination rate.

---

## Conclusion
The system transforms unstructured emails into an executive‑ready, evidence‑backed portfolio report. It uses a hybrid retriever for efficiency, a three‑agent LangGraph pipeline for rigor, deterministic scoring for consistency, and model tiering to optimize cost and quality. The PoC is runnable and CI‑checked.

Commands:
```
make ingest && make index && make run
```
Output: `data/report/portfolio_health.md`.
