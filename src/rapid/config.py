from dataclasses import dataclass, field
from typing import Dict, Any

# ── Confidence thresholds ────────────────────────────────────────────────────
CONFIDENCE_HIGH   = 0.65
CONFIDENCE_MEDIUM = 0.40

# ── Confidence scoring weights ───────────────────────────────────────────────
WEIGHT_RELEVANCE    = 0.30
WEIGHT_FAITHFULNESS = 0.50
WEIGHT_COMPLETENESS = 0.20

# ── LLM providers ────────────────────────────────────────────────────────────
LLM_PROVIDERS = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "default_model": "gpt-4o-mini",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"],
    },
    "anthropic": {
        "base_url": None,   # uses anthropic SDK directly
        "requires_key": True,
        "default_model": "claude-3-5-haiku-20241022",
        "models": ["claude-opus-4-5", "claude-sonnet-4-5", "claude-3-5-haiku-20241022"],
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "requires_key": False,
        "default_model": "llama3.2",
        "models": ["llama3.2", "llama3.1", "mistral", "qwen2.5"],
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "requires_key": True,
        "default_model": "meta-llama/llama-3.1-8b-instruct:free",
        "models": ["meta-llama/llama-3.1-8b-instruct:free",
                   "google/gemma-2-9b-it:free",
                   "mistralai/mistral-7b-instruct:free"],
    },
    "lm_studio": {
        "base_url": "http://localhost:1234/v1",
        "requires_key": False,
        "default_model": "local-model",
        "models": ["local-model"],
    },
}

# ── Embedding providers ───────────────────────────────────────────────────────
EMBEDDING_PROVIDERS = {
    "openai": {
        "model": "text-embedding-3-small",
        "dimensions": 1536,
        "requires_key": True,
    },
    "ollama": {
        "model": "nomic-embed-text",
        "dimensions": 768,
        "requires_key": False,
    },
    "local": {
        "model": "all-MiniLM-L6-v2",
        "dimensions": 384,
        "requires_key": False,
    },
}

# ── RAG domain presets ────────────────────────────────────────────────────────
RAG_MODES: Dict[str, Dict[str, Any]] = {
    "general": {
        "label": "General / Mixed",
        "icon": "📄",
        "chunk_size": 512,
        "chunk_overlap": 77,
        "vector_weight": 0.60,
        "bm25_weight": 0.40,
        "top_k": 5,
        "confidence_high": 0.65,
        "confidence_medium": 0.40,
        "web_fallback": True,
    },
    "hr": {
        "label": "HR / Policy",
        "icon": "🗂️",
        "chunk_size": 512,
        "chunk_overlap": 77,
        "vector_weight": 0.50,
        "bm25_weight": 0.50,
        "top_k": 5,
        "confidence_high": 0.65,
        "confidence_medium": 0.40,
        "web_fallback": True,
    },
    "legal": {
        "label": "Legal",
        "icon": "⚖️",
        "chunk_size": 1024,
        "chunk_overlap": 154,
        "vector_weight": 0.65,
        "bm25_weight": 0.35,
        "top_k": 3,
        "confidence_high": 0.75,
        "confidence_medium": 0.55,
        "web_fallback": False,
    },
    "financial": {
        "label": "Financial",
        "icon": "💰",
        "chunk_size": 1024,
        "chunk_overlap": 154,
        "vector_weight": 0.35,
        "bm25_weight": 0.65,
        "top_k": 5,
        "confidence_high": 0.80,
        "confidence_medium": 0.60,
        "web_fallback": False,
    },
    "technical": {
        "label": "Technical",
        "icon": "🔧",
        "chunk_size": 512,
        "chunk_overlap": 77,
        "vector_weight": 0.30,
        "bm25_weight": 0.70,
        "top_k": 7,
        "confidence_high": 0.65,
        "confidence_medium": 0.45,
        "web_fallback": True,
    },
    "medical": {
        "label": "Medical",
        "icon": "🏥",
        "chunk_size": 512,
        "chunk_overlap": 77,
        "vector_weight": 0.55,
        "bm25_weight": 0.45,
        "top_k": 5,
        "confidence_high": 0.85,
        "confidence_medium": 0.65,
        "web_fallback": False,
    },
    "research": {
        "label": "Research",
        "icon": "🔬",
        "chunk_size": 768,
        "chunk_overlap": 115,
        "vector_weight": 0.75,
        "bm25_weight": 0.25,
        "top_k": 5,
        "confidence_high": 0.70,
        "confidence_medium": 0.50,
        "web_fallback": True,
    },
    "compliance": {
        "label": "Compliance / Regulatory",
        "icon": "📋",
        "chunk_size": 1024,
        "chunk_overlap": 154,
        "vector_weight": 0.55,
        "bm25_weight": 0.45,
        "top_k": 5,
        "confidence_high": 0.80,
        "confidence_medium": 0.60,
        "web_fallback": False,
    },
    "contracts": {
        "label": "Contracts",
        "icon": "📝",
        "chunk_size": 1024,
        "chunk_overlap": 154,
        "vector_weight": 0.45,
        "bm25_weight": 0.55,
        "top_k": 5,
        "confidence_high": 0.75,
        "confidence_medium": 0.55,
        "web_fallback": False,
    },
    "operations": {
        "label": "Operations / SOPs",
        "icon": "⚙️",
        "chunk_size": 512,
        "chunk_overlap": 77,
        "vector_weight": 0.50,
        "bm25_weight": 0.50,
        "top_k": 7,
        "confidence_high": 0.65,
        "confidence_medium": 0.40,
        "web_fallback": True,
    },
}

