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
from rapid.services.llm_service import LLMService

logger = logging.getLogger(__name__)
from rapid.config import (
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
    ) -> ConfidenceResult:
        relevance    = self._score_relevance(query, chunks)
        faithfulness = await self._score_faithfulness(answer, summaries)
        completeness = self._score_completeness(answer, query)

        score = (
            WEIGHT_RELEVANCE    * relevance +
            WEIGHT_FAITHFULNESS * faithfulness +
            WEIGHT_COMPLETENESS * completeness
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
