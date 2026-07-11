import asyncio
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from aegis.config import CHUNK_K_CONSTANT
from aegis.services.bm25_engine import BM25Engine
from aegis.services.embedding_service import EmbeddingService
from aegis.services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

_MULTI_QUERY_SYSTEM = (
    "You are a search query optimizer. Generate 3 different phrasings of the user's "
    "question to improve document retrieval coverage. Use synonyms, alternate word "
    "orders, and rephrasings. Return ONLY a valid JSON array of exactly 3 strings — "
    "no markdown, no explanation, no code fences. Example output: "
    '[\"phrasing one\", \"phrasing two\", \"phrasing three\"]'
)
_MULTI_QUERY_PROMPT = "{query}"  # user message is just the query; system carries the instruction

# ---------------------------------------------------------------------------
# Module-level reranker singleton (loaded once, shared across all instances)
# ---------------------------------------------------------------------------

_RERANKER_MODEL = None
_RERANKER_LOCK = threading.Lock()


def _get_reranker():
    global _RERANKER_MODEL
    if _RERANKER_MODEL is not None:
        return _RERANKER_MODEL
    with _RERANKER_LOCK:
        if _RERANKER_MODEL is not None:
            return _RERANKER_MODEL
        try:
            from aegis.services.reranker import _get_model
            _RERANKER_MODEL = _get_model()
        except Exception as e:
            logger.warning(f"Reranker unavailable: {e}")
            _RERANKER_MODEL = False  # False = checked and unavailable
    return _RERANKER_MODEL


