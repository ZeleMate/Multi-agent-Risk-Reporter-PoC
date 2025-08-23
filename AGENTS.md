# AGENTS.md — Multi‑agent Risk Reporter PoC

> **Purpose of this file**  
> This document follows the [agents.md](https://agents.md/) pattern to help coding agents (and new teammates) work effectively in this repository. It provides the project overview, build/test commands, code style, security considerations, and concrete task instructions.  
> Place this file at the **repository root**. If you split the project into subpackages later, you can add **nested `AGENTS.md`** files per subproject; agents will read the closest file in the directory tree.

---

## Table of Contents

1. [Project Overview](#project-overview)  
2. [Architecture & Data Flow](#architecture--data-flow)  
3. [Dev Environment & Setup](#dev-environment--setup)  
4. [Build, Lint & Test Commands](#build-lint--test-commands)  
5. [Configuration & Environment Variables](#configuration--environment-variables)  
6. [Data Ingestion & Cleaning](#data-ingestion--cleaning)  
7. [Vector Store & Retrieval](#vector-store--retrieval)  
8. [Agent Workflow & Contracts](#agent-workflow--contracts)  
9. [Report Format](#report-format)  
10. [Security & Privacy Considerations](#security--privacy-considerations)  
11. [CI Pipeline](#ci-pipeline)  
12. [Deployment Notes](#deployment-notes)  
13. [Troubleshooting](#troubleshooting)  
14. [Extending the System](#extending-the-system)  
15. [Style & Conventions](#style--conventions)  

---

## Project Overview

**Goal:** Transform **unstructured documents** (e.g., email threads, logs, reports) into a **structured, evidence‑backed risk report** using a **LangGraph‑based multi‑agent pipeline** and a local **ChromaDB** RAG stack.  
**Primary flags:**  
- **ERB** — Emerging Risks / Blockers  
- **UHPAI** — Unresolved High‑Priority Action Items

**Key properties**
- Deterministic preprocessing (regex parsing, thread building, PII redaction)
- Local development first; portable to cloud (Azure/GCP/AWS)
- Clear interfaces between agents; strict JSON contracts
- English‑only repository (code, comments, docs)

---

## Architecture & Data Flow

```mermaid
graph TD
  A[Raw Docs (email .txt)] --> B[Preprocessing and PII Redaction]
  B --> C[Chunking + Metadata]
  C --> D[ChromaDB Vector Store]
  D --> E[Hybrid Retrieval]
  E --> F[Analyzer Agent]
  F --> G[Verifier Agent]
  G --> H[Composer Agent]
  H --> I[Markdown + JSON Report]
```

**Repository layout (backend‑only)**

```
multi-agent-risk-reporter-poc/
├─ configs/               # model.yaml, pipeline.yaml
├─ data/
│  ├─ raw/                # input documents (not committed)
│  └─ clean/              # normalized/cleaned docs (gitignored)
├─ src/
│  ├─ agents/             # analyzer.py, verifier.py, composer.py
│  ├─ graph/              # app.py (LangGraph wiring)
│  ├─ ingestion/          # parser.py, pii.py
│  ├─ retrieval/          # store.py (Chroma), retriever.py (hybrid)
│  ├─ services/           # llm.py (OpenAI), config.py
│  ├─ types.py            # TypedDict schemas
│  └─ cli.py              # CLI entrypoints
├─ scripts/               # ci_smoke.py
├─ tests/                 # unit + integration tests
├─ report/                # generated reports (gitignored except samples)
├─ .github/workflows/     # ci.yml
├─ .env.example
├─ Makefile
├─ pyproject.toml
└─ README.md
```

---

## Dev Environment & Setup

**Requirements**
- Python **3.11+**
- Make (GNU Make)
- An OpenAI API key (no network calls are made during CI)

**First‑time setup**
```bash
git clone <this-repo>
cd multi-agent-risk-reporter-poc
cp .env.example .env
# edit .env to set OPENAI_API_KEY

make setup
```

**Typical local loop**
```bash
make ingest     # parse raw docs -> data/clean
make index      # build/update Chroma index
make run        # run Analyzer -> Verifier -> Composer
make report     # write report/portfolio_health.md
make lint       # code quality (Black, Ruff, Mypy, Bandit)
make test       # run pytest
```

---

## Build, Lint & Test Commands

**Make targets**
- `setup` — create venv, install project in editable mode
- `ingest` — parse & clean documents from `data/raw` to `data/clean`
- `index` — build Chroma index at `.vectorstore/`
- `run` — execute the LangGraph pipeline (stdout prints Markdown)
- `report` — write final markdown to `./report/portfolio_health.md`
- `lint` / `fmt` — quality checks (Black & Ruff), formatting
- `test` — run pytest
- `ci-smoke` — compile the graph, no LLM/network requests

**Local smoke (no network)**
```bash
make ci-smoke
```

**Run a minimal test suite**
```bash
make test
```

---

## Configuration & Environment Variables

**Environment (`.env` / `.env.example`)**
```ini
OPENAI_API_KEY=sk-<your-key>
VECTORSTORE_DIR=.vectorstore
DATA_RAW=./data/raw
DATA_CLEAN=./data/clean
```

**Model config (`configs/model.yaml`)**
```yaml
provider: openai
chat_model: "gpt-5-mini"
embedding_model: "text-embedding-3-small"
temperature: 0.1
max_output_tokens: 800
json_response: true
```

**Pipeline config (`configs/pipeline.yaml`)**
```yaml
retrieval:
  top_k: 10
  prefilter_keywords: ["blocker","risk","delayed","waiting","asap","urgent","deadline","unresolved","issue"]
flags:
  uhpai:
    aging_days: 5
    role_weights: {"director": 2.0, "pm": 1.5, "ba": 1.2, "dev": 1.0}
  erb:
    critical_terms: ["blocked","waiting on","missing","unclear","cannot","security","payment","prod"]
scoring:
  repeat_weight: 0.5
  topic_weight: 0.7
  age_weight: 0.8
  role_weight: 1.0
report:
  top_n_per_project: 5
```

> Agents must **not** hardcode parameters; always read from `AppConfig` / YAML.

---

## Data Ingestion & Cleaning

**Input expectations**
- Plain text **email threads** (`.txt`) or other unstructured text files.
- Heuristics remove quoted replies and signatures.

**Parsing & normalization** (see `src/ingestion/parser.py`)
- Extract headers: From, To, Cc, Date, Subject
- Canonical subject (strip `RE:`, `FW:`), lowercase, trim
- Build `thread_id` by canonical subject + participants window + time window
- Redact PII (emails, phone numbers, IDs) using `src/ingestion/pii.py`
- Produce cleaned records with metadata (file, line ranges, date, roles, thread_id)

**Chunking policy**
- Chunk at **thread scope** (≈800–1200 tokens, with 80–120 overlap)
- Preserve **sentence IDs** and `file:line_start-line_end` for citations

**Output**
- Cleaned JSON/Parquet to `data/clean`
- Embeddings written to the vector store during `make index`

---

## Vector Store & Retrieval

**Store**: Local **ChromaDB** (persisted at `${VECTORSTORE_DIR}`)  
**Retrieval**: **Hybrid** strategy
1. Lightweight **keyword/BM25 prefilter** using `prefilter_keywords`
2. **Vector top_k** retrieval using `embedding_model`  
3. Metadata filters (project/thread/date/roles) when available

**Goal**: Minimize token usage while maximizing evidence quality. Agents should request **at most 6** chunks per project for classification.

---

## Agent Workflow & Contracts

The pipeline uses **three agents** orchestrated by LangGraph:

### Shared types (from `src/types.py`)

```python
Label = Literal["erb", "uhpai", "none"]
Confidence = Literal["low", "mid", "high"]

class EvidenceSpan(TypedDict):
    file: str
    lines: str   # "12-24"

class FlagItem(TypedDict, total=False):
    label: Label
    title: str
    reason: str
    owner_hint: str
    next_step: str
    evidence: List[EvidenceSpan]
    thread_id: str
    timestamp: str
    confidence: Confidence
    score: float
```

> **Hard rule**: **no‑evidence → no‑claim**. If an item cannot cite at least one `file:lines`, it must be dropped or labeled `none`.

---

### Analyzer Agent

**Purpose**: Classify retrieved chunks into **ERB / UHPAI / none**, attach citations, compute a deterministic `score`.

**Input**:
- Up to **6** evidence chunks (text + `file:line_start-line_end`, `thread_id`, `date`, `roles`)
- Pipeline thresholds from config

**Output**:
- `candidates: List[FlagItem]` (ERB/UHPAI only; drop `none`)
- Each item must include: `title`, `reason`, `owner_hint`, `next_step (<=15 words)`, `evidence[]`, `thread_id`, `timestamp`, and preliminary `score`

**Scoring guidance**:
- `score = role_weight + age_weight + topic_weight + repeat_weight`  
  (weights from `configs/pipeline.yaml`)

**Prompt contract (summary)**:
- “Use ONLY the provided EVIDENCE snippets; output JSON `{"items":[...]}`. If uncertain, return `none`.”

---

### Verifier Agent

**Purpose**: Enforce evidence, remove unsupported items, merge duplicates, assign `confidence`.

**Input**:
- `candidates: List[FlagItem]` from Analyzer
- Full **text of cited evidence** chunks

**Rules**:
- If the cited evidence does not explicitly support the claim, set `label: "none"` (or drop).
- Merge near‑duplicates (same thread/topic) and **union evidence** spans.
- Assign `confidence`: `high | mid | low`.

**Output**:
- `verified: List[FlagItem]` (ERB/UHPAI only), top‑N by `score` (configurable)

---

### Composer Agent

**Purpose**: Produce a **Director‑level report**.  
**Input**: `verified: List[FlagItem]` with `confidence` and `score`.  
**Constraint**: **Do not invent facts**; summarize only verified content.

**Output**:
- Markdown report (see format below)
- Optional machine‑readable JSON mirror for automation/QA

---

## Report Format

The Composer must produce Markdown with the following structure:

1. **Executive TL;DR**  
   3–6 bullets, sorted by `score` (desc), concise and actionable.

2. **Project Breakdown (Table)**  
   Columns:  
   - Type (ERB/UHPAI)  
   - Title  
   - Why it matters (reason)  
   - Owner (owner_hint)  
   - Next step (≤ 15 words)  
   - Evidence (list of `file:line`)

3. **Appendix (Evidence Excerpts)**  
   - Up to 2 lines per item  
   - Must include `file:line` citations

---

## Security & Privacy Considerations

- **Never commit secrets**. Only commit `.env.example`.  
- PII redaction is done in **preprocessing** (deterministic regex) before any agent sees the text.  
- Keep raw data under `data/raw` and do **not commit** it.  
- In CI, we set a **dummy** `OPENAI_API_KEY`; tests must not make network calls.  
- For production/cloud, use a secrets manager (e.g., Azure Key Vault) and private networking.

---

## CI Pipeline

The workflow is defined in `.github/workflows/ci.yml` with two jobs:

1. **Lint & Quality Checks**  
   - Black, Ruff, optional Mypy & Bandit  
   - Markdownlint for docs  
   - Optional NBQA checks if `notebooks/` exists

2. **Install & Smoke Tests**  
   - Installs the project (`pip install -e .`)  
   - Verifies core imports  
   - Runs `scripts/ci_smoke.py` which **compiles the graph without network calls**  
   - Runs `pytest` if `tests/` exists

**Local parity**
```bash
make lint
make ci-smoke
make test
```

---

## Deployment Notes

**Local Docker (suggested outline)**
- Base image: `python:3.11-slim`
- Copy `pyproject.toml`, install deps
- Copy `src/`, `configs/`
- Mount volumes for `data/` and `.vectorstore/`
- Provide `OPENAI_API_KEY` via environment

**Cloud portability**
- Replace Chroma with a managed vector DB (e.g., CosmosDB/pgvector, Azure AI Search)
- Store reports in object storage (Azure Blob, GCS, S3)
- Use container orchestration (Azure Container Apps/AKS, Cloud Run, ECS)

---

## Troubleshooting

- **“OpenAI key missing”**  
  Ensure `.env` is present and exported in your shell (or passed to Docker). In CI, a dummy key is set automatically.

- **“Empty report”**  
  Increase `retrieval.top_k`, relax `prefilter_keywords`, or verify that your cleaned dataset is not empty.

- **“JSON validation failed” (agent output)**  
  Re‑run with lower temperature (`0–0.2`) and ensure response format uses `response_format={"type":"json_object"}`.

- **“Vector store not found”**  
  Run `make index` after `make ingest`; ensure `${VECTORSTORE_DIR}` exists and is writable.

---

## Extending the System

- **Add a new agent** (e.g., Action Item Extractor)  
  - Create `src/agents/<new_agent>.py` with a clear input/output contract (TypedDict or Pydantic).  
  - Wire the node in `src/graph/app.py`.  
  - Update `AGENTS.md` and `docs/Blueprint.md`.

- **Swap LLM provider** (e.g., Azure OpenAI)  
  - Extend `configs/model.yaml` and `src/services/llm.py` to read provider‑specific settings.  
  - Keep the same `chat_json` and `compose` interface.

- **Nested AGENTS files**  
  - If you add subpackages (e.g., `packages/ingestion-service`), place an `AGENTS.md` inside each.  
  - Agents will read the closest `AGENTS.md`, so subprojects can have tailored instructions.

---

## Style & Conventions

- **English‑only** for code, comments, docstrings, commit messages, and documentation.  
- **Formatting & Linting**: Black (line length 100), Ruff (default rules), optional Mypy & Bandit.  
- **Docstrings**: Google style; include input/output and edge cases.  
- **Config‑driven**: No hardcoded constants in agents; use `AppConfig`.  
- **Determinism**: Prefer deterministic preprocessing; agents operate only on retrieved evidence.  
- **Contracts first**: Enforce JSON schemas (e.g., `FlagItem`) at runtime and in tests.

---

### Quick Reference

```bash
# Setup
make setup

# Data pipeline
make ingest
make index

# Run multi-agent pipeline
make run
make report

# Quality & tests
make lint
make test
make ci-smoke
```

> This `AGENTS.md` is the single source of truth for agents and contributors. If you change the pipeline, thresholds, or agent contracts, **update this file** and mirror prompt changes in `docs/Blueprint.md`.
