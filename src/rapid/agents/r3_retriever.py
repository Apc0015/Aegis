import logging
from typing import List, Dict, Optional
from rapid.services.vector_store_service import VectorStoreService
from rapid.services.bm25_engine import BM25Engine
from rapid.services.embedding_service import EmbeddingService
from rapid.config import CHUNK_K_CONSTANT

logger = logging.getLogger(__name__)


class R3Retriever:
    """
    Hybrid retrieval: vector search + BM25, merged with Reciprocal Rank Fusion.
    Formula: score(d) = Σ weight × 1 / (k + rank(d))  where k=60

    After RRF merge, an optional cross-encoder reranker re-scores chunks for
    better precision (requires sentence-transformers; graceful fallback if absent).
    """

    def __init__(
        self,
        vector_store: VectorStoreService,
        bm25: BM25Engine,
        embeddings: EmbeddingService,
    ):
        self.vector = vector_store
        self.bm25 = bm25
        self.embeddings = embeddings

        # Check reranker availability once at init time
        try:
            from rapid.services.reranker import _get_model
            self._reranker_available = _get_model() is not None
        except Exception as e:
            logger.warning(f"Reranker unavailable at init (sentence-transformers missing or failed): {e}")
            self._reranker_available = False

    async def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.6,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        query_embedding = await self.embeddings.embed(query)

        # Fetch 2× candidates so reranker has enough to pick from
        vector_results = self.vector.query(
            project_id, query_embedding, top_k=top_k * 2, where=where
        )
        bm25_results = self.bm25.query(project_id, query, top_k=top_k * 2)

        merged = self._rrf_merge(vector_results, bm25_results, vector_weight, top_k)

        # Optional cross-encoder reranking (post-RRF)
        if self._reranker_available and len(merged) > 1:
            try:
                from rapid.services.reranker import rerank
                merged = rerank(query, merged, top_k)
            except Exception as e:
                logger.warning(f"Cross-encoder reranking failed, keeping RRF order: {e}")

        return merged

    def _rrf_merge(
        self,
        vector_results: List[Dict],
        bm25_results: List[Dict],
        vector_weight: float,
        top_k: int,
    ) -> List[Dict]:
        k = CHUNK_K_CONSTANT
        bm25_weight = 1 - vector_weight
        scores: Dict[str, float] = {}
        docs: Dict[str, Dict] = {}

        for rank, doc in enumerate(vector_results):
            uid = doc["metadata"].get("source", "") + str(doc["metadata"].get("chunk_index", rank))
            scores[uid] = scores.get(uid, 0) + vector_weight * (1 / (k + rank + 1))
            docs[uid] = doc

        for rank, doc in enumerate(bm25_results):
            uid = doc["metadata"].get("source", "") + str(doc["metadata"].get("chunk_index", rank))
            scores[uid] = scores.get(uid, 0) + bm25_weight * (1 / (k + rank + 1))
            if uid not in docs:
                docs[uid] = doc

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [docs[uid] for uid, _ in ranked]
