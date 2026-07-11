"""
OneDrive connector — uses Microsoft Graph API with MSAL user OAuth2.

Uses /me/drive/items/{folder_id}/delta for efficient incremental sync.
Delta link persisted per folder so only changes since last sync are fetched.

OAuth2 user flow:
  1. GET /api/v1/connectors/onedrive/auth-url  → redirect to Microsoft consent
  2. Microsoft redirects to /api/v1/connectors/onedrive/callback?code=...
  3. exchange_code() stores tokens in data/connector_tokens/onedrive.json
"""
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

import requests

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

TOKEN_PATH = Path("data/connector_tokens/onedrive.json")
DELTA_LINK_PATH = Path("data/connector_tokens/onedrive_delta.json")
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
SCOPES = ["Files.Read", "offline_access"]
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}


class OneDriveConnector(BaseConnector):
    SOURCE = "onedrive"

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
        self._token_data: Optional[dict] = self._load_token()


    def _load_token(self) -> Optional[dict]:
        if not TOKEN_PATH.exists():
            return None
        try:
            return json.loads(TOKEN_PATH.read_text())
        except Exception:
            return None

    def _save_token(self, data: dict) -> None:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(json.dumps(data, indent=2))
        self._token_data = data

    def _get_msal_app(self):
        import msal
        return msal.PublicClientApplication(
            client_id=self._client_id,
            authority=f"https://login.microsoftonline.com/{self._tenant_id}",
        )

    def _get_access_token(self) -> str:
        """Return a valid access token, refreshing silently if needed."""
        app = self._get_msal_app()
        accounts = app.get_accounts()
        if accounts:
            result = app.acquire_token_silent(SCOPES, account=accounts[0])
            if result and "access_token" in result:
                self._save_token(result)
                return result["access_token"]
        return (self._token_data or {}).get("access_token", "")

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._get_access_token()}"}


    def is_authenticated(self) -> bool:
        return bool(self._token_data and self._token_data.get("access_token"))

    def get_auth_url(self, state: str) -> str:
        from urllib.parse import quote
        scope_str = "%20".join(SCOPES)
        return (
            f"https://login.microsoftonline.com/{self._tenant_id}/oauth2/v2.0/authorize"
            f"?client_id={self._client_id}"
            f"&response_type=code"
            f"&redirect_uri={quote(self._redirect_uri, safe='')}"
            f"&scope={scope_str}"
            f"&state={state}"
            f"&response_mode=query"
        )

    def exchange_code(self, code: str) -> None:
        app = self._get_msal_app()
        result = app.acquire_token_by_authorization_code(
            code=code,
            scopes=SCOPES,
            redirect_uri=self._redirect_uri,
        )
        if "access_token" not in result:
            raise ValueError(
                f"OneDrive auth failed: {result.get('error_description', result.get('error', 'unknown'))}"
            )
        self._save_token(result)
        logger.info("OneDriveConnector: OAuth exchange complete, token saved")

    def disconnect(self) -> None:
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
        self._token_data = None


    def _load_delta_link(self, folder_id: str) -> Optional[str]:
        if not DELTA_LINK_PATH.exists():
            return None
        try:
            return json.loads(DELTA_LINK_PATH.read_text()).get(folder_id)
        except Exception:
            return None

    def _save_delta_link(self, folder_id: str, link: str) -> None:
        DELTA_LINK_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if DELTA_LINK_PATH.exists():
            try:
                data = json.loads(DELTA_LINK_PATH.read_text())
            except Exception:
                pass
        data[folder_id] = link
        DELTA_LINK_PATH.write_text(json.dumps(data, indent=2))


    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        if not self.is_authenticated():
            logger.warning("OneDriveConnector: not authenticated — skipping sync")
            return

        folder_id = dept_config.get("folder_id")
        if not folder_id:
            logger.warning(f"OneDriveConnector: no folder_id for project '{project_id}'")
            return

        headers = self._headers()
        delta_link = self._load_delta_link(folder_id)
        url = delta_link or f"{GRAPH_BASE}/me/drive/items/{folder_id}/delta"

        while url:
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
            except requests.HTTPError as e:
                if resp.status_code == 410:
                    # Delta token expired — full resync
                    logger.warning("OneDriveConnector: delta token expired, doing full resync")
                    url = f"{GRAPH_BASE}/me/drive/items/{folder_id}/delta"
                    self._save_delta_link(folder_id, "")
                    continue
                logger.error(f"OneDriveConnector: API error: {e}")
                return

            data = resp.json()

            for item in data.get("value", []):
                if item.get("deleted"):
                    continue

                name = item.get("name", "")
                ext = Path(name).suffix.lower()
                if ext not in SUPPORTED_EXTENSIONS:
                    continue

                item_id = item["id"]
                etag = item.get("eTag") or item.get("lastModifiedDateTime", "")

                if not self._tracker.is_new(self.SOURCE, item_id, etag):
                    continue

                # Prefer pre-signed download URL from delta response
                dl_url = item.get("@microsoft.graph.downloadUrl")
                try:
                    if dl_url:
                        dl_resp = requests.get(dl_url, timeout=60)
                    else:
                        dl_resp = requests.get(
                            f"{GRAPH_BASE}/me/drive/items/{item_id}/content",
                            headers=headers,
                            timeout=60,
                            allow_redirects=True,
                        )
                    dl_resp.raise_for_status()
                    file_data = dl_resp.content
                except Exception as e:
                    logger.warning(f"OneDriveConnector: could not download '{name}': {e}")
                    continue

                self._tracker.mark_seen(self.SOURCE, item_id, etag)
                logger.debug(f"OneDriveConnector: new file '{name}' (project={project_id})")
                yield ConnectorFile(file_data, name, item_id, project_id)

            # Persist delta link for next sync
            next_delta = data.get("@odata.deltaLink")
            if next_delta:
                self._save_delta_link(folder_id, next_delta)

            url = data.get("@odata.nextLink")  # pagination
