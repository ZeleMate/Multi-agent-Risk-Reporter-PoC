import argparse
import logging
import os
from typing import Any

from langgraph.graph import END, START, StateGraph

from src.agents.analyzer_agent import analyzer_agent
from src.agents.composer_agent import composer_agent
from src.agents.state import OverallState
from src.agents.verifier_agent import verifier_agent
from src.services.config import get_config

logger = logging.getLogger(__name__)


def create_graph() -> Any:
    """Create the overall graph."""
    graph = StateGraph(OverallState)

    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("verifier", verifier_agent)
    graph.add_node("composer", composer_agent)

    graph.add_edge(START, "analyzer")
    graph.add_edge("analyzer", "verifier")
    graph.add_edge("verifier", "composer")
    graph.add_edge("composer", END)

    compiled = graph.compile()

    return compiled


def _load_chunks_from_chroma(vectorstore_dir: str) -> list[dict[str, Any]]:
    """Load chunks from ChromaDB."""
    try:
        import chromadb
        from chromadb.config import Settings

        client = chromadb.PersistentClient(
            path=vectorstore_dir, settings=Settings(anonymized_telemetry=False)
        )
        collection = client.get_collection(name="email_chunks")
        raw = collection.get(include=["documents", "metadatas"])
        docs = raw.get("documents", []) or []
        metas = raw.get("metadatas", []) or []

        return [
            {"id": f"doc_{i}", "text": d or "", "metadata": m or {}}
            for i, (d, m) in enumerate(zip(docs, metas, strict=False))
        ]
    except Exception:
        return []


# Create the graph instance (compiled)
graph = create_graph()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run multi-agent risk reporter pipeline")
    parser.add_argument("--vectorstore-dir", default=os.getenv("VECTORSTORE_DIR", ".vectorstore"))
    parser.add_argument("--output-file", default="")
    parser.add_argument("--project-context", default="QBR preparation report")
    args = parser.parse_args()

    # Load config for retrieval settings
    config = get_config()

    # Primary path: use HybridRetriever to select Top-K chunks
    chunks = []
    selected_via = "retrieval"
    try:
        # Import locally to avoid heavy deps during CI smoke
        from src.retrieval.retriever import create_retriever

        retriever = create_retriever(
            vectorstore_dir=args.vectorstore_dir,
            collection_name="email_chunks",
            top_k=config.retrieval.top_k,
            prefilter_keywords=config.retrieval.prefilter_keywords,
        )

        # Build query from project context and config keywords
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

    # Fallback: load full dataset if retrieval unavailable
    if not chunks:
        try:
            chunks = _load_chunks_from_chroma(args.vectorstore_dir)
        except Exception as e:
            logger.warning(f"Chroma loading failed: {e}")
            chunks = []

        # Final fallback to JSON
        if not chunks:
            try:
                import json

                with open("data/clean/chunks.json", encoding="utf-8") as f:
                    chunks = json.load(f)
            except Exception as e:
                logger.error(f"All chunk loading methods failed: {e}")
                chunks = []

    logger.info(f"Selected {len(chunks)} chunks via {selected_via}")

    initial_state = {
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
