"""Command-line interface for the Multi-agent Risk Reporter.

Provides a console script (``risk-reporter``) that runs the same
end-to-end pipeline logic as ``python -m src.agents.graph``: it performs
retrieval (with fallbacks), executes the Analyzer → Verifier → Composer
graph, and writes/prints the report.
"""

from __future__ import annotations

import argparse
import logging
import os
from typing import Any

from src.agents.graph import _load_chunks_from_chroma, graph
from src.services.config import get_config


logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Multi-agent Risk Reporter pipeline")
    parser.add_argument("--vectorstore-dir", default=os.getenv("VECTORSTORE_DIR", ".vectorstore"))
    parser.add_argument("--output-file", default="")
    parser.add_argument("--project-context", default="QBR preparation report")
    args = parser.parse_args()

    # Load config and prepare retrieval query
    config = get_config()

    chunks: list[dict[str, Any]] = []
    selected_via = "retrieval"

    try:
        # Import locally to avoid heavy deps during import
        from src.retrieval.retriever import create_retriever

        retriever = create_retriever(
            vectorstore_dir=args.vectorstore_dir,
            collection_name="email_chunks",
            top_k=config.retrieval.top_k,
            prefilter_keywords=config.retrieval.prefilter_keywords,
        )

        keywords = list(
            dict.fromkeys(
                (config.flags.erb.get("critical_terms") or [])
                + (config.retrieval.prefilter_keywords or [])
            )
        )
        project_ctx = args.project_context or "portfolio health"
        query = f"{project_ctx} " + " ".join(keywords)

        topk = retriever.retrieve(query, top_k=config.retrieval.top_k)
        if isinstance(topk, list) and len(topk) > 0:
            chunks = topk
        else:
            selected_via = "full_dataset"
    except Exception as e:
        logger.warning(f"Retrieval failed, falling back to full dataset: {e}")
        selected_via = "full_dataset"
        chunks = []

    # Fallbacks: Chroma collection, then JSON file
    if not chunks:
        try:
            chunks = _load_chunks_from_chroma(args.vectorstore_dir)
        except Exception as e:
            logger.warning(f"Chroma loading failed: {e}")
            chunks = []

        if not chunks:
            try:
                import json

                with open("data/clean/chunks.json", encoding="utf-8") as f:
                    chunks = json.load(f)
            except Exception as e:
                logger.error(f"All chunk loading methods failed: {e}")
                chunks = []

    logger.info(f"Selected {len(chunks)} chunks via {selected_via}")

    initial_state: dict[str, Any] = {
        "chunks": chunks,
        "project_context": args.project_context,
        "candidates": [],
        "verified": [],
        "report": "",
    }

    result = graph.invoke(initial_state)
    report_text = result.get("report", "")

    if args.output_file:
        os.makedirs(os.path.dirname(args.output_file), exist_ok=True)
        with open(args.output_file, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"Report written to {args.output_file}")
    else:
        print(report_text)


if __name__ == "__main__":
    main()
