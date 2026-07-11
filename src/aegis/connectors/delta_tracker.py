"""
Delta tracker — persists which files have already been ingested.
Keyed by "source:file_id" → {version, hash, last_seen} record.
Prevents re-ingesting unchanged files on every sync cycle.

State file schema (v2):
  {
    "source:file_id": {
      "version": "<etag or modifiedTime string>",
      "hash": "<sha256 hex or null>",
      "last_seen": "<ISO-8601 UTC timestamp>"
    },
    ...
  }

Backward-compatible: old flat string values are read as {version: value, hash: null,
last_seen: null} and silently migrated on next write.
"""
import hashlib
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Generator, Optional

STATE_PATH = Path("data/connector_state.json")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DeltaTracker:
    """Thread-safe file-level change tracker backed by a JSON state file."""

    def __init__(self, state_path: Path = STATE_PATH):
        self._path = state_path
        self._lock = threading.Lock()
        self._state: dict = self._load()
        # Batch support: when > 0 we are inside a batch and defer saves
        self._batch_depth: int = 0
        self._batch_dirty: bool = False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load(self) -> dict:
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                return {k: self._normalize(v) for k, v in raw.items()}
            except Exception:
                return {}
        return {}

    @staticmethod
    def _normalize(value) -> dict:
        """Migrate old flat string values to the new record schema."""
        if isinstance(value, str):
            return {"version": value, "hash": None, "last_seen": None}
        if isinstance(value, dict):
            return {
                "version": value.get("version"),
                "hash": value.get("hash"),
                "last_seen": value.get("last_seen"),
            }
        return {"version": None, "hash": None, "last_seen": None}

    def _save(self) -> None:
        """Write state to disk. Caller must hold self._lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._state, indent=2))

    def _save_or_defer(self) -> None:
        """Save immediately unless we are inside a batch."""
        if self._batch_depth > 0:
            self._batch_dirty = True
        else:
            self._save()

    def _key(self, source: str, file_id: str) -> str:
        return f"{source}:{file_id}"

    # ------------------------------------------------------------------
    # Original public API (fully backward-compatible)
    # ------------------------------------------------------------------

    def is_new(self, source: str, file_id: str, version: str) -> bool:
        """Return True if this file/version has NOT been seen before."""
        with self._lock:
            record = self._state.get(self._key(source, file_id))
            if record is None:
                return True
            return record.get("version") != version

    def mark_seen(self, source: str, file_id: str, version: str) -> None:
        """Record that this file/version has been ingested."""
        with self._lock:
            key = self._key(source, file_id)
            existing = self._state.get(key, {})
            self._state[key] = {
                "version": version,
                "hash": existing.get("hash"),
                "last_seen": _now_iso(),
            }
            self._save_or_defer()

    def forget(self, source: str, file_id: str) -> None:
        """Remove a file from tracking (force re-ingest on next sync)."""
        with self._lock:
            self._state.pop(self._key(source, file_id), None)
            self._save_or_defer()

    @staticmethod
    def md5(data: bytes) -> str:
        return hashlib.md5(data).hexdigest()

    # ------------------------------------------------------------------
    # Task A: Content hash tracking
    # ------------------------------------------------------------------

    def is_content_changed(self, source: str, file_id: str, data: bytes) -> bool:
        """
        Return True if the SHA-256 of *data* differs from the stored hash,
        or if no hash has been recorded yet.

        More reliable than etag/modifiedTime for sources that report
        spurious metadata changes without actual content changes.
        """
        new_hash = hashlib.sha256(data).hexdigest()
        with self._lock:
            record = self._state.get(self._key(source, file_id))
            if record is None:
                return True
            return record.get("hash") != new_hash

    def record_content_hash(self, source: str, file_id: str, data: bytes) -> None:
        """
        Persist the SHA-256 of *data* for future is_content_changed() calls.
        Updates last_seen timestamp; preserves existing version string.
        """
        new_hash = hashlib.sha256(data).hexdigest()
        with self._lock:
            key = self._key(source, file_id)
            existing = self._state.get(key, {})
            self._state[key] = {
                "version": existing.get("version"),
                "hash": new_hash,
                "last_seen": _now_iso(),
            }
            self._save_or_defer()

    # ------------------------------------------------------------------
    # Task B: Batch save context manager
    # ------------------------------------------------------------------

    @contextmanager
    def begin_batch(self) -> Generator[None, None, None]:
        """
        Context manager that batches all mark_seen / forget / record_content_hash
        calls and writes to disk only once on exit.

        Batches are re-entrant: nested begin_batch() calls are safe and the
        outer context performs the final flush.

        Usage::

            with tracker.begin_batch():
                for item in many_items:
                    tracker.mark_seen(source, item.id, item.version)
            # single disk write here
        """
        with self._lock:
            self._batch_depth += 1
        try:
            yield
        finally:
            with self._lock:
                self._batch_depth -= 1
                if self._batch_depth == 0 and self._batch_dirty:
                    self._save()
                    self._batch_dirty = False

    # ------------------------------------------------------------------
    # Task C/D: Timestamp tracking + pruning
    # ------------------------------------------------------------------

    def prune_older_than(self, days: int, source: str) -> int:
        """
        Remove entries for *source* that have not been mark_seen'd in more
        than *days* days.  Returns the number of entries removed.

        Entries with a null last_seen timestamp are left untouched (they
        were written by an older version of the tracker and we cannot tell
        their age).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        prefix = f"{source}:"
        removed = 0

        with self._lock:
            stale_keys = []
            for key, record in self._state.items():
                if not key.startswith(prefix):
                    continue
                last_seen_str: Optional[str] = record.get("last_seen")
                if not last_seen_str:
                    continue  # cannot determine age — keep
                try:
                    last_seen = datetime.fromisoformat(last_seen_str)
                    if last_seen < cutoff:
                        stale_keys.append(key)
                except ValueError:
                    continue  # malformed timestamp — keep

            for key in stale_keys:
                del self._state[key]
                removed += 1

            if removed:
                self._save_or_defer()

        return removed
