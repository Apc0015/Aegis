# Aegis

### Ask your company's data. See only what you're allowed to.

**Aegis** is governed enterprise RAG. Any employee asks a question in plain English
about company documents or connected tools; role-based access control blocks or
anonymizes anything they're not permitted to see **before the LLM ever sees it**;
and every access decision is logged.

Connect your sources once (Drive, Slack, Gmail, SharePoint, OneDrive, an internal
database). Employees ask questions through the console. RBAC + column/row rules +
confidence-gated routing (direct answer / disclaimer / web fallback / refuse)
guarantee nobody sees what they're not cleared for. It's the safe internal
alternative to pasting company data into a public chatbot — built for
security-conscious and regulated organizations (healthcare, finance, legal).

> **New here?** Read [`ARCHITECTURE.md`](ARCHITECTURE.md) for how the governance
> model works in plain language.

---

## Why Aegis

Most "chat with your data" tools bolt access control on *after* the model has
already read everything. Aegis inverts that: the **data firewall** runs at the
retrieval layer, so the language model is only ever handed rows and documents the
asker is cleared for. Three guarantees:

- **Fail-closed by default** — an unknown role, a malformed rule, or an ambiguous
  JOIN results in *less* access, never more.
- **Deterministic security path** — routing and access decisions are keyword- and
  rule-based. No LLM sits in the security-relevant path.
- **Everything audited** — every query, allow, anonymize, and denial is logged
  with latency and exportable to CSV.

---

## Features

- **Hybrid RAG pipeline** — FAISS vector search + BM25 keyword search with optional reranking
- **Data firewall** — blocks columns, anonymizes PII, and enforces access rules *before* the LLM sees any data
- **Role-based access control** — `employee / manager / admin` with document-category, row-level, and column-level rules
- **Database query agent** — auto-generates read-only SQL with row- and column-level filtering enforced by RBAC
- **R1–R4 agent pipeline** — Classify → Rewrite → Retrieve → Summarize
- **Confidence-gated routing** — faithfulness/relevance/completeness scoring routes each answer: direct → disclaimer → web fallback → refuse
- **External connectors** — Gmail, Google Drive, OneDrive, SharePoint, Slack, local disk (with delta tracking)
- **Full audit trail** — every access decision logged and exportable
- **Multi-LLM support** — OpenAI, Anthropic, Groq, OpenRouter, Google Gemini, Ollama, LM Studio
- **React web console** — chat, document manager, audit viewer, admin panel, real-time SSE streaming

---

## Sample data

Aegis ships with a **bundled sample dataset** so you can evaluate the firewall
immediately: a fictional 500-employee healthcare company with employees, payroll,
patients, `patient_pii`, `medical_records`, and `hipaa_access_logs`. It is the
clearest possible demonstration of governance — ask for a patient's SSN as an
employee and watch it get blocked; ask as an admin and it comes through.

**None of it is real.** No real people or PHI are included. The console shows a
"sample data" notice while `AEGIS_DEMO_MODE=true`. When you connect your own
sources, set `AEGIS_DEMO_MODE=false` and the notice disappears.

---

## Quick start (Docker)

The fastest way to stand up the full stack (API + web console):

```bash
git clone https://github.com/Apc0015/Aegis.git
cd Aegis
cp .env.example .env          # add your LLM API key (or use a local Ollama/LM Studio)
docker compose up --build
```

- Web console → http://localhost:8080
- API docs → http://localhost:8000/api/docs

On first boot the API container seeds the sample database and builds document
indexes (this can take a few minutes — it also downloads the local embedding and
reranker models). Subsequent boots are fast; data persists in a named volume.

> Log in with any user from `AEGIS_USERS` in your `.env`
> (the example file ships with `admin / admin123`).

---

## Quick start (local / no Docker)

**Requirements:** Python 3.10+ and Node 18+.

### 1. Install

```bash
git clone https://github.com/Apc0015/Aegis.git
cd Aegis

python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e .                     # installs the `aegis` package (from src/)
```

> `pip install -e .` is required — the `aegis` package lives in `src/`, and
> without it `uvicorn api.main:app` fails with `No module named 'aegis'`.

### 2. Configure

```bash
cp .env.example .env
```

Minimum settings in `.env`:

```env
AEGIS_LLM_PROVIDER=openrouter          # or openai | anthropic | ollama | groq | google | lm_studio
AEGIS_MAIN_MODEL=meta-llama/llama-3.3-70b-instruct:free
AEGIS_MAIN_API_KEY=your-api-key-here   # or a provider-specific key like OPENROUTER_API_KEY

AEGIS_EMBED_PROVIDER=local             # no key needed — uses sentence-transformers

AEGIS_JWT_SECRET=replace-with-32-char-random-string
AEGIS_USERS=admin:admin:admin123,alice:manager:alice123:EMP0001,bob:employee:bob123:EMP0042
```

### 3. Seed the sample database (optional — bundled DB already included)

```bash
python scripts/seed_medical_database.py
```

### 4. Index documents

```bash
python scripts/index_knowledge_base.py --embed-provider local
```

Builds FAISS + BM25 indexes from `documents/`. Add your own files to any subfolder
and re-run.

### 5. Start the backend

```bash
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
```

API docs: http://localhost:8000/api/docs

### 6. Run the web console

```bash
cd aegis_web
npm install
npm run dev                           # proxies /api to http://localhost:8000
```

Log in with any user from `AEGIS_USERS` (e.g. `admin` / `admin123`).

---

## How governance works