# ── RBAC role definitions ─────────────────────────────────────────────────────
RBAC_ROLES = {
    "admin": {
        "label": "Administrator",
        "departments": ["hr", "finance", "legal", "technical", "medical", "research", "general"],
        "can_delete_docs": True,
        "can_export_audit": True,
        "can_manage_users": True,
    },
    "manager": {
        "label": "Manager",
        "departments": ["hr", "general"],
        "can_delete_docs": False,
        "can_export_audit": False,
        "can_manage_users": False,
    },
    "employee": {
        "label": "Employee",
        "departments": ["hr", "general"],
        "can_delete_docs": False,
        "can_export_audit": False,
        "can_manage_users": False,
    },
}

# ── Document type detection keywords (R1 classifier) ─────────────────────────
DOC_TYPE_KEYWORDS = {
    "legal": ["agreement", "contract", "clause", "whereas", "indemnify",
              "jurisdiction", "liability", "plaintiff", "defendant", "arbitration"],
    "financial": ["revenue", "ebitda", "quarterly", "fiscal", "balance sheet",
                  "cash flow", "income statement", "expense", "budget", "profit"],
    "medical": ["patient", "diagnosis", "treatment", "clinical", "dosage",
                "prescription", "symptom", "physician", "hipaa", "healthcare"],
    "hr": ["employee", "leave", "policy", "benefits", "onboarding", "handbook",
           "remote work", "vacation", "performance review", "compensation"],
    "technical": ["api", "endpoint", "deployment", "architecture", "database",
                  "microservice", "docker", "kubernetes", "pipeline", "schema"],
    "research": ["hypothesis", "methodology", "findings", "abstract", "literature",
                 "peer review", "citations", "experiment", "analysis", "dataset"],
    "compliance": ["regulation", "compliance", "audit", "sox", "gdpr", "requirement",
                   "violation", "penalty", "standard", "regulatory"],
    "contracts": ["contract", "party", "obligation", "term", "breach", "execution",
                  "amendment", "covenant", "consideration", "binding"],
    "operations": ["procedure", "workflow", "sop", "runbook", "checklist",
                   "maintenance", "incident", "escalation", "handoff", "process"],
}

# ── Audit log SQLite path ─────────────────────────────────────────────────────
AUDIT_DB_PATH = "data/audit.db"

# ── Internal query signals (for web fallback gating) ─────────────────────────
INTERNAL_QUERY_SIGNALS = [
    "our", "company", "organization", "hr", "policy", "employee",
    "team", "department", "office", "manager", "we", "internal",
]

# ── App settings ──────────────────────────────────────────────────────────────
APP_TITLE = "RAPID"
APP_SUBTITLE = "RAG Application for Private Instant Deployment"
APP_VERSION = "1.0.0"
MAX_FILE_SIZE_MB = 50
SUPPORTED_FILE_TYPES = ["pdf", "docx", "txt", "md"]
MAX_CHUNKS_PER_QUERY = 4
CHUNK_K_CONSTANT = 60  # RRF formula constant
