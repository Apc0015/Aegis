"""
Unit tests for ConfidenceScorer calibration.

Verifies that:
- High-quality context + coherent answer → score ≥ CONFIDENCE_HIGH (0.65)
- Empty context → score < CONFIDENCE_MEDIUM (0.40)
- Weights sum to 1.0
- Score is always in [0, 1]
"""
import pytest
from unittest.mock import MagicMock, patch

from rapid.config import (
    CONFIDENCE_HIGH,
    CONFIDENCE_MEDIUM,
    WEIGHT_RELEVANCE,
    WEIGHT_FAITHFULNESS,
    WEIGHT_COMPLETENESS,
)


# ---------------------------------------------------------------------------
# Helpers to build mock ConfidenceScorer responses
# ---------------------------------------------------------------------------

def _make_scorer(relevance: float, faithfulness: float, completeness: float):
    """Return a ConfidenceScorer whose LLM always returns the given sub-scores."""
    from rapid.agents.confidence_scorer import ConfidenceScorer

    mock_llm = MagicMock()
    # The scorer calls llm.complete() and parses JSON from the response.
    mock_llm.complete.return_value = (
        f'{{"relevance": {relevance}, "faithfulness": {faithfulness}, '
        f'"completeness": {completeness}}}'
    )

    scorer = ConfidenceScorer.__new__(ConfidenceScorer)
    scorer.llm = mock_llm
    return scorer


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestConfidenceWeights:

    def test_weights_sum_to_one(self):
        total = WEIGHT_RELEVANCE + WEIGHT_FAITHFULNESS + WEIGHT_COMPLETENESS
        assert total == pytest.approx(1.0), f"Weights sum to {total}, expected 1.0"

    def test_high_scores_produce_high_confidence(self):
        """relevance=0.9, faithfulness=0.9, completeness=0.9 → score ≥ CONFIDENCE_HIGH"""
        expected = (
            0.9 * WEIGHT_RELEVANCE
            + 0.9 * WEIGHT_FAITHFULNESS
            + 0.9 * WEIGHT_COMPLETENESS
        )
        assert expected >= CONFIDENCE_HIGH, (
            f"Expected score {expected:.3f} should be >= CONFIDENCE_HIGH {CONFIDENCE_HIGH}"
        )

    def test_low_scores_produce_low_confidence(self):
        """relevance=0.1, faithfulness=0.1, completeness=0.1 → score < CONFIDENCE_MEDIUM"""
        expected = (
            0.1 * WEIGHT_RELEVANCE
            + 0.1 * WEIGHT_FAITHFULNESS
            + 0.1 * WEIGHT_COMPLETENESS
        )
        assert expected < CONFIDENCE_MEDIUM, (
            f"Expected score {expected:.3f} should be < CONFIDENCE_MEDIUM {CONFIDENCE_MEDIUM}"
        )

    def test_faithfulness_dominates_relevance(self):
        """Faithfulness weight (0.50) must exceed relevance weight (0.30)."""
        assert WEIGHT_FAITHFULNESS > WEIGHT_RELEVANCE

    def test_completeness_is_smallest_weight(self):
        assert WEIGHT_COMPLETENESS < WEIGHT_RELEVANCE < WEIGHT_FAITHFULNESS

    def test_score_range_clamp(self):
        """Weighted average of values in [0, 1] must stay in [0, 1]."""
        for r, f, c in [(0, 0, 0), (1, 1, 1), (0.5, 0.5, 0.5), (0.3, 0.8, 0.6)]:
            score = r * WEIGHT_RELEVANCE + f * WEIGHT_FAITHFULNESS + c * WEIGHT_COMPLETENESS
            assert 0.0 <= score <= 1.0, f"Score {score} out of [0,1] for r={r}, f={f}, c={c}"


class TestConfidenceScorerIntegration:
    """Integration-style tests that instantiate ConfidenceScorer with a mock LLM."""

    def _run(self, coro):
        import asyncio
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_high_quality_context_yields_high_confidence(self):
        from rapid.agents.confidence_scorer import ConfidenceScorer, ConfidenceResult

        mock_llm = MagicMock()
        # faithfulness: chat_simple returns "9" (out of 10 → 0.9)
        mock_llm.chat_simple = MagicMock(return_value=self._async_return("9"))

        scorer = ConfidenceScorer(llm=mock_llm)
        chunks = [{"text": "Employee leave policy allows 15 days annual paid leave."}]
        summaries = ["Employee leave policy allows 15 days annual paid leave."]
        result = self._run(scorer.score(
            query="What is the employee leave policy?",
            chunks=chunks,
            summaries=summaries,
            answer="Employees get 15 days of annual paid leave per year.",
        ))
        assert isinstance(result, ConfidenceResult)
        assert result.score >= CONFIDENCE_HIGH, (
            f"Score {result.score:.3f} should be >= {CONFIDENCE_HIGH} for high-quality input"
        )

    def test_empty_context_yields_low_confidence(self):
        from rapid.agents.confidence_scorer import ConfidenceScorer, ConfidenceResult

        mock_llm = MagicMock()
        mock_llm.chat_simple = MagicMock(return_value=self._async_return("0"))

        scorer = ConfidenceScorer(llm=mock_llm)
        result = self._run(scorer.score(
            query="What is the leave policy?",
            chunks=[],
            summaries=[],
            answer="I don't know.",
        ))
        assert isinstance(result, ConfidenceResult)
        assert result.score < CONFIDENCE_MEDIUM, (
            f"Score {result.score:.3f} should be < {CONFIDENCE_MEDIUM} for empty context"
        )

    def test_result_has_verdict_field(self):
        from rapid.agents.confidence_scorer import ConfidenceScorer, ConfidenceResult

        mock_llm = MagicMock()
        mock_llm.chat_simple = MagicMock(return_value=self._async_return("7"))

        scorer = ConfidenceScorer(llm=mock_llm)
        result = self._run(scorer.score(
            query="What are the benefits?",
            chunks=[{"text": "Health insurance benefits after 90 days."}],
            summaries=["Health insurance benefits after 90 days."],
            answer="Health insurance starts after 90-day probation.",
        ))
        assert hasattr(result, "verdict"), "ConfidenceResult must have a 'verdict' field"
        assert result.verdict in {"high", "medium", "low"}

    @staticmethod
    def _async_return(value):
        """Wrap a value in a coroutine so MagicMock can simulate async calls."""
        import asyncio

        async def _coro(*args, **kwargs):
            return value

        return _coro()
