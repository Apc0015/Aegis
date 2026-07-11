import json
import logging
import pickle
import re
import threading
from pathlib import Path
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi

logger = logging.getLogger(__name__)

# Defense-in-depth: routers sanitize project_id, but the engine must also refuse
# anything that could escape storage_dir ("../x" previously wrote/read files —
# formerly *pickle* files, i.e. arbitrary code on load — anywhere on disk).
_SAFE_ID_RE = re.compile(r"^_?[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")


class BM25Engine:
    """
    Per-project BM25 index.

    Persistence is JSON (corpus + metadata); the BM25 structure is rebuilt from
    the corpus on load. Legacy ``.pkl`` files from earlier versions are still
    read once and migrated to JSON on the next save — but pickle is never
    written anymore (unpickling data files is an arbitrary-code-execution risk).

    Thread-safety: a re-entrant lock serializes mutation and query. Cross-process
    freshness: file mtime is checked on access so another process's writes (e.g.
    the ARQ ingest worker) are picked up instead of served stale.
    """

    def __init__(self, storage_dir: str = "data/bm25"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._indexes: Dict[str, dict] = {}
        self._mtimes: Dict[str, float] = {}
        self._lock = threading.RLock()

    def _path(self, project_id: str) -> Path:
        if not _SAFE_ID_RE.match(project_id or ""):
            raise ValueError(f"Unsafe project_id for BM25 engine: {project_id!r}")
        return self.storage_dir / f"{project_id}.json"

    def _legacy_pickle_path(self, project_id: str) -> Path:
        if not _SAFE_ID_RE.match(project_id or ""):
            raise ValueError(f"Unsafe project_id for BM25 engine: {project_id!r}")
        return self.storage_dir / f"{project_id}.pkl"

    @staticmethod
    def _build_bm25(corpus: List[str]) -> Optional[BM25Okapi]:
        tokenized = [t.lower().split() for t in corpus]
        return BM25Okapi(tokenized) if tokenized else None

    def _load(self, project_id: str) -> dict:
        with self._lock:
            p = self._path(project_id)
            disk_mtime = p.stat().st_mtime if p.exists() else None

            if project_id in self._indexes:
                if disk_mtime is None or disk_mtime == self._mtimes.get(project_id):
                    return self._indexes[project_id]
                logger.info(f"BM25 index for '{project_id}' changed on disk — reloading")

            if p.exists():
                with open(p, "r", encoding="utf-8") as f:
                    data = json.load(f)
                idx = {
                    "corpus": data.get("corpus", []),
                    "metadata": data.get("metadata", []),
                    "bm25": None,
                }
                idx["bm25"] = self._build_bm25(idx["corpus"])
                self._mtimes[project_id] = disk_mtime
            else:
                legacy = self._legacy_pickle_path(project_id)
                if legacy.exists():
                    # One-time migration of pre-existing pickle indexes created by
                    # this app. New writes are always JSON.
                    try:
                        with open(legacy, "rb") as f:
                            old = pickle.load(f)
                        idx = {
                            "corpus": old.get("corpus", []),
                            "metadata": old.get("metadata", []),
                            "bm25": None,
                        }
                        idx["bm25"] = self._build_bm25(idx["corpus"])
                        logger.info(
                            f"BM25: migrated legacy pickle index for '{project_id}' "
                            f"({len(idx['corpus'])} chunks) — will persist as JSON"
                        )
                        self._indexes[project_id] = idx
                        self._save(project_id)
                        legacy.unlink(missing_ok=True)
                        return self._indexes[project_id]
                    except Exception as e:
                        logger.warning(
                            f"BM25: legacy pickle migration failed for '{project_id}': {e}"
                        )
                idx = {"corpus": [], "metadata": [], "bm25": None}
                self._mtimes.pop(project_id, None)

            self._indexes[project_id] = idx
            return self._indexes[project_id]

    def _save(self, project_id: str):
        with self._lock:
            idx = self._indexes[project_id]
            p = self._path(project_id)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"corpus": idx["corpus"], "metadata": idx["metadata"]}, f)
            self._mtimes[project_id] = p.stat().st_mtime

    def add_documents(self, project_id: str, texts: List[str], metadatas: List[Dict]):
        with self._lock:
            idx = self._load(project_id)
            for text, meta in zip(texts, metadatas):
                idx["corpus"].append(text)
                idx["metadata"].append(meta)
            idx["bm25"] = self._build_bm25(idx["corpus"])
            self._save(project_id)

    def query(self, project_id: str, query: str, top_k: int = 5) -> List[Dict]:
        with self._lock:
            idx = self._load(project_id)
            if not idx["bm25"] or not idx["corpus"]:
                return []
            tokens = query.lower().split()
            scores = idx["bm25"].get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
            return [
                {
                    "text": idx["corpus"][i],
                    "metadata": idx["metadata"][i],
                    "score": float(s),
                    "rank": r,
                }
                for r, (i, s) in enumerate(ranked)
            ]

    def remove_by_source(self, project_id: str, source: str):
        with self._lock:
            idx = self._load(project_id)
            keep = [(t, m) for t, m in zip(idx["corpus"], idx["metadata"])
                    if m.get("source") != source and m.get("doc_id") != source]
            idx["corpus"] = [x[0] for x in keep]
            idx["metadata"] = [x[1] for x in keep]
            idx["bm25"] = self._build_bm25(idx["corpus"])
            self._save(project_id)

    def list_documents(self, project_id: str) -> List[Dict]:
        """Return one summary row per indexed document for a project."""
        with self._lock:
            idx = self._load(project_id)
            docs: Dict[str, Dict] = {}
            for meta in idx["metadata"]:
                doc_id = meta.get("doc_id") or meta.get("source") or "unknown"
                source = meta.get("source", doc_id)
                if doc_id not in docs:
                    docs[doc_id] = {
                        "doc_id": doc_id,
                        "filename": source,
                        "chunks_count": 0,
                    }
                docs[doc_id]["chunks_count"] += 1
            return list(docs.values())

    def clear(self, project_id: str):
        with self._lock:
            self._indexes.pop(project_id, None)
            self._mtimes.pop(project_id, None)
            for p in (self._path(project_id), self._legacy_pickle_path(project_id)):
                if p.exists():
                    p.unlink()
