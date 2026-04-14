"""
Document management endpoints.

GET    /api/v1/documents?project_id=  — list indexed documents
POST   /api/v1/documents/upload       — upload & index files (multipart)
DELETE /api/v1/documents/{doc_id}     — remove document from vector + BM25 index
"""
import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_agent
from rapid.services.document_processor import DocumentProcessor
from rapid.services.embedding_service import EmbeddingService
from rapid.services.vector_store_service import VectorStoreService
from rapid.services.bm25_engine import BM25Engine
from rapid.config import RAG_MODES, MAX_FILE_SIZE_MB, SUPPORTED_FILE_TYPES

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/documents", tags=["documents"])

_processor = DocumentProcessor()
ALLOWED_EXTENSIONS = set(SUPPORTED_FILE_TYPES + ["md"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class DocumentInfo(BaseModel):
    doc_id: str
    filename: str
    project_id: str
    chunks_count: int


class UploadResult(BaseModel):
    doc_id: str
    filename: str
    chunks_created: int
    message: str


class DeleteResult(BaseModel):
    doc_id: str
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────────
def _safe_slug(name: str) -> str:
    """Create a filesystem/collection-safe slug from filename."""
    import re
    base = name.rsplit(".", 1)[0]
    return re.sub(r"[^a-z0-9_]", "_", base.lower())[:48]


async def _ingest_file(
    file_bytes: bytes,
    filename: str,
    project_id: str,
    rag_mode: str,
    agent,
) -> UploadResult:
    """Extract, chunk, embed, and index a single document."""
    doc_id = f"{_safe_slug(filename)}_{uuid.uuid4().hex[:8]}"
    mode = RAG_MODES.get(rag_mode, RAG_MODES["general"])

    text = _processor.extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError(f"No extractable text found in '{filename}'")

    texts, metas = _processor.chunk(
        text,
        chunk_size=mode["chunk_size"],
        overlap=mode.get("chunk_overlap", 77),
        source=filename,
        doc_id=doc_id,
        domain=rag_mode,
    )

    # Embed all chunks
    embeddings = await agent.r3.embeddings.embed_batch(texts)

    # Upsert into vector store
    for i, (chunk_text, meta, emb) in enumerate(zip(texts, metas, embeddings)):
        agent.r3.vector.upsert(
            project_id=project_id,
            doc_id=doc_id,
            chunk_index=i,
            text=chunk_text,
            embedding=emb,
            metadata={**meta, "project_id": project_id},
        )

    # Add to BM25 index
    agent.r3.bm25.add_documents(project_id, texts, metas)

    return UploadResult(
        doc_id=doc_id,
        filename=filename,
        chunks_created=len(texts),
        message=f"Indexed {len(texts)} chunks from '{filename}'",
    )


# ── List documents ─────────────────────────────────────────────────────────────
@router.get("", response_model=List[DocumentInfo])
async def list_documents(
    project_id: str,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """Return list of documents indexed in the given project."""
    if not project_id.strip():
        raise HTTPException(status_code=422, detail="project_id cannot be empty")

    try:
        bm25_index = agent.r3.bm25._load_index(project_id)
    except Exception:
        return []

    if not bm25_index:
        return []

    # Derive unique filenames from BM25 metadata
    sources_seen: dict[str, DocumentInfo] = {}
    for meta in bm25_index.get("metadatas", []):
        source = meta.get("source", "unknown")
        doc_id = meta.get("doc_id", source)
        if source not in sources_seen:
            sources_seen[source] = DocumentInfo(
                doc_id=doc_id,
                filename=source,
                project_id=project_id,
                chunks_count=0,
            )
        sources_seen[source].chunks_count += 1

    return list(sources_seen.values())


# ── Upload documents ───────────────────────────────────────────────────────────
@router.post("/upload", response_model=List[UploadResult])
async def upload_documents(
    project_id: str = Form(...),
    rag_mode: str = Form("general"),
    files: List[UploadFile] = File(...),
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Upload and index one or more documents.
    Supports: pdf, docx, txt, md.
    Max file size: MAX_FILE_SIZE_MB MB per file.
    """
    if not project_id.strip():
        raise HTTPException(status_code=422, detail="project_id cannot be empty")
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

        try:
            result = await _ingest_file(content, filename, project_id, rag_mode, agent)
            results.append(result)
            logger.info(f"Indexed '{filename}' → {result.chunks_created} chunks (project={project_id})")
        except Exception as e:
            logger.error(f"Failed to index '{filename}': {e}")
            errors.append(f"'{filename}': {e}")

    if errors and not results:
        raise HTTPException(status_code=422, detail="; ".join(errors))

    if errors:
        # Partial success — return results, log errors
        logger.warning(f"Upload partial failure: {'; '.join(errors)}")

    return results


# ── Delete document ────────────────────────────────────────────────────────────
@router.delete("/{doc_id}", response_model=DeleteResult)
async def delete_document(
    doc_id: str,
    project_id: str,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Remove a document from the vector store and BM25 index.
    Requires manager or admin role.
    """
    if current_user.user_role == "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin role required to delete documents",
        )

    try:
        agent.r3.vector.delete_by_source(project_id, doc_id)
        agent.r3.bm25.remove_by_source(project_id, doc_id)
    except Exception as e:
        logger.error(f"Failed to delete doc '{doc_id}' from project '{project_id}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deletion failed: {e}",
        )

    return DeleteResult(doc_id=doc_id, message=f"Document '{doc_id}' removed from project '{project_id}'")
