"""
SharePoint connector — monitors SharePoint document libraries via Microsoft Graph API.

Shares the same OAuth tokens as OneDriveConnector (both use MS Graph).
Requires same AEGIS_MICROSOFT_* env vars as OneDrive.

Config in connectors.yaml per project:
  sharepoint:
    enabled: true
    site_url: "https://company.sharepoint.com/sites/HR"
    library: "Documents"     # document library name (default: "Documents")
    folder: "/Policies"      # optional subfolder filter
"""
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional
from urllib.parse import urlparse

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

# Reuse the OneDrive token — same MS Graph application
TOKEN_PATH = Path("data/connector_tokens/onedrive.json")

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

SUPPORTED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

# Map file extension → MIME type for SUPPORTED_MIME filtering
EXT_MIME_MAP = {
    ".pdf":  "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt":  "text/plain",
    ".md":   "text/markdown",
}


class SharePointConnector(BaseConnector):
    """
    Connector for SharePoint Online — lists and downloads documents from a
    SharePoint site library using the Microsoft Graph delta API.
    """

    SOURCE = "sharepoint"

    def __init__(
        self,
        tracker: DeltaTracker,
        client_id: str,
        tenant_id: str,
        redirect_uri: str,
    ):
        self._tracker = tracker
        self._client_id = client_id
        self._tenant_id = tenant_id
        self._redirect_uri = redirect_uri
        self._token_cache: Optional[dict] = self._load_token()

    # ------------------------------------------------------------------
    # Token management (shared with OneDriveConnector)
    # ------------------------------------------------------------------

    def _load_token(self) -> Optional[dict]:
        if not TOKEN_PATH.exists():
            return None
        try:
            return json.loads(TOKEN_PATH.read_text())
        except Exception as e:
            logger.warning(f"SharePointConnector: could not load token: {e}")
            return None

    def _save_token(self, token_data: dict) -> None:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(json.dumps(token_data, indent=2))
        self._token_cache = token_data

    def _get_access_token(self) -> Optional[str]:
        """Return a valid access token, refreshing via MSAL if needed."""
        try:
            import msal
        except ImportError:
            logger.warning(
                "SharePointConnector: msal not installed — skipping sync. "
                "Install with: pip install msal"
            )
            return None

        if not self._token_cache:
            return None

        app = msal.PublicClientApplication(
            client_id=self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
            token_cache=self._build_msal_cache(),
        )
        accounts = app.get_accounts()
        if not accounts:
            return None

        scopes = ["https://graph.microsoft.com/.default"]
        result = app.acquire_token_silent(scopes, account=accounts[0])
        if result and "access_token" in result:
            # Persist updated cache (may contain refreshed tokens)
            self._save_token(json.loads(app.token_cache.serialize()))
            return result["access_token"]

        return None

    def _build_msal_cache(self):
        """Restore a SerializableTokenCache from the stored JSON blob."""
        try:
            import msal
            cache = msal.SerializableTokenCache()
            cache.deserialize(json.dumps(self._token_cache))
            return cache
        except Exception:
            return None

    # ------------------------------------------------------------------
    # BaseConnector interface
    # ------------------------------------------------------------------

    def is_authenticated(self) -> bool:
        return TOKEN_PATH.exists() and bool(self._token_cache)

    def get_auth_url(self, state: str) -> str:
        """
        SharePoint uses the same OAuth flow as OneDrive.
        Return empty string here; the OneDrive auth URL should be used.
        """
        return ""

    def exchange_code(self, code: str) -> None:
        """SharePoint tokens come from the OneDrive OAuth flow — no-op here."""
        pass

    # ------------------------------------------------------------------
    # Graph API helpers
    # ------------------------------------------------------------------

    def _graph_get(self, token: str, path: str, params: Optional[dict] = None) -> dict:
        """Synchronous Graph GET.  Returns parsed JSON or raises."""
        import urllib.request
        import urllib.parse

        url = path if path.startswith("https://") else f"{GRAPH_BASE}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    def _graph_download(self, token: str, url: str) -> bytes:
        import urllib.request
        req = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {token}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()

    def _resolve_site_id(self, token: str, site_url: str) -> Optional[str]:
        """
        Resolve a SharePoint site URL to a Graph site ID.
        Uses GET /v1.0/sites/{hostname}:{site_path}
        """
        parsed = urlparse(site_url)
        hostname = parsed.netloc
        site_path = parsed.path.rstrip("/")
        if not hostname or not site_path:
            logger.error(
                f"SharePointConnector: invalid site_url '{site_url}' — "
                "expected https://tenant.sharepoint.com/sites/SiteName"
            )
            return None
        try:
            data = self._graph_get(token, f"/sites/{hostname}:{site_path}")
            return data.get("id")
        except Exception as e:
            logger.error(f"SharePointConnector: could not resolve site '{site_url}': {e}")
            return None

    def _resolve_drive_id(
        self, token: str, site_id: str, library_name: str
    ) -> Optional[str]:
        """
        Find the drive ID for a document library by name.
        Falls back to the default drive if the named library is not found.
        """
        try:
            data = self._graph_get(token, f"/sites/{site_id}/drives")
            drives = data.get("value", [])
            for drive in drives:
                if drive.get("name", "").lower() == library_name.lower():
                    return drive["id"]
            # Fallback: default drive
            if drives:
                logger.warning(
                    f"SharePointConnector: library '{library_name}' not found — "
                    f"using default drive"
                )
                default = self._graph_get(token, f"/sites/{site_id}/drive")
                return default.get("id")
        except Exception as e:
            logger.error(
                f"SharePointConnector: could not resolve drive for site "
                f"'{site_id}', library '{library_name}': {e}"
            )
        return None

    # ------------------------------------------------------------------
    # Main sync logic
    # ------------------------------------------------------------------

    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        try:
            import msal  # noqa: F401 — ensure available before heavy work
        except ImportError:
            logger.warning(
                "SharePointConnector: msal not installed — skipping sync. "
                "Install with: pip install msal"
            )
            return

        if not self.is_authenticated():
            logger.warning(
                "SharePointConnector: no OneDrive/MS Graph token found — skipping sync"
            )
            return

        token = self._get_access_token()
        if not token:
            logger.warning(
                "SharePointConnector: could not acquire access token — skipping sync"
            )
            return

        site_url: str = dept_config.get("site_url", "")
        library: str = dept_config.get("library", "Documents")
        folder_filter: Optional[str] = dept_config.get("folder")

        if not site_url:
            logger.warning(
                f"SharePointConnector: no site_url configured for project '{project_id}'"
            )
            return

        site_id = self._resolve_site_id(token, site_url)
        if not site_id:
            return

        drive_id = self._resolve_drive_id(token, site_id, library)
        if not drive_id:
            return

        logger.debug(
            f"SharePointConnector: syncing site='{site_url}' library='{library}' "
            f"drive='{drive_id}' (project={project_id})"
        )

        # Use Graph delta to efficiently find changed items
        delta_link_key = f"{site_id}:{drive_id}:delta_link"
        delta_url = self._get_delta_url(site_id, drive_id, delta_link_key)

        new_delta_link: Optional[str] = None

        with self._tracker.begin_batch():
            while delta_url:
                try:
                    data = self._graph_get(token, delta_url)
                except Exception as e:
                    logger.error(
                        f"SharePointConnector: delta query failed for drive "
                        f"'{drive_id}': {e}"
                    )
                    break

                items = data.get("value", [])
                for item in items:
                    # Skip folders
                    if "folder" not in item and "file" not in item:
                        continue
                    if "folder" in item:
                        continue

                    item_id = item.get("id", "")
                    name: str = item.get("name", "")
                    etag: str = item.get("eTag", item.get("lastModifiedDateTime", ""))
                    parent_path: str = (
                        item.get("parentReference", {}).get("path", "") or ""
                    )

                    # Apply optional folder filter
                    if folder_filter and folder_filter not in parent_path:
                        continue

                    # Check extension support
                    suffix = Path(name).suffix.lower()
                    if suffix not in EXT_MIME_MAP:
                        continue

                    # Delta tracking by etag
                    if not self._tracker.is_new(self.SOURCE, f"{site_id}:{item_id}", etag):
                        continue

                    # Download content
                    download_url = item.get(
                        "@microsoft.graph.downloadUrl"
                    ) or f"{GRAPH_BASE}/drives/{drive_id}/items/{item_id}/content"

                    try:
                        file_bytes = self._graph_download(token, download_url)
                    except Exception as e:
                        logger.warning(
                            f"SharePointConnector: could not download '{name}' "
                            f"({item_id}): {e}"
                        )
                        continue

                    self._tracker.mark_seen(
                        self.SOURCE, f"{site_id}:{item_id}", etag
                    )
                    logger.debug(
                        f"SharePointConnector: new file '{name}' (project={project_id})"
                    )
                    yield ConnectorFile(file_bytes, name, item_id, project_id)

                # Follow @odata.nextLink or capture @odata.deltaLink
                next_link = data.get("@odata.nextLink")
                delta_link = data.get("@odata.deltaLink")

                if next_link:
                    delta_url = next_link
                else:
                    # Save delta link for next sync
                    new_delta_link = delta_link
                    delta_url = None

        # Persist new delta link so next sync only sees changes
        if new_delta_link:
            self._tracker.mark_seen(
                self.SOURCE, delta_link_key, new_delta_link
            )

    # ------------------------------------------------------------------
    # Delta link helpers
    # ------------------------------------------------------------------

    def _get_delta_url(
        self, site_id: str, drive_id: str, delta_link_key: str
    ) -> str:
        """
        Return the URL to start a delta query from.
        Uses a stored deltaLink from the last sync if available,
        otherwise starts from the beginning (full enumeration).
        """
        key = f"{self.SOURCE}:{delta_link_key}"
        with self._tracker._lock:
            record = self._tracker._state.get(key)
            if record:
                stored = record.get("version")
                if stored and stored.startswith("https://"):
                    return stored

        # No stored delta link — full initial enumeration
        return f"{GRAPH_BASE}/drives/{drive_id}/root/delta"
