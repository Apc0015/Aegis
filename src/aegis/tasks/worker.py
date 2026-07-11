"""
ARQ task queue worker for Aegis.

Offloads CPU/IO-heavy operations from the API request thread:
  - Document ingestion (chunking + embedding + indexing)

Setup:
  pip install arq
  AEGIS_REDIS_URL=redis://localhost:6379

Run worker:
  arq aegis.tasks.worker.WorkerSettings
"""
import base64
import logging
import os
import uuid

logger = logging.getLogger(__name__)


# ── ARQ task ─────────────────────────────────────────────────────────────────

async def ingest_document_task(
    ctx,
    file_bytes_b64: str,
    filename: str,
    project_id: str,
    rag_mode: str,
) -> dict:
    """
    ARQ task: decode file bytes, run the full Aegis ingest pipeline.

    Args:
        ctx: ARQ context (provides redis connection, job_id, etc.)
        file_bytes_b64: base64-encoded file bytes (JSON-serializable)
        filename: original filename (used for text extraction + metadata)
        project_id: target project collection
        rag_mode: one of the configured RAG mode keys (e.g. "general", "medical")

    Returns:
        {"status": "ok", "filename": filename, "chunks": n}
    """
    import re

    from aegis.services.document_processor import DocumentProcessor
    from aegis.services.embedding_service import EmbeddingService
    from aegis.services.vector_store_service import VectorStoreService
    from aegis.services.bm25_engine import BM25Engine
    from aegis.config import RAG_MODES, DEPT_TO_RAG_MODE
    from aegis.security import sanitize_project_id

    job_id = ctx.get("job_id", "unknown")
    logger.info(f"[job={job_id}] Starting ingest for '{filename}' (project={project_id}, mode={rag_mode})")

    # Defense-in-depth: the API sanitizes project_id, but the worker must not
    # trust queue payloads either (they feed filesystem paths).
    project_id = sanitize_project_id(project_id)

    # Decode bytes
    file_bytes = base64.b64decode(file_bytes_b64)
    logger.info(f"[job={job_id}] Decoded {len(file_bytes):,} bytes")

    # Build services from env vars (mirrors factory.py pattern)
    embed_provider = os.getenv("AEGIS_EMBED_PROVIDER", "local")
    embed_api_key = (
        os.getenv("AEGIS_MAIN_API_KEY")
        or os.getenv("OPENAI_API_KEY", "")
    )
    embed_svc = EmbeddingService(embed_provider, embed_api_key)
    vector_svc = VectorStoreService(dimension=embed_svc.dimensions)
    bm25_svc = BM25Engine()
    processor = DocumentProcessor()

    # Extract text
    logger.info(f"[job={job_id}] Extracting text from '{filename}'")
    text = processor.extract_text(file_bytes, filename)
    if not text.strip():
        raise ValueError(f"No extractable text found in '{filename}'")
    logger.info(f"[job={job_id}] Extracted {len(text):,} characters")

    # Determine mode config — rag_mode may be a department id ("finance"),
    # so map department names to their RAG_MODES key ("financial") instead of
    # silently falling back to general on the naming mismatch.
    mode_key = rag_mode if rag_mode in RAG_MODES else DEPT_TO_RAG_MODE.get(rag_mode, "general")
    mode = RAG_MODES.get(mode_key, RAG_MODES.get("general", {}))

    # Build doc_id
    def _safe_slug(name: str) -> str:
        base = name.rsplit(".", 1)[0]
        return re.sub(r"[^a-z0-9_]", "_", base.lower())[:48]

    doc_id = f"{_safe_slug(filename)}_{uuid.uuid4().hex[:8]}"

    # Chunk
    logger.info(f"[job={job_id}] Chunking document (doc_id={doc_id})")
    texts, metas = processor.chunk(
        text,
        chunk_size=mode.get("chunk_size", 512),
        overlap=mode.get("chunk_overlap", 77),
        source=filename,
        doc_id=doc_id,
        domain=rag_mode,
    )
    logger.info(f"[job={job_id}] Created {len(texts)} chunks")

    # Embed
    logger.info(f"[job={job_id}] Embedding {len(texts)} chunks")
    embeddings = await embed_svc.embed_batch(texts)

    # Upsert into vector store
    logger.info(f"[job={job_id}] Indexing into vector store")
    for i, (chunk_text, meta, emb) in enumerate(zip(texts, metas, embeddings)):
        vector_svc.upsert(
            project_id=project_id,
            doc_id=doc_id,
            chunk_index=i,
            text=chunk_text,
            embedding=emb,
            metadata={**meta, "project_id": project_id},
        )

    # Add to BM25 index
    logger.info(f"[job={job_id}] Adding to BM25 index")
    bm25_svc.add_documents(project_id, texts, metas)

    logger.info(f"[job={job_id}] Ingest complete: '{filename}' → {len(texts)} chunks (doc_id={doc_id})")
    return {"status": "ok", "filename": filename, "doc_id": doc_id, "chunks": len(texts)}


