"""
Query endpoints — the core of RAPID.

POST /api/v1/query        — batch, returns full QueryResult JSON
GET  /api/v1/query/stream — SSE streaming, yields tokens then final QueryResult JSON
"""
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from api.auth import UserInfo, get_current_user
from api.dependencies import get_agent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/query", tags=["query"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────
class QueryRequest(BaseModel):
    user_query: str
    project_id: str
    rag_mode: str = "general"
    force_db: bool = False
    llm_intent: bool = False
    mode: str = "auto"  # "chat" | "rag" | "db" | "auto"


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


# ── Helpers ────────────────────────────────────────────────────────────────────
def _result_to_dict(result) -> dict:
    """Convert QueryResult dataclass to a JSON-serializable dict."""
    d = result.__dict__.copy()
    if hasattr(d.get("access_decision"), "__dict__"):
        d["access_decision"] = d["access_decision"].__dict__
    return d


# ── Batch query ────────────────────────────────────────────────────────────────
@router.post("", response_model=QueryResultResponse)
async def query_batch(
    req: QueryRequest,
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Non-streaming query. Waits for the full answer before returning.
    Prefer /stream for real-time UI responses.
    """
    if not req.user_query.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="user_query cannot be empty")

    # Fallback project_id to 'general' when in chat mode
    project_id = req.project_id.strip() or ("general" if req.mode == "chat" else "")
    if not project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="project_id cannot be empty")

    try:
        if req.mode == "chat":
            result = await agent.chat_direct(
                user_query=req.user_query,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
            )
        elif req.mode == "db":
            result = await agent.query(
                user_query=req.user_query,
                project_id=project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                rag_mode=req.rag_mode,
                force_db=True,
                llm_intent=req.llm_intent,
            )
        elif req.mode == "rag":
            result = await agent.query(
                user_query=req.user_query,
                project_id=project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                rag_mode=req.rag_mode,
                force_db=False,
                llm_intent=req.llm_intent,
            )
        else:
            # mode == "auto" — current behavior
            result = await agent.query(
                user_query=req.user_query,
                project_id=project_id,
                user_id=current_user.user_id,
                user_role=current_user.user_role,
                rag_mode=req.rag_mode,
                force_db=req.force_db,
                llm_intent=req.llm_intent,
            )
        return _result_to_dict(result)
    except RuntimeError as e:
        logger.error(f"Query pipeline error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=str(e))


# ── Streaming query (SSE) ──────────────────────────────────────────────────────
@router.get("/stream")
async def query_stream(
    user_query: str,
    project_id: str = "",
    rag_mode: str = "general",
    force_db: bool = False,
    llm_intent: bool = False,
    mode: str = "auto",
    current_user: UserInfo = Depends(get_current_user),
    agent = Depends(get_agent),
):
    """
    Server-Sent Events streaming query.

    mode: "chat" | "rag" | "db" | "auto"
      - chat: direct LLM, no retrieval (project_id not required)
      - rag:  force RAG pipeline
      - db:   force DB/SQL pipeline
      - auto: current auto-detect behavior

    Yields:
      data: <token>\\n\\n          — one line per token while the answer streams
      data: <QueryResult JSON>\\n\\n — final complete result metadata
      data: [DONE]\\n\\n            — sentinel marking end of stream

    Client should:
      1. Concatenate tokens into the live answer display
      2. On JSON event: replace partial display with full QueryResult
      3. On [DONE]: close the connection
    """
    if not user_query.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="user_query cannot be empty")

    # Fallback project_id to 'general' when in chat mode
    effective_project_id = project_id.strip() or ("general" if mode == "chat" else "")
    if not effective_project_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="project_id cannot be empty")

    def event_generator():
        try:
            if mode == "chat":
                stream_iter = agent.chat_stream_direct(
                    user_query=user_query,
                    user_id=current_user.user_id,
                    user_role=current_user.user_role,
                )
            elif mode == "db":
                stream_iter = agent.query_stream(
                    user_query=user_query,
                    project_id=effective_project_id,
                    user_id=current_user.user_id,
                    user_role=current_user.user_role,
                    rag_mode=rag_mode,
                    force_db=True,
                    llm_intent=llm_intent,
                )
            elif mode == "rag":
                stream_iter = agent.query_stream(
                    user_query=user_query,
                    project_id=effective_project_id,
                    user_id=current_user.user_id,
                    user_role=current_user.user_role,
                    rag_mode=rag_mode,
                    force_db=False,
                    llm_intent=llm_intent,
                )
            else:
                # mode == "auto"
                stream_iter = agent.query_stream(
                    user_query=user_query,
                    project_id=effective_project_id,
                    user_id=current_user.user_id,
                    user_role=current_user.user_role,
                    rag_mode=rag_mode,
                    force_db=force_db,
                    llm_intent=llm_intent,
                )

            for item in stream_iter:
                if isinstance(item, dict):
                    # Final metadata object — serialize access_decision sub-object
                    if hasattr(item.get("access_decision"), "__dict__"):
                        item = dict(item)
                        item["access_decision"] = item["access_decision"].__dict__
                    yield f"data: {json.dumps(item)}\n\n"
                else:
                    # Plain token — escape newlines so SSE framing stays intact
                    token = str(item).replace("\n", "\\n")
                    yield f"data: {token}\n\n"
            yield "data: [DONE]\n\n"
        except RuntimeError as e:
            logger.error(f"Streaming query error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )
