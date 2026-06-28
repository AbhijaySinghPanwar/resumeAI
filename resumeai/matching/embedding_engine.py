"""
matching/embedding_engine.py — Singleton embedding engine using Sentence Transformers.

Model: all-MiniLM-L6-v2 (fast, accurate, ~80MB)
- Model is preloaded at startup via preload_model()
- Cached as singleton — never reloads per request
- Startup/health check via is_available()
- If unavailable, raises RuntimeError (no silent fallback)
"""
from __future__ import annotations

import threading
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# ── Model singleton ───────────────────────────────────────────────────────────
_MODEL = None
_MODEL_LOCK = threading.Lock()
_MODEL_NAME = "all-MiniLM-L6-v2"
_LOAD_ERROR: Optional[str] = None


def preload_model() -> bool:
    """
    Explicitly preload the embedding model at startup.
    Returns True on success, False on failure.
    Call this once during app startup to fail fast if model is unavailable.
    """
    global _MODEL, _LOAD_ERROR
    try:
        _get_model()
        logger.info("Embedding model '%s' loaded successfully.", _MODEL_NAME)
        return True
    except Exception as e:
        _LOAD_ERROR = str(e)
        logger.error("Failed to load embedding model '%s': %s", _MODEL_NAME, e)
        return False


def _get_model():
    """Load or return the cached Sentence Transformer model (thread-safe)."""
    global _MODEL, _LOAD_ERROR
    if _MODEL is not None:
        return _MODEL
    with _MODEL_LOCK:
        if _MODEL is not None:
            return _MODEL
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as _np  # noqa: verify numpy available
            _MODEL = SentenceTransformer(_MODEL_NAME)
            _LOAD_ERROR = None
            return _MODEL
        except ImportError as e:
            _LOAD_ERROR = str(e)
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers numpy"
            ) from e
        except Exception as e:
            _LOAD_ERROR = str(e)
            raise RuntimeError(
                f"Failed to load embedding model '{_MODEL_NAME}': {e}"
            ) from e


def is_available() -> bool:
    """Check if the embedding model is loaded and ready."""
    try:
        _get_model()
        return True
    except Exception:
        return False


def get_status() -> dict:
    """Return embedding engine status for health checks."""
    available = is_available()
    return {
        "available": available,
        "model": _MODEL_NAME,
        "error": _LOAD_ERROR if not available else None,
    }


def encode_texts(texts: List[str]):
    """
    Encode a list of texts into embedding vectors.
    Raises RuntimeError if model is not available.
    """
    import numpy as np
    if not texts:
        return np.array([])
    model = _get_model()
    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=64,
    )
    return np.array(embeddings)


def cosine_similarity_matrix(a, b):
    """
    Compute cosine similarity between two sets of L2-normalised vectors.
    Returns shape (m, n).
    """
    import numpy as np
    if a.ndim == 1:
        a = a.reshape(1, -1)
    if b.ndim == 1:
        b = b.reshape(1, -1)
    return np.dot(a, b.T)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Compute semantic similarity between two text strings.
    Returns float in [0.0, 1.0].
    Raises RuntimeError if model unavailable.
    """
    if not text_a.strip() or not text_b.strip():
        return 0.0
    vecs = encode_texts([text_a, text_b])
    sim = float(cosine_similarity_matrix(vecs[0], vecs[1])[0][0])
    return max(0.0, min(1.0, sim))


def max_similarity_scores(
    query_texts: List[str],
    corpus_texts: List[str],
) -> List[float]:
    """
    For each query text, find the maximum similarity against any corpus text.
    Raises RuntimeError if model unavailable.
    """
    if not query_texts or not corpus_texts:
        return [0.0] * len(query_texts)

    q_vecs = encode_texts(query_texts)
    c_vecs = encode_texts(corpus_texts)

    sim_matrix = cosine_similarity_matrix(q_vecs, c_vecs)  # (q, c)
    max_scores = sim_matrix.max(axis=1).tolist()
    return [max(0.0, min(1.0, float(s))) for s in max_scores]
