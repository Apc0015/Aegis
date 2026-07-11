#!/usr/bin/env python3
"""
Index all documents in documents/ into FAISS + BM25 indexes.

Usage:
    python scripts/index_knowledge_base.py [--embed-provider local|openai|ollama] [--api-key KEY]

Project IDs match department folder names (lowercase), e.g.:
    HR -> "hr", Customer_Success -> "customer_success"
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add src to path so aegis package is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from aegis.services.document_processor import DocumentProcessor
from aegis.services.embedding_service import EmbeddingService
from aegis.services.vector_store_service import VectorStoreService
from aegis.services.bm25_engine import BM25Engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

DOCS_DIR = ROOT / "documents"

# Map folder names -> project_id (lowercase, underscores)
def folder_to_project_id(folder_name: str) -> str:
    return folder_name.lower().replace(" ", "_").replace("-", "_")


async def index_all(embed_provider: str, api_key: str):
    log.info(f"Embedding provider: {embed_provider}")

    emb = EmbeddingService(provider=embed_provider, api_key=api_key or None)
    vs = VectorStoreService(
        persist_dir=str(ROOT / "data" / "faiss"),
        dimension=emb.dimensions,
    )
    bm25 = BM25Engine(storage_dir=str(ROOT / "data" / "bm25"))
    proc = DocumentProcessor()

    departments = sorted([d for d in DOCS_DIR.iterdir() if d.is_dir()])
    if not departments:
        log.error(f"No department folders found in {DOCS_DIR}")
        sys.exit(1)

    total_chunks = 0
    total_docs = 0

    for dept_dir in departments:
        project_id = folder_to_project_id(dept_dir.name)
        files = sorted(dept_dir.glob("*.md")) + sorted(dept_dir.glob("*.txt")) + \
                sorted(dept_dir.glob("*.pdf")) + sorted(dept_dir.glob("*.docx"))

        if not files:
            log.warning(f"  {dept_dir.name}: no files found, skipping")
            continue

        log.info(f"\n{'─'*50}")
        log.info(f"Department: {dept_dir.name}  →  project_id='{project_id}'  ({len(files)} files)")

        dept_chunks = 0

        for filepath in files:
            doc_id = filepath.stem  # filename without extension
            file_bytes = filepath.read_bytes()

            try:
                text = proc.extract_text(file_bytes, filepath.name)
            except Exception as e:
                log.warning(f"  Skip {filepath.name}: {e}")
                continue

            if not text.strip():
                log.warning(f"  Skip {filepath.name}: empty text")
                continue

            chunks, metadatas = proc.chunk(
                text,
                source=filepath.name,
                doc_id=doc_id,
                domain=project_id,
            )

            if not chunks:
                log.warning(f"  Skip {filepath.name}: no chunks produced")
                continue

            # Embed all chunks in one batch (or one-by-one for local)
            try:
                embeddings = await emb.embed_batch(chunks)
            except Exception as e:
                log.error(f"  Embedding failed for {filepath.name}: {e}")
                continue

            # Add to FAISS
            for i, (chunk_text, meta, embedding) in enumerate(zip(chunks, metadatas, embeddings)):
                vs.upsert(
                    project_id=project_id,
                    doc_id=doc_id,
                    chunk_index=i,
                    text=chunk_text,
                    embedding=embedding,
                    metadata=meta,
                )

            # Add to BM25
            bm25.add_documents(project_id, chunks, metadatas)

            log.info(f"  ✓ {filepath.name}  →  {len(chunks)} chunks")
            dept_chunks += len(chunks)
            total_docs += 1

        log.info(f"  Subtotal: {dept_chunks} chunks for '{project_id}'")
        total_chunks += dept_chunks

    log.info(f"\n{'='*50}")
    log.info(f"Done. {total_docs} documents, {total_chunks} total chunks indexed.")
    log.info(f"FAISS indexes: {ROOT / 'data' / 'faiss'}")
    log.info(f"BM25  indexes: {ROOT / 'data' / 'bm25'}")


def main():
    parser = argparse.ArgumentParser(description="Index Aegis knowledge base documents")
    parser.add_argument(
        "--embed-provider",
        default="local",
        choices=["local", "openai", "ollama"],
        help="Embedding provider (default: local — no API key needed)",
    )
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY", ""),
        help="API key for openai/ollama providers",
    )
    args = parser.parse_args()

    if args.embed_provider == "openai" and not args.api_key:
        print("ERROR: --api-key or OPENAI_API_KEY required for openai provider")
        sys.exit(1)

    asyncio.run(index_all(args.embed_provider, args.api_key))


if __name__ == "__main__":
    main()
