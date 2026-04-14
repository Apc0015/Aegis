import pickle
import os
from pathlib import Path
from typing import List, Dict, Optional
from rank_bm25 import BM25Okapi

class BM25Engine:
    """
    Per-project BM25 index with pickle persistence.
    """

    def __init__(self, storage_dir: str = "data/bm25"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._indexes: Dict[str, dict] = {}

    def _path(self, project_id: str) -> Path:
        return self.storage_dir / f"{project_id}.pkl"

    def _load(self, project_id: str) -> dict:
        if project_id not in self._indexes:
            p = self._path(project_id)
            if p.exists():
                with open(p, "rb") as f:
                    self._indexes[project_id] = pickle.load(f)
            else:
                self._indexes[project_id] = {"corpus": [], "metadata": [], "bm25": None}
        return self._indexes[project_id]

    def _save(self, project_id: str):
        with open(self._path(project_id), "wb") as f:
            pickle.dump(self._indexes[project_id], f)

    def add_documents(self, project_id: str, texts: List[str], metadatas: List[Dict]):
        idx = self._load(project_id)
        for text, meta in zip(texts, metadatas):
            idx["corpus"].append(text)
            idx["metadata"].append(meta)
        tokenized = [t.lower().split() for t in idx["corpus"]]
        idx["bm25"] = BM25Okapi(tokenized) if tokenized else None
        self._save(project_id)

    def query(self, project_id: str, query: str, top_k: int = 5) -> List[Dict]:
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
        idx = self._load(project_id)
        keep = [(t, m) for t, m in zip(idx["corpus"], idx["metadata"])
                if m.get("source") != source]
        idx["corpus"] = [x[0] for x in keep]
        idx["metadata"] = [x[1] for x in keep]
        tokenized = [t.lower().split() for t in idx["corpus"]]
        idx["bm25"] = BM25Okapi(tokenized) if tokenized else None
        self._save(project_id)

    def clear(self, project_id: str):
        self._indexes.pop(project_id, None)
        p = self._path(project_id)
        if p.exists():
            p.unlink()
