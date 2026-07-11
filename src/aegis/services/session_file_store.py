"""
Session-scoped FAISS + BM25 indexes for uploaded files.

When a user uploads a file via POST /api/v1/query/with-file, this module
creates a temporary index for that file's chunks under a session project ID.
The index lives for TTL_SECONDS (default 2 hours), then is lazily deleted on
the next upload. Explicit cleanup is also available.

Project ID format: _session_{user_id}_{file_hash[:12]}
"""
import hashlib
import logging
import re
import time
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

TTL_SECONDS = 7200  # 2 hours


class SessionFileStore:
    """
    Lightweight registry that tracks which temp project IDs exist and when
    they were created. Does NOT hold the actual vectors — those live in
    VectorStoreService and BM25Engine under the temp project ID.
    """

    def __init__(self):
        # project_id -> {"created_at": float, "filename": str, "user_id": str}
        self._registry: Dict[str, dict] = {}

    # ------------------------------------------------------------------
    # Project ID helpers
    # ------------------------------------------------------------------

    def make_project_id(self, user_id: str, file_bytes: bytes) -> str:
        """
        Deterministic temp project ID from user + file content.
        Same user uploading the same file within the TTL reuses the same index.

        The user component is reduced to [a-z0-9_] so the resulting id is always
        filesystem-safe (it becomes part of FAISS/BM25 file paths).
        """
        digest = hashlib.sha256(file_bytes).hexdigest()[:12]
        safe_user = re.sub(r"[^a-z0-9_]", "_", user_id.lower())[:20]
        return f"_session_{safe_user}_{digest}"

    # ------------------------------------------------------------------
    # Registry operations
    # ------------------------------------------------------------------

    def register(self, project_id: str, user_id: str, filename: str) -> None:
        """Record that a temp index was created now."""
        self._registry[project_id] = {
            "created_at": time.time(),
            "user_id": user_id,
            "filename": filename,
        }
        logger.info(
            f"SessionFileStore: registered '{project_id}' "
            f"(user={user_id}, file='{filename}')"
        )

    def is_registered(self, project_id: str) -> bool:
        return project_id in self._registry

    def is_fresh(self, project_id: str) -> bool:
        """True if the index exists and has not yet expired."""
        entry = self._registry.get(project_id)
        if not entry:
            return False
        return time.time() - entry["created_at"] < TTL_SECONDS

    def unregister(self, project_id: str) -> None:
        self._registry.pop(project_id, None)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(self, vector_store, bm25) -> int:
        """
        Delete all expired temp indexes from FAISS and BM25.
        Called lazily at the start of each new file upload.
        Returns the number of indexes deleted.
        """
        now = time.time()
        expired = [
            pid for pid, entry in self._registry.items()
            if now - entry["created_at"] >= TTL_SECONDS
        ]
        deleted = 0
        for pid in expired:
            try:
                vector_store.delete_collection(pid)
                bm25.clear(pid)
                self.unregister(pid)
                logger.info(f"SessionFileStore: expired index '{pid}' cleaned up")
                deleted += 1
            except Exception as e:
                logger.warning(f"SessionFileStore: cleanup failed for '{pid}': {e}")
        return deleted

    def delete(self, project_id: str, vector_store, bm25) -> None:
        """Explicitly delete a single temp index (e.g. after query completes)."""
        try:
            vector_store.delete_collection(project_id)
            bm25.clear(project_id)
            self.unregister(project_id)
            logger.info(f"SessionFileStore: deleted index '{project_id}'")
        except Exception as e:
            logger.warning(f"SessionFileStore: delete failed for '{project_id}': {e}")

    def list_active(self) -> List[dict]:
        """Return metadata for all non-expired session indexes."""
        now = time.time()
        return [
            {"project_id": pid, **entry}
            for pid, entry in self._registry.items()
            if now - entry["created_at"] < TTL_SECONDS
        ]
