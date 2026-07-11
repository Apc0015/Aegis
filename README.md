# Aegis — Enterprise RAG with a Data Firewall

**Aegis** is an enterprise-grade Retrieval-Augmented Generation (RAG) system built for regulated industries. It combines semantic document search, structured database querying, role-based access control, and a compliance-first data firewall — all exposed through a real-time React web console and a clean FastAPI backend.

---

## Features

- **Hybrid RAG Pipeline** — FAISS vector search + BM25 keyword search with optional semantic reranking
- **Database Query Agent** — Auto-generates SQL with row-level and column-level filtering enforced by RBAC
- **R1–R4 Agent Architecture** — Classify → Rewrite → Retrieve → Summarize modular pipeline
- **Multi-LLM Support** — OpenAI, Anthropic, Groq, OpenRouter, Google Gemini, Ollama, LM Studio
- **Data Firewall** — Blocks columns, anonymizes PII, enforces access rules *before* the LLM sees any data
- **Role-Based Access Control** — `employee / manager / admin` roles with document-category and column-level rules
- **Confidence Scoring** — Multi-model evaluation (faithfulness, relevance, completeness) with routing: direct → disclaimer → web fallback → refuse
- **Real-Time Streaming** — SSE token-by-token streaming to the web UI
- **External Connectors** — Gmail, Google Drive, OneDrive, SharePoint, Slack, local disk (with delta tracking)
- **Full Audit Trail** — Every query, access decision, and denial is logged with latency and exported to CSV
- **Multi-Turn Memory** — Per-user conversation context persisted across sessions
- **React Web Console** — Responsive chat, document manager, audit viewer, admin panel

---

## Architecture

```
User Query (Web console)
        │
        ▼
  FastAPI + JWT Auth
        │
   ┌────▼─────┐
   │   RBAC   │ ──→ Deny (audited)
   └────┬─────┘
        │ Allow
   ┌────▼──────────────────────────┐
   │  MasterAgent orchestration    │
   │                               │
   │  Intent Detect                │
   │       ↓                       │
   │  R1 Classify (domain)         │
   │       ↓                       │
   │  R2 Rewrite (query expansion) │
   │       ↓                       │
   │  ┌──────────┬──────────┐      │
   │  │ RAG Path │  DB Path │      │
   │  │ FAISS+   │ SQL gen  │      │
   │  │ BM25     │ + filter │      │
   │  └────┬─────┴─────┬────┘      │
   │       └─────┬─────┘           │
   │        Data Firewall          │
   │             ↓                 │
   │    R4 Summarize (LLM)         │
   │             ↓                 │
   │   Confidence Score            │
   │             ↓                 │
   │   Route: Direct / Disclaimer  │
   │          / Web / Refuse       │
   └───────────────────────────────┘
        │
   Audit Log
        │
        ▼
  SSE Response → Web console
  (answer, sources, confidence, routing path)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.111+, Python 3.10+ |
| Vector Search | FAISS (cpu), sentence-transformers |
| Keyword Search | BM25 (rank-bm25, bm25s) |
| LLMs | OpenAI, Anthropic, Groq, OpenRouter, Gemini, Ollama, LM Studio |
| Embeddings | OpenAI `text-embedding-3-small`, local `all-MiniLM-L6-v2`, Ollama |
| Database | SQLite (default), PostgreSQL, MySQL |
| Auth | JWT (python-jose), bcrypt |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |
| Document I/O | pypdf, python-docx, pdfplumber, openpyxl |

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Apc0015/Aegis.git
cd Aegis

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env` — at minimum set:

```env
AEGIS_LLM_PROVIDER=openrouter          # or openai | anthropic | ollama | groq | google | lm_studio
AEGIS_MAIN_MODEL=meta-llama/llama-3.3-70b-instruct:free
AEGIS_MAIN_API_KEY=your-api-key-here

AEGIS_EMBED_PROVIDER=local             # no key needed — uses sentence-transformers

AEGIS_JWT_SECRET=replace-with-32-char-random-string
AEGIS_USERS=admin:admin:admin123,alice:manager:alice123,bob:employee:bob123
```

### 3. Seed the Demo Database (optional)

```bash
python scripts/seed_medical_database.py
```

This creates `data/medical_company.db` — a 500-employee medical company with HR, finance, clinical, and compliance data.

### 4. Index Documents

```bash
python scripts/index_knowledge_base.py
```

This builds FAISS and BM25 indexes from the `documents/` folder. Add your own files to any subfolder and re-run.

### 5. Start the Backend

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)

### 6. Run the Web Console

```bash
cd aegis_web
npm install
npm run dev
```

Log in with any user from `AEGIS_USERS` (e.g. `admin` / `admin123`).

---

## LLM Provider Setup

### Free / No-Key Options