# ── Periodic connector sync task ─────────────────────────────────────────────

async def sync_connectors_task(ctx):
    """Periodic task: run all configured connectors to sync new content."""
    from aegis.connectors.connector_manager import ConnectorManager
    logger.info("Connector sync task starting...")
    try:
        manager = ConnectorManager()
        results = await manager.sync_all()
        logger.info(f"Connector sync complete: {results}")
    except Exception as e:
        logger.error(f"Connector sync task failed: {e}")


# ── ARQ WorkerSettings ────────────────────────────────────────────────────────

try:
    from arq.connections import RedisSettings as _RedisSettings
    from arq.cron import cron

    class WorkerSettings:
        """ARQ WorkerSettings — run with: arq aegis.tasks.worker.WorkerSettings"""
        functions = [ingest_document_task, sync_connectors_task]
        cron_jobs = [
            cron(sync_connectors_task, hour={0, 6, 12, 18}, minute=0)  # every 6 hours
        ]
        redis_settings = _RedisSettings.from_dsn(
            os.getenv("AEGIS_REDIS_URL", "redis://localhost:6379")
        )
        max_jobs = 10
        job_timeout = 300   # 5 minutes per job
        keep_result = 3600  # keep result for 1 hour

    # Alias exported as "Settings" per __init__.py contract
    Settings = WorkerSettings

except ImportError:
    # arq not installed — define stubs so imports don't blow up
    class WorkerSettings:  # type: ignore[no-redef]
        pass

    Settings = WorkerSettings  # type: ignore[misc]


# ── Helper: enqueue ───────────────────────────────────────────────────────────

async def enqueue_ingest(
    file_bytes: bytes,
    filename: str,
    project_id: str,
    rag_mode: str,
) -> "str | None":
    """
    Enqueue an ingest job via ARQ.

    Returns the job_id string on success, or None if Redis is unavailable
    or arq is not installed (graceful degradation — caller falls back to
    synchronous ingest).
    """
    try:
        from arq import create_pool
        from arq.connections import RedisSettings as _RedisSettings

        redis_url = os.getenv("AEGIS_REDIS_URL", "redis://localhost:6379")
        pool = await create_pool(_RedisSettings.from_dsn(redis_url))
        job = await pool.enqueue_job(
            "ingest_document_task",
            base64.b64encode(file_bytes).decode(),
            filename,
            project_id,
            rag_mode,
        )
        await pool.aclose()
        if job is None:
            logger.warning("ARQ enqueue returned None (duplicate job?)")
            return None
        logger.info(f"Enqueued ingest job {job.job_id} for '{filename}'")
        return job.job_id

    except ImportError:
        logger.debug("arq not installed — skipping async enqueue")
        return None
    except Exception as exc:
        logger.warning(f"Could not connect to Redis for async ingest: {exc}")
        return None


# ── Helper: status ────────────────────────────────────────────────────────────

async def get_job_status(job_id: str) -> dict:
    """
    Return the current status of an ARQ ingest job.

    Possible statuses: queued | running | complete | failed | not_found | unknown
    """
    try:
        from arq import create_pool
        from arq.connections import RedisSettings as _RedisSettings
        from arq.jobs import Job, JobStatus

        redis_url = os.getenv("AEGIS_REDIS_URL", "redis://localhost:6379")
        pool = await create_pool(_RedisSettings.from_dsn(redis_url))
        job = Job(job_id, pool)

        status = await job.status()
        await pool.aclose()

        if status == JobStatus.queued:
            return {"status": "queued", "job_id": job_id}
        if status == JobStatus.in_progress:
            return {"status": "running", "job_id": job_id}
        if status == JobStatus.complete:
            info = await job.result_info()
            if info and info.success:
                return {"status": "complete", "job_id": job_id, "result": info.result}
            error_msg = str(info.result) if info else "unknown error"
            return {"status": "failed", "job_id": job_id, "error": error_msg}
        if status == JobStatus.not_found:
            return {"status": "not_found", "job_id": job_id}

        return {"status": str(status), "job_id": job_id}

    except ImportError:
        logger.debug("arq not installed — cannot check job status")
        return {"status": "unknown", "job_id": job_id}
    except Exception as exc:
        logger.warning(f"Could not fetch job status for {job_id}: {exc}")
        return {"status": "unknown", "job_id": job_id, "error": str(exc)}