class R3Retriever:
    """
    Hybrid retrieval: vector search + BM25, merged with Reciprocal Rank Fusion.
    Formula: score(d) = Σ weight × 1 / (k + rank(d))  where k=60

    After RRF merge, an optional cross-encoder reranker re-scores chunks for
    better precision (requires sentence-transformers; graceful fallback if absent).

    Optional LLM-powered enhancement (requires llm= at construction time):
      - Multi-query (multi_query=True): retrieve for several query variants and merge
    """

    def __init__(
        self,
        vector_store: VectorStoreService,
        bm25: BM25Engine,
        embeddings: EmbeddingService,
        llm=None,
    ):
        self.vector = vector_store
        self.bm25 = bm25
        self.embeddings = embeddings
        self.llm = llm  # optional, for multi-query
        self._reranker_available = False
        try:
            self._reranker_available = _get_reranker() not in (None, False)
        except Exception:
            self._reranker_available = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        project_id: str,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.6,
        where: Optional[Dict] = None,
        multi_query: bool = False,
        variants: Optional[List[str]] = None,
    ) -> List[Dict]:
        """
        Hybrid retrieve for one (project, query).

        variants: pre-generated query variants to fold in. When provided (even an
          empty list), no LLM call is made here — the caller has already generated
          them once and reuses them across departments. When None and
          multi_query=True, variants are generated on demand (legacy path).
        """
        # Query-length adaptive weights
        words = len(query.split())
        if words <= 3:
            vector_weight = max(0.30, vector_weight - 0.15)  # short query → BM25 dominant
        elif words >= 12:
            vector_weight = min(0.85, vector_weight + 0.10)  # long NL → vector dominant

        query_embedding = await self.embeddings.embed(query)

        # Fetch 2× candidates so reranker has enough to pick from
        vector_results = self.vector.query(
            project_id, query_embedding, top_k=top_k * 2, where=where
        )
        bm25_results = self.bm25.query(project_id, query, top_k=top_k * 2)

        merged = self._rrf_merge(vector_results, bm25_results, vector_weight, top_k)

        # Resolve variants: use caller-supplied list, else generate if requested.
        if variants is None and multi_query and self.llm is not None:
            variants = await self.generate_variants(query)

        # Multi-query: retrieve for variants and fold into the main results
        if variants:
            variant_chunks = await self._retrieve_variants(
                project_id, variants, top_k, vector_weight
            )
            if variant_chunks:
                # Build a synthetic second result list from variant chunks so we
                # can re-merge everything through RRF for a consistent ranking.
                merged = self._rrf_merge(merged, variant_chunks, vector_weight, top_k)

        # Near-duplicate removal (bag-of-words Jaccard) before reranking
        merged = self._jaccard_deduplicate(merged, top_k)

        # Optional cross-encoder reranking (post-RRF, post-MMR)
        if _get_reranker() not in (None, False) and len(merged) > 1:
            try:
                from aegis.services.reranker import rerank
                merged = rerank(query, merged, top_k)
            except Exception as e:
                logger.warning(f"Cross-encoder reranking failed, keeping RRF order: {e}")

        return merged

    # ------------------------------------------------------------------
    # Near-duplicate filtering
    # ------------------------------------------------------------------

    def _jaccard_deduplicate(self, chunks: List[Dict], top_k: int) -> List[Dict]:
        """Filter near-duplicate chunks by bag-of-words Jaccard similarity (> 0.85)."""
        if len(chunks) <= 1:
            return chunks
        try:
            def _bow(text: str):
                words = set(text.lower().split())
                return words

            selected = [chunks[0]]
            for candidate in chunks[1:]:
                cand_words = _bow(candidate.get("text", ""))
                max_sim = max(
                    len(cand_words & _bow(s.get("text", ""))) / max(len(cand_words | _bow(s.get("text", ""))), 1)
                    for s in selected
                )
                if max_sim < 0.85:
                    selected.append(candidate)
                if len(selected) >= top_k:
                    break
            return selected
        except Exception as e:
            logger.warning(f"Jaccard dedup failed: {e}")
            return chunks[:top_k]

    # ------------------------------------------------------------------
    # Multi-query retrieval
    # ------------------------------------------------------------------

    async def generate_variants(self, query: str) -> List[str]:
        """
        Generate up to 3 alternate phrasings of *query* via the LLM.

        Split out from retrieval so the caller can generate variants once per
        sub-query and reuse them across every department index (one LLM call
        instead of one-per-department). Returns [] on any error or if no LLM.
        """
        if self.llm is None:
            return []
        try:
            raw = await self.llm.chat_simple(
                _MULTI_QUERY_PROMPT.format(query=query),
                system=_MULTI_QUERY_SYSTEM,
                temperature=0.4,
            )
            if not raw:
                logger.warning("Multi-query variant generation failed: LLM returned empty response")
                return []
            # Strip markdown code fences if LLM wrapped output (e.g. ```json ... ```)
            stripped = raw.strip()
            if stripped.startswith("```"):
                stripped = stripped.split("```")[1]
                if stripped.startswith("json"):
                    stripped = stripped[4:]
                stripped = stripped.strip()
            variants = json.loads(stripped)
            if not (isinstance(variants, list) and all(isinstance(v, str) for v in variants)):
                raise ValueError(f"Unexpected variants format from LLM: {type(variants)}")
            variants = [v.strip() for v in variants if v.strip()]
            return variants
        except Exception as e:
            logger.warning(f"Multi-query variant generation failed: {e}")
            return []

    async def _retrieve_variants(
        self,
        project_id: str,
        variants: List[str],
        top_k: int,
        vector_weight: float,
    ) -> List[Dict]:
        """
        Retrieve for each pre-generated variant concurrently and deduplicate.
        Returns up to top_k * 2 unique chunks. Falls back to [] on any error.
        """
        if not variants:
            return []

        async def _retrieve_one(variant: str) -> List[Dict]:
            try:
                emb = await self.embeddings.embed(variant)
                vec = self.vector.query(project_id, emb, top_k=top_k)
                bm = self.bm25.query(project_id, variant, top_k=top_k)
                return self._rrf_merge(vec, bm, vector_weight, top_k)
            except Exception as e:
                logger.warning(f"Multi-query single-variant retrieval failed for '{variant}': {e}")
                return []

        all_results: List[List[Dict]] = await asyncio.gather(*[_retrieve_one(v) for v in variants])

        # Deduplicate by chunk uid, preserving first-seen order
        seen: set = set()
        unique: List[Dict] = []
        for result_list in all_results:
            for doc in result_list:
                uid = doc["metadata"].get("source", "") + str(doc["metadata"].get("chunk_index", ""))
                if uid not in seen:
                    seen.add(uid)
                    unique.append(doc)
                    if len(unique) >= top_k * 2:
                        return unique

        return unique

    # ------------------------------------------------------------------
    # RRF merge
    # ------------------------------------------------------------------

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

        # Recency boost: documents indexed recently score slightly higher
        now = datetime.now(timezone.utc)
        for uid, doc in docs.items():
            indexed_at = doc.get("metadata", {}).get("indexed_at")
            if indexed_at:
                try:
                    dt = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
                    age_days = (now - dt).days
                    recency = 1.0 + max(0.0, (365 - age_days) / 365) * 0.15
                    scores[uid] = scores.get(uid, 0) * recency
                except Exception:
                    pass

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [docs[uid] for uid, _ in ranked]
