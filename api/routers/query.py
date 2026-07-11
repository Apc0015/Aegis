"""
Query endpoints — the core of Aegis.

POST /api/v1/query              — batch, returns full QueryResult JSON
GET  /api/v1/query/stream       — SSE streaming, yields answer chunks then final QueryResult JSON
POST /api/v1/query/with-file    — batch query with uploaded file (multipart)
"""
import asyncio
import hashlib
import json
import logging
import os
from typing import Optional

from cachetools import TTLCache
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_agent, get_conversation_store
from api.ratelimit import check_rate_limit
from aegis.core.conversation_store import ConversationStore
from aegis.security import InvalidProjectId, sanitize_project_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/query", tags=["query"])

_query_cache: TTLCache = TTLCache(maxsize=256, ttl=300)

QUERY_TIMEOUT_SECONDS = int(os.getenv("AEGIS_QUERY_TIMEOUT_SECONDS", "120"))


def _safe_project_id(raw: str) -> str:
    """Sanitize a client-supplied project_id, mapping blank → 'general'."""
    try:
        return sanitize_project_id(raw, default="general")
    except InvalidProjectId as e:
        raise HTTPException(status_code=422, detail=str(e))


def _spawn_logged(coro, label: str) -> None:
    """
    Fire-and-forget an async task WITH exception logging. A bare
    asyncio.create_task swallows failures into 'task exception was never
    retrieved' noise at interpreter shutdown.
    """
    task = asyncio.create_task(coro)

    def _log_result(t: asyncio.Task) -> None:
        exc = t.exception() if not t.cancelled() else None
        if exc:
            logger.warning(f"Background task '{label}' failed: {exc}")

    task.add_done_callback(_log_result)


class QueryRequest(BaseModel):
    user_query: str
    project_id: str
    conversation_id: Optional[str] = None  # UUID from client for history


class AccessDecisionSchema(BaseModel):
    permitted: bool
    user_role: str
    user_id: str
    query: str
    permitted_departments: list
    denial_reason: Optional[str] = None


class QueryResultResponse(BaseModel):
    answer: str
    confidence: float
    verdict: str
    should_refuse: bool
    is_external: bool
    sources: list
    chunks_used: int
    routing_path: str
    model_used: str
    latency_ms: int
    web_used: bool
    cross_model_eval: bool
    reranker_used: bool
    db_triggered: bool
    columns_blocked: list
    columns_anonymized: list
    access_decision: AccessDecisionSchema
    cached: bool = False
    query_source: str = "faiss"


def _result_to_dict(result) -> dict:
    """Convert QueryResult dataclass to a JSON-serializable dict."""
    d = result.__dict__.copy()
    if hasattr(d.get("access_decision"), "__dict__"):
        d["access_decision"] = d["access_decision"].__dict__
    return d


