"""
Project management endpoints.

GET  /api/v1/projects      — list all projects
POST /api/v1/projects      — create a new project
"""
import re
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class ProjectInfo(BaseModel):
    project_id: str
    project_name: str
    collection_name: str


class CreateProjectRequest(BaseModel):
    name: str


# ── Helpers ────────────────────────────────────────────────────────────────────
def _slugify(name: str) -> str:
    """Convert project name to a safe project_id slug (matches app.py logic)."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())[:32]


# ── List projects ──────────────────────────────────────────────────────────────
@router.get("", response_model=List[ProjectInfo])
async def list_projects(
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """Return all projects (ChromaDB collections prefixed with 'rapid_')."""
    try:
        collections = agent.r3.vector._client.list_collections()
    except Exception as e:
        logger.error(f"Failed to list ChromaDB collections: {e}")
        raise HTTPException(status_code=500, detail=f"Could not list projects: {e}")

    results = []
    for col in collections:
        name = col.name if hasattr(col, "name") else str(col)
        if name.startswith("rapid_"):
            project_id = name[len("rapid_"):]
            results.append(ProjectInfo(
                project_id=project_id,
                project_name=project_id.replace("_", " ").title(),
                collection_name=name,
            ))
    return results


# ── Create project ─────────────────────────────────────────────────────────────
@router.post("", response_model=ProjectInfo, status_code=201)
async def create_project(
    req: CreateProjectRequest,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Create a new project workspace.
    Initializes an empty ChromaDB collection and BM25 index slot.
    """
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="Project name cannot be empty")

    project_id = _slugify(req.name)
    if not project_id:
        raise HTTPException(status_code=422, detail="Project name produced an invalid slug")

    try:
        # get_or_create is idempotent — safe to call even if collection exists
        agent.r3.vector._collection(project_id)
        logger.info(f"Project created/verified: '{project_id}' by user '{current_user.user_id}'")
    except Exception as e:
        logger.error(f"Failed to create project '{project_id}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not create project: {e}")

    collection_name = f"rapid_{project_id}".replace("-", "_")[:63]
    return ProjectInfo(
        project_id=project_id,
        project_name=req.name.strip(),
        collection_name=collection_name,
    )
