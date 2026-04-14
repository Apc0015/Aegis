"""
Health check endpoint.

GET /api/v1/health — returns service status
"""
import logging
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api.dependencies import get_agent
from rapid import __version__

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/health", tags=["health"])


class HealthStatus(BaseModel):
    status: str           # "ok" | "degraded" | "error"
    version: str
    llm_provider: str
    llm_model: str
    embed_provider: str
    db_connected: bool
    vector_store_ok: bool
    message: str = ""


@router.get("", response_model=HealthStatus)
async def health_check(
    agent = Depends(get_agent),
):
    """
    Check connectivity to all RAPID subsystems.
    Returns overall status and per-component health.
    """
    issues = []

    # Check vector store
    vector_ok = True
    try:
        agent.r3.vector._client.list_collections()
    except Exception as e:
        vector_ok = False
        issues.append(f"Vector store: {e}")
        logger.warning(f"Health check — vector store error: {e}")

    # Check HR database
    db_ok = True
    try:
        import sqlite3
        from rapid.database.hr_database import DB_PATH as HR_DB_PATH
        with sqlite3.connect(HR_DB_PATH) as conn:
            conn.execute("SELECT 1")
    except Exception as e:
        db_ok = False
        issues.append(f"HR DB: {e}")
        logger.warning(f"Health check — HR DB error: {e}")

    overall = "ok" if not issues else ("degraded" if vector_ok else "error")

    return HealthStatus(
        status=overall,
        version=__version__,
        llm_provider=agent.llm.provider,
        llm_model=agent.llm.model,
        embed_provider=agent.r3.embeddings.provider,
        db_connected=db_ok,
        vector_store_ok=vector_ok,
        message="; ".join(issues) if issues else "All systems operational",
    )
