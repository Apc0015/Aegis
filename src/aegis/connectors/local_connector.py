"""
Local disk connector — monitors a folder path for new/changed documents.

Two modes:
  - Live watch: watchdog Observer fires on every file create/modify event
  - Scheduled scan: list_new_files() called every 15 min by ConnectorManager
"""
import asyncio
import logging
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class LocalConnector(BaseConnector):
    SOURCE = "local"

    def __init__(self, tracker: DeltaTracker, ingest_callback: Callable):
        """
        ingest_callback: async callable(bytes, filename, project_id) → None
        Called immediately when watchdog detects a new/changed file.
        """
        self._tracker = tracker
        self._ingest_callback = ingest_callback
        self._observers: dict[str, object] = {}  # project_id → Observer


    def is_authenticated(self) -> bool:
        return True

    def get_auth_url(self, state: str) -> str:
        return ""

    def exchange_code(self, code: str) -> None:
        pass


    def start_watcher(self, project_id: str, watch_path: str) -> None:
        """Start a watchdog Observer for the given path. Idempotent."""
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning("LocalConnector: 'watchdog' not installed — live watch disabled")
            return

        path = Path(watch_path)
        if not path.exists():
            logger.warning(f"LocalConnector: watch path does not exist: {path}")
            return

        if project_id in self._observers:
            return

        tracker = self._tracker
        callback = self._ingest_callback
        source = self.SOURCE

        class _Handler(FileSystemEventHandler):
            def _handle(self, file_path: Path) -> None:
                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    return
                try:
                    data = file_path.read_bytes()
                except OSError:
                    return
                version = DeltaTracker.md5(data)
                file_id = str(file_path)
                if tracker.is_new(source, file_id, version):
                    tracker.mark_seen(source, file_id, version)
                    asyncio.run(callback(data, file_path.name, project_id))

            def on_created(self, event):
                if not event.is_directory:
                    self._handle(Path(event.src_path))

            def on_modified(self, event):
                if not event.is_directory:
                    self._handle(Path(event.src_path))

        observer = Observer()
        observer.schedule(_Handler(), str(path), recursive=True)
        observer.start()
        self._observers[project_id] = observer
        logger.info(f"LocalConnector: watching '{path}' for project '{project_id}'")

    def stop_all(self) -> None:
        for obs in self._observers.values():
            try:
                obs.stop()  # type: ignore[attr-defined]
                obs.join()  # type: ignore[attr-defined]
            except Exception:
                pass
        self._observers.clear()


    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        path = Path(dept_config.get("path", ""))
        if not path.exists():
            logger.warning(f"LocalConnector: path not found for project '{project_id}': {path}")
            return

        for file_path in sorted(path.rglob("*")):
            if not file_path.is_file():
                continue
            if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            try:
                data = file_path.read_bytes()
            except OSError as e:
                logger.warning(f"LocalConnector: could not read {file_path}: {e}")
                continue

            version = DeltaTracker.md5(data)
            file_id = str(file_path)

            if self._tracker.is_new(self.SOURCE, file_id, version):
                self._tracker.mark_seen(self.SOURCE, file_id, version)
                yield ConnectorFile(data, file_path.name, file_id, project_id)
