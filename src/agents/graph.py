from src.agents.state import OverallState
from langgraph.graph import StateGraph, START, END
from src.agents.analyzer_agent import analyzer_agent
from src.agents.verifier_agent import verifier_agent
from src.agents.composer_agent import composer_agent
from src.services.config import get_config
import argparse
import os
import chromadb
from chromadb.config import Settings

def create_graph() -> StateGraph:
    """Create the overall graph."""
    graph = StateGraph(OverallState)

    graph.add_node("analyzer", analyzer_agent)
    graph.add_node("verifier", verifier_agent)
    graph.add_node("composer", composer_agent)

    graph.add_edge(START, "analyzer")
    graph.add_edge("analyzer", "verifier")
    graph.add_edge("verifier", "composer")
    graph.add_edge("composer", END)

    graph = graph.compile()

    return graph

def _load_all_chunks_from_chroma(vectorstore_dir: str, collection_name: str = "email_chunks"):
    client = chromadb.PersistentClient(path=vectorstore_dir, settings=Settings(anonymized_telemetry=False))
    collection = client.get_collection(name=collection_name)
    total = collection.count()
    if total <= 0:
        return []
    # Try fetching all rows with explicit limit; if still empty, fallback to paging
    try:
        raw = collection.get(include=["documents", "metadatas"], limit=total, offset=0)
        # Chroma get() doesn't support ids in include; ids may be absent
        ids = []
        docs = raw.get("documents", []) or []
        metas = raw.get("metadatas", []) or []
        # Some backends may return nested lists; flatten if needed
        if ids and isinstance(ids[0], list):
            ids = [item for sub in ids for item in sub]
        if docs and isinstance(docs[0], list):
            docs = [item for sub in docs for item in sub]
        if metas and isinstance(metas[0], list):
            metas = [item for sub in metas for item in sub]
        # Create synthetic ids if not available
        if not ids or len(ids) != len(docs):
            ids = [f"doc_{i}" for i in range(len(docs))]
        chunks = [{"id": i, "text": d or "", "metadata": m or {}} for i, d, m in zip(ids, docs, metas)]
        if chunks:
            return chunks
    except Exception:
        pass
    # Fallback: page through results
    chunks = []
    page = 0
    page_size = 100
    while True:
        try:
            raw = collection.get(include=["documents", "metadatas"], limit=page_size, offset=page * page_size)
            ids = []
            docs = raw.get("documents", []) or []
            metas = raw.get("metadatas", []) or []
            if not ids:
                # synth ids if none provided
                ids = [f"doc_{page*page_size + i}" for i in range(len(docs))]
            chunks.extend([{"id": i, "text": d or "", "metadata": m or {}} for i, d, m in zip(ids, docs, metas)])
            if len(docs) < page_size:
                break
            page += 1
        except Exception:
            break
    return chunks


# Create the graph instance
graph = create_graph()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run multi-agent risk reporter pipeline")
    parser.add_argument("--vectorstore-dir", default=os.getenv("VECTORSTORE_DIR", ".vectorstore"))
    parser.add_argument("--output-file", default="")
    parser.add_argument("--project-context", default="QBR preparation report")
    args = parser.parse_args()

    # Load config once
    config = get_config()

    # Primary path: use HybridRetriever to select Top-K chunks
    chunks = []
    selected_via = "retrieval"
    try:
        # Import locally to avoid heavy deps during CI smoke (when graph is only imported)
        from src.retrieval.retriever import create_retriever  # type: ignore

        retriever = create_retriever(
            vectorstore_dir=args.vectorstore_dir,
            collection_name="email_chunks",
            top_k=config.retrieval.top_k,
            prefilter_keywords=config.retrieval.prefilter_keywords,
        )

        # Build a deterministic aggregate query from project context and config keywords
        keywords = list(dict.fromkeys((config.flags.erb.get("critical_terms") or []) + (config.retrieval.prefilter_keywords or [])))
        project_ctx = args.project_context or "portfolio health"
        query = f"{project_ctx} " + " ".join(keywords)

        topk = retriever.retrieve(query, top_k=config.retrieval.top_k)
        if isinstance(topk, list) and len(topk) > 0:
            chunks = topk
        else:
            selected_via = "full_dataset"
    except Exception:
        # On any retriever error, fall back to full dataset
        selected_via = "full_dataset"
        chunks = []

    # Fallback: load full dataset from Chroma if Top-K unavailable
    if not chunks:
        try:
            chunks = _load_all_chunks_from_chroma(args.vectorstore_dir)
        except Exception:
            chunks = []

    # Debug: write initial chunks info (optional)
    if getattr(config, "debug_logs", False):
        try:
            report_dir = getattr(config, "report_dir", "report")
            os.makedirs(report_dir, exist_ok=True)
            with open(os.path.join(report_dir, "graph_initial_chunks.json"), "w", encoding="utf-8") as f:
                import json as _json
                _json.dump({
                    "total_chunks": len(chunks) if isinstance(chunks, list) else 0,
                    "sample_ids": [ch.get("id") for ch in (chunks[:5] if isinstance(chunks, list) else [])],
                    "selected_via": selected_via
                }, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # Fallback: if ChromaDB returned no chunks, try loading from data/clean/chunks.json
    if not chunks:
        try:
            clean_dir = os.getenv("DATA_CLEAN", config.data_clean)
            chunks_file = os.path.join(clean_dir, "chunks.json")
            if os.path.exists(chunks_file):
                import json as _json
                with open(chunks_file, "r", encoding="utf-8") as f:
                    chunks = _json.load(f)
        except Exception:
            chunks = []

    initial_state = {
        "messages": [],
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
            f.write(report_text or "")
        print(f"Report written to {args.output_file}")
    else:
        print(report_text)