"""
Unit tests for the Qdrant-backed VectorStoreService (embedded mode).

Runs entirely in-process against a temporary embedded Qdrant — no server, no
network — so it's a valid CI gate. Covers the contract every caller depends on:
create/list, buffered-then-flushed upsert, similarity query, in-place update via
deterministic ids, filtered delete, and collection delete.
"""
import pytest

from aegis.services.vector_store_service import VectorStoreService

DIM = 8


def _vec(seed: int):
    """Deterministic distinct unit-ish vectors from a small int."""
    return [float((seed >> b) & 1) for b in range(DIM)]


@pytest.fixture
def store(tmp_path):
    vs = VectorStoreService(persist_dir=str(tmp_path / "qdrant"), dimension=DIM)
    try:
        yield vs
    finally:
        vs.close()


def test_ensure_index_makes_empty_project_visible(store):
    assert store.list_projects() == []
    store.ensure_index("hr")
    assert store.list_projects() == ["hr"]
    assert store.count("hr") == 0


def test_buffered_upsert_then_flush(store):
    for i in range(5):
        store.upsert("hr", doc_id="policy", chunk_index=i, text=f"chunk {i}",
                     embedding=_vec(i), metadata={"source": "policy.md"}, persist=False)
    assert store.count("hr") == 0          # buffered, not yet sent
    store.flush("hr")
    assert store.count("hr") == 5


def test_query_returns_nearest_with_metadata(store):
    for i in range(5):
        store.upsert("hr", doc_id="d", chunk_index=i, text=f"chunk {i}",
                     embedding=_vec(i), metadata={"source": "d.md", "n": i})
    res = store.query("hr", _vec(3), top_k=3)
    assert len(res) == 3
    assert res[0]["text"] == "chunk 3"                 # exact match ranks first
    assert res[0]["metadata"]["n"] == 3
    scores = [r["score"] for r in res]
    assert scores == sorted(scores, reverse=True)      # best-first


def test_query_missing_collection_returns_empty(store):
    assert store.query("nope", _vec(1), top_k=3) == []


def test_deterministic_id_updates_in_place(store):
    store.upsert("hr", doc_id="d", chunk_index=0, text="v1", embedding=_vec(1), metadata={})
    store.upsert("hr", doc_id="d", chunk_index=0, text="v2", embedding=_vec(1), metadata={})
    assert store.count("hr") == 1                        # not duplicated
    assert store.query("hr", _vec(1), top_k=1)[0]["text"] == "v2"


def test_delete_by_source(store):
    store.upsert("hr", doc_id="a", chunk_index=0, text="a0", embedding=_vec(1),
                 metadata={"source": "a.md"})
    store.upsert("hr", doc_id="b", chunk_index=0, text="b0", embedding=_vec(2),
                 metadata={"source": "b.md"})
    store.delete_by_source("hr", "a.md")                 # match on source payload
    assert store.count("hr") == 1
    store.delete_by_source("hr", "b")                    # match on doc_id payload
    assert store.count("hr") == 0


def test_delete_collection(store):
    store.ensure_index("hr")
    store.ensure_index("it")
    assert set(store.list_projects()) == {"hr", "it"}
    store.delete_collection("hr")
    assert store.list_projects() == ["it"]


def test_dimension_mismatch_raises(store):
    with pytest.raises(ValueError):
        store.upsert("hr", doc_id="d", chunk_index=0, text="x",
                     embedding=[0.0] * (DIM + 1), metadata={})


def test_unsafe_project_id_rejected(store):
    for bad in ("../evil", "a/b", "a b", "a;b"):
        with pytest.raises(ValueError):
            store.ensure_index(bad)
