"""
Shared FastAPI dependencies:
  - get_agent()             — returns the singleton MasterAgent
  - get_conversation_store() — returns the singleton ConversationStore
  - get_connector_manager() — returns the singleton ConnectorManager
  - require_admin()         — 403 if role is not admin
  - require_manager_or_above() — 403 if role is employee
"""
import logging
from fastapi import Depends, HTTPException, status

from api.auth import UserInfo, get_current_user
from aegis.core.conversation_store import ConversationStore

logger = logging.getLogger(__name__)

_agent = None
_conversation_store: ConversationStore = ConversationStore()
_connector_manager = None


def set_agent(agent) -> None:
    """Called once at startup from main.py lifespan."""
    global _agent
    _agent = agent


def get_agent():
    """FastAPI dependency that returns the singleton MasterAgent."""
    if _agent is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not yet initialized — server is starting up",
        )
    return _agent


def get_conversation_store() -> ConversationStore:
    return _conversation_store


def set_connector_manager(mgr) -> None:
    global _connector_manager
    _connector_manager = mgr


def get_connector_manager():
    if _connector_manager is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Connector manager not initialized",
        )
    return _connector_manager


async def require_admin(current_user: UserInfo = Depends(get_current_user)) -> UserInfo:
    if current_user.user_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Admin role required (your role: {current_user.user_role})",
        )
    return current_user


async def require_manager_or_above(
    current_user: UserInfo = Depends(get_current_user),
) -> UserInfo:
    if current_user.user_role == "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin role required",
        )
    return current_user
