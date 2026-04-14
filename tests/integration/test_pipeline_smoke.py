"""
Integration smoke test for the full R1→R2→R3→R4 pipeline.

Marked with `live` — skipped by default (pytest.ini: addopts = -m "not live").
Run explicitly with:  pytest -m live tests/integration/test_pipeline_smoke.py

Requires:
  - .env with a valid OPENAI_API_KEY (or ANTHROPIC_API_KEY)
  - At least one document indexed in the ChromaDB store
"""
import pytest


pytestmark = pytest.mark.live


@pytest.fixture(scope="module")
def agent():
    """Build a real MasterAgent from the factory (uses live credentials)."""
    from rapid.factory import build_agent
    return build_agent()


def test_pipeline_returns_non_empty_answer(agent):
    """A simple factual query must return a non-empty answer string."""
    result = agent.run(
        query="What is the employee leave policy?",
        role="employee",
    )
    assert isinstance(result, dict), "run() must return a dict"
    answer = result.get("answer", "")
    assert len(answer.strip()) > 0, "Answer must not be empty"


def test_pipeline_returns_confidence_score(agent):
    """Response must include a numeric confidence score in [0, 1]."""
    result = agent.run(
        query="Summarise the health insurance benefits.",
        role="employee",
    )
    score = result.get("confidence", {}).get("score")
    assert score is not None, "Response must include 'confidence.score'"
    assert 0.0 <= score <= 1.0, f"Confidence score {score} out of range"


def test_pipeline_returns_sources(agent):
    """Response must include at least one source chunk."""
    result = agent.run(
        query="What are the remote work requirements?",
        role="employee",
    )
    sources = result.get("sources", [])
    assert len(sources) > 0, "Response must include at least one source"


def test_pipeline_low_confidence_triggers_web_fallback(agent):
    """
    A query with no matching internal docs should trigger the web-fallback
    flag when web_fallback is enabled for the active RAG mode.
    """
    result = agent.run(
        query="What is the current federal minimum wage in the United States?",
        role="employee",
    )
    # This query has no internal docs — web_fallback should fire or confidence must be low.
    score = result.get("confidence", {}).get("score", 1.0)
    web_used = result.get("web_fallback_used", False)
    assert score < 0.65 or web_used, (
        "Query with no internal match should have low confidence or trigger web fallback"
    )


def test_all_rag_modes_build_without_error():
    """Instantiate the agent for every RAG mode — none should raise."""
    from rapid.config import RAG_MODES
    from rapid.factory import build_agent

    for mode_key in RAG_MODES:
        try:
            _agent = build_agent(rag_mode=mode_key)
        except Exception as exc:
            pytest.fail(f"build_agent(rag_mode='{mode_key}') raised: {exc}")
