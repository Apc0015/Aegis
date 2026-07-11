"""
Document management endpoints.

GET    /api/v1/documents?project_id=  — list indexed documents
POST   /api/v1/documents/upload       — upload & index files (multipart)
DELETE /api/v1/documents/{doc_id}     — remove document from vector + BM25 index
"""
import logging
import os
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_agent
from aegis.services.document_processor import DocumentProcessor
from aegis.config import RAG_MODES, MAX_FILE_SIZE_MB, SUPPORTED_FILE_TYPES, DEPT_TO_RAG_MODE
from aegis.core.department_router import DEPARTMENT_KEYWORDS
from aegis.security import InvalidProjectId, sanitize_project_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

# Department project ids that are subject to role-based access. Custom
# user-created projects (not in this set) are open workspaces.
_KNOWN_DEPARTMENTS = set(DEPARTMENT_KEYWORDS.keys()) | {"general"}


def _safe_project_id(raw: str) -> str:
    try:
        return sanitize_project_id(raw)
    except InvalidProjectId as e:
        raise HTTPException(status_code=422, detail=str(e))


def _authorize_department_access(agent, user: UserInfo, project_id: str) -> None:
    """
    Block non-admin document operations on department indexes their role cannot
    read. Without this, any employee could upload into (poison) or enumerate the
    legal/finance index that RBAC blocks them from querying. Custom projects are
    exempt — they are user workspaces, not governed departments.
    """
    if project_id not in _KNOWN_DEPARTMENTS:
        return
    allowed, denied = agent.rbac.authorize_departments(user.user_role, [project_id])
    if denied:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Your role does not have access to the '{project_id}' department",
        )


def _seed_r1_prototypes(project_id: str, text_sample: str, filename: str) -> None:
    """Write/update data/domain_prototypes/{project_id}.json with a text sample."""
    import json, os
    from aegis.agents.r1_classifier import R1Classifier
    try:
        proto_dir = "data/domain_prototypes"
        os.makedirs(proto_dir, exist_ok=True)
        proto_path = os.path.join(proto_dir, f"{project_id}.json")
        existing = {}
        if os.path.exists(proto_path):
            with open(proto_path) as f:
                existing = json.load(f)
        # Use R1 to classify the sample and record domain -> sample sentence
        classifier = R1Classifier()
        domain, _, confidence = classifier.classify(text_sample[:2000], filename=filename, project_id="")
        if confidence >= 0.4 and domain not in ("multi", "general"):
            # Store first 200 chars of sample as prototype for this domain
            existing[domain] = text_sample[:200].replace("\n", " ").strip()
            with open(proto_path, "w") as f:
                json.dump(existing, f, indent=2)
            logger.info(f"R1 prototype seeded: project={project_id} domain={domain} conf={confidence:.2f}")
    except Exception as e:
        logger.warning(f"R1 prototype seeding failed for project '{project_id}': {e}")

_processor = DocumentProcessor()
ALLOWED_EXTENSIONS = set(SUPPORTED_FILE_TYPES + ["md"])


class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    project_id: str
    chunks_count: int


class UploadResult(BaseModel):
    doc_id: str
    filename: str
    chunks_created: int
    status: str = "indexed"
    message: str


class DeleteResult(BaseModel):
    doc_id: str
    message: str


def _safe_slug(name: str) -> str:
    """Create a filesystem/collection-safe slug from filename."""
    import re
    base = name.rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9_]", "_", base.lower())[:48]


# Hard ceiling on extracted text per document. A 50MB text file would otherwise
# turn into thousands of embedding calls on the synchronous upload path.
MAX_EXTRACT_CHARS = int(os.getenv("AEGIS_MAX_EXTRACT_CHARS", "2000000"))


async def _ingest_file(
    file_bytes: bytes,
    filename: str,
    project_id: str,
    rag_mode: str,
    agent,
    seed_prototypes: bool = False,
) -> UploadResult:
    """Extract, chunk, embed, and index a single document."""
    doc_id = f"{_safe_slug(filename)}_{uuid.uuid4().hex[:8]}"
    # rag_mode may be a department id ("finance", "engineering") — map it to its
    # RAG_MODES key so per-domain chunking applies instead of silently falling
    # back to "general" on the naming mismatch.
    mode_key = rag_mode if rag_mode in RAG_MODES else DEPT_TO_RAG_MODE.get(rag_mode, "general")
    mode = RAG_MODES[mode_key]

    text = _processor.extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError(f"No extractable text found in '{filename}'")
    if len(text) > MAX_EXTRACT_CHARS:
        logger.warning(
            f"'{filename}' extracted {len(text):,} chars — truncating to {MAX_EXTRACT_CHARS:,}"
        )
        text = text[:MAX_EXTRACT_CHARS]

    texts, metas = _processor.chunk(
        text,
        chunk_size=mode["chunk_size"],
        overlap=mode.get("chunk_overlap", 77),
        source=filename,
        doc_id=doc_id,
        domain=rag_mode,
    )

    if seed_prototypes:
        _seed_r1_prototypes(project_id, text, filename)

    # Embed all chunks
    embeddings = await agent.r3.embeddings.embed_batch(texts)

    # Upsert into vector store — defer disk writes until all chunks are added,
    # then flush once (avoids O(n²) full-index rewrites during ingestion).
    for i, (chunk_text, meta, emb) in enumerate(zip(texts, metas, embeddings)):
        agent.r3.vector.upsert(
            project_id=project_id,
            doc_id=doc_id,
            chunk_index=i,
            text=chunk_text,
            embedding=emb,
            metadata={**meta, "project_id": project_id},
            persist=False,
        )
    agent.r3.vector.flush(project_id)

    # Add to BM25 index
    agent.r3.bm25.add_documents(project_id, texts, metas)

    return UploadResult(
        doc_id=doc_id,
        filename=filename,
        chunks_created=len(texts),
        message=f"Indexed {len(texts)} chunks from '{filename}'",
    )


