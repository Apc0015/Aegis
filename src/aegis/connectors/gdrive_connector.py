"""
Google Drive connector — monitors specific folders for new/changed documents.

Uses Drive API files.list() per folder with version/modifiedTime tracking.
Google Docs are exported as DOCX; native files (PDF, DOCX, TXT) downloaded directly.

OAuth2 user flow: same callback URL pattern as GmailConnector
  (GET /api/v1/connectors/google/callback handles both gmail + gdrive if scopes combined)
"""
import json
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

TOKEN_PATH = Path("data/connector_tokens/gdrive.json")
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SUPPORTED_NATIVE_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}

# Google Workspace types → export as (mime, extension)
EXPORT_MAP = {
    "application/vnd.google-apps.document": (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".docx",
    ),
}


class GDriveConnector(BaseConnector):
    SOURCE = "gdrive"

    def __init__(
        self,
        tracker: DeltaTracker,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ):
        self._tracker = tracker
        self._client_id = client_id
        self._client_secret = client_secret
        self._redirect_uri = redirect_uri
        self._creds = self._load_creds()


    def _load_creds(self) -> Optional[object]:
        if not TOKEN_PATH.exists():
            return None
        try:
            from google.oauth2.credentials import Credentials
            return Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception as e:
            logger.warning(f"GDriveConnector: could not load token: {e}")
            return None

    def _save_creds(self, creds) -> None:
        TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_PATH.write_text(creds.to_json())
        self._creds = creds

    def _refresh_if_expired(self) -> None:
        if not self._creds:
            return
        if self._creds.expired and self._creds.refresh_token:
            from google.auth.transport.requests import Request
            self._creds.refresh(Request())
            self._save_creds(self._creds)

    def _make_flow(self):
        from google_auth_oauthlib.flow import Flow
        return Flow.from_client_config(
            {
                "web": {
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self._redirect_uri],
                }
            },
            scopes=SCOPES,
            redirect_uri=self._redirect_uri,
        )


    def is_authenticated(self) -> bool:
        if not self._creds:
            return False
        return self._creds.valid or (
            self._creds.expired and bool(self._creds.refresh_token)
        )

    def get_auth_url(self, state: str) -> str:
        flow = self._make_flow()
        auth_url, _ = flow.authorization_url(
            state=state, access_type="offline", prompt="consent"
        )
        return auth_url

    def exchange_code(self, code: str) -> None:
        flow = self._make_flow()
        flow.fetch_token(code=code)
        self._save_creds(flow.credentials)
        logger.info("GDriveConnector: OAuth exchange complete, token saved")

    def disconnect(self) -> None:
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
        self._creds = None


    def _build_service(self):
        self._refresh_if_expired()
        from googleapiclient.discovery import build
        return build("drive", "v3", credentials=self._creds)

    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        if not self.is_authenticated():
            logger.warning("GDriveConnector: not authenticated — skipping sync")
            return

        folder_id = dept_config.get("folder_id")
        if not folder_id:
            logger.warning(f"GDriveConnector: no folder_id configured for project '{project_id}'")
            return

        svc = self._build_service()
        query = f"'{folder_id}' in parents and trashed=false"
        page_token = None

        while True:
            resp = (
                svc.files()
                .list(
                    q=query,
                    fields="nextPageToken,files(id,name,mimeType,version,modifiedTime)",
                    pageSize=100,
                    pageToken=page_token,
                )
                .execute()
            )

            for f in resp.get("files", []):
                file_id = f["id"]
                name = f["name"]
                mime = f["mimeType"]
                # Use version if available, else modifiedTime as change signal
                version = str(f.get("version") or f.get("modifiedTime", ""))

                if not self._tracker.is_new(self.SOURCE, file_id, version):
                    continue

                try:
                    if mime in EXPORT_MAP:
                        export_mime, ext = EXPORT_MAP[mime]
                        data = (
                            svc.files()
                            .export_media(fileId=file_id, mimeType=export_mime)
                            .execute()
                        )
                        name = name + ext
                    elif mime in SUPPORTED_NATIVE_MIME:
                        data = svc.files().get_media(fileId=file_id).execute()
                    else:
                        continue
                except Exception as e:
                    logger.warning(f"GDriveConnector: could not download '{name}' ({file_id}): {e}")
                    continue

                self._tracker.mark_seen(self.SOURCE, file_id, version)
                logger.debug(f"GDriveConnector: new file '{name}' (project={project_id})")
                yield ConnectorFile(data, name, file_id, project_id)

            page_token = resp.get("nextPageToken")
            if not page_token:
                break
