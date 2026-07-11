"""
3-axis confidence scoring:
  Context Relevance  (30%) — keyword overlap between query and retrieved chunks
  Faithfulness       (50%) — LLM judges whether answer is grounded in context
  Completeness       (20%) — answer length relative to query complexity

Cross-model evaluation:
  If evaluator_llm is provided (a DIFFERENT LLMService instance), faithfulness
  is judged by that model rather than the generator — eliminating self-preference bias.
"""
import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from aegis.services.llm_service import LLMService

logger = logging.getLogger(__name__)
from aegis.config import (
    WEIGHT_RELEVANCE, WEIGHT_FAITHFULNESS, WEIGHT_COMPLETENESS,
    CONFIDENCE_HIGH, CONFIDENCE_MEDIUM, INTERNAL_QUERY_SIGNALS
)

STOPWORDS = {
    "a","an","the","and","or","but","in","on","at","to","for",
    "of","with","by","from","is","are","was","were","be","been",
    "have","has","had","do","does","did","will","would","could",
    "should","may","might","can","what","how","when","where","who","which",
}

FAITHFULNESS_PROMPT = """Rate from 0 to 10 how well the answer is supported by
the provided context. 10 = fully supported, 0 = not supported at all.
Reply with ONLY a single integer 0-10. No explanation."""


@dataclass
class ConfidenceResult:
    score: float
    verdict: str          # "high", "medium", "low"
    relevance: float
    faithfulness: float
    completeness: float
    should_refuse: bool
    is_external: bool
    cross_model_eval: bool = False   # True if evaluator_llm was used
    db_triggered: bool = False       # True if DB pipeline contributed to this answer
    columns_blocked: list = None     # Columns blocked by access rules