```
User Query (Web console)
        │
        ▼
  FastAPI + JWT Auth
        │
   ┌────▼─────┐
   │   RBAC   │ ──→ Deny (audited)
   └────┬─────┘
        │ Allow (permitted departments only)
   ┌────▼──────────────────────────┐
   │  MasterAgent orchestration    │
   │  Intent → R1 classify →       │
   │  R2 rewrite →                 │
   │  ┌──────────┬──────────┐      │
   │  │ RAG path │  DB path │      │
   │  │ FAISS+   │ read-only│      │
   │  │ BM25     │ SQL+RBAC │      │
   │  └────┬─────┴─────┬────┘      │
   │       └─────┬─────┘           │
   │      Data Firewall            │  ← block / anonymize columns,
   │             ↓                 │    row-level ownership, JOIN-safe
   │    R4 Summarize (LLM)         │
   │             ↓                 │
   │   Confidence Score            │
   │             ↓                 │
   │  Route: Direct / Disclaimer   │
   │         / Web / Refuse        │
   └───────────────────────────────┘
        │
   Audit Log → SSE Response → Web console
```

The security-relevant path (RBAC, department routing, column/row rules) is
deterministic — no LLM decides who sees what. See [`ARCHITECTURE.md`](ARCHITECTURE.md)
for the full plain-language walkthrough.

---

## Access control

RBAC rules live in [`config/access_rules.yaml`](config/access_rules.yaml). Each
role defines the document categories it may read and per-table column rules
(`ALLOW` / `ANONYMIZE` / `BLOCK`). Anything unrecognized is treated as `BLOCK`.

Example (`employee` role — real excerpt):

```yaml
roles:
  employee:
    allowed_document_categories: [policies, handbook, onboarding, compliance]
    db_column_rules:
      payroll:
        payroll_id: ALLOW
        employee_id: ALLOW
        gross_salary: BLOCK
        net_pay: BLOCK
        payment_date: ALLOW
      patient_pii:
        ALL: BLOCK           # employees never see patient PII
      medical_records:
        diagnosis: ALLOW
        patient_id: BLOCK
        notes: BLOCK
```

- **Column rules** — `ALLOW` returns the value, `ANONYMIZE` masks it, `BLOCK`
  drops the column entirely. In a JOIN across multiple tables, the *strictest*
  rule for a column wins.
- **Row-level security** — employees see only their own records in personal
  tables; managers additionally see their reports'; admins see all. A row that
  can't prove ownership is dropped (fail-closed).
- **Department scoping** — a role can only retrieve from departments it's
  permitted (plus always-readable `general`). Unknown roles get nothing.

Role capabilities and department scoping live in `src/aegis/config.py`
(`RBAC_ROLES`).

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | FastAPI, Python 3.10+ |
| Vector search | FAISS (cpu), sentence-transformers |
| Keyword search | BM25 (rank-bm25, bm25s) |
| LLMs | OpenAI, Anthropic, Groq, OpenRouter, Gemini, Ollama, LM Studio |
| Embeddings | OpenAI `text-embedding-3-small`, local `all-MiniLM-L6-v2`, Ollama |
| Database | **SQLite (validated)** · PostgreSQL / MySQL (experimental) |
| Auth | JWT (PyJWT), bcrypt |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, TanStack Query |

> **Database support:** SQLite is the validated backend for v1 and backs the
> bundled sample data. It's opened read-only at the OS level (`mode=ro`), so a
> generated query can never write. PostgreSQL/MySQL wiring exists (read-only
> session enforced) but is **experimental** and not yet validated end-to-end.

---

## API reference

Interactive docs at `/api/docs` (Swagger UI) when the server is running.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/query` | Submit a query (batch response) |
| `GET` | `/api/v1/query/stream` | Submit a query (SSE streaming) |
| `POST` | `/api/v1/query/with-file` | Query with an attached file |
| `GET` | `/api/v1/documents` | List indexed documents |
| `POST` | `/api/v1/documents/upload` | Upload and index a document |
| `GET` | `/api/v1/audit` | Paginated audit log |
| `POST` | `/api/v1/audit/export` | Export audit log as CSV |
| `GET` | `/api/v1/admin/users` | List users (admin only) |
| `GET` | `/api/v1/health` | Health check (includes `demo_mode`) |

---

## External connectors

Configure connectors in `config/connectors.yaml` and set credentials in `.env`:

| Connector | Required env vars |
|---|---|
| Gmail | `AEGIS_GOOGLE_CLIENT_ID`, `AEGIS_GOOGLE_CLIENT_SECRET` |
| Google Drive | `AEGIS_GOOGLE_CLIENT_ID`, `AEGIS_GOOGLE_CLIENT_SECRET` |
| OneDrive | `AEGIS_MICROSOFT_CLIENT_ID`, `AEGIS_MICROSOFT_TENANT_ID` |
| SharePoint | `AEGIS_MICROSOFT_CLIENT_ID`, `AEGIS_MICROSOFT_TENANT_ID` |
| Slack | `AEGIS_SLACK_BOT_TOKEN` |
| Local disk | Path configured in `connectors.yaml` (no auth) |

Connectors use delta tracking — only new or changed files are re-indexed each sync.

---

## Running tests

```bash
pytest tests/unit/          # unit tests (no external dependencies)
pytest tests/integration/   # integration tests (requires live DB / LLM)
```

The RBAC / data-firewall suite (`tests/unit/test_rbac*.py`,
`tests/unit/test_security_fixes.py`) is a **CI gate** — see
[`.github/workflows/ci.yml`](.github/workflows/ci.yml). It pins the fail-closed
contract (unknown roles, malformed rules, JOIN column governance) and must stay
green.

---

## Project docs

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — the governance model in plain language
- [`DECISIONS.md`](DECISIONS.md) — what changed to productize Aegis, and why
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — development workflow

---

## License

MIT — see [LICENSE](LICENSE).
