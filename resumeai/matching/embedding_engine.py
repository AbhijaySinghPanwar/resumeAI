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


def _is_onnx() -> bool:
    import os
    from core.config import settings
    return getattr(settings, "EMBEDDING_ENGINE", "pytorch").lower() == "onnx"


def preload_model() -> bool:
    """
    Explicitly preload the embedding model at startup.
    Returns True on success, False on failure.
    Call this once during app startup to fail fast if model is unavailable.
    """
    global _MODEL, _LOAD_ERROR
    try:
        if _is_onnx():
            from resumeai.matching.onnx_engine import _get_onnx_model
            _get_onnx_model()
            logger.info("ONNX Embedding model '%s' loaded successfully.", _MODEL_NAME)
        else:
            _get_model()
            logger.info("PyTorch Embedding model '%s' loaded successfully.", _MODEL_NAME)
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
            import os
            import sys
            sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
            from resumeai.utils.memory_profiler import log_memory
            
            log_memory("Before model load")
            _MODEL = SentenceTransformer(_MODEL_NAME, device="cpu")
            log_memory("After model load")
            
            _LOAD_ERROR = None
            return _MODEL
        except ImportError as e:
            _LOAD_ERROR = str(e)
            raise RuntimeError(
                "sentence-transformers is not installed. "
                "Run: pip install sentence-transformers numpy torch"
            ) from e
        except Exception as e:
            _LOAD_ERROR = str(e)
            raise RuntimeError(
                f"Failed to load embedding model '{_MODEL_NAME}': {e}"
            ) from e


def is_available() -> bool:
    """Check if the embedding model is loaded and ready."""
    try:
        if _is_onnx():
            from resumeai.matching.onnx_engine import _get_onnx_model
            _get_onnx_model()
        else:
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
    import torch
    import os
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", ".."))
    from resumeai.utils.memory_profiler import log_memory

    if not texts:
        return np.array([])
        
    if _is_onnx():
        from resumeai.matching.onnx_engine import encode_texts as onnx_encode
        return onnx_encode(texts)
        
    model = _get_model()
    
    log_memory("Before embedding generation")
    batch_size = int(os.environ.get("EMBEDDING_BATCH_SIZE", "8"))
    with torch.inference_mode():
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
            batch_size=batch_size,
        )
    log_memory("After embedding generation")
    
    return embeddings


def batch_encode_with_cache(texts: List[str], cache: dict):
    """
    Encode a list of texts, utilizing a per-request cache.
    Normalizes texts (lowercase, strip) before caching/encoding.
    Returns a numpy array of shape (len(texts), hidden_size).
    """
    import numpy as np

    normalized_texts = []
    for t in texts:
        if not t:
            normalized_texts.append("")
        else:
            normalized_texts.append(t.strip().lower())

    unique_to_encode = []
    for t in set(normalized_texts):
        if t and t not in cache:
            unique_to_encode.append(t)

    if unique_to_encode:
        new_embs = encode_texts(unique_to_encode)
        for t, emb in zip(unique_to_encode, new_embs):
            cache[t] = emb

    hits = 0
    misses = len(unique_to_encode)
    
    # Build the output array
    out = []
    for t in normalized_texts:
        if not t:
            # Handle empty strings with zero vector
            dim = next(iter(cache.values())).shape[0] if cache else 384
            out.append(np.zeros(dim, dtype=np.float32))
        else:
            if t not in unique_to_encode:
                hits += 1
            out.append(cache[t])
            
    print(f"[CACHE] Hits: {hits}, Misses: {misses}, Total: {len(normalized_texts)}", flush=True)
    
    return np.array(out)



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
    cache: dict = None,
) -> List[float]:
    """
    For each query text, find the maximum similarity against any corpus text.
    Raises RuntimeError if model unavailable.
    """
    if not query_texts or not corpus_texts:
        return [0.0] * len(query_texts)

    if cache is None:
        q_vecs = encode_texts(query_texts)
        c_vecs = encode_texts(corpus_texts)
    else:
        q_vecs = batch_encode_with_cache(query_texts, cache)
        c_vecs = batch_encode_with_cache(corpus_texts, cache)

    sim_matrix = cosine_similarity_matrix(q_vecs, c_vecs)  # (q, c)
    max_scores = sim_matrix.max(axis=1).tolist()
    
    # explicit cleanup for memory safety
    import gc
    del q_vecs
    del c_vecs
    del sim_matrix
    gc.collect()
    
    return [max(0.0, min(1.0, float(s))) for s in max_scores]
