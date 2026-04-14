"""
Shared FastAPI dependencies:
  - get_agent()      — returns the singleton MasterAgent
  - require_admin()  — 403 if role is not admin
  - require_manager_or_above() — 403 if role is employee
"""
import logging
from functools import lru_cache
from fastapi import Depends, HTTPException, status

from api.auth import UserInfo, get_current_user

logger = logging.getLogger(__name__)

# ── Singleton MasterAgent ──────────────────────────────────────────────────────
_agent = None


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


# ── RBAC guards ────────────────────────────────────────────────────────────────
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
