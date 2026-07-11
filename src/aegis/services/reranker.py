"""
Cross-encoder reranker — optional post-RRF re-scoring step.

Uses cross-encoder/ms-marco-MiniLM-L-6-v2 (22M params, ~50ms per 10 pairs on CPU).
Works with the flat structure's List[Dict] chunk format.

If sentence-transformers is not installed, rerank() returns chunks unchanged.
"""
import math
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

_model = None          # lazy singleton
_model_available: Optional[bool] = None   # None = not yet checked


def _get_model():
    global _model, _model_available
    if _model_available is False:
        return None
    if _model is not None:
        return _model
    try:
        from sentence_transformers import CrossEncoder
        _model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512)
        _model_available = True
    except Exception as e:
        logger.warning(f"Cross-encoder reranker could not be loaded (sentence-transformers unavailable or model download failed): {e}")
        _model_available = False
    return _model


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def rerank(query: str, chunks: List[Dict], top_k: int) -> List[Dict]:
    """
    Re-score chunks using a cross-encoder, return top_k sorted by score descending.

    Args:
        query:   User query (rewritten or original).
        chunks:  List of chunk dicts with at least {"text": str, ...}.
        top_k:   How many to return.

    Returns:
        Up to top_k chunks, sorted best-first.
        If sentence-transformers is unavailable, returns chunks[:top_k] unchanged.
    """
    if not chunks:
        return chunks

    model = _get_model()
    if model is None:
        return chunks[:top_k]

    try:
        pairs = [(query, c.get("text", "")[:800]) for c in chunks]
        raw_scores = model.predict(pairs)
        for chunk, raw in zip(chunks, raw_scores):
            chunk["score"] = _sigmoid(float(raw))
        chunks.sort(key=lambda c: c.get("score", 0.0), reverse=True)
    except Exception as e:
        logger.warning(f"Cross-encoder prediction failed, returning chunks in original order: {e}")

    return chunks[:top_k]
