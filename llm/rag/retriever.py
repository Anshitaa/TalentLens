"""
RAG retriever: lazy-loads the FAISS index on first call and provides
a simple search interface for HR policy chunks.
"""

import numpy as np
from sentence_transformers import SentenceTransformer

_MODEL_NAME = "all-MiniLM-L6-v2"

# Module-level cache — populated on first call to search()
_index = None
_doc_chunks: list[dict] | None = None
_embed_model: SentenceTransformer | None = None


def _ensure_loaded() -> None:
    """Lazily load the FAISS index, chunk store, and embedding model."""
    global _index, _doc_chunks, _embed_model
    if _index is not None:
        return  # already loaded

    from llm.rag.indexer import load_index
    _index, _doc_chunks = load_index()
    _embed_model = SentenceTransformer(_MODEL_NAME)


def search(query: str, k: int = 3) -> list[str]:
    """
    Return the top-*k* most relevant HR policy text chunks for *query*.

    Each returned string is the raw chunk text. The caller can use these
    as context for LLM prompts.

    Raises FileNotFoundError if the index has not been built yet — call
    llm.rag.indexer.build_index() once to create it.
    """
    _ensure_loaded()

    query_vec: np.ndarray = _embed_model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = _index.search(query_vec, k)

    results = []
    for idx in indices[0]:
        if idx < 0 or idx >= len(_doc_chunks):
            continue
        results.append(_doc_chunks[idx]["text"])

    return results


def search_with_sources(query: str, k: int = 3) -> list[dict]:
    """
    Like search(), but returns dicts with both 'source' and 'text' keys.
    Useful when you want to label which policy document a chunk came from.
    """
    _ensure_loaded()

    query_vec: np.ndarray = _embed_model.encode([query], convert_to_numpy=True).astype("float32")
    distances, indices = _index.search(query_vec, k)

    results = []
    for rank, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(_doc_chunks):
            continue
        chunk = _doc_chunks[idx]
        results.append({
            "rank": rank + 1,
            "source": chunk["source"],
            "text": chunk["text"],
            "distance": float(distances[0][rank]),
        })

    return results
