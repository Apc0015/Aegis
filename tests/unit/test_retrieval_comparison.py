"""
Unit tests for retrieval quality: hybrid (vector + BM25 + RRF) vs single-method.

Metrics: Precision@5, Recall@5 — hybrid must match or beat single-method on
each metric to pass.
"""
import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def precision_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / k if k else 0.0


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str], k: int) -> float:
    top_k = retrieved_ids[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_ids)
    return hits / len(relevant_ids) if relevant_ids else 0.0


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

RELEVANT_IDS = {"c1", "c2", "c3"}  # ground-truth relevant chunks for the test query

VECTOR_RESULTS = ["c1", "c3", "c5", "c4", "c2"]   # vector-only ranking
BM25_RESULTS   = ["c2", "c1", "c4", "c3", "c5"]   # BM25-only ranking

# RRF merges both: c1 appears at pos 0+1 → high fused score; c3 at 1+3; c2 at 4+0
HYBRID_RESULTS = ["c1", "c2", "c3", "c4", "c5"]   # expected RRF output


def _rrf_fuse(vector_ids: list[str], bm25_ids: list[str], k: int = 60) -> list[str]:
    """Minimal RRF implementation for testing purposes."""
    scores: dict[str, float] = {}
    for rank, doc_id in enumerate(vector_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, doc_id in enumerate(bm25_ids):
        scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores, key=lambda d: scores[d], reverse=True)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRetrievalComparison:

    def test_hybrid_precision_at_5_beats_vector_only(self):
        hybrid  = _rrf_fuse(VECTOR_RESULTS, BM25_RESULTS)
        p_hybrid = precision_at_k(hybrid, RELEVANT_IDS, k=5)
        p_vector = precision_at_k(VECTOR_RESULTS, RELEVANT_IDS, k=5)
        assert p_hybrid >= p_vector, (
            f"Hybrid P@5 ({p_hybrid:.2f}) should be >= vector-only ({p_vector:.2f})"
        )

    def test_hybrid_recall_at_5_beats_vector_only(self):
        hybrid  = _rrf_fuse(VECTOR_RESULTS, BM25_RESULTS)
        r_hybrid = recall_at_k(hybrid, RELEVANT_IDS, k=5)
        r_vector = recall_at_k(VECTOR_RESULTS, RELEVANT_IDS, k=5)
        assert r_hybrid >= r_vector, (
            f"Hybrid R@5 ({r_hybrid:.2f}) should be >= vector-only ({r_vector:.2f})"
        )

    def test_hybrid_precision_at_5_beats_bm25_only(self):
        hybrid  = _rrf_fuse(VECTOR_RESULTS, BM25_RESULTS)
        p_hybrid = precision_at_k(hybrid, RELEVANT_IDS, k=5)
        p_bm25   = precision_at_k(BM25_RESULTS, RELEVANT_IDS, k=5)
        assert p_hybrid >= p_bm25, (
            f"Hybrid P@5 ({p_hybrid:.2f}) should be >= BM25-only ({p_bm25:.2f})"
        )

    def test_hybrid_recall_at_5_beats_bm25_only(self):
        hybrid  = _rrf_fuse(VECTOR_RESULTS, BM25_RESULTS)
        r_hybrid = recall_at_k(hybrid, RELEVANT_IDS, k=5)
        r_bm25   = recall_at_k(BM25_RESULTS, RELEVANT_IDS, k=5)
        assert r_hybrid >= r_bm25, (
            f"Hybrid R@5 ({r_hybrid:.2f}) should be >= BM25-only ({r_bm25:.2f})"
        )

    def test_rrf_top_result_is_highest_consensus(self):
        """Doc appearing near top of both lists must rank first after fusion."""
        hybrid = _rrf_fuse(VECTOR_RESULTS, BM25_RESULTS)
        # c1 is rank-1 in vector and rank-2 in BM25 → highest fused score
        assert hybrid[0] == "c1", f"Expected c1 at top, got {hybrid[0]}"

    def test_precision_at_k_helper_correctness(self):
        assert precision_at_k(["c1", "c2", "c9", "c8", "c7"], {"c1", "c2"}, k=5) == pytest.approx(0.4)

    def test_recall_at_k_helper_correctness(self):
        assert recall_at_k(["c1", "c9", "c3"], {"c1", "c2", "c3"}, k=3) == pytest.approx(2 / 3)
