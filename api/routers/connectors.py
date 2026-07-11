"""
Connector management endpoints.

GET    /api/v1/connectors/status                  — all connector auth + config status
POST   /api/v1/connectors/sync                    — trigger manual full sync
POST   /api/v1/connectors/sync/{project_id}       — trigger sync for one department

Google OAuth (Gmail + GDrive share the same OAuth app):
  GET  /api/v1/connectors/google/auth-url         — returns Google OAuth redirect URL
  GET  /api/v1/connectors/google/callback         — handles OAuth code exchange
  DELETE /api/v1/connectors/google/disconnect     — revoke stored Google tokens

OneDrive OAuth:
  GET  /api/v1/connectors/onedrive/auth-url       — returns Microsoft OAuth redirect URL
  GET  /api/v1/connectors/onedrive/callback       — handles OAuth code exchange
  DELETE /api/v1/connectors/onedrive/disconnect   — revoke stored OneDrive token
"""
import logging
import threading
import time
import uuid as _uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_connector_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])

# OAuth CSRF protection: `state` values issued by the auth-url endpoints are
# recorded here and must be presented back by the provider callback. Previously
# state was generated but never checked, so an attacker could complete the OAuth
# flow with their own account and bind their tokens to this server (login CSRF).
_STATE_TTL_SECONDS = 600
_pending_states: Dict[str, float] = {}
_state_lock = threading.Lock()


def _issue_state() -> str:
    state = _uuid.uuid4().hex
    now = time.time()
    with _state_lock:
        # Prune expired states while we hold the lock
        for s, ts in list(_pending_states.items()):
            if now - ts > _STATE_TTL_SECONDS:
                del _pending_states[s]
        _pending_states[state] = now
    return state


def _consume_state(state: str) -> None:
    """Validate and invalidate a state token (single use). Raises 400 if invalid."""
    with _state_lock:
        issued_at = _pending_states.pop(state, None)
    if issued_at is None or time.time() - issued_at > _STATE_TTL_SECONDS:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired OAuth state — restart the connection flow",
        )



class ConnectorStatus(BaseModel):
    source: str
    authenticated: bool
    configured_projects: list[str]


class StatusResponse(BaseModel):
    connectors: list[ConnectorStatus]


class SyncResult(BaseModel):
    files_ingested: Dict[str, int]
    message: str


class AuthUrlResponse(BaseModel):
    auth_url: str
    state: str



def _require_admin(user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if user.user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required to manage connectors",
        )
    return user



@router.get("/status", response_model=StatusResponse)
async def connector_status(
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Return auth status and configured departments for all connectors."""
    raw = mgr.status()
    return StatusResponse(
        connectors=[
            ConnectorStatus(
                source=src,
                authenticated=info["authenticated"],
                configured_projects=info["configured_projects"],
            )
            for src, info in raw.items()
        ]
    )



@router.post("/sync", response_model=SyncResult)
async def sync_all(
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Trigger immediate full sync across all connectors and departments."""
    counts = await mgr.sync_all()
    total = sum(counts.values())
    return SyncResult(
        files_ingested=counts,
        message=f"Sync complete — {total} new file(s) ingested",
    )


@router.post("/sync/{project_id}", response_model=SyncResult)
async def sync_project(
    project_id: str,
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Trigger sync for a single department."""
    counts = await mgr.sync_project(project_id)
    total = sum(counts.values())
    return SyncResult(
        files_ingested=counts,
        message=f"Sync complete for '{project_id}' — {total} new file(s) ingested",
    )



@router.get("/google/auth-url", response_model=AuthUrlResponse)
async def google_auth_url(
    source: str = Query(..., description="gmail or gdrive"),
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Return Google OAuth2 authorization URL. Open in browser to grant access."""
    state = _issue_state()
    connector = mgr.gmail if source == "gmail" else mgr.gdrive
    auth_url = connector.get_auth_url(state)
    if not auth_url:
        raise HTTPException(status_code=400, detail="Google credentials not configured (AEGIS_GOOGLE_CLIENT_ID / SECRET)")
    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/google/callback", include_in_schema=False)
async def google_callback(
    code: str = Query(...),
    state: str = Query(default=""),
    source: str = Query(default="gdrive"),
    mgr=Depends(get_connector_manager),
):
    """
    OAuth2 callback — Google redirects here after user grants consent.
    Exchanges authorization code for tokens and stores them.
    Validates the CSRF `state` issued by the auth-url endpoint.
    """
    _consume_state(state)
    try:
        connector = mgr.gmail if source == "gmail" else mgr.gdrive
        connector.exchange_code(code)
    except Exception as e:
        logger.error(f"Google OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail="OAuth exchange failed")

    return {"message": f"Google ({source}) connected successfully. You can close this tab."}


@router.delete("/google/disconnect")
async def google_disconnect(
    source: str = Query(..., description="gmail or gdrive"),
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Revoke stored Google tokens."""
    connector = mgr.gmail if source == "gmail" else mgr.gdrive
    connector.disconnect()
    return {"message": f"Google ({source}) disconnected"}



@router.get("/onedrive/auth-url", response_model=AuthUrlResponse)
async def onedrive_auth_url(
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Return Microsoft OAuth2 authorization URL."""
    state = _issue_state()
    auth_url = mgr.onedrive.get_auth_url(state)
    if not auth_url:
        raise HTTPException(status_code=400, detail="Microsoft credentials not configured (AEGIS_MICROSOFT_CLIENT_ID)")
    return AuthUrlResponse(auth_url=auth_url, state=state)


@router.get("/onedrive/callback", include_in_schema=False)
async def onedrive_callback(
    code: str = Query(...),
    state: str = Query(default=""),
    mgr=Depends(get_connector_manager),
):
    """OAuth2 callback — Microsoft redirects here after consent. Validates CSRF `state`."""
    _consume_state(state)
    try:
        mgr.onedrive.exchange_code(code)
    except Exception as e:
        logger.error(f"OneDrive OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail="OAuth exchange failed")

    return {"message": "OneDrive connected successfully. You can close this tab."}


@router.delete("/onedrive/disconnect")
async def onedrive_disconnect(
    _: UserInfo = Depends(_require_admin),
    mgr=Depends(get_connector_manager),
):
    """Revoke stored OneDrive token."""
    mgr.onedrive.disconnect()
    return {"message": "OneDrive disconnected"}
