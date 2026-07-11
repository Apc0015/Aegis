#!/usr/bin/env bash
# Start the ARQ background worker for async document ingestion and connector sync.
# Requires: AEGIS_REDIS_URL set in .env
# Usage: bash scripts/start_worker.sh

set -e
cd "$(dirname "$0")/.."
source .env 2>/dev/null || true

if [ -z "$AEGIS_REDIS_URL" ]; then
  echo "ERROR: AEGIS_REDIS_URL is not set. Worker requires Redis." >&2
  exit 1
fi

echo "Starting Aegis ARQ worker..."
exec python -m arq aegis.tasks.worker.WorkerSettings
