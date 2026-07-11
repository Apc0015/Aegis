"""
Unit tests for query API schema and response structure.
No live LLM required — MasterAgent is fully mocked.
"""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import List

import pytest
from fastapi.testclient import TestClient
import jwt  # PyJWT

# ── Env setup before any app import ──────────────────────────────────────────
os.environ.setdefault("AEGIS_USERNAME", "testadmin")
os.environ.setdefault("AEGIS_PASSWORD", "testpass")
os.environ.setdefault("AEGIS_DEFAULT_ROLE", "admin")
os.environ.setdefault("AEGIS_JWT_SECRET", "test-secret-key-32-bytes-xxxxxxxx")
os.environ.setdefault("AEGIS_LLM_PROVIDER", "openai")
os.environ.setdefault("AEGIS_MAIN_MODEL", "gpt-4o-mini")


# ── Minimal QueryResult stub ──────────────────────────────────────────────────
@dataclass
class _FakeAccessDecision:
    permitted: bool = True
    user_role: str = "admin"
    user_id: str = "testadmin"
    query: str = ""
    permitted_departments: list = field(default_factory=list)
    denial_reason: str = None


@dataclass
class _FakeQueryResult:
    answer: str = "Test answer."
    confidence: float = 0.85
    verdict: str = "high"
    should_refuse: bool = False
    is_external: bool = False
    sources: list = field(default_factory=list)
    chunks_used: int = 2
    routing_path: str = "direct"
    model_used: str = "openai/gpt-4o-mini"
    latency_ms: int = 500
    web_used: bool = False
    cross_model_eval: bool = False
    reranker_used: bool = False
    db_triggered: bool = False
    columns_blocked: list = field(default_factory=list)
    columns_anonymized: list = field(default_factory=list)
    access_decision: _FakeAccessDecision = field(default_factory=_FakeAccessDecision)
    cached: bool = False


def _make_mock_agent():
    agent = MagicMock()
    agent.query = AsyncMock(return_value=_FakeQueryResult())
    agent.maybe_compress_history = AsyncMock()
    # _ingest_file calls agent.r3.embeddings.embed_batch (async), upsert, add_documents
    agent.r3.embeddings.embed_batch = AsyncMock(return_value=[[0.1] * 384])
    agent.r3.vector.upsert = MagicMock()
    agent.r3.bm25.add_documents = MagicMock()
    # Document endpoints authorize department access via the RBAC module —
    # return (allowed, denied) so the tuple unpack works with the mock.
    agent.rbac.authorize_departments = MagicMock(return_value=(["hr"], []))
    agent.rbac.can_delete_docs = MagicMock(return_value=True)
    return agent


def _make_mock_conv_store():
    store = MagicMock()
    store.get_history = MagicMock(return_value=[])
    store.append = MagicMock()
    return store


def _get_token(role: str = "admin") -> str:
    from api.auth import SECRET_KEY, ALGORITHM
    return jwt.encode(
        {"sub": "testadmin", "role": role},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


@pytest.fixture(scope="module")
def client():
    from api.main import app
    from api.dependencies import get_agent, get_conversation_store

    mock_agent = _make_mock_agent()
    mock_store = _make_mock_conv_store()

    # Use FastAPI dependency_overrides so the mock is used regardless of what
    # lifespan sets via set_agent().
    app.dependency_overrides[get_agent] = lambda: mock_agent
    app.dependency_overrides[get_conversation_store] = lambda: mock_store

    try:
        with TestClient(app, raise_server_exceptions=False) as c:
            yield c, mock_agent
    finally:
        app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_query_requires_user_query_field(client):
    c, _ = client
    token = _get_token()
    # Wrong field name → 422
    resp = c.post(
        "/api/v1/query",
        json={"query": "what is our leave policy?", "project_id": "hr"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422

    # Correct field name → proceeds (mocked agent returns 200)
    resp = c.post(
        "/api/v1/query",
        json={"user_query": "what is our leave policy?", "project_id": "hr"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_query_requires_auth(client):
    c, _ = client
    resp = c.post(
        "/api/v1/query",
        json={"user_query": "what is our leave policy?", "project_id": "hr"},
    )
    assert resp.status_code == 401


def test_query_accepts_optional_conversation_id(client):
    import uuid
    c, _ = client
    token = _get_token()
    resp = c.post(
        "/api/v1/query",
        json={
            "user_query": "what is our leave policy?",
            "project_id": "hr",
            "conversation_id": str(uuid.uuid4()),
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200


def test_cached_field_present_in_response(client):
    c, _ = client
    token = _get_token()
    resp = c.post(
        "/api/v1/query",
        json={"user_query": "what is our vacation policy?", "project_id": "hr"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "cached" in body
    assert isinstance(body["cached"], bool)


def test_upload_returns_upload_result(client, tmp_path):
    c, _ = client
    token = _get_token()

    txt = tmp_path / "policy.txt"
    txt.write_text("This is an HR policy document.\n\nSection 1: Leave Policy.\n\nEmployees get 20 days.")

    with open(txt, "rb") as f:
        resp = c.post(
            "/api/v1/documents/upload",
            data={"project_id": "hr", "rag_mode": "hr"},
            files={"files": ("policy.txt", f, "text/plain")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    first = body[0]
    assert "doc_id" in first
    assert "chunks_created" in first
    assert "status" in first


def test_upload_wrong_file_type(client, tmp_path):
    c, _ = client
    token = _get_token()

    exe = tmp_path / "virus.exe"
    exe.write_bytes(b"\x4d\x5a\x90\x00")

    with open(exe, "rb") as f:
        resp = c.post(
            "/api/v1/documents/upload",
            data={"project_id": "hr", "rag_mode": "hr"},
            files={"files": ("virus.exe", f, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 422
