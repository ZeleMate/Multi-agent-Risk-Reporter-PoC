[![CI](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC/actions/workflows/ci.yaml)
[![Python Version](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Linting: Ruff](https://img.shields.io/badge/linting-ruff-6638B6.svg)](https://github.com/charliermarsh/ruff)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC/actions/workflows/ci.yaml)
[![Coverage](https://img.shields.io/badge/coverage-100%-green.svg)](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC)
[![LangGraph](https://img.shields.io/badge/LangGraph-3.0+-purple.svg)](https://github.com/langchain-ai/langgraph)
[![ChromaDB](https://img.shields.io/badge/ChromaDB-0.4+-green.svg)](https://www.trychroma.com/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--5-blue.svg)](https://openai.com/)

# Multi-agent Risk Reporter (PoC)
High-signal, evidence‑backed risk summaries from unstructured communications.

This PoC demonstrates a LangGraph‑based multi‑agent pipeline that ingests email threads, performs deterministic PII redaction and chunking, indexes content into a local ChromaDB vector store, and runs an Analyzer → Verifier → Composer flow to produce a well‑structured Markdown report. The system emphasizes determinism, citations, and cost‑aware retrieval.

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Make (GNU Make)

### Installation
```bash
# Clone the repository
git clone <this-repo>
cd multi-agent-risk-reporter-poc

# Setup environment with uv
make setup

# Or manually with uv
uv sync --dev
```

### Usage (Typical Loop)
```bash
# Setup data pipeline
make ingest       # Parse raw docs -> data/clean (parallel)
make index        # Build/update Chroma index (incremental)

# Run multi-agent pipeline
make run          # Run Analyzer → Verifier → Composer
make report       # Write data/report/portfolio_health.md

# Development
make lint         # Code quality checks (Ruff)
make fmt          # Format code (Black)
make test         # Run tests (pytest)
```

### Configuration
Copy `.env.example` to `.env` and set required variables.

Key environment variables:
```
OPENAI_API_KEY=sk-...
VECTORSTORE_DIR=.vectorstore
DATA_RAW=./data/raw
DATA_CLEAN=./data/clean
REPORT_DIR=./data/report
DEBUG_LOGS=false
```

Model/pipeline settings live under `configs/` and are loaded via `src/services/config.py`.

### Data Pipeline Commands (Advanced)
- Ingestion (parallel parsing):
```bash
uv run python -m src.ingestion.parser \
  --input-dir ./data/raw \
  --output-dir ./data/clean \
  --workers 8
```

- Indexing (incremental upsert, micro-batching):
```bash
uv run python -m src.retrieval.store \
  --input-dir ./data/clean \
  --vectorstore-dir .vectorstore \
  --batch-size 200 \
  --embed-batch-size 64           # per-forward embedding mini-batch
# Optional flags:
#   --no-incremental               # force full re-index
#   --prune-missing                # delete entries missing from chunks.json
```

### Tech Stack
- Orchestration: LangGraph (Analyzer, Verifier, Composer)
- LLMs: `gpt-5-mini` (analysis/verification), `gpt-5` (composition)
- Embeddings & Vector Store: Qwen3 Embedding + ChromaDB (local)
- Ingestion: deterministic parsing, PII redaction, thread-aware chunking
- Tooling: uv, Black, Ruff, pytest

### Key Features
- Evidence-first classification (file:line citations) with YAML agent contracts
- Parallel ingestion and incremental indexing (hash-based upsert)
- Cost-aware retrieval (optional keyword prefilter + vector top_k)
- Config-driven, debug artifacts toggle (`DEBUG_LOGS`)

### Output
- Markdown report: `data/report/portfolio_health.md`

### Documentation
- Operator/developer guide: `AGENTS.md`
- Architectural rationale: `BLUEPRINT.md` (final authoritative blueprint)
