#!/usr/bin/env bash
# Aegis API container entrypoint.
# Makes `docker compose up` self-sufficient: on first boot it seeds the bundled
# sample database and builds indexes if they don't already exist, then launches
# the API. On later boots (data persisted via volumes) it starts fast.
set -euo pipefail

DB_PATH="${AEGIS_DB_PATH:-data/medical_company.db}"
EMBED_PROVIDER="${AEGIS_EMBED_PROVIDER:-local}"

mkdir -p data/bm25 data/qdrant

# If using a Qdrant server, wait for it to accept connections before indexing.
if [ -n "${AEGIS_QDRANT_URL:-}" ]; then
  echo "[entrypoint] Waiting for Qdrant at $AEGIS_QDRANT_URL ..."
  for i in $(seq 1 60); do
    if curl -fsS "$AEGIS_QDRANT_URL/readyz" >/dev/null 2>&1 \
       || curl -fsS "$AEGIS_QDRANT_URL/healthz" >/dev/null 2>&1 \
       || curl -fsS "$AEGIS_QDRANT_URL" >/dev/null 2>&1; then
      echo "[entrypoint] Qdrant is up."
      break
    fi
    sleep 2
  done
fi

if [ ! -f "$DB_PATH" ]; then
  echo "[entrypoint] No database at $DB_PATH — seeding bundled sample dataset..."
  python scripts/seed_medical_database.py || echo "[entrypoint] WARN: seed step failed; continuing"
fi

# BM25 files are built alongside the Qdrant collections, so an empty data/bm25
# is our "not indexed yet" signal (works for both embedded and server Qdrant).
if [ -z "$(ls -A data/bm25 2>/dev/null || true)" ]; then
  echo "[entrypoint] No indexes found — indexing documents/ (provider=$EMBED_PROVIDER)..."
  python scripts/index_knowledge_base.py --embed-provider "$EMBED_PROVIDER" \
    || echo "[entrypoint] WARN: indexing step failed; continuing (document RAG will be empty)"
fi

echo "[entrypoint] Starting Aegis API on 0.0.0.0:8000"
exec uvicorn api.main:app --host 0.0.0.0 --port 8000
