"""
Base classes for external data source connectors.
All connectors yield ConnectorFile objects which feed directly into
the same _ingest_file pipeline used by the upload API.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ConnectorFile:
    """A file fetched from an external source, ready for ingestion."""
    bytes_: bytes
    filename: str
    source_id: str    # unique stable ID for delta tracking (path, msg_id, file_id, etc.)
    project_id: str   # target Aegis department index


class BaseConnector(ABC):
    """Abstract connector — one subclass per source type."""

    @abstractmethod
    def is_authenticated(self) -> bool:
        """Return True if valid credentials are stored."""

    @abstractmethod
    def get_auth_url(self, state: str) -> str:
        """Return OAuth redirect URL. Empty string for sources with no OAuth."""

    @abstractmethod
    def exchange_code(self, code: str) -> None:
        """Exchange OAuth authorization code for tokens and persist them."""

    @abstractmethod
    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        """
        Yield ConnectorFile for each new/changed file since last sync.
        Must be idempotent — already-seen files must not be yielded again.
        """
        yield  # type: ignore[misc]
