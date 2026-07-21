# ── Aegis API (FastAPI backend) ───────────────────────────────────────────────
# Governed enterprise RAG. Ships with the bundled sample dataset; the entrypoint
# seeds it and builds document indexes on first boot if they don't exist.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    KMP_DUPLICATE_LIB_OK=TRUE \
    AEGIS_DB_PATH=data/medical_company.db \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

# build-essential covers any source builds (rank-bm25 etc.); curl for healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first (layer caching), then the aegis package itself so
# `import aegis` works without PYTHONPATH (the package lives in src/).
COPY requirements.txt pyproject.toml ./
RUN pip install --upgrade pip && pip install -r requirements.txt
COPY . .
RUN pip install -e . && chmod +x scripts/docker-entrypoint.sh

EXPOSE 8000

# start-period is generous: first boot may seed the DB, build indexes, and pull
# the local embedding + reranker models.
HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=5 \
    CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

ENTRYPOINT ["scripts/docker-entrypoint.sh"]