class ConfidenceScorer:
    """
    Args:
        llm:           The main LLM (used as fallback evaluator if no evaluator_llm).
        evaluator_llm: Optional separate LLMService for faithfulness scoring.
                       Should be a DIFFERENT model from llm to avoid self-preference bias.
    """

    def __init__(
        self,
        llm: LLMService,
        evaluator_llm: Optional[LLMService] = None,
    ):
        self.llm = llm
        self.evaluator_llm = evaluator_llm

    def _keywords(self, text: str) -> set:
        return {w.lower() for w in re.findall(r'\b\w+\b', text)
                if w.lower() not in STOPWORDS and len(w) > 2}

    def _score_relevance(self, query: str, chunks: List[Dict]) -> float:
        qkw = self._keywords(query)
        if not qkw or not chunks:
            return 0.0
        hits = 0
        for chunk in chunks:
            ckw = self._keywords(chunk.get("text", ""))
            hits += len(qkw & ckw)
        ratio = hits / (len(qkw) * len(chunks))
        return min(1.0, ratio * 2.5)

    async def _score_faithfulness(self, answer: str, summaries: List[str]) -> float:
        # Use evaluator_llm if provided (cross-model), else fall back to main llm
        judge = self.evaluator_llm if self.evaluator_llm is not None else self.llm

        context = "\n".join(summaries[:3])
        prompt = f"Context:\n{context}\n\nAnswer:\n{answer}\n\nRate support (0-10):"
        try:
            raw = await judge.chat_simple(prompt, system=FAITHFULNESS_PROMPT)
            score = int(re.search(r'\d+', raw).group()) / 10.0
            return min(1.0, max(0.0, score))
        except Exception as e:
            logger.warning(f"LLM-based faithfulness scoring failed, falling back to keyword heuristic: {e}")
            # Fallback: word overlap heuristic (no LLM)
            ans_kw = self._keywords(answer)
            ctx_kw = self._keywords(" ".join(summaries))
            if not ans_kw:
                return 0.0
            return min(1.0, len(ans_kw & ctx_kw) / len(ans_kw))

    def _score_completeness(self, answer: str, query: str) -> float:
        words = len(answer.split())
        q_len = len(query.split())
        expected = 20 if q_len <= 5 else (40 if q_len <= 10 else 60)
        return min(1.0, words / expected)

    def _get_adaptive_weights(
        self,
        dept_experience: dict,
    ) -> tuple:
        """
        Return (weight_relevance, weight_faithfulness, weight_completeness) adjusted
        based on historical department performance stored in AgentMemoryStore.

        Tuning logic:
          - < 10 total queries  → not enough data, use defaults
          - high_ratio > 0.7    → dept does well, reward faithfulness more
          - high_ratio < 0.3    → dept struggles, boost relevance strictness
          - otherwise           → defaults

        All three weights always sum to 1.0.
        """
        total = dept_experience.get("total_queries", 0)
        if total < 10:
            return WEIGHT_RELEVANCE, WEIGHT_FAITHFULNESS, WEIGHT_COMPLETENESS

        high_count = dept_experience.get("high_confidence_count", 0)
        high_ratio = high_count / total

        if high_ratio > 0.7:
            # Department is performing well — lean harder on faithfulness
            return 0.25, 0.55, 0.20
        elif high_ratio < 0.3:
            # Department is struggling — be stricter about retrieval relevance
            return 0.40, 0.45, 0.15
        else:
            return WEIGHT_RELEVANCE, WEIGHT_FAITHFULNESS, WEIGHT_COMPLETENESS

    def _is_external(self, query: str) -> bool:
        q = query.lower()
        return not any(sig in q for sig in INTERNAL_QUERY_SIGNALS)

    async def score(
        self,
        query: str,
        chunks: List[Dict],
        summaries: List[str],
        answer: str,
        confidence_high: float = CONFIDENCE_HIGH,
        confidence_medium: float = CONFIDENCE_MEDIUM,
        db_triggered: bool = False,
        columns_blocked: list = None,
        dept_experience: dict = None,
        query_source: str = "faiss",
    ) -> ConfidenceResult:
        # File upload: bypass chunk-based relevance and LLM faithfulness judge.
        # The file IS the source (always relevant). Faithfulness uses keyword overlap
        # against the file summary — deterministic, not affected by answer meta-commentary.
        if query_source == "file_upload":
            relevance = 0.80
            ans_kw = self._keywords(answer)
            ctx_kw = self._keywords(" ".join(summaries))
            if not ans_kw:
                faithfulness = 0.50
            else:
                overlap = len(ans_kw & ctx_kw) / len(ans_kw)
                faithfulness = min(1.0, overlap * 1.5)
        else:
            relevance = self._score_relevance(query, chunks)
            faithfulness = await self._score_faithfulness(answer, summaries)
        completeness = self._score_completeness(answer, query)

        if dept_experience is not None:
            w_relevance, w_faithfulness, w_completeness = self._get_adaptive_weights(
                dept_experience
            )
        else:
            w_relevance, w_faithfulness, w_completeness = (
                WEIGHT_RELEVANCE,
                WEIGHT_FAITHFULNESS,
                WEIGHT_COMPLETENESS,
            )

        score = (
            w_relevance    * relevance +
            w_faithfulness * faithfulness +
            w_completeness * completeness
        )

        is_external = self._is_external(query)

        if score >= confidence_high:
            verdict, refuse = "high", False
        elif score >= confidence_medium:
            verdict, refuse = "medium", False
        else:
            verdict = "low"
            refuse  = not is_external  # internal low-conf → refuse; external → web fallback

        return ConfidenceResult(
            score=round(score, 3),
            verdict=verdict,
            relevance=round(relevance, 3),
            faithfulness=round(faithfulness, 3),
            completeness=round(completeness, 3),
            should_refuse=refuse,
            is_external=is_external,
            cross_model_eval=self.evaluator_llm is not None,
            db_triggered=db_triggered,
            columns_blocked=columns_blocked or [],
        )
