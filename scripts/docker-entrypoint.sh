#!/usr/bin/env bash
# Aegis API container entrypoint.
# Makes `docker compose up` self-sufficient: on first boot it seeds the bundled
# sample database and builds document indexes if they don't already exist, then
# launches the API. On later boots (data persisted via volume) it starts fast.
set -euo pipefail

DB_PATH="${AEGIS_DB_PATH:-data/medical_company.db}"
EMBED_PROVIDER="${AEGIS_EMBED_PROVIDER:-local}"

mkdir -p data/faiss data/bm25

if [ ! -f "$DB_PATH" ]; then
  echo "[entrypoint] No database at $DB_PATH — seeding bundled sample dataset..."
  python scripts/seed_medical_database.py || echo "[entrypoint] WARN: seed step failed; continuing"
fi

if [ -z "$(ls -A data/faiss 2>/dev/null || true)" ]; then
  echo "[entrypoint] No FAISS indexes found — indexing documents/ (provider=$EMBED_PROVIDER)..."
  python scripts/index_knowledge_base.py --embed-provider "$EMBED_PROVIDER" \
    || echo "[entrypoint] WARN: indexing step failed; continuing (document RAG will be empty)"
fi

echo "[entrypoint] Starting Aegis API on 0.0.0.0:8000"
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
