"""
RAPID FastAPI backend — replaces app.py (Streamlit).

Startup:
    uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Environment (from .env):
    RAPID_LLM_PROVIDER     openai | anthropic | ollama | openrouter | lm_studio
    RAPID_MAIN_MODEL       e.g. gpt-4o-mini
    RAPID_MAIN_API_KEY     API key (or OPENAI_API_KEY / ANTHROPIC_API_KEY)
    RAPID_EMBED_PROVIDER   openai | ollama
    RAPID_WEB_ENABLED      true | false
    RAPID_EVALUATOR_PROVIDER / RAPID_EVALUATOR_MODEL / RAPID_EVALUATOR_API_KEY
    RAPID_JWT_SECRET       (set to a random 32-byte value in production!)
    RAPID_USERS            alice:admin:password,bob:employee:pass123
    RAPID_USERNAME / RAPID_PASSWORD  (single-user fallback)
"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.routing import APIRoute

from dotenv import load_dotenv
load_dotenv()

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Agent factory ──────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the singleton MasterAgent once at startup."""
    from rapid.factory import build_agent
    from api.dependencies import set_agent

    provider   = os.getenv("RAPID_LLM_PROVIDER",  os.getenv("RAPID_MAIN_PROVIDER", "openai"))
    model      = os.getenv("RAPID_MAIN_MODEL",     "gpt-4o-mini")
    api_key    = (
        os.getenv("RAPID_MAIN_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("GROQ_API_KEY")
        or ""
    )
    embed_prov = os.getenv("RAPID_EMBED_PROVIDER", "openai")
    web_ok     = os.getenv("RAPID_WEB_ENABLED", "true").lower() in ("1", "true", "yes")

    eval_prov  = os.getenv("RAPID_EVALUATOR_PROVIDER")
    eval_model = os.getenv("RAPID_EVALUATOR_MODEL")
    eval_key   = os.getenv("RAPID_EVALUATOR_API_KEY")

    logger.info(f"Initializing RAPID agent: {provider}/{model} | embed={embed_prov} | web={web_ok}")

    agent = build_agent(
        llm_provider=provider,
        llm_model=model,
        api_key=api_key,
        embed_provider=embed_prov,
        web_enabled=web_ok,
        evaluator_provider=eval_prov or None,
        evaluator_model=eval_model or None,
        evaluator_api_key=eval_key or None,
    )
    set_agent(agent)
    logger.info("RAPID agent initialized successfully")

    yield  # application runs here

    logger.info("RAPID shutting down")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RAPID API",
    description="RAG Application for Private Instant Deployment — enterprise RAG with RBAC and data firewall",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS (allow Flutter web app from any origin in dev; lock down in prod) ────
CORS_ORIGINS = os.getenv("RAPID_CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


# ── Auth route (outside prefix so OAuth2PasswordRequestForm works with Bearer) ─
from api.auth import login
from fastapi import Depends
from fastapi.security import OAuth2PasswordRequestForm

@app.post("/api/v1/auth/login", tags=["auth"])
async def auth_login(form_data: OAuth2PasswordRequestForm = Depends()):
    return await login(form_data)


# ── Routers ────────────────────────────────────────────────────────────────────
from api.routers import query, documents, projects, audit, health, llm

app.include_router(query.router)
app.include_router(documents.router)
app.include_router(projects.router)
app.include_router(audit.router)
app.include_router(health.router)
app.include_router(llm.router)


# ── Root redirect ──────────────────────────────────────────────────────────────
@app.get("/", include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/api/docs")
