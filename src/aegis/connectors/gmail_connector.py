"""
Gmail connector — fetches PDF/DOCX/TXT attachments from specified labels.

OAuth2 user flow:
  1. GET /api/v1/connectors/google/auth-url  → redirect to Google consent
  2. Google redirects to /api/v1/connectors/google/callback?code=...
  3. exchange_code() stores refresh token in data/connector_tokens/gmail.json
  4. Subsequent calls auto-refresh using stored refresh token
"""
import base64
import logging
from pathlib import Path
from typing import AsyncIterator, Optional

from aegis.connectors.base import BaseConnector, ConnectorFile
from aegis.connectors.delta_tracker import DeltaTracker

logger = logging.getLogger(__name__)

TOKEN_PATH = Path("data/connector_tokens/gmail.json")
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SUPPORTED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
    "text/markdown",
}


class GmailConnector(BaseConnector):
    SOURCE = "gmail"

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
            logger.warning(f"GmailConnector: could not load token: {e}")
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
        logger.info("GmailConnector: OAuth exchange complete, token saved")

    def disconnect(self) -> None:
        if TOKEN_PATH.exists():
            TOKEN_PATH.unlink()
        self._creds = None


    def _build_service(self):
        self._refresh_if_expired()
        from googleapiclient.discovery import build
        return build("gmail", "v1", credentials=self._creds)

    async def list_new_files(
        self, project_id: str, dept_config: dict
    ) -> AsyncIterator[ConnectorFile]:
        if not self.is_authenticated():
            logger.warning("GmailConnector: not authenticated — skipping sync")
            return

        labels: list = dept_config.get("labels", [])
        svc = self._build_service()

        # Build query: label filter + has attachment
        label_query = " OR ".join(f"label:{lb}" for lb in labels) if labels else ""
        query = (f"({label_query}) has:attachment" if label_query else "has:attachment").strip()

        result = (
            svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=200)
            .execute()
        )
        messages = result.get("messages", [])
        logger.info(f"GmailConnector: found {len(messages)} messages for project '{project_id}'")

        for msg_meta in messages:
            msg_id = msg_meta["id"]
            try:
                msg = (
                    svc.users()
                    .messages()
                    .get(userId="me", id=msg_id, format="full")
                    .execute()
                )
            except Exception as e:
                logger.warning(f"GmailConnector: could not fetch message {msg_id}: {e}")
                continue

            for part in msg.get("payload", {}).get("parts", []):
                mime = part.get("mimeType", "")
                filename = part.get("filename", "")
                if not filename or mime not in SUPPORTED_MIME:
                    continue

                part_id = part.get("partId", "0")
                file_id = f"{msg_id}:{part_id}"
                version = msg_id  # Gmail messages are immutable

                if not self._tracker.is_new(self.SOURCE, file_id, version):
                    continue

                attachment_id = part.get("body", {}).get("attachmentId")
                if not attachment_id:
                    continue

                try:
                    att = (
                        svc.users()
                        .messages()
                        .attachments()
                        .get(userId="me", messageId=msg_id, id=attachment_id)
                        .execute()
                    )
                    data = base64.urlsafe_b64decode(att["data"])
                except Exception as e:
                    logger.warning(f"GmailConnector: could not download attachment {file_id}: {e}")
                    continue

                self._tracker.mark_seen(self.SOURCE, file_id, version)
                logger.debug(f"GmailConnector: new attachment '{filename}' (project={project_id})")
                yield ConnectorFile(data, filename, file_id, project_id)
