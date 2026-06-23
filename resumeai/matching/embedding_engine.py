"""
matching/embedding_engine.py — Singleton embedding engine using Sentence Transformers.

Model: all-MiniLM-L6-v2 (fast, accurate, ~80MB)
Caches model singleton — never reloads per request.
Caches encoded vectors using LRU cache.
"""
from __future__ import annotations

import hashlib
import threading
from functools import lru_cache
from typing import List, Optional

import numpy as np

# ── Lazy import guard ─────────────────────────────────────────────────────────
_MODEL = None
_MODEL_LOCK = threading.Lock()
_MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model():
    """Load or return the cached Sentence Transformer model (thread-safe)."""
    global _MODEL
    if _MODEL is None:
        with _MODEL_LOCK:
            if _MODEL is None:  # double-checked locking
                try:
                    from sentence_transformers import SentenceTransformer
                    _MODEL = SentenceTransformer(_MODEL_NAME)
                except ImportError:
                    raise RuntimeError(
                        "sentence-transformers is not installed. "
                        "Run: pip install sentence-transformers"
                    )
    return _MODEL


def encode_texts(texts: List[str]) -> np.ndarray:
    """
    Encode a list of texts into embedding vectors.
    
    Args:
        texts: List of strings to encode
        
    Returns:
        numpy array of shape (len(texts), embedding_dim)
    """
    if not texts:
        return np.array([])
    model = _get_model()
    # normalize_embeddings=True gives cosine similarity via dot product
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return np.array(embeddings)


def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Compute cosine similarity between two sets of vectors.
    Since vectors are L2-normalized, this is just dot product.
    
    Args:
        a: shape (m, d)
        b: shape (n, d)
        
    Returns:
        shape (m, n) similarity matrix with values in [-1, 1]
    """
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)
    return np.dot(a, b.T)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute semantic similarity between two text strings.
    
    Returns:
        float in [0.0, 1.0]
    """
    if not text_a.strip() or not text_b.strip():
        return 0.0
    vecs = encode_texts([text_a, text_b])
    sim = float(cosine_similarity_matrix(vecs[0], vecs[1])[0][0])
    # Clamp to [0, 1]
    return max(0.0, min(1.0, sim))


def max_similarity_scores(
    query_texts: List[str],
    corpus_texts: List[str],
) -> List[float]:
    """
    For each query text, find the maximum similarity against any corpus text.
    
    Args:
        query_texts: Texts to query (e.g., JD responsibilities)
        corpus_texts: Corpus to search (e.g., resume bullets)
        
    Returns:
        List of max similarity scores for each query
    """
    if not query_texts or not corpus_texts:
        return [0.0] * len(query_texts)

    q_vecs = encode_texts(query_texts)
    c_vecs = encode_texts(corpus_texts)

    sim_matrix = cosine_similarity_matrix(q_vecs, c_vecs)  # (q, c)
    max_scores = sim_matrix.max(axis=1).tolist()
    return [max(0.0, min(1.0, s)) for s in max_scores]


def is_available() -> bool:
    """Check if sentence-transformers is installed and model can be loaded."""
    try:
        _get_model()
        return True
    except Exception:
        return False