@router.get("", response_model=List[DocumentInfo])
async def list_documents(
    project_id: str,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """Return list of documents indexed in the given project."""
    project_id = _safe_project_id(project_id)
    _authorize_department_access(agent, current_user, project_id)

    try:
        docs = agent.r3.bm25.list_documents(project_id)
    except Exception as e:
        logger.error(f"Failed to list documents for project '{project_id}': {e}")
        raise HTTPException(status_code=500, detail="Could not list documents")

    return [
        DocumentInfo(
            doc_id=doc["doc_id"],
            filename=doc["filename"],
            project_id=project_id,
            chunks_count=doc["chunks_count"],
        )
        for doc in docs
    ]


@router.post("/upload", response_model=List[UploadResult])
async def upload_documents(
    project_id: str = Form(...),
    rag_mode: str = Form("general"),
    files: List[UploadFile] = File(...),
    async_ingest: bool = Query(False, description="Enqueue ingestion via ARQ instead of processing inline"),
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Upload and index one or more documents.
    Supports: pdf, docx, txt, md.
    Max file size: MAX_FILE_SIZE_MB MB per file.

    Pass ?async_ingest=true to offload heavy ingestion to the ARQ worker.
    Returns status="queued" with a job_id that can be polled via GET /jobs/{job_id}.
    Falls back to synchronous ingestion if ARQ/Redis is unavailable.
    """
    project_id = _safe_project_id(project_id)
    _authorize_department_access(agent, current_user, project_id)
    if not files:
        raise HTTPException(status_code=422, detail="No files provided")

    results: List[UploadResult] = []
    errors: List[str] = []

    for upload in files:
        filename = upload.filename or "unknown"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext not in ALLOWED_EXTENSIONS:
            errors.append(f"'{filename}': unsupported type (.{ext})")
            continue

        content = await upload.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            errors.append(f"'{filename}': file too large ({size_mb:.1f} MB, max {MAX_FILE_SIZE_MB} MB)")
            continue

        # ── Async path ──────────────────────────────────────────────────────
        if async_ingest:
            try:
                from aegis.tasks.worker import enqueue_ingest
                job_id = await enqueue_ingest(content, filename, project_id, rag_mode)
            except Exception as e:
                logger.warning(f"async_ingest enqueue failed for '{filename}': {e}; falling back to sync")
                job_id = None

            if job_id is not None:
                results.append(UploadResult(
                    doc_id=job_id,
                    filename=filename,
                    chunks_created=0,
                    status="queued",
                    message=f"Ingestion queued (job_id={job_id}). Poll GET /api/v1/documents/jobs/{job_id} for status.",
                ))
                logger.info(f"Queued ingest job {job_id} for '{filename}' (project={project_id})")
                continue
            # fall through to synchronous ingest if enqueue returned None

        # ── Synchronous path (default, or async fallback) ───────────────────
        try:
            result = await _ingest_file(content, filename, project_id, rag_mode, agent, seed_prototypes=True)
            results.append(result)
            logger.info(f"Indexed '{filename}' → {result.chunks_created} chunks (project={project_id})")
            logger.info(f"Upload response: {result.model_dump()}")
        except Exception as e:
            logger.error(f"Failed to index '{filename}': {e}")
            errors.append(f"'{filename}': {e}")

    if errors and not results:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    if errors:
        # Partial success — return results, log errors
        logger.warning(f"Upload partial failure: {'; '.join(errors)}")

    return results


@router.get("/jobs/{job_id}")
async def get_ingest_job_status(
    job_id: str,
    current_user: UserInfo = Depends(get_current_user),
):
    """Check status of an async ingest job enqueued via ?async_ingest=true."""
    from aegis.tasks.worker import get_job_status
    return await get_job_status(job_id)


@router.delete("/{doc_id}", response_model=DeleteResult)
async def delete_document(
    doc_id: str,
    project_id: str,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Remove a document from the vector store and BM25 index.
    Requires a role with the can_delete_docs capability (RBAC_ROLES config).
    """
    # Enforce the configured capability instead of a hardcoded role check —
    # config says only admins may delete (manager: can_delete_docs=False).
    if not agent.rbac.can_delete_docs(current_user.user_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your role does not have document deletion permission",
        )

    project_id = _safe_project_id(project_id)
    _authorize_department_access(agent, current_user, project_id)

    try:
        agent.r3.vector.delete_by_source(project_id, doc_id)
        agent.r3.bm25.remove_by_source(project_id, doc_id)
    except Exception as e:
        logger.error(f"Failed to delete doc '{doc_id}' from project '{project_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Deletion failed",
        )

    return DeleteResult(doc_id=doc_id, message=f"Document '{doc_id}' removed from project '{project_id}'")
