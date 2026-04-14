"""Shared fixtures for RAPID test suite."""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def sample_chunks():
    """Five representative document chunks for retrieval tests."""
    return [
        {"id": "c1", "text": "Employee leave policy allows 15 days annual paid leave.", "score": 0.91},
        {"id": "c2", "text": "Remote work requires manager approval and VPN access.", "score": 0.85},
        {"id": "c3", "text": "Performance reviews are conducted bi-annually in June and December.", "score": 0.78},
        {"id": "c4", "text": "Health insurance benefits begin after 90-day probation period.", "score": 0.72},
        {"id": "c5", "text": "Expense reimbursement must be submitted within 30 days of incurrence.", "score": 0.65},
    ]


@pytest.fixture
def mock_llm_service():
    """LLMService stub that returns deterministic completions."""
    svc = MagicMock()
    svc.complete.return_value = (
        "Based on the provided context, the answer is clearly supported by the documents."
    )
    svc.provider = "openai"
    svc.model = "gpt-4o-mini"
    return svc


@pytest.fixture
def mock_embedder():
    """Embedder stub returning a fixed 4-dim vector."""
    import numpy as np

    embedder = MagicMock()
    embedder.embed.return_value = np.array([0.1, 0.2, 0.3, 0.4])
    embedder.embed_batch.side_effect = lambda texts: [
        np.array([0.1 * (i + 1), 0.2, 0.3, 0.4]) for i, _ in enumerate(texts)
    ]
    return embedder
