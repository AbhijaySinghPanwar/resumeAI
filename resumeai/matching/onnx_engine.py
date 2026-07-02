"""
resumeai/matching/onnx_engine.py — ONNX Runtime alternative to PyTorch SentenceTransformers.
"""
import os
import threading
from typing import List, Dict, Tuple
import numpy as np
from resumeai.utils.memory_profiler import log_memory

_SESSION = None
_TOKENIZER = None
_MODEL_LOCK = threading.Lock()

_MODEL_NAME = "Xenova/all-MiniLM-L6-v2"

def _get_onnx_model():
    """Lazy load ONNX model and tokenizer using huggingface_hub."""
    global _SESSION, _TOKENIZER
    with _MODEL_LOCK:
        if _SESSION is not None and _TOKENIZER is not None:
            return _SESSION, _TOKENIZER
            
        try:
            log_memory("Before ONNX model load")
            import onnxruntime as ort
            from tokenizers import Tokenizer
            from huggingface_hub import snapshot_download
            
            # Download exactly the onnx and tokenizer files
            model_path = snapshot_download(
                repo_id=_MODEL_NAME, 
                allow_patterns=["onnx/model.onnx", "tokenizer.json", "tokenizer_config.json"],
                local_files_only=False
            )
            
            onnx_file = os.path.join(model_path, "onnx", "model.onnx")
            tokenizer_file = os.path.join(model_path, "tokenizer.json")
            
            # Create session (limit threads for predictable memory/CPU)
            sess_options = ort.SessionOptions()
            sess_options.intra_op_num_threads = int(os.environ.get("ONNX_NUM_THREADS", "2"))
            sess_options.inter_op_num_threads = 1
            
            _SESSION = ort.InferenceSession(onnx_file, sess_options, providers=['CPUExecutionProvider'])
            _TOKENIZER = Tokenizer.from_file(tokenizer_file)
            
            # SentenceTransformers often adds special padding rules, Tokenizers handles padding 
            _TOKENIZER.enable_padding(pad_id=0, pad_token="[PAD]", direction='right')
            _TOKENIZER.enable_truncation(max_length=256)
            
            log_memory("After ONNX model load")
            return _SESSION, _TOKENIZER
        except Exception as e:
            from fastapi import HTTPException
            import logging
            logging.getLogger(__name__).error("ONNX initialization failed: %s", e, exc_info=True)
            raise HTTPException(status_code=503, detail="Embedding service unavailable")

def _mean_pooling(token_embeddings: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
    """
    Numpy equivalent of PyTorch mean pooling for sentence embeddings.
    token_embeddings: (batch_size, seq_len, hidden_size)
    attention_mask: (batch_size, seq_len)
    """
    input_mask_expanded = np.expand_dims(attention_mask, axis=-1)
    # Multiply token embeddings by mask (broadcast)
    sum_embeddings = np.sum(token_embeddings * input_mask_expanded, axis=1)
    # Clamp sum_mask to avoid division by zero
    sum_mask = np.clip(np.sum(input_mask_expanded, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask

def encode_texts(texts: List[str]) -> np.ndarray:
    """
    Encode a list of texts into embedding vectors using ONNX Runtime.
    """
    if not texts:
        return np.array([])
        
    session, tokenizer = _get_onnx_model()
    
    log_memory("Before ONNX embedding generation")
    
    # Tokenize
    encoded = tokenizer.encode_batch(texts)
    
    input_ids = np.array([e.ids for e in encoded], dtype=np.int64)
    attention_mask = np.array([e.attention_mask for e in encoded], dtype=np.int64)
    token_type_ids = np.array([e.type_ids for e in encoded], dtype=np.int64)
    
    ort_inputs = {
        "input_ids": input_ids,
        "attention_mask": attention_mask,
        "token_type_ids": token_type_ids
    }
    
    # Inference
    ort_outs = session.run(None, ort_inputs)
    token_embeddings = ort_outs[0]
    
    # Pooling
    sentence_embeddings = _mean_pooling(token_embeddings, attention_mask)
    
    # L2 Normalization
    norms = np.linalg.norm(sentence_embeddings, axis=1, keepdims=True)
    sentence_embeddings = sentence_embeddings / np.clip(norms, a_min=1e-12, a_max=None)
    
    log_memory("After ONNX embedding generation")
    return sentence_embeddings

def batch_encode_with_cache(texts: List[str], cache: Dict[str, np.ndarray]) -> np.ndarray:
    """
    Encode logic utilizing per-request cache.
    """
    if not texts:
        return np.array([])
        
    normalized_texts = [t.strip() for t in texts]
    unique_to_encode = list(set([t for t in normalized_texts if t and t not in cache]))
    
    if unique_to_encode:
        # ONNX batches naturally by sending all to encode_texts
        # We can implement batch_size splitting here if needed for memory, but for ONNX
        # usually small inputs can all go in one chunk if they aren't huge.
        # But we'll respect EMBEDDING_BATCH_SIZE to be safe.
        batch_size = int(os.environ.get("EMBEDDING_BATCH_SIZE", "8"))
        
        all_new_embs = []
        for i in range(0, len(unique_to_encode), batch_size):
            batch = unique_to_encode[i:i+batch_size]
            new_embs = encode_texts(batch)
            all_new_embs.append(new_embs)
            
        if all_new_embs:
            new_embs = np.vstack(all_new_embs)
        
        for t, emb in zip(unique_to_encode, new_embs):
            cache[t] = emb
            
    out = []
    for t in normalized_texts:
        if not t:
            dim = next(iter(cache.values())).shape[0] if cache else 384
            out.append(np.zeros(dim, dtype=np.float32))
        else:
            out.append(cache[t])
            
    return np.array(out)
