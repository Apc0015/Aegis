import os
import re
import uuid
import logging
import threading
from typing import List, Dict, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

logger = logging.getLogger(__name__)

# Defense-in-depth: routers sanitize project_id, but the service must also refuse
# anything unsafe before it becomes a Qdrant collection name.
_SAFE_ID_RE = re.compile(r"^_?[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")

# Collection prefix keeps Aegis's collections namespaced within a shared Qdrant.
_PREFIX = "aegis_"

# Deterministic point-id namespace so re-ingesting the same chunk UPDATES the
# point in place instead of creating a duplicate (FAISS appended duplicates).
_ID_NAMESPACE = uuid.UUID("a3f1c2d4-5e6f-4a7b-8c9d-0e1f2a3b4c5d")


class VectorStoreService:
    """
    Qdrant-backed vector store with per-project collection isolation.

    Each project (department, document workspace, or ephemeral chat session) maps
    to a Qdrant collection named ``aegis_<project_id>``. The public interface is
    unchanged from the previous FAISS implementation, so nothing downstream had to
    change — this is a storage swap, not an API change.

    Deployment modes (chosen by ``AEGIS_QDRANT_URL`` / the ``url`` arg):
      * **Embedded** (default) — a local, file-backed Qdrant at ``persist_dir``.
        Zero infrastructure; ideal for laptops, the demo, and single-process runs.
        NOTE: embedded Qdrant locks its storage to ONE process. Run the API and
        the ingest worker against a Qdrant *server* if you need both at once.
      * **Server** — set ``AEGIS_QDRANT_URL`` (e.g. ``http://qdrant:6333``). The
        client is safe for concurrent processes; this is the production setup and
        what docker-compose wires up.

    Distance metric is Euclidean (``Distance.EUCLID``) to match the prior
    ``IndexFlatL2`` behaviour; scores are converted to a ``1/(1+distance)``
    similarity so downstream fusion/scoring see the same shape. (Cosine is a
    reasonable future tuning knob — a one-line change here.)

    Thread-safety: a re-entrant lock serialises collection creation and the
    per-project write buffer. Qdrant itself handles concurrent reads/writes.
    """

    def __init__(
        self,
        persist_dir: str = "data/qdrant",
        dimension: int = 1536,
        url: Optional[str] = None,
    ):
        self.dimension = dimension
        self._url = (url or os.getenv("AEGIS_QDRANT_URL", "")).strip() or None
        self._lock = threading.RLock()
        self._ensured: set = set()          # collections verified/created this process
        self._buffers: Dict[str, List[PointStruct]] = {}  # project_id -> pending points

        if self._url:
            api_key = os.getenv("AEGIS_QDRANT_API_KEY") or None
            self._client = QdrantClient(url=self._url, api_key=api_key, prefer_grpc=False)
            logger.info(f"VectorStoreService: connected to Qdrant server at {self._url}")
        else:
            from pathlib import Path
            Path(persist_dir).mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=persist_dir)
            logger.info(f"VectorStoreService: embedded Qdrant at {persist_dir}")

    # ── naming / collection lifecycle ─────────────────────────────────────────

    def _collection(self, project_id: str) -> str:
        if not _SAFE_ID_RE.match(project_id or ""):
            raise ValueError(f"Unsafe project_id for vector store: {project_id!r}")
        safe_id = project_id.replace("-", "_")[:63]
        return f"{_PREFIX}{safe_id}"

    def _ensure_collection(self, project_id: str) -> str:
        col = self._collection(project_id)
        with self._lock:
            if col in self._ensured:
                return col
            if not self._client.collection_exists(col):
                self._client.create_collection(
                    collection_name=col,
                    vectors_config=VectorParams(size=self.dimension, distance=Distance.EUCLID),
                )
                logger.info(f"Created Qdrant collection '{col}' (dim={self.dimension})")
            self._ensured.add(col)
            return col

    def ensure_index(self, project_id: str) -> None:
        """Create an empty collection for a project so it's visible immediately."""
        self._ensure_collection(project_id)

    # ── writes ────────────────────────────────────────────────────────────────

    def upsert(
        self,
        project_id: str,
        doc_id: str,
        chunk_index: int,
        text: str,
        embedding: List[float],
        metadata: Dict,
        persist: bool = True,
    ):
        """
        Add or update a chunk's vector.

        persist=False buffers the point in memory; call flush(project_id) once at
        the end of an ingestion loop to send them as a single batch (cheaper than
        one network round-trip per chunk). persist=True sends immediately,
        including anything already buffered for the project.

        The point id is derived deterministically from (doc_id, chunk_index), so
        re-ingesting the same chunk overwrites it rather than duplicating.
        """
        if len(embedding) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch for project '{project_id}': "
                f"collection expects {self.dimension}, got {len(embedding)}"
            )

        col = self._ensure_collection(project_id)
        uid = f"{doc_id}_chunk_{chunk_index}"
        point = PointStruct(
            id=str(uuid.uuid5(_ID_NAMESPACE, f"{col}:{uid}")),
            vector=list(embedding),
            payload={
                "uid": uid,
                "text": text,
                "metadata": metadata,
                # Top-level keys enable server-side filtered deletes (see delete_by_source).
                "doc_id": doc_id,
                "source": (metadata or {}).get("source") or doc_id,
            },
        )
        with self._lock:
            self._buffers.setdefault(project_id, []).append(point)
            if persist:
                self._flush_locked(project_id)

    def flush(self, project_id: str):
        """Send any buffered points for a project (pairs with upsert(persist=False))."""
        with self._lock:
            self._flush_locked(project_id)

    def _flush_locked(self, project_id: str):
        buf = self._buffers.get(project_id)
        if not buf:
            return
        col = self._ensure_collection(project_id)
        self._client.upsert(collection_name=col, points=buf, wait=True)
        self._buffers[project_id] = []

    # ── reads ─────────────────────────────────────────────────────────────────

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Search for similar chunks. Returns [{text, metadata, score}], best-first.

        ``where`` is accepted for interface compatibility but not yet applied
        (the prior FAISS store ignored it too). Payload-filter pushdown is a
        natural follow-up that maps directly onto Qdrant's Filter.
        """
        if len(query_embedding) != self.dimension:
            raise ValueError(
                f"Embedding dimension mismatch for project '{project_id}': "
                f"collection expects {self.dimension}, got {len(query_embedding)}"
            )
        col = self._collection(project_id)
        if not self._client.collection_exists(col):
            return []

        resp = self._client.query_points(
            collection_name=col,
            query=list(query_embedding),
            limit=top_k,
            with_payload=True,
        )

        out = []
        for p in resp.points:
            payload = p.payload or {}
            # EUCLID score is a distance (smaller = closer). Convert to the same
            # 1/(1+d) similarity the FAISS store emitted. Qdrant already returns
            # points best-first, so relative ranking is preserved regardless.
            distance = p.score if p.score is not None else 0.0
            score = 1.0 / (1.0 + max(distance, 0.0))
            out.append({
                "text": payload.get("text", ""),
                "metadata": payload.get("metadata", {}),
                "score": float(score),
            })
        return out

    def count(self, project_id: str) -> int:
        """Vector count for a project (0 if the collection doesn't exist yet)."""
        try:
            col = self._collection(project_id)
            if not self._client.collection_exists(col):
                return 0
            return self._client.count(collection_name=col, exact=True).count
        except Exception as e:
            logger.warning(f"Could not count vectors for project '{project_id}': {e}")
            raise RuntimeError(f"Vector store count failed for project '{project_id}'") from e

    def list_projects(self) -> List[str]:
        """List all Aegis projects (collections prefixed with 'aegis_')."""
        cols = self._client.get_collections().collections
        return [c.name[len(_PREFIX):] for c in cols if c.name.startswith(_PREFIX)]

    # ── deletes ───────────────────────────────────────────────────────────────

    def delete_by_source(self, project_id: str, source: str):
        """
        Remove all chunks belonging to a source/document.

        Matches either the top-level ``doc_id`` or ``source`` payload — server-side
        in Qdrant, so there's no read-modify-rewrite of the whole index (a big
        simplification over the FAISS rebuild path).
        """
        col = self._collection(project_id)
        if not self._client.collection_exists(col):
            return
        self._client.delete(
            collection_name=col,
            points_selector=Filter(
                should=[
                    FieldCondition(key="doc_id", match=MatchValue(value=source)),
                    FieldCondition(key="source", match=MatchValue(value=source)),
                ]
            ),
            wait=True,
        )
        logger.info(f"Deleted vectors for source/doc '{source}' in project '{project_id}'")

    def delete_collection(self, project_id: str):
        """Delete a project's entire collection."""
        with self._lock:
            col = self._collection(project_id)
            try:
                if self._client.collection_exists(col):
                    self._client.delete_collection(collection_name=col)
                self._ensured.discard(col)
                self._buffers.pop(project_id, None)
                logger.info(f"Deleted collection for project '{project_id}'")
            except Exception as e:
                logger.warning(f"Could not delete collection for project '{project_id}': {e}")

    def close(self):
        """Release the underlying client (embedded mode holds a storage lock)."""
        try:
            self._client.close()
        except Exception:
            pass