| Provider | Setup |
|---|---|
| **Ollama** (local) | Install [ollama.com](https://ollama.com), run `ollama pull llama3`, set `AEGIS_LLM_PROVIDER=ollama` |
| **LM Studio** (local) | Start LM Studio server on `localhost:1234`, set `AEGIS_LLM_PROVIDER=lm_studio` |
| **OpenRouter** (free tier) | Get a free key at [openrouter.ai](https://openrouter.ai), use free models like `meta-llama/llama-3.3-70b-instruct:free` |

### Cloud Providers

Set `AEGIS_LLM_PROVIDER` and add the corresponding key:

```env
# OpenAI
AEGIS_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...

# Anthropic
AEGIS_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Groq (fast, free tier available)
AEGIS_LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

# Google Gemini
AEGIS_LLM_PROVIDER=google
AEGIS_MAIN_API_KEY=AIza...
AEGIS_MAIN_MODEL=gemini-1.5-flash
```

---

## Project Structure

```
aegis/
├── api/                    # FastAPI application
│   ├── main.py             # Entry point
│   ├── auth.py             # JWT auth
│   ├── dependencies.py     # DI (agent, stores)
│   └── routers/            # Route handlers (query, documents, projects, audit, admin, health)
│
├── src/aegis/              # Core RAG engine
│   ├── core/
│   │   ├── master_agent.py         # End-to-end orchestration
│   │   ├── db_pipeline.py          # Database retrieval with RBAC
│   │   ├── conversation_store.py   # Multi-turn memory
│   │   └── department_router.py    # Dept-based routing
│   ├── agents/
│   │   ├── r1_classifier.py        # Domain classification
│   │   ├── r2_rewriter.py          # Query expansion
│   │   ├── r3_retriever.py         # Hybrid FAISS + BM25 retrieval
│   │   ├── r4_summarizer.py        # LLM generation + firewall
│   │   ├── confidence_scorer.py    # Multi-model evaluation
│   │   ├── intent_detector.py      # Query intent classification
│   │   └── web_agent.py            # DuckDuckGo fallback
│   ├── rbac/
│   │   ├── rbac_module.py          # Access enforcement
│   │   └── audit_log.py            # Audit trail
│   ├── services/
│   │   ├── llm_service.py          # Multi-provider LLM abstraction
│   │   ├── embedding_service.py    # Embedding abstraction
│   │   ├── vector_store_service.py # FAISS management
│   │   ├── bm25_engine.py          # BM25 search
│   │   └── document_processor.py  # PDF/DOCX/XLSX extraction
│   └── connectors/
│       ├── gmail_connector.py
│       ├── gdrive_connector.py
│       ├── onedrive_connector.py
│       ├── sharepoint_connector.py
│       └── slack_connector.py
│
├── aegis_web/              # React web frontend
├── config/
│   ├── access_rules.yaml   # RBAC role definitions
│   └── connectors.yaml     # Connector credentials
├── documents/              # Source documents (organized by dept)
├── data/                   # Runtime data (indexes, databases, memory)
├── scripts/                # Setup & seeding utilities
├── sql/                    # Database schemas
└── tests/                  # Unit + integration tests
```

---

## Access Control

RBAC rules live in [`config/access_rules.yaml`](config/access_rules.yaml). Each role specifies:

- **document_categories** — which document types the role can read
- **departments** — which organizational departments are accessible
- **database_rules** — per-table column allow/block/anonymize lists

Example (employee role):
```yaml
employee:
  document_categories:
    allow: [policies, handbook, onboarding, compliance]
  database_rules:
    employees:
      allow: [employee_id, name, department_id, job_title]
      block: [salary, ssn]
    payroll:
      allow: [payment_date, method, status]
      block: [gross_pay, net_pay, tax_withheld]
    patient_pii:
      block: all
```

---

## API Reference

Interactive API docs are available at `/api/docs` (Swagger UI) when the server is running.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Submit a query (batch response) |
| `GET` | `/api/v1/query/stream` | Submit a query (SSE streaming) |
| `POST` | `/api/v1/query/with-file` | Query with an attached file |
| `GET` | `/api/v1/documents` | List indexed documents |
| `POST` | `/api/v1/documents/upload` | Upload and index a document |
| `DELETE` | `/api/v1/documents/{id}` | Remove a document |
| `GET` | `/api/v1/projects` | List RAG projects (FAISS collections) |
| `POST` | `/api/v1/projects` | Create a new project |
| `GET` | `/api/v1/audit` | Paginated audit log |
| `POST` | `/api/v1/audit/export` | Export audit log as CSV |
| `GET` | `/api/v1/admin/users` | List users (admin only) |
| `GET` | `/api/v1/health` | Health check |

---

## Running Tests

```bash
pytest tests/unit/          # Unit tests (no external dependencies)
pytest tests/integration/   # Integration tests (requires live DB / LLM)
pytest                      # All tests
```

---

## External Connectors

Configure connectors in `config/connectors.yaml` and set credentials in `.env`:

| Connector | Required Env Vars |
|---|---|
| Gmail | `AEGIS_GOOGLE_CLIENT_ID`, `AEGIS_GOOGLE_CLIENT_SECRET` |
| Google Drive | `AEGIS_GOOGLE_CLIENT_ID`, `AEGIS_GOOGLE_CLIENT_SECRET` |
| OneDrive | `AEGIS_MICROSOFT_CLIENT_ID`, `AEGIS_MICROSOFT_TENANT_ID` |
| SharePoint | `AEGIS_MICROSOFT_CLIENT_ID`, `AEGIS_MICROSOFT_TENANT_ID` |
| Slack | `AEGIS_SLACK_BOT_TOKEN` |
| Local Disk | Path configured in `connectors.yaml` (no auth needed) |

Connectors use delta tracking — only new or changed files are re-indexed on each sync.

---

## License

MIT — see [LICENSE](LICENSE).
