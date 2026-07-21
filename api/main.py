"""
Aegis FastAPI backend.

Startup:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Environment (from .env):
    AEGIS_LLM_PROVIDER     openai | anthropic | ollama | openrouter | lm_studio
    AEGIS_MAIN_MODEL       e.g. gpt-4o-mini
    AEGIS_MAIN_API_KEY     API key (or OPENAI_API_KEY / ANTHROPIC_API_KEY)
    AEGIS_EMBED_PROVIDER   openai | ollama
    AEGIS_WEB_ENABLED      true | false
    AEGIS_EVALUATOR_PROVIDER / AEGIS_EVALUATOR_MODEL / AEGIS_EVALUATOR_API_KEY
    AEGIS_JWT_SECRET       (set to a random 32-byte value in production!)
    AEGIS_USERS            alice:admin:password,bob:employee:pass123:EMP0042
                           (optional 4th field = HR employee_id for row-level security)
    AEGIS_USERNAME / AEGIS_PASSWORD  (single-user fallback)
    AEGIS_CORS_ORIGINS     comma-separated allowed origins (default: allow all localhost in dev)
    AEGIS_ENV              production | development (default: development)
"""
import os
import logging
import traceback
import uuid as _uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dotenv import load_dotenv
load_dotenv()

_log_level = os.getenv("AEGIS_LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, _log_level, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

IS_PRODUCTION = os.getenv("AEGIS_ENV", "development").lower() == "production"


def _api_key_for(provider: str, explicit_env: str = "") -> str:
    """Return the best API key for a provider without mixing providers accidentally."""
    if explicit_env:
        key = os.getenv(explicit_env)
        if key:
            return key

    provider_env = {
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "groq": "GROQ_API_KEY",
        "google": "GOOGLE_API_KEY",
        "azure": "AZURE_OPENAI_API_KEY",
        "cohere": "COHERE_API_KEY",
    }.get(provider)
    return os.getenv(provider_env, "") if provider_env else ""


def _run_startup_checks(provider: str, api_key: str, embed_prov: str) -> None:
    """Warn loudly (but don't crash) about missing config at startup."""
    warnings = []

    # API key check for providers that require one
    key_required = provider not in ("ollama", "lm_studio", "local")
    if key_required and not api_key:
        warnings.append(
            f"No API key found for LLM provider '{provider}'. "
            "Set AEGIS_MAIN_API_KEY (or the provider-specific env var)."
        )

    embed_key_required = embed_prov not in ("ollama", "local")
    embed_key = _api_key_for(embed_prov, "AEGIS_EMBED_API_KEY")
    if embed_key_required and not embed_key:
        warnings.append(
            f"No API key found for embedding provider '{embed_prov}'. "
            "Set AEGIS_EMBED_API_KEY (or OPENAI_API_KEY for openai)."
        )

    # FAISS data directory
    faiss_dir = Path("data/faiss")
    if not any(faiss_dir.glob("*.index")):
        warnings.append(
            "No FAISS indexes found in data/faiss/. "
            "Run: python scripts/index_knowledge_base.py"
        )

    # JWT secret in production
    jwt_secret = os.getenv("AEGIS_JWT_SECRET", "")
    if IS_PRODUCTION and (not jwt_secret or len(jwt_secret) < 32):
        warnings.append(
            "AEGIS_JWT_SECRET is not set or too short for production. "
            "Set it to a random 32+ byte value."
        )

    for w in warnings:
        logger.warning(f"[STARTUP] {w}")


def _cleanup_orphaned_session_indexes() -> None:
    """
    Delete leftover per-session file indexes from previous runs.

    Session indexes are registered only in memory (SessionFileStore); after a
    restart nothing remembers them, so their FAISS/BM25 files would accumulate
    on disk forever. They are ephemeral by definition — safe to remove at boot.
    """
    removed = 0
    for pattern, base in (("aegis__session_*", Path("data/faiss")), ("_session_*", Path("data/bm25"))):
        if not base.exists():
            continue
        for p in base.glob(pattern):
            try:
                p.unlink()
                removed += 1
            except OSError as e:
                logger.warning(f"[STARTUP] could not remove orphaned session index {p}: {e}")
    if removed:
        logger.info(f"[STARTUP] removed {removed} orphaned session index file(s)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the singleton MasterAgent once at startup."""
    from aegis.factory import build_agent
    from api.dependencies import set_agent

    _cleanup_orphaned_session_indexes()

    provider   = os.getenv("AEGIS_LLM_PROVIDER",  os.getenv("AEGIS_MAIN_PROVIDER", "openai"))
    model      = os.getenv("AEGIS_MAIN_MODEL",     "gpt-4o-mini")
    api_key    = _api_key_for(provider, "AEGIS_MAIN_API_KEY")
    embed_prov = os.getenv("AEGIS_EMBED_PROVIDER", "openai")
    embed_key  = _api_key_for(embed_prov, "AEGIS_EMBED_API_KEY")
    web_ok     = os.getenv("AEGIS_WEB_ENABLED", "true").lower() in ("1", "true", "yes")

    eval_prov  = os.getenv("AEGIS_EVALUATOR_PROVIDER")
    eval_model = os.getenv("AEGIS_EVALUATOR_MODEL")
    eval_key   = _api_key_for(eval_prov or "", "AEGIS_EVALUATOR_API_KEY")

    _run_startup_checks(provider, api_key, embed_prov)

    logger.info(f"Initializing Aegis agent: {provider}/{model} | embed={embed_prov} | web={web_ok}")

    agent = build_agent(
        llm_provider=provider,
        llm_model=model,
        api_key=api_key,
        embed_provider=embed_prov,
        embed_api_key=embed_key,
        web_enabled=web_ok,
        evaluator_provider=eval_prov or None,
        evaluator_model=eval_model or None,
        evaluator_api_key=eval_key or None,
    )
    set_agent(agent)
    logger.info("Aegis agent initialized successfully")

    from aegis.connectors.connector_manager import ConnectorManager
    from api.routers.documents import _ingest_file
    from api.dependencies import set_connector_manager

    async def _connector_ingest(data: bytes, filename: str, project_id: str) -> None:
        # Pass the department id straight through — _ingest_file maps department
        # names to their RAG mode (e.g. finance → financial) and falls back to
        # general for unknown projects.
        await _ingest_file(data, filename, project_id, project_id, agent)

    connector_mgr = ConnectorManager(ingest_fn=_connector_ingest)
    set_connector_manager(connector_mgr)
    await connector_mgr.start()
    logger.info("Aegis connector manager started")

    yield  # application runs here

    await connector_mgr.stop()
    logger.info("Aegis shutting down")


app = FastAPI(
    title="Aegis API",
    description="Governed enterprise RAG — ask your company's data, see only what you're allowed to. Role-based access control and a data firewall on every answer.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

_cors_env = os.getenv("AEGIS_CORS_ORIGINS")
if _cors_env:
    # Explicit list — used in production
    CORS_ORIGINS = [o.strip() for o in _cors_env.split(",") if o.strip()]
    CORS_REGEX = None
elif IS_PRODUCTION:
    # Production with no config: block cross-origin by default
    CORS_ORIGINS = []
    CORS_REGEX = None
    logger.warning("[STARTUP] AEGIS_CORS_ORIGINS not set in production — cross-origin requests blocked")
else:
    # Development: allow all localhost / 127.0.0.1 origins automatically
    CORS_ORIGINS = []
    CORS_REGEX = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=CORS_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = str(_uuid.uuid4())[:8]
    logger.error(
        f"Unhandled exception [{request_id}] {request.method} {request.url}: "
        f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"
    )
    # Fail closed: only expose internal error details when AEGIS_ENV is EXPLICITLY
    # set to "development". If the env var is unset/misconfigured (e.g. a prod deploy
    # that forgot AEGIS_ENV=production), default to the generic message rather than
    # leaking exception text and stack details to clients.
    _verbose_errors = os.getenv("AEGIS_ENV", "").lower() == "development"
    detail = (
        f"{type(exc).__name__}: {exc} [{request_id}]"
        if _verbose_errors
        else f"Internal server error [{request_id}]"
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": detail, "request_id": request_id},
    )


from api.auth import login
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

@app.post("/api/v1/auth/login", tags=["auth"])
async def auth_login(form_data: OAuth2PasswordRequestForm = Depends()):
    return await login(form_data)


from api.routers import query, documents, projects, audit, health, llm, connectors
from api.routers.admin import router as admin_router

app.include_router(query.router)
app.include_router(documents.router)
app.include_router(projects.router)
app.include_router(audit.router)
app.include_router(health.router)
app.include_router(llm.router)
app.include_router(connectors.router)
app.include_router(admin_router)


@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")
