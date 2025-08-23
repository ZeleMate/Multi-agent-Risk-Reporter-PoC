[![CI](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/ZeleMate/Multi-agent-Risk-Reporter-PoC/actions/workflows/ci.yaml)

# Multi-agent-Risk-Reporter-PoC
This project demonstrates a LangGraph-based multi-agent pipeline designed to transform unstructured documents into structured risk reports.
It integrates classical data ingestion and preprocessing, local vector database storage, and multiple specialized agents for risk detection, validation, sensitive data filtering, and report composition.
The solution is modular, scalable, and designed to be portable across environments, from local PoC setups to cloud-native deployments.

## Quick Start

### Prerequisites
- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

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

### Usage
```bash
# Setup data pipeline
make ingest     # Parse raw docs -> data/clean
make index      # Build/update Chroma index

# Run multi-agent pipeline
make run        # Run Analyzer -> Verifier -> Composer
make report     # Write report/portfolio_health.md

# Development
make lint       # Code quality checks
make fmt        # Format code
make test       # Run tests
```
