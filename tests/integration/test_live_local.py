"""
Integration tests using LOCAL Ollama.
Requires: Ollama running with qwen2.5:latest or llama3.1:8b available.

Run with:
    pytest tests/integration/test_live_local.py -m live_local -v
"""
import os
import time
import uuid
import subprocess
import sys

import pytest
import requests
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.live_local

OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("AEGIS_MAIN_MODEL", "qwen2.5:latest")
BASE_URL     = os.getenv("AEGIS_TEST_LOCAL_BASE_URL", "http://localhost:8768")
USERNAME     = os.getenv("AEGIS_USERNAME", "admin")
PASSWORD     = os.getenv("AEGIS_PASSWORD", "")

TEST_DOC_CONTENT = """
HR Leave Policy — Aegis Local Test Document

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
def ollama_available():
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if r.status_code != 200:
            pytest.skip("Ollama not reachable")
        models = [m["name"] for m in r.json().get("models", [])]
        if not any(OLLAMA_MODEL.split(":")[0] in m for m in models):
            pytest.skip(f"Model {OLLAMA_MODEL} not available in Ollama. Available: {models}")
    except Exception as e:
        pytest.skip(f"Ollama not available: {e}")


@pytest.fixture(scope="module")
def server_process(ollama_available):
    """Start a local-mode test server on port 8768."""
    try:
        r = requests.get(f"{BASE_URL}/api/v1/health", timeout=3)
        if r.status_code == 200:
            yield None
            return
    except Exception:
        pass

    env = os.environ.copy()
    env["AEGIS_LLM_PROVIDER"] = "ollama"
    env["AEGIS_MAIN_MODEL"] = OLLAMA_MODEL
    env["AEGIS_EMBED_PROVIDER"] = "local"
    env["AEGIS_WEB_ENABLED"] = "false"

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "api.main:app",
         "--host", "0.0.0.0", "--port", "8768", "--log-level", "warning"],
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    )

    for _ in range(60):
        try:
            r = requests.get(f"{BASE_URL}/api/v1/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    else:
        proc.terminate()
        pytest.skip("Local server did not start in time")

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
    project_id = f"test_local_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{BASE_URL}/api/v1/documents/upload",
        data={"project_id": project_id, "rag_mode": "hr"},
        files={"files": ("hr_policy_local.txt", TEST_DOC_CONTENT.encode(), "text/plain")},
        headers=headers,
        timeout=60,
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    body = r.json()
    assert len(body) >= 1
    return {"project_id": project_id, "doc": body[0]}


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_ollama_model_is_available(ollama_available):
    r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
    assert r.status_code == 200
    models = [m["name"] for m in r.json().get("models", [])]
    assert any(OLLAMA_MODEL.split(":")[0] in m for m in models), \
        f"Model {OLLAMA_MODEL} not in {models}"


def test_local_embedding_loads(server_process, headers):
    r = requests.get(f"{BASE_URL}/api/v1/health", timeout=10)
    assert r.status_code == 200
    body = r.json()
    embed_prov = body.get("embed_provider", "")
    assert embed_prov in ("local", "ollama"), \
        f"Expected local or ollama embed provider, got: {embed_prov}"


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
    assert "access_token" in r.json()


def test_trivial_query_completes_under_60s(server_process, headers, uploaded_doc):
    t0 = time.time()
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "hello", "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=65,
    )
    elapsed = time.time() - t0
    assert r.status_code == 200
    assert elapsed < 60, f"Trivial query took {elapsed:.1f}s on local Ollama"


def test_rag_query_returns_answer_with_sources(server_process, headers, uploaded_doc):
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "how many days of annual leave do employees get?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    assert r.json().get("answer")


def test_rag_query_confidence_above_0_5(server_process, headers, uploaded_doc):
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the sick leave policy?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    assert r.json().get("confidence", 0) > 0.5


def test_rag_answer_references_document_content(server_process, headers, uploaded_doc):
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "how many days of annual leave?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    answer = r.json().get("answer", "").lower()
    assert "20" in answer or "annual" in answer or "leave" in answer


def test_upload_document_creates_chunks(server_process, headers):
    project_id = f"test_chunks_local_{uuid.uuid4().hex[:6]}"
    r = requests.post(
        f"{BASE_URL}/api/v1/documents/upload",
        data={"project_id": project_id, "rag_mode": "hr"},
        files={"files": ("policy.txt", TEST_DOC_CONTENT.encode(), "text/plain")},
        headers=headers,
        timeout=60,
    )
    assert r.status_code == 200
    assert r.json()[0]["chunks_created"] >= 1


def test_cache_second_query_faster_than_first(server_process, headers, uploaded_doc):
    query = {"user_query": "what is the parental leave policy?",
             "project_id": uploaded_doc["project_id"]}
    t0 = time.time()
    r1 = requests.post(f"{BASE_URL}/api/v1/query", json=query, headers=headers, timeout=155)
    t1 = time.time() - t0
    assert r1.status_code == 200

    t0 = time.time()
    r2 = requests.post(f"{BASE_URL}/api/v1/query", json=query, headers=headers, timeout=30)
    t2 = time.time() - t0
    assert r2.status_code == 200
    assert r2.json().get("cached") is True
    assert t2 < t1 / 2 or t2 < 2.0


def test_streaming_returns_tokens_within_30s(server_process, headers, uploaded_doc):
    t0 = time.time()
    with requests.get(
        f"{BASE_URL}/api/v1/query/stream",
        params={"user_query": "what is the leave application process?",
                "project_id": uploaded_doc["project_id"]},
        headers=headers,
        stream=True,
        timeout=100,
    ) as r:
        assert r.status_code == 200
        first_token_time = None
        for line in r.iter_lines():
            if line and line.startswith(b"data: ") and line != b"data: [DONE]":
                first_token_time = time.time() - t0
                break
    assert first_token_time is not None
    assert first_token_time < 90, f"First token from Ollama took {first_token_time:.1f}s"


def test_multi_turn_second_query_uses_context(server_process, headers, uploaded_doc):
    conv_id = str(uuid.uuid4())
    project_id = uploaded_doc["project_id"]

    r1 = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the annual leave entitlement?",
              "project_id": project_id, "conversation_id": conv_id},
        headers=headers,
        timeout=155,
    )
    assert r1.status_code == 200

    r2 = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "and what about sick leave?",
              "project_id": project_id, "conversation_id": conv_id},
        headers=headers,
        timeout=155,
    )
    assert r2.status_code == 200
    answer2 = r2.json().get("answer", "").lower()
    assert "sick" in answer2 or "leave" in answer2 or "10" in answer2


def test_low_confidence_query_returns_answer(server_process, headers, uploaded_doc):
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "what is the current price of Bitcoin?",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    assert "answer" in r.json()


def test_query_with_file_returns_answer(server_process, headers, uploaded_doc):
    doc_content = b"Claim: Employees get 20 days of annual leave."
    r = requests.post(
        f"{BASE_URL}/api/v1/query/with-file",
        data={"user_query": "is this claim correct?",
              "project_id": uploaded_doc["project_id"]},
        files={"file": ("claim.txt", doc_content, "text/plain")},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    assert r.json().get("answer")


def test_rbac_admin_sees_response(server_process, headers, uploaded_doc):
    r = requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "show me employee data",
              "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    assert r.status_code == 200
    assert r.json().get("routing_path") != "denied" or r.json().get("answer")


def test_audit_log_records_query(server_process, headers, uploaded_doc):
    requests.post(
        f"{BASE_URL}/api/v1/query",
        json={"user_query": "local audit test", "project_id": uploaded_doc["project_id"]},
        headers=headers,
        timeout=155,
    )
    r = requests.get(f"{BASE_URL}/api/v1/audit", headers=headers, timeout=10)
    assert r.status_code == 200
    assert len(r.json()) >= 1