@router.post("", response_model=QueryResultResponse)
async def query_batch(
    req: QueryRequest,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
    conv_store: ConversationStore = Depends(get_conversation_store),
):
    """
    Non-streaming query. Waits for the full answer before returning.
    Prefer /stream for real-time UI responses.
    Pass conversation_id (UUID) to enable multi-turn memory.
    """
    if not req.user_query.strip():
        raise HTTPException(status_code=422, detail="user_query cannot be empty")

    check_rate_limit(current_user.user_id)
    project_id = _safe_project_id(req.project_id)
    history = (
        conv_store.get_history(current_user.user_id, req.conversation_id)
        if req.conversation_id else None
    )

    # user_id is part of the key: answers are row-filtered per user, so two users
    # with the same role and query still have different correct answers. Omitting
    # user_id would serve one user's personal data to another.
    cache_key = hashlib.sha256(
        f"{req.user_query}|{project_id}|{current_user.user_role}|{current_user.user_id}".encode()
    ).hexdigest()

    # Conversational turns are history-dependent — an identically-worded follow-up
    # has a different correct answer, so the cache only serves history-free queries.
    cacheable = not history
    if cacheable and cache_key in _query_cache:
        cached_result = dict(_query_cache[cache_key])
        cached_result["cached"] = True
        return cached_result

    try:
        result = await asyncio.wait_for(
            agent.query(
                user_query=req.user_query,
                project_id=project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                history=history,
                employee_id=current_user.employee_id,
            ),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out")
    except HTTPException:
        raise
    except Exception as e:
        # Log the real error; never echo internals to the client.
        logger.error(f"Query pipeline error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Query pipeline failed")

    if req.conversation_id and result.routing_path not in ("denied", "refuse"):
        conv_store.append(current_user.user_id, req.conversation_id, "user", req.user_query)
        conv_store.append(current_user.user_id, req.conversation_id, "assistant", result.answer)
        # Compress history if it's grown too long
        _spawn_logged(
            agent.maybe_compress_history(conv_store, current_user.user_id, req.conversation_id),
            "compress_history",
        )

    result_dict = _result_to_dict(result)
    result_dict["cached"] = False
    if cacheable and result.routing_path not in ("denied", "refuse"):
        _query_cache[cache_key] = result_dict
    return result_dict


@router.get("/stream")
async def query_stream(
    user_query: str,
    project_id: str = "general",
    conversation_id: Optional[str] = None,
    current_user: UserInfo = Depends(get_current_user),
    agent=Depends(get_agent),
    conv_store: ConversationStore = Depends(get_conversation_store),
):
    """
    SSE streaming query. System auto-decides RAG vs DB vs multi-dept based on
    RBAC role + intent detection. User sends query only — no pipeline control.

    The full answer is produced and confidence-scored server-side BEFORE emission
    starts, so refused/denied answers are never partially shown. Emission is then
    chunked over SSE (protocol unchanged for clients):

      data: <text chunk>         — answer text while "streaming"
      data: <QueryResult JSON>   — final metadata
      data: [DONE]               — end of stream
    """
    if not user_query.strip():
        raise HTTPException(status_code=422, detail="user_query cannot be empty")

    check_rate_limit(current_user.user_id)
    effective_project_id = _safe_project_id(project_id)
    history = (
        conv_store.get_history(current_user.user_id, conversation_id)
        if conversation_id else None
    )

    async def event_generator():
        final_answer = None
        routing_path = None
        try:
            events = agent.query_stream_events(
                user_query=user_query,
                project_id=effective_project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                history=history,
                employee_id=current_user.employee_id,
            )
            async for item in events:
                if isinstance(item, dict):
                    d = dict(item)
                    if hasattr(d.get("access_decision"), "__dict__"):
                        d["access_decision"] = d["access_decision"].__dict__
                    final_answer = d.get("answer")
                    routing_path = d.get("routing_path")
                    yield f"data: {json.dumps(d)}\n\n"
                else:
                    yield f"data: {str(item).replace(chr(10), chr(92) + 'n')}\n\n"

            if conversation_id and final_answer and routing_path not in ("denied", "refuse"):
                conv_store.append(current_user.user_id, conversation_id, "user", user_query)
                conv_store.append(current_user.user_id, conversation_id, "assistant", final_answer)
                if len(conv_store.get_history(current_user.user_id, conversation_id)) >= 16:
                    _spawn_logged(
                        agent.maybe_compress_history(conv_store, current_user.user_id, conversation_id),
                        "compress_history",
                    )

            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Streaming query error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'error': 'Query pipeline failed'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/with-file", response_model=QueryResultResponse)
async def query_with_file(
    user_query: str = Form(...),
    project_id: str = Form("general"),
    conversation_id: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    current_user: UserInfo = Depends(get_current_user),
    agent=Depends(get_agent),
    conv_store: ConversationStore = Depends(get_conversation_store),
):
    """
    Query with an optional file attachment.

    Supports: PDF, DOCX, TXT, MD, CSV, XLSX, JSON, XML, images (JPG/PNG),
              audio (MP3/WAV), code files.

    - Text files  → extracted and injected as context
    - Images      → sent to vision LLM directly (or described if non-vision)
    - Audio       → transcribed to text via Whisper
    - is_verify   → auto-detected when user says "correct?", "verify", etc.
    """
    from aegis.media.media_pipeline import process as media_process, build_context_block
    from aegis.agents.intent_detector import detect_intent

    if not user_query.strip():
        raise HTTPException(status_code=422, detail="user_query cannot be empty")

    check_rate_limit(current_user.user_id)
    effective_project_id = _safe_project_id(project_id)

    file_context: Optional[str] = None
    is_verify: bool = False
    vision_data: Optional[dict] = None  # {b64, mime} for vision LLM
    data: Optional[bytes] = None

    if file and file.filename:
        try:
            data = await file.read()
            llm_provider = os.getenv("AEGIS_LLM_PROVIDER", "openai")

            media_result = await media_process(
                data=data,
                filename=file.filename,
                question=user_query,
                llm_service=agent.llm,
                llm_provider=llm_provider,
            )

            if media_result.is_vision:
                # Vision image — will be passed directly to LLM
                vision_data = {"b64": media_result.image_b64, "mime": media_result.image_mime}
                file_context = f"[User uploaded image: {file.filename}]"
            else:
                file_context = build_context_block(media_result, file.filename)

            # Detect verify intent
            intent = detect_intent(user_query, has_file=True)
            is_verify = intent["is_verify"]

            logger.info(
                f"File processed: '{file.filename}' | category={media_result.category} "
                f"| is_verify={is_verify} | vision={media_result.is_vision}"
            )
        except Exception as e:
            logger.error(f"File processing failed for '{file.filename}': {e}")
            raise HTTPException(status_code=422, detail="File could not be processed")

    history = (
        conv_store.get_history(current_user.user_id, conversation_id)
        if conversation_id else None
    )

    # Pipeline 3: chunk + embed text file into session FAISS, then retrieve via R3.
    # Vision images skip this — they go directly to the vision LLM.
    file_project_id: Optional[str] = None
    if file_context and not vision_data and data is not None and file and file.filename:
        try:
            file_project_id = await agent.ingest_session_file(
                file_bytes=data,
                filename=file.filename,
                user_id=current_user.user_id,
            )
            # Raw file text is no longer needed — R3 will retrieve relevant chunks
            file_context = None
            logger.info(f"Pipeline 3: file indexed → session project_id='{file_project_id}'")
        except Exception as e:
            logger.warning(f"Pipeline 3 ingest failed, falling back to direct context: {e}")
            # Fallback: old path — summarize and pass as context
            file_context = await agent.r4.summarize_file_content(file_context, user_query)

    try:
        result = await asyncio.wait_for(
            agent.query(
                user_query=user_query,
                project_id=effective_project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                file_context=file_context,
                is_verify=is_verify,
                vision_data=vision_data,
                history=history,
                file_project_id=file_project_id,
                employee_id=current_user.employee_id,
            ),
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query with file error: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Query pipeline failed")

    if conversation_id and result.routing_path not in ("denied", "refuse"):
        conv_store.append(current_user.user_id, conversation_id, "user", user_query)
        conv_store.append(current_user.user_id, conversation_id, "assistant", result.answer)
        _spawn_logged(
            agent.maybe_compress_history(conv_store, current_user.user_id, conversation_id),
            "compress_history",
        )

    return _result_to_dict(result)
