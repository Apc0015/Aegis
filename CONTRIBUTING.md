# Contributing to Aegis

Thank you for your interest in contributing. This document covers how to set up a development environment, the project conventions, and how to submit changes.

---

## Development Setup

```bash
git clone https://github.com/Apc0015/Aegis.git
cd Aegis

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — set at least AEGIS_LLM_PROVIDER, AEGIS_MAIN_API_KEY, AEGIS_JWT_SECRET
```

Run the backend in reload mode:

```bash
uvicorn api.main:app --reload
```

Run the web console:

```bash
cd aegis_web
npm install
npm run dev
```

---

## Project Layout

| Path | What lives here |
|---|---|
| `api/` | FastAPI routes, auth, DI |
| `src/aegis/agents/` | R1–R4 pipeline agents |
| `src/aegis/core/` | Orchestration (MasterAgent, DB pipeline, memory) |
| `src/aegis/services/` | LLM, embedding, vector store, BM25 abstractions |
| `src/aegis/rbac/` | Access enforcement and audit logging |
| `src/aegis/connectors/` | External source connectors |
| `aegis_web/src/features/` | React feature modules |
| `config/` | RBAC rules and connector config |
| `tests/` | Unit and integration tests |

---

## Code Conventions

### Python
- **Style**: follow existing code style (no strict linter enforced, but keep it readable)
- **Type hints**: use them on function signatures
- **Comments**: only when the *why* is non-obvious — don't describe what the code does
- **No docstrings** on trivial functions; keep existing multi-line docstrings on public interfaces

### TypeScript / React
- Follow the existing code style (`npm run lint` runs `tsc --noEmit`)
- State via TanStack Query for server state; local component state via hooks
- Use `react-router-dom` for navigation

---

## Testing

Run tests before submitting a PR:

```bash
pytest tests/unit/           # always required
pytest tests/integration/    # run if your change touches retrieval, DB, or LLM paths
```

Integration tests require a running database and a valid LLM provider configured in `.env`.

---

## Submitting Changes

1. Fork the repo and create a branch: `git checkout -b feat/my-feature`
2. Make your changes and add or update tests where appropriate
3. Run `pytest tests/unit/` and confirm it passes
4. Open a pull request against `main` with a clear description of what changed and why

---

## Adding a New LLM Provider

1. Add a new branch in `src/aegis/services/llm_service.py` (follow the existing OpenAI/Anthropic pattern)
2. Add the provider name to the `SUPPORTED_LLM_PROVIDERS` list in `src/aegis/config.py`
3. Document the required env var in `.env.example`
4. Add a brief entry to the LLM Provider table in `README.md`

## Adding a New Connector

1. Create `src/aegis/connectors/<name>_connector.py` implementing the `BaseConnector` interface (`src/aegis/connectors/base.py`)
2. Register it in `src/aegis/connectors/connector_manager.py`
3. Add credentials to `.env.example` and the connector table in `README.md`
