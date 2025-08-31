# Multi-agent Risk Reporter PoC Makefile

.PHONY: help setup ingest index run report lint fmt test tests ci ci-smoke clean

# Default target
help:
	@echo "Multi-agent Risk Reporter PoC - Available targets:"
	@echo ""
	@echo "Setup & Environment:"
	@echo "  setup      - Create venv with uv, install project in editable mode"
	@echo "  clean      - Clean generated files and directories"
	@echo ""
	@echo "Data Pipeline:"
	@echo "  ingest     - Parse & clean documents from data/raw to data/clean"
	@echo "  index      - Build Chroma index at .vectorstore/"
	@echo ""
	@echo "Multi-agent Pipeline:"
	@echo "  run        - Execute pipeline and write ./data/report/portfolio_health.md"
	@echo "  report     - Same as 'run' (forces overwrite)"
	@echo ""
	@echo "Quality & Testing:"
	@echo "  lint       - Run code quality checks (Black, Ruff, Mypy, Bandit)"
	@echo "  fmt        - Format code (Black & Ruff)"
	@echo "  test       - Run pytest"
	@echo "  tests      - Alias for 'test'"
	@echo "  ci         - Run complete CI pipeline simulation (lint + smoke tests)"
	@echo "  ci-smoke   - Compile the graph, no LLM/network requests"

# Environment variables
PYTHON := python3.11
UV := uv
VENV := .venv
PYTHON_VENV := $(VENV)/bin/python
UV_VENV := $(UV) run

# Directories
DATA_RAW := ./data/raw
DATA_CLEAN := ./data/clean
VECTORSTORE_DIR := .vectorstore
REPORT_DIR := ./data/report

# Setup virtual environment and install dependencies
setup:
	@echo "Setting up development environment with uv..."
	$(UV) sync --extra dev
	@echo "Setup complete! Use 'uv run' to run commands or 'uv shell' to activate environment"

# Data ingestion: parse & clean documents
ingest:
	@echo "Ingesting and cleaning documents..."
	@mkdir -p $(DATA_CLEAN)
	$(UV_VENV) -m src.ingestion.parser --input-dir $(DATA_RAW) --output-dir $(DATA_CLEAN)
	@echo "Ingestion complete. Cleaned documents in $(DATA_CLEAN)"

# Build Chroma vector index
index:
	@echo "Building vector index..."
	@mkdir -p $(VECTORSTORE_DIR)
	$(UV_VENV) -m src.retrieval.store --input-dir $(DATA_CLEAN) --vectorstore-dir $(VECTORSTORE_DIR)
	@echo "Vector index built at $(VECTORSTORE_DIR)"

# Run the complete LangGraph pipeline
run:
	@echo "Running multi-agent pipeline..."
	@mkdir -p $(REPORT_DIR)
	@rm -f $(REPORT_DIR)/portfolio_health.md
	REPORT_DIR=$(REPORT_DIR) VECTORSTORE_DIR=$(VECTORSTORE_DIR) DATA_CLEAN=$(DATA_CLEAN) DATA_RAW=$(DATA_RAW) $(UV_VENV) -m src.agents.graph --vectorstore-dir $(VECTORSTORE_DIR) --output-file $(REPORT_DIR)/portfolio_health.md
	@echo "Report generated at $(REPORT_DIR)/portfolio_health.md"

# Generate final report
report:
	@echo "Generating final report..."
	@mkdir -p $(REPORT_DIR)
	@rm -f $(REPORT_DIR)/portfolio_health.md
	REPORT_DIR=$(REPORT_DIR) VECTORSTORE_DIR=$(VECTORSTORE_DIR) DATA_CLEAN=$(DATA_CLEAN) DATA_RAW=$(DATA_RAW) $(UV_VENV) -m src.agents.graph --vectorstore-dir $(VECTORSTORE_DIR) --output-file $(REPORT_DIR)/portfolio_health.md
	@echo "Report generated at $(REPORT_DIR)/portfolio_health.md"

# Code quality checks
lint:
	@echo "Running code quality checks..."
	@echo "Running Black..."
	@if $(UV_VENV) black --check --line-length=100 src/ tests/; then \
		echo "Black: PASSED"; \
	else \
		echo "Black: FAILED"; \
	fi
	@echo "Running Ruff..."
	@if $(UV_VENV) ruff check src/ tests/; then \
		echo "Ruff: PASSED"; \
	else \
		echo "Ruff: FAILED"; \
	fi
	@echo "Running MyPy..."
	@if $(UV_VENV) mypy src/; then \
		echo "MyPy: PASSED"; \
	else \
		echo "MyPy: FAILED ($$? errors)"; \
	fi
	@echo "Running Bandit..."
	@if $(UV_VENV) bandit -r src/ --skip B110 -f json -o bandit-report.json; then \
		echo "Bandit: PASSED"; \
	else \
		echo "Bandit: FAILED"; \
	fi
	@echo "Linting complete"

# Code formatting
fmt:
	@echo "Formatting code..."
	$(UV_VENV) black --line-length=100 src/ tests/
	$(UV_VENV) ruff check --fix src/ tests/
	@echo "Code formatting complete"

# Run tests
test:
	@echo "Running tests..."
	$(UV_VENV) pytest tests/ -v --tb=short
	@echo "Tests complete"

# Alias target for convenience
tests: test

# Complete CI pipeline simulation
ci:
	@echo "=========================================="
	@echo "SIMULATING COMPLETE CI PIPELINE"
	@echo "=========================================="
	@echo ""
	@echo "Phase 1: Lint & Quality Checks"
	@echo "=================================="
	$(MAKE) lint
	@echo ""
	@echo "Phase 2: Install & Smoke Tests"
	@echo "=================================="
	$(MAKE) ci-smoke
	@echo ""
	@echo "=========================================="
	@echo "CI PIPELINE COMPLETED SUCCESSFULLY!"
	@echo "=========================================="

# CI smoke test (no network calls)
ci-smoke:
	@echo "Running CI smoke test..."
	$(UV_VENV) tests/ci_smoke.py
	@echo "CI smoke test passed"

# Clean generated files
clean:
	@echo "Cleaning generated files..."
	rm -rf $(VENV)
	rm -rf $(VECTORSTORE_DIR)
	rm -rf $(DATA_CLEAN)
	rm -rf $(REPORT_DIR)
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -f bandit-report.json
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

# Development convenience targets
dev-setup: setup ingest index
	@echo "Development environment ready!"

full-pipeline: ingest index run report
	@echo "Full pipeline completed!"

# Check if virtual environment exists
check-venv:
	@if [ ! -d "$(VENV)" ]; then \
		echo "Virtual environment not found. Run 'make setup' first."; \
		echo "Or run 'uv sync --dev' to create the environment."; \
		exit 1; \
	fi

# Ensure data directories exist
check-data:
	@if [ ! -d "$(DATA_RAW)" ]; then \
		echo "Data directory $(DATA_RAW) not found. Please create it and add your documents."; \
		exit 1; \
	fi

# Dependencies for targets
ingest: check-venv check-data
index: check-venv
run: check-venv
report: check-venv
lint: check-venv
fmt: check-venv
test: check-venv
ci-smoke: check-venv
