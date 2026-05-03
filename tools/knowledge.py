"""Local knowledge base / RAG tool (optional — needs chromadb, sentence-transformers)."""

from __future__ import annotations

import os
import hashlib

from tool_registry import tool
from sandbox import safe_resolve

# Lazy-initialised globals
_collection = None
_embedder = None


def _init_knowledge():
    """Lazy-load chromadb and sentence-transformers."""
    global _collection, _embedder
    if _collection is not None:
        return

    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
    except ImportError:
        raise RuntimeError(
            "Knowledge tools require: pip install chromadb sentence-transformers"
        )

    client = chromadb.Client()
    _collection = client.get_or_create_collection("agent_knowledge")
    _embedder = SentenceTransformer("all-MiniLM-L6-v2")


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


@tool(
    name="index_directory",
    description="Index all text files in a directory into the local knowledge base for semantic search.",
    parameters={
        "path": {"type": "string", "description": "Directory to index"},
    },
)
def index_directory(path: str) -> str:
    try:
        _init_knowledge()
    except RuntimeError as exc:
        return f"ERROR: {exc}"

    resolved = safe_resolve(path)
    if not os.path.isdir(resolved):
        return f"ERROR: Not a directory: {resolved}"

    text_extensions = {".py", ".js", ".ts", ".md", ".txt", ".json", ".yaml", ".yml",
                       ".toml", ".cfg", ".ini", ".html", ".css", ".java", ".go",
                       ".rs", ".c", ".cpp", ".h", ".rb", ".php", ".sh", ".bat"}
    indexed = 0

    for root, _dirs, files in os.walk(resolved):
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in text_extensions:
                continue
            fpath = os.path.join(root, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except OSError:
                continue

            chunks = _chunk_text(content)
            rel_path = os.path.relpath(fpath, resolved)

            ids = []
            documents = []
            metadatas = []
            for i, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{rel_path}:{i}".encode()).hexdigest()
                ids.append(doc_id)
                documents.append(chunk)
                metadatas.append({"source": rel_path, "chunk": i})

            if documents:
                embeddings = _embedder.encode(documents).tolist()
                _collection.upsert(
                    ids=ids,
                    documents=documents,
                    embeddings=embeddings,
                    metadatas=metadatas,
                )
                indexed += len(documents)

    return f"Indexed {indexed} chunks from {resolved}"


@tool(
    name="search_knowledge",
    description="Semantic search over previously indexed documents.",
    parameters={
        "query": {"type": "string", "description": "Search query"},
    },
)
def search_knowledge(query: str) -> str:
    try:
        _init_knowledge()
    except RuntimeError as exc:
        return f"ERROR: {exc}"

    if _collection.count() == 0:
        return "Knowledge base is empty. Use index_directory first."

    query_embedding = _embedder.encode([query]).tolist()
    results = _collection.query(query_embeddings=query_embedding, n_results=5)

    if not results["documents"] or not results["documents"][0]:
        return "No relevant results found."

    parts: list[str] = []
    for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
        source = meta.get("source", "unknown")
        parts.append(f"--- {source} ---\n{doc}\n")

    return "\n".join(parts)
