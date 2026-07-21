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


class ProjectInfo(BaseModel):
    project_id: str
    project_name: str
    collection_name: str


class CreateProjectRequest(BaseModel):
    name: str


def _slugify(name: str) -> str:
    """Convert project name to a safe project_id slug (matches app.py logic)."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())[:32]


@router.get("", response_model=List[ProjectInfo])
async def list_projects(
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """Return all projects (FAISS indexes prefixed with 'aegis_')."""
    try:
        project_ids = agent.r3.vector.list_projects()
    except Exception as e:
        logger.error(f"Failed to list FAISS projects: {e}")
        raise HTTPException(status_code=500, detail="Could not list projects")

    results = []
    for project_id in project_ids:
        results.append(ProjectInfo(
            project_id=project_id,
            project_name=project_id.replace("_", " ").title(),
            collection_name=f"aegis_{project_id}",
        ))
    return results


@router.post("", response_model=ProjectInfo, status_code=201)
async def create_project(
    req: CreateProjectRequest,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Create a new project workspace.
    Initializes an empty FAISS index and BM25 index slot.
    """
    if not req.name.strip():
        raise HTTPException(status_code=422, detail="Project name cannot be empty")

    project_id = _slugify(req.name)
    if not project_id:
        raise HTTPException(status_code=422, detail="Project name produced an invalid slug")

    try:
        # Create and PERSIST an empty FAISS index (idempotent). Persisting is
        # required so the new project is visible in list_projects(), which
        # enumerates by globbing *.index files on disk.
        agent.r3.vector.ensure_index(project_id)
        logger.info(f"Project created/verified: '{project_id}' by user '{current_user.user_id}'")
    except Exception as e:
        logger.error(f"Failed to create project '{project_id}': {e}")
        raise HTTPException(status_code=500, detail="Could not create project")

    collection_name = f"aegis_{project_id}".replace("-", "_")[:63]
    return ProjectInfo(
        project_id=project_id,
        project_name=req.name.strip(),
        collection_name=collection_name,
    )
