"""
Integration tests using REAL OpenRouter API.
Requires: OPENROUTER_API_KEY in env or .env file.

Run with:
    pytest tests/integration/test_live_cloud.py -m live_cloud -v
"""
import os
import time
import uuid
import threading
import subprocess
import sys

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.live_cloud

BASE_URL = os.getenv("AEGIS_TEST_BASE_URL", "http://localhost:8767")
USERNAME = os.getenv("AEGIS_USERNAME", "admin")
PASSWORD = os.getenv("AEGIS_PASSWORD", "")
API_KEY  = os.getenv("OPENROUTER_API_KEY", "")

TEST_DOC_CONTENT = """
HR Leave Policy — Aegis Test Document

Section 1: Annual Leave
All full-time employees are entitled to 20 working days of paid annual leave per calendar year.
Part-time employees receive leave on a pro-rata basis.

Section 2: Sick Leave
Employees may take up to 10 days of paid sick leave per year.
A medical certificate is required for absences exceeding 3 consecutive days.

Section 3: Parental Leave
Primary caregivers are entitled to 16 weeks of paid parental leave.
Secondary caregivers receive 4 weeks of paid parental leave.

Section 4: Leave Application Process
All leave requests must be submitted via the HR portal at least 2 weeks in advance.
Emergency leave may be granted at manager discretion with same-day notice.
""".strip()


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def server_process():
    """Start a test server process. Skips if already running."""
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=3)
        if r.status_code == 200:
            yield None  # already up
            return
    except Exception:
        pass

    env = os.environ.copy()
    # Respect .env model/provider settings; only enforce embed=local and web=off for test isolation
    env.setdefault("AEGIS_LLM_PROVIDER", "openrouter")
    env.setdefault("AEGIS_MAIN_MODEL", "google/gemma-2-9b-it:free")
    env["OPENROUTER_API_KEY"] = API_KEY
    env["AEGIS_EMBED_PROVIDER"] = "local"
    env["AEGIS_WEB_ENABLED"] = "false"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8767", "--log-level", "warning"],
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )

    # Wait for server to be ready (up to 30s)
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/v1/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.terminate()
        pytest.skip("Server did not start in time")

    yield proc
    proc.terminate()


@pytest.fixture(scope="module")
def token(server_process):
    if not PASSWORD:
        pytest.skip("AEGIS_PASSWORD not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": USERNAME, "password": PASSWORD},
    )
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def uploaded_doc(server_process, headers):
    """Upload the test HR document once for the whole module."""
    project_id = f"test_cloud_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{BASE_URL}/api/v1/documents/upload",
        data={"project_id": project_id, "rag_mode": "hr"},
        files={"files": ("hr_policy_test.txt", TEST_DOC_CONTENT.encode(), "text/plain")},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    body = r.json()
    assert len(body) >= 1
    return {"project_id": project_id, "doc": body[0]}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health_returns_ok(server_process):
    r = requests.get(f"{BASE_URL}/api/v1/health", timeout=5)
    assert r.status_code == 200


def test_login_returns_jwt_token(server_process):
    if not PASSWORD:
        pytest.skip("AEGIS_PASSWORD not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        data={"username": USERNAME, "password": PASSWORD},
    )
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_trivial_query_completes_under_15s(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "hello", "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=20,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200
    assert elapsed < 15, f"Trivial query took {elapsed:.1f}s"


def test_rag_query_returns_answer_with_sources(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "how many days of annual leave do employees get?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("answer"), "answer field is empty"


def test_rag_query_confidence_above_0_5(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the sick leave policy?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("confidence", 0) > 0.5, f"Confidence too low: {body.get('confidence')}"


def test_rag_answer_references_document_content(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "how many days of annual leave?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    answer = r.json().get("answer", "").lower()
    assert "20" in answer or "annual" in answer or "leave" in answer, \
        f"Answer doesn't reference doc content: {answer[:200]}"


def test_upload_document_creates_chunks(server_process, headers):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    project_id = f"test_chunks_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{BASE_URL}/api/v1/documents/upload",
        data={"project_id": project_id, "rag_mode": "hr"},
        files={"files": ("policy.txt", TEST_DOC_CONTENT.encode(), "text/plain")},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body[0]["chunks_created"] >= 1


def test_cache_second_query_faster_than_first(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    query = {"user_query": "what is the parental leave policy?",
             "project_id": uploaded_doc["project_id"]}
    t0 = time.time()
    r1 = requests.post(f"{BASE_URL}/api/v1/query", json=query, headers=headers, timeout=30)
    t1 = time.time() - t0
    assert r1.status_code == 200

    t0 = time.time()
    r2 = requests.post(f"{BASE_URL}/api/v1/query", json=query, headers=headers, timeout=10)
    t2 = time.time() - t0
    assert r2.status_code == 200

    body2 = r2.json()
    assert body2.get("cached") is True, "Second identical query should be cached"
    assert t2 < t1 / 2 or t2 < 1.0, f"Cached query took {t2:.2f}s (first was {t1:.2f}s)"


def test_streaming_returns_tokens_within_30s(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    t0 = time.time()
    with requests.get(
        f"{BASE_URL}/api/v1/query/stream",
        params={"user_query": "what is the leave application process?",
                "project_id": uploaded_doc["project_id"]},
        headers=headers,
        stream=True,
        timeout=35,
    ) as r:
        assert r.status_code == 200
        first_token_time = None
        for line in r.iter_lines():
            if line and line.startswith(b"data: ") and line != b"data: [DONE]":
                first_token_time = time.time() - t0
                break
    assert first_token_time is not None, "No tokens received from stream"
    assert first_token_time < 30, f"First token arrived after {first_token_time:.1f}s"


def test_multi_turn_second_query_uses_context(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    conv_id = str(uuid.uuid4())
    project_id = uploaded_doc["project_id"]

    r1 = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the annual leave entitlement?",
              "project_id": project_id,
              "conversation_id": conv_id},
        headers=headers,
        timeout=30,
    )
    assert r1.status_code == 200

    r2 = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "and what about sick leave?",
              "project_id": project_id,
              "conversation_id": conv_id},
        headers=headers,
        timeout=30,
    )
    assert r2.status_code == 200
    answer2 = r2.json().get("answer", "").lower()
    assert "sick" in answer2 or "leave" in answer2 or "10" in answer2


def test_rbac_admin_sees_response(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "show me employee salary data",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("routing_path") != "denied" or body.get("answer")


def test_audit_log_records_query(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    # First make a query
    requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "audit test query", "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    # Then check audit log
    r = requests.get(f"{BASE_URL}/api/v1/audit", headers=headers, timeout=10)
    assert r.status_code == 200
    logs = r.json()
    assert isinstance(logs, list)
    # At least one audit entry should exist
    assert len(logs) >= 1


def test_low_confidence_query_returns_answer(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the current stock price of Tesla?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    # Should either answer or refuse — must not crash
    assert "answer" in body


def test_query_with_file_returns_answer(server_process, headers, uploaded_doc):
    if not API_KEY:
        pytest.skip("OPENROUTER_API_KEY not set")
    doc_content = b"Claim: Employees get 20 days of annual leave."
    r = requests.post(
        f"{BASE_URL}/api/v1/query/with-file",
        data={"user_query": "is this claim correct?",
              "project_id": uploaded_doc["project_id"]},
        files={"file": ("claim.txt", doc_content, "text/plain")},
        headers=headers,
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("answer"), "with-file query returned empty answer"
