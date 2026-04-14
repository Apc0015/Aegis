import re
import logging
from pathlib import Path
from typing import List, Dict, Tuple
from rapid.config import SUPPORTED_FILE_TYPES

logger = logging.getLogger(__name__)

# Lazy-load tiktoken encoder (cl100k_base — used by GPT-4 and text-embedding-3-small)
_enc = None

def _get_encoder():
    global _enc
    if _enc is None:
        try:
            import tiktoken
            _enc = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"tiktoken unavailable, falling back to word-based chunking: {e}")
    return _enc


class DocumentProcessor:
    """
    Ingests PDF, DOCX, TXT, MD files.
    Chunks text by token count (cl100k_base via tiktoken) with sliding window overlap.
    Falls back to word-based chunking if tiktoken is unavailable.
    """

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        ext = Path(filename).suffix.lower()
        if ext == ".pdf":
            return self._extract_pdf(file_bytes)
        elif ext in (".docx", ".doc"):
            return self._extract_docx(file_bytes)
        elif ext in (".txt", ".md"):
            return file_bytes.decode("utf-8", errors="replace")
        else:
            raise ValueError(f"Unsupported file type: {ext}")

    def _extract_pdf(self, data: bytes) -> str:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(p.extract_text() or "" for p in reader.pages)

    def _extract_docx(self, data: bytes) -> str:
        import io
        from docx import Document
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    def chunk(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 77,
        source: str = "",
        doc_id: str = "",
        domain: str = "general",
    ) -> Tuple[List[str], List[Dict]]:
        """
        Token-based chunking with sliding window overlap.
        chunk_size and overlap are measured in tokens (cl100k_base encoding).
        Falls back to word-based chunking if tiktoken is unavailable.
        Returns (texts, metadatas).
        """
        enc = _get_encoder()

        if enc is not None:
            return self._chunk_by_tokens(text, chunk_size, overlap, source, doc_id, domain, enc)
        else:
            return self._chunk_by_words(text, chunk_size, overlap, source, doc_id, domain)

    def _chunk_by_tokens(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        source: str,
        doc_id: str,
        domain: str,
        enc,
    ) -> Tuple[List[str], List[Dict]]:
        """Primary path: chunk by real token count using tiktoken."""
        tokens = enc.encode(text)
        chunks, metadatas = [], []
        step = max(1, chunk_size - overlap)
        for i in range(0, max(1, len(tokens) - overlap), step):
            chunk_tokens = tokens[i: i + chunk_size]
            if not chunk_tokens:
                break
            chunk_text = enc.decode(chunk_tokens)
            chunks.append(chunk_text)
            metadatas.append({
                "source": source,
                "doc_id": doc_id,
                "chunk_index": len(chunks) - 1,
                "domain": domain,
                "token_count": len(chunk_tokens),
                "char_count": len(chunk_text),
            })
        return chunks, metadatas

    def _chunk_by_words(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        source: str,
        doc_id: str,
        domain: str,
    ) -> Tuple[List[str], List[Dict]]:
        """Fallback path: chunk by word count when tiktoken is unavailable."""
        words = text.split()
        chunks, metadatas = [], []
        step = max(1, chunk_size - overlap)
        for i in range(0, max(1, len(words) - overlap), step):
            chunk_words = words[i: i + chunk_size]
            if not chunk_words:
                break
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)
            metadatas.append({
                "source": source,
                "doc_id": doc_id,
                "chunk_index": len(chunks) - 1,
                "domain": domain,
                "char_count": len(chunk_text),
            })
        return chunks, metadatas
