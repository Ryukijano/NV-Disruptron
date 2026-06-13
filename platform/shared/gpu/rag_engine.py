"""NeMo Retriever-style RAG with GPU vector search.

Uses cuVS (RAPIDS GPU vector search) for in-GPU retrieval, falling back to
FAISS-CPU if cuVS is unavailable. Embeddings via Llama-Nemotron Embed or
OpenAI-compatible embed endpoint.

Usage:
    from shared.gpu.rag_engine import RAGEngine
    rag = RAGEngine()
    rag.add_documents([{"text": "TfL Step-Free Access Guide...", "source": "tfl"}])
    results = rag.query("Where can I find step-free tube stations?")
"""

import json
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[4]
RAG_DB = REPO_ROOT / "data" / "rag_vectors.db"
RAG_DB.parent.mkdir(parents=True, exist_ok=True)

GPU_VS_AVAILABLE = False
try:
    import cuvs
    from cuvs.neighbors import cagra
    GPU_VS_AVAILABLE = True
except Exception:
    pass

# FAISS fallback
FAISS_AVAILABLE = False
try:
    import faiss
    FAISS_AVAILABLE = True
except Exception:
    pass


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float
    metadata: dict[str, Any]


class RAGEngine:
    """GPU-accelerated RAG retrieval engine."""

    def __init__(
        self,
        embedding_dim: int = 768,
        top_k: int = 5,
        embed_url: str = "http://localhost:8000/v1/embeddings",
        embed_model: str = "llama-nemotron-embed",
    ) -> None:
        self.embedding_dim = embedding_dim
        self.top_k = top_k
        self.embed_url = embed_url
        self.embed_model = embed_model
        self._chunks: list[dict] = []
        self._vectors: np.ndarray | None = None
        self._gpu_index: Any = None
        self._faiss_index: Any = None
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(RAG_DB) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY,
                    text TEXT NOT NULL,
                    source TEXT,
                    embedding BLOB,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY,
                    query TEXT,
                    results TEXT,
                    latency_ms REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _get_embedding(self, texts: list[str]) -> np.ndarray:
        """Get embeddings via local vLLM embed endpoint or HTTP fallback."""
        import httpx
        try:
            resp = httpx.post(
                self.embed_url,
                json={"model": self.embed_model, "input": texts},
                timeout=30.0,
            )
            data = resp.json()
            embeddings = [item["embedding"] for item in data["data"]]
            return np.array(embeddings, dtype=np.float32)
        except Exception:
            # Fallback to simple sentence-transformers style avg word vectors
            return self._fallback_embedding(texts)

    def _fallback_embedding(self, texts: list[str]) -> np.ndarray:
        """Simple hash-based embedding fallback for when embed endpoint is down."""
        vectors = []
        for text in texts:
            tokens = text.lower().split()
            vec = np.zeros(self.embedding_dim, dtype=np.float32)
            for i, tok in enumerate(tokens):
                h = hash(tok) % self.embedding_dim
                vec[h] += 1.0
            if np.linalg.norm(vec) > 0:
                vec = vec / np.linalg.norm(vec)
            vectors.append(vec)
        return np.array(vectors, dtype=np.float32)

    def add_documents(self, documents: list[dict[str, Any]]) -> None:
        """Ingest documents and build GPU vector index."""
        texts = [d["text"] for d in documents]
        embeddings = self._get_embedding(texts)

        # Store in SQLite
        with sqlite3.connect(RAG_DB) as conn:
            for doc, emb in zip(documents, embeddings):
                conn.execute(
                    """INSERT INTO chunks (text, source, embedding, metadata)
                       VALUES (?, ?, ?, ?)""",
                    (
                        doc["text"],
                        doc.get("source", "unknown"),
                        emb.tobytes(),
                        json.dumps(doc.get("metadata", {})),
                    ),
                )
            conn.commit()

        # Load all vectors for index rebuild
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild cuVS (GPU) or FAISS (CPU) index from SQLite."""
        with sqlite3.connect(RAG_DB) as conn:
            rows = conn.execute(
                "SELECT id, text, source, embedding, metadata FROM chunks ORDER BY id"
            ).fetchall()

        if not rows:
            return

        self._chunks = [
            {
                "id": r[0],
                "text": r[1],
                "source": r[2],
                "metadata": json.loads(r[4]) if r[4] else {},
            }
            for r in rows
        ]

        vectors = np.array(
            [np.frombuffer(r[3], dtype=np.float32) for r in rows],
            dtype=np.float32,
        )
        self._vectors = vectors

        if GPU_VS_AVAILABLE and vectors.shape[0] > 0:
            try:
                import cupy as cp
                gpu_vecs = cp.asarray(vectors)
                # Build CAGRA index
                index_params = cagra.IndexParams(
                    metric="sqeuclidean",
                    graph_degree=32,
                )
                self._gpu_index = cagra.build(index_params, gpu_vecs)
            except Exception as exc:
                self._gpu_index = None

        if self._gpu_index is None and FAISS_AVAILABLE and vectors.shape[0] > 0:
            self._faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            faiss.normalize_L2(vectors)
            self._faiss_index.add(vectors)

    def query(self, query_text: str) -> dict[str, Any]:
        """Retrieve top-k chunks for query."""
        import time
        t0 = time.perf_counter()

        query_vec = self._get_embedding([query_text])
        query_vec = query_vec / (np.linalg.norm(query_vec) + 1e-8)

        if self._gpu_index is not None:
            # cuVS GPU search
            import cupy as cp
            gpu_q = cp.asarray(query_vec)
            search_params = cagra.SearchParams()
            distances, indices = cagra.search(
                search_params, self._gpu_index, gpu_q, self.top_k
            )
            distances = cp.asnumpy(distances)[0]
            indices = cp.asnumpy(indices)[0]
        elif self._faiss_index is not None:
            # FAISS CPU search
            faiss.normalize_L2(query_vec)
            distances, indices = self._faiss_index.search(query_vec, self.top_k)
            distances = distances[0]
            indices = indices[0]
        else:
            # Brute force fallback
            if self._vectors is None or self._vectors.shape[0] == 0:
                return {"results": [], "gpu_accelerated": False, "latency_ms": 0}
            scores = np.dot(self._vectors, query_vec[0])
            top_idx = np.argsort(scores)[::-1][:self.top_k]
            distances = scores[top_idx]
            indices = top_idx

        results = []
        for idx, dist in zip(indices, distances):
            if idx < 0 or idx >= len(self._chunks):
                continue
            chunk = self._chunks[idx]
            results.append(
                RetrievedChunk(
                    text=chunk["text"],
                    source=chunk["source"],
                    score=float(dist),
                    metadata=chunk["metadata"],
                )
            )

        latency_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Log query
        with sqlite3.connect(RAG_DB) as conn:
            conn.execute(
                "INSERT INTO queries (query, results, latency_ms) VALUES (?, ?, ?)",
                (query_text, json.dumps([{"text": r.text, "source": r.source, "score": r.score} for r in results]), latency_ms),
            )
            conn.commit()

        return {
            "query": query_text,
            "results": [
                {
                    "text": r.text,
                    "source": r.source,
                    "score": round(r.score, 4),
                    "metadata": r.metadata,
                }
                for r in results
            ],
            "gpu_accelerated": self._gpu_index is not None,
            "latency_ms": latency_ms,
        }


# Singleton engine
_rag_engine: RAGEngine | None = None


def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
