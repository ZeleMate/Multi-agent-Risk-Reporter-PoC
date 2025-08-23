# Blueprint for the project

## Build System Choice: Hatchling

**Choice**: Hatchling build backend  
**Rationale**: Modern, fast Rust-based build tool that well supports src layout and requires minimal configuration. Ideal choice for CI/CD pipelines and integration with modern Python tooling stack (Black, Ruff, MyPy).

**Alternatives considered**:
- setuptools: traditional, but slower and more verbose
- poetry: dependency management + build, but overkill for this project
- flit: simple, but less flexible

## Project Architecture Decisions

### Repository Layout
- **src/ layout**: cleaner import structure, better testability
- **configs/**: YAML configurations instead of hardcoded values
- **data/raw** and **data/clean**: separated data pipelines
- **tests/**: unit and integration tests

### Multi-agent Pipeline
- **LangGraph**: stateful, deterministic agent workflow
- **ChromaDB**: local vector store, easily portable
- **Hybrid retrieval**: keyword + vector search optimization

### Development Workflow
- **Makefile**: simple commands for complex operations
- **CI/CD**: GitHub Actions, smoke tests without network
- **Quality gates**: Black, Ruff, MyPy, Bandit

## Key Design Principles

1. **Determinism**: preprocessing is deterministic, agents work only on retrieved evidence
2. **Evidence-based**: every claim must be supported by file:line references
3. **Config-driven**: no hardcoded constants in agents
4. **Local-first**: local development, cloud-ready architecture
5. **English-only**: code, comments, documentation in English

## Technology Stack Rationale

- **Python 3.11+**: modern type hints, performance improvements
- **LangGraph**: stateful multi-agent workflows
- **ChromaDB**: local vector store, simple deployment
- **OpenAI API**: stable, well-documented LLM provider
- **Pydantic**: runtime type validation, JSON schema enforcement