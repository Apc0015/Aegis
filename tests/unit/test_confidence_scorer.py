"""
Unit tests for ConfidenceScorer — no live LLM required.
Faithfulness is mocked to return a controlled value.
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from aegis.agents.confidence_scorer import ConfidenceScorer
from aegis.config import CONFIDENCE_HIGH, CONFIDENCE_MEDIUM


def _make_scorer(faithfulness_score: float = 0.9) -> ConfidenceScorer:
    mock_llm = MagicMock()
    # chat_simple returns "9" → faithfulness = 0.9 (for default)
    mock_llm.chat_simple = AsyncMock(return_value=str(round(faithfulness_score * 10)))
    return ConfidenceScorer(llm=mock_llm)


_GOOD_CHUNKS = [
    {"text": "Employees are entitled to 20 days of annual leave per year."},
    {"text": "Leave requests must be approved by the line manager at least two weeks in advance."},
]
_GOOD_SUMMARIES = ["Employees get 20 days annual leave. Manager approval required 2 weeks in advance."]
_GOOD_QUERY = "how many days of leave do employees get?"
_GOOD_ANSWER = "Employees are entitled to 20 days of annual leave per year."


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Score correctness ─────────────────────────────────────────────────────────

def test_high_relevance_faithfulness_completeness_gives_high_score():
    scorer = _make_scorer(faithfulness_score=0.9)
    result = _run(scorer.score(
        query=_GOOD_QUERY,
        chunks=_GOOD_CHUNKS,
        summaries=_GOOD_SUMMARIES,
        answer=_GOOD_ANSWER,
    ))
    assert result.score >= CONFIDENCE_HIGH, f"Expected high score, got {result.score}"
    assert result.verdict == "high"


def test_zero_faithfulness_gives_low_overall():
    scorer = _make_scorer(faithfulness_score=0.0)
    result = _run(scorer.score(
        query=_GOOD_QUERY,
        chunks=_GOOD_CHUNKS,
        summaries=_GOOD_SUMMARIES,
        answer=_GOOD_ANSWER,
    ))
    # faithfulness weight = 0.50 → even perfect relevance + completeness tops at 0.50
    assert result.score < 0.5, f"Zero faithfulness should keep score < 0.5, got {result.score}"


def test_score_is_clamped_between_0_and_1():
    for f in (0.0, 0.5, 1.0):
        scorer = _make_scorer(faithfulness_score=f)
        result = _run(scorer.score(
            query=_GOOD_QUERY,
            chunks=_GOOD_CHUNKS,
            summaries=_GOOD_SUMMARIES,
            answer=_GOOD_ANSWER,
        ))
        assert 0.0 <= result.score <= 1.0


# ── Verdict thresholds ────────────────────────────────────────────────────────

def test_high_confidence_verdict_above_threshold():
    scorer = _make_scorer(faithfulness_score=0.95)
    result = _run(scorer.score(
        query=_GOOD_QUERY,
        chunks=_GOOD_CHUNKS,
        summaries=_GOOD_SUMMARIES,
        answer=_GOOD_ANSWER,
        confidence_high=CONFIDENCE_HIGH,
        confidence_medium=CONFIDENCE_MEDIUM,
    ))
    assert result.verdict == "high"
    assert result.score >= CONFIDENCE_HIGH


def test_medium_confidence_verdict():
    # Low faithfulness → medium-range score
    scorer = _make_scorer(faithfulness_score=0.4)
    result = _run(scorer.score(
        query=_GOOD_QUERY,
        chunks=_GOOD_CHUNKS,
        summaries=_GOOD_SUMMARIES,
        answer=_GOOD_ANSWER,
        confidence_high=CONFIDENCE_HIGH,
        confidence_medium=CONFIDENCE_MEDIUM,
    ))
    assert CONFIDENCE_MEDIUM <= result.score < CONFIDENCE_HIGH or result.verdict in ("medium", "low")


def test_low_confidence_verdict():
    scorer = _make_scorer(faithfulness_score=0.0)
    result = _run(scorer.score(
        query="what is the external market trend for tech salaries?",
        chunks=[],  # no chunks → zero relevance
        summaries=["No relevant data found."],
        answer="I don't know.",
        confidence_high=CONFIDENCE_HIGH,
        confidence_medium=CONFIDENCE_MEDIUM,
    ))
    assert result.score < CONFIDENCE_MEDIUM
    assert result.verdict == "low"
