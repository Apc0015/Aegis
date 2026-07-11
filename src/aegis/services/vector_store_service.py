import logging
import json
import re
import threading
import numpy as np
import faiss
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Defense-in-depth: routers sanitize project_id, but the service must also refuse
# anything that could escape persist_dir (path separators, "..", etc.).
_SAFE_ID_RE = re.compile(r"^_?[a-zA-Z0-9][a-zA-Z0-9_\-]{0,62}$")


class VectorStoreService:
    """
    FAISS-based vector store with per-project index isolation.
    Each project gets a separate FAISS index stored on disk.

    Thread-safety: a re-entrant lock serializes all index mutation and search.
    FAISS indexes and the parallel metadata list are NOT safe for concurrent
    mutate+search — an interleaved upsert during a query can misalign FAISS row
    ids with metadata positions and silently return the wrong chunks.

    Cross-process freshness: the on-disk index mtime is checked on each access,
    so indexes written by another process (e.g. the ARQ ingest worker) are
    reloaded instead of served stale from the in-memory cache.
    """

    def __init__(self, persist_dir: str = "data/faiss", dimension: int = 1536):
        self.persist_dir = Path(persist_dir)
        self.dimension = dimension
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._indexes = {}  # in-memory cache: project_id -> (index, metadata_list)
        self._mtimes: Dict[str, float] = {}  # project_id -> index file mtime at load
        self._lock = threading.RLock()

    def _get_index_path(self, project_id: str) -> tuple:
        """Returns (index_path, metadata_path) for a project."""
        if not _SAFE_ID_RE.match(project_id or ""):
            raise ValueError(f"Unsafe project_id for vector store: {project_id!r}")
        safe_id = project_id.replace("-", "_")[:63]
        return (
            self.persist_dir / f"rapid_{safe_id}.index",
            self.persist_dir / f"rapid_{safe_id}_meta.json",
        )

    def _load_or_create_index(self, project_id: str):
        """
        Load FAISS index from disk, or create new one if it doesn't exist.
        Reloads from disk if the file changed since we cached it (another
        process — e.g. the ingest worker — may have written it).
        """
        index_path, meta_path = self._get_index_path(project_id)

        with self._lock:
            if project_id in self._indexes:
                disk_mtime = index_path.stat().st_mtime if index_path.exists() else None
                if disk_mtime is None or disk_mtime == self._mtimes.get(project_id):
                    return self._indexes[project_id]
                logger.info(
                    f"Vector index for '{project_id}' changed on disk — reloading"
                )

            if index_path.exists() and meta_path.exists():
                # Load existing index
                index = faiss.read_index(str(index_path))
                with open(meta_path, 'r') as f:
                    metadata = json.load(f)
                self._mtimes[project_id] = index_path.stat().st_mtime
            else:
                index = faiss.IndexFlatL2(self.dimension)
                metadata = []
                self._mtimes.pop(project_id, None)

            self._indexes[project_id] = (index, metadata)
            return self._indexes[project_id]

    def _save_index(self, project_id: str):
        """Persist FAISS index and metadata to disk."""
        with self._lock:
            if project_id not in self._indexes:
                return

            index_path, meta_path = self._get_index_path(project_id)
            index, metadata = self._indexes[project_id]

            faiss.write_index(index, str(index_path))
            with open(meta_path, 'w') as f:
                json.dump(metadata, f)
            self._mtimes[project_id] = index_path.stat().st_mtime

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
        Add or update a vector in the index.

        persist: when False, the change is kept in memory but NOT written to disk.
        Use persist=False in a per-chunk ingestion loop and call flush(project_id)
        once at the end — writing the whole index + metadata on every chunk is
        quadratic I/O for large documents.

        Note: embeddings live ONLY inside FAISS (reconstructable via
        index.reconstruct); duplicating them as JSON floats in metadata roughly
        tripled the metadata file size (~30KB/chunk) for no benefit.
        """
        with self._lock:
            index, meta_list = self._load_or_create_index(project_id)
            uid = f"{doc_id}_chunk_{chunk_index}"

            embedding_array = np.array([embedding], dtype=np.float32)
            if embedding_array.shape[1] != index.d:
                raise ValueError(
                    f"Embedding dimension mismatch for project '{project_id}': "
                    f"index expects {index.d}, got {embedding_array.shape[1]}"
                )

            # Add to index
            index.add(embedding_array)

            # Track metadata (embedding intentionally NOT duplicated here)
            meta_list.append({
                "uid": uid,
                "text": text,
                "metadata": metadata,
            })

            if persist:
                self._save_index(project_id)

    def flush(self, project_id: str):
        """Persist any in-memory changes for a project (pairs with upsert(persist=False))."""
        self._save_index(project_id)

    def ensure_index(self, project_id: str) -> None:
        """
        Create an (empty) index for a project and persist it to disk.

        _load_or_create_index only builds the index in memory; without a disk
        write, list_projects() — which enumerates by globbing *.index files —
        cannot see a freshly created empty project until a document is added.
        This makes an empty project visible immediately after creation.
        """
        with self._lock:
            self._load_or_create_index(project_id)
            self._save_index(project_id)

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """Search for similar vectors."""
        with self._lock:
            index, meta_list = self._load_or_create_index(project_id)

            if len(meta_list) == 0:
                return []

            # Convert query embedding to numpy array
            query_array = np.array([query_embedding], dtype=np.float32)
            if query_array.shape[1] != index.d:
                raise ValueError(
                    f"Embedding dimension mismatch for project '{project_id}': "
                    f"index expects {index.d}, got {query_array.shape[1]}"
                )

            # Search FAISS index
            k = min(top_k, len(meta_list))
            distances, indices = index.search(query_array, k)

        # Convert L2 distances to similarity scores
        out = []
        for i, idx in enumerate(indices[0]):
            if idx == -1:  # Invalid index
                continue
            score = 1.0 / (1.0 + distances[0][i])  # Convert L2 to similarity
            if idx < len(meta_list):
                meta = meta_list[idx]
                out.append({
                    "text": meta["text"],
                    "metadata": meta["metadata"],
                    "score": float(score),
                })

        return out

    def delete_by_source(self, project_id: str, source: str):
        """Remove all vectors from a specific source."""
        with self._lock:
            index, meta_list = self._load_or_create_index(project_id)

            kept = []
            kept_embeddings = []
            deleted = 0

            for row_idx, meta in enumerate(meta_list):
                metadata = meta.get("metadata", {})
                matches = (
                    metadata.get("source") == source
                    or metadata.get("doc_id") == source
                    or meta.get("uid", "").startswith(f"{source}_chunk_")
                )
                if matches:
                    deleted += 1
                    continue

                kept.append(meta)
                # Embeddings are recovered from FAISS (legacy metadata may still
                # carry an "embedding" key from older index files — used if present).
                embedding = meta.pop("embedding", None) or metadata.get("embedding")
                if embedding is None and row_idx < index.ntotal:
                    try:
                        embedding = index.reconstruct(row_idx).tolist()
                    except Exception as e:
                        logger.warning(
                            f"Could not reconstruct vector {row_idx} while deleting "
                            f"'{source}' from project '{project_id}': {e}"
                        )
                if embedding is not None:
                    kept_embeddings.append(embedding)

            if deleted:
                logger.info(
                    f"Deleted {deleted} vectors for source/doc '{source}' in project '{project_id}'"
                )
                self._rebuild_index(project_id, kept, kept_embeddings, index.d)
                self._save_index(project_id)

    def _rebuild_index(
        self,
        project_id: str,
        meta_list: Optional[List[Dict]] = None,
        embeddings: Optional[List[List[float]]] = None,
        dimension: Optional[int] = None,
    ):
        """Rebuild FAISS index from metadata (after deletions)."""
        if meta_list is None:
            current_index, meta_list = self._indexes[project_id]
            dimension = dimension or current_index.d
            embeddings = [
                m.get("embedding") or m.get("metadata", {}).get("embedding")
                for m in meta_list
                if m.get("embedding") or m.get("metadata", {}).get("embedding")
            ]
        else:
            dimension = dimension or self.dimension

        new_index = faiss.IndexFlatL2(dimension)
        if embeddings:
            embeddings_array = np.array(embeddings, dtype=np.float32)
            if embeddings_array.shape[1] != dimension:
                raise ValueError(
                    f"Cannot rebuild project '{project_id}': expected dimension "
                    f"{dimension}, got {embeddings_array.shape[1]}"
                )
            new_index.add(embeddings_array)

        if len(meta_list) != new_index.ntotal:
            logger.warning(
                f"Project '{project_id}' metadata/vector count mismatch after rebuild: "
                f"metadata={len(meta_list)}, vectors={new_index.ntotal}"
            )

        self._indexes[project_id] = (new_index, meta_list)

    def delete_collection(self, project_id: str):
        """Delete a project's index."""
        with self._lock:
            index_path, meta_path = self._get_index_path(project_id)
            try:
                if index_path.exists():
                    index_path.unlink()
                if meta_path.exists():
                    meta_path.unlink()
                self._indexes.pop(project_id, None)
                self._mtimes.pop(project_id, None)
                logger.info(f"Deleted index for project '{project_id}'")
            except Exception as e:
                logger.warning(f"Could not delete index for project '{project_id}': {e}")

    def count(self, project_id: str) -> int:
        """Get vector count for a project."""
        try:
            with self._lock:
                index, meta_list = self._load_or_create_index(project_id)
                return len(meta_list)
        except Exception as e:
            logger.warning(f"Could not count vectors for project '{project_id}': {e}")
            raise RuntimeError(f"Vector store count failed for project '{project_id}'") from e

    def list_projects(self) -> List[str]:
        """List all projects (indices) in the store."""
        projects = []
        for path in self.persist_dir.glob("rapid_*.index"):
            name = path.stem  # e.g., "rapid_project_name"
            project_id = name[len("rapid_"):]
            projects.append(project_id)
        return projects
