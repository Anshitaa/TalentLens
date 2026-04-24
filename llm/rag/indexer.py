"""
RAG indexer: load HR policy markdown files, chunk them, embed with
sentence-transformers, and persist a FAISS index alongside a pickled chunk list.
"""

import os
import pickle
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

DOCS_DIR = Path(__file__).parent / "docs"
INDEX_PATH = Path(__file__).parent / "faiss_index"

_MODEL_NAME = "all-MiniLM-L6-v2"
_CHUNK_SIZE = 500   # characters
_CHUNK_OVERLAP = 50  # characters


# ─────────────────────────────────────────────────────────────────────────────
# Chunking helpers
# ─────────────────────────────────────────────────────────────────────────────

def _chunk_text(text: str, chunk_size: int = _CHUNK_SIZE, overlap: int = _CHUNK_OVERLAP) -> list[str]:
    """
    Split *text* into overlapping fixed-size character chunks.
    Returns a list of non-empty string chunks.
    """
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + chunk_size, length)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start += chunk_size - overlap
    return chunks


def _load_docs(docs_dir: str | Path = DOCS_DIR) -> list[dict]:
    """
    Read all .md files in *docs_dir* and return a list of
    {"source": filename, "text": full_content} dicts.
    """
    docs_dir = Path(docs_dir)
    docs = []
    for md_file in sorted(docs_dir.glob("*.md")):
        text = md_file.read_text(encoding="utf-8")
        docs.append({"source": md_file.name, "text": text})
    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def build_index(docs_dir: str = str(DOCS_DIR)) -> None:
    """
    Load .md files from *docs_dir*, chunk them, embed with
    sentence-transformers all-MiniLM-L6-v2, and save a FAISS flat-L2 index
    plus a pickled list of chunk metadata to INDEX_PATH.

    The saved artefacts:
      <INDEX_PATH>.index  — FAISS binary index
      <INDEX_PATH>.pkl    — list of {"source": str, "text": str} dicts
    """
    docs = _load_docs(docs_dir)
    if not docs:
        raise FileNotFoundError(f"No .md files found in {docs_dir}")

    # Build chunks with source labels
    all_chunks: list[dict] = []
    for doc in docs:
        for chunk in _chunk_text(doc["text"]):
            all_chunks.append({"source": doc["source"], "text": chunk})

    print(f"[indexer] {len(docs)} docs → {len(all_chunks)} chunks")

    # Embed
    model = SentenceTransformer(_MODEL_NAME)
    texts = [c["text"] for c in all_chunks]
    embeddings: np.ndarray = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
    embeddings = embeddings.astype("float32")

    # Build FAISS index
    dim = embeddings.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(embeddings)

    # Persist
    index_path = Path(INDEX_PATH)
    index_path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(index_path) + ".index")
    with open(str(index_path) + ".pkl", "wb") as fh:
        pickle.dump(all_chunks, fh)

    print(f"[indexer] Index saved → {index_path}.index  ({index.ntotal} vectors, dim={dim})")


def load_index() -> tuple:
    """
    Load the persisted FAISS index and chunk list from INDEX_PATH.

    Returns:
        (index, doc_chunks)
        index      — faiss.Index ready for search
        doc_chunks — list of {"source": str, "text": str} dicts
    """
    index_file = str(INDEX_PATH) + ".index"
    chunks_file = str(INDEX_PATH) + ".pkl"

    if not os.path.exists(index_file):
        raise FileNotFoundError(
            f"FAISS index not found at {index_file}. "
            "Run llm.rag.indexer.build_index() first."
        )

    index = faiss.read_index(index_file)
    with open(chunks_file, "rb") as fh:
        doc_chunks = pickle.load(fh)

    return index, doc_chunks
