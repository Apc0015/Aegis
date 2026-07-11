import re
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Tuple
from aegis.config import SUPPORTED_FILE_TYPES

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


# ---------------------------------------------------------------------------
# Section-header detection regex used by chunk_contextual()
# Matches:
#   - Markdown headers:           # Title, ## Title
#   - Numbered sections:          1., 2., 2.1, 2.1.3
#   - Keyword-led headers:        Section X, SECTION X, Article X
# ---------------------------------------------------------------------------
_SECTION_RE = re.compile(
    r"^(?:"
    r"#{1,6}\s+"                          # Markdown # / ## / ...
    r"|(?:\d+\.)+\s+"                     # 1. / 2.1. / 3.1.2.
    r"|(?:Section|SECTION|Article)\s+"   # Section N / Article N
    r")",
    re.MULTILINE,
)


def _count_units(text: str, enc) -> int:
    """Return token count if enc is available, otherwise word count."""
    if enc is not None:
        return len(enc.encode(text))
    return len(text.split())


class DocumentProcessor:
    """
    Ingests PDF, DOCX, TXT, MD files.

    Chunking strategies:
      "contextual" (default) — paragraph/section-aware semantic chunking.
      "token"                — original sliding-window token/word chunking.

    Existing callers that omit `strategy` automatically receive contextual
    chunking for improved retrieval quality.
    """

    # ------------------------------------------------------------------
    # Text extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Public chunking entry point
    # ------------------------------------------------------------------

    def chunk(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 77,
        source: str = "",
        doc_id: str = "",
        domain: str = "general",
        strategy: str = "contextual",
    ) -> Tuple[List[str], List[Dict]]:
        """
        Chunk *text* and return (texts, metadatas).

        Parameters
        ----------
        strategy : {"contextual", "token"}
            "contextual" — paragraph/section-aware semantic chunking
                           (default; better retrieval quality).
            "token"      — original sliding-window token/word chunking.
        chunk_size : int
            Target chunk size in tokens (or words if tiktoken unavailable).
        overlap : int
            For "token" strategy: sliding-window overlap in tokens/words.
            For "contextual" strategy: the last paragraph of a completed
            chunk is re-used as the lead paragraph of the next chunk
            (semantic overlap).
        """
        if strategy == "contextual":
            return self.chunk_contextual(text, chunk_size, overlap, source, doc_id, domain)
        else:
            enc = _get_encoder()
            if enc is not None:
                return self._chunk_by_tokens(text, chunk_size, overlap, source, doc_id, domain, enc)
            else:
                return self._chunk_by_words(text, chunk_size, overlap, source, doc_id, domain)

    # ------------------------------------------------------------------
    # Contextual / semantic chunking
    # ------------------------------------------------------------------

    def chunk_contextual(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 77,
        source: str = "",
        doc_id: str = "",
        domain: str = "general",
    ) -> Tuple[List[str], List[Dict]]:
        """
        Paragraph- and section-header-aware chunking.

        Algorithm
        ---------
        1. Split text on two-or-more blank lines into raw blocks.
        2. Further split each raw block when a section header is detected
           mid-block (so headers always start a new logical unit).
        3. Walk the logical units, accumulating them into a chunk until
           the next unit would exceed *chunk_size*.
        4. Flush the current chunk, then start the next one by re-using
           the last paragraph as semantic overlap context.
        5. If a single paragraph exceeds *chunk_size* on its own, delegate
           to token/word splitting for that paragraph alone.

        Each metadata dict gains a ``section_title`` field — the text of
        the most recently seen section header (empty string if none).
        """
        enc = _get_encoder()

        # ---- Step 1 & 2: build logical units -------------------------
        units = self._split_into_units(text)

        if not units:
            return [], []

        chunks: List[str] = []
        metadatas: List[Dict] = []
        current_units: List[str] = []
        current_size: int = 0
        last_section_title: str = ""

        def flush(section_title: str):
            """Emit the accumulated units as one chunk."""
            if not current_units:
                return
            chunk_text = "\n\n".join(current_units).strip()
            if not chunk_text:
                return
            chunks.append(chunk_text)
            metadatas.append({
                "source": source,
                "doc_id": doc_id,
                "chunk_index": len(chunks) - 1,
                "domain": domain,
                "char_count": len(chunk_text),
                "section_title": section_title,
                "indexed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })

        for unit in units:
            unit_stripped = unit.strip()
            if not unit_stripped:
                continue

            # Track the last section header we saw
            if _SECTION_RE.match(unit_stripped):
                last_section_title = unit_stripped.splitlines()[0].strip()

            unit_size = _count_units(unit_stripped, enc)

            # ---- Oversized single paragraph: sub-chunk it ------------
            if unit_size > chunk_size:
                # Flush what we have first
                flush(last_section_title)
                current_units = []
                current_size = 0

                sub_chunks, sub_metas = self._sub_chunk(
                    unit_stripped, chunk_size, overlap,
                    source, doc_id, domain, last_section_title, enc,
                    start_index=len(chunks),
                )
                chunks.extend(sub_chunks)
                metadatas.extend(sub_metas)
                continue

            # ---- Would adding this unit exceed chunk_size? -----------
            # +2 for the "\n\n" separator we would insert
            projected = current_size + (2 if current_units else 0) + unit_size

            if current_units and projected > chunk_size:
                # Flush current chunk
                flush(last_section_title)
                # Semantic overlap: carry the last paragraph into the next chunk
                overlap_unit = current_units[-1]
                current_units = [overlap_unit, unit_stripped]
                current_size = _count_units(overlap_unit, enc) + 2 + unit_size
            else:
                current_units.append(unit_stripped)
                current_size = projected if current_units else unit_size

        # Flush final chunk
        flush(last_section_title)

        # Re-index chunk_index to be sequential (flush uses len(chunks) - 1
        # which is already correct, but sub-chunks inject with start_index)
        for i, meta in enumerate(metadatas):
            meta["chunk_index"] = i

        return chunks, metadatas

    # ------------------------------------------------------------------
    # Helpers for contextual chunking
    # ------------------------------------------------------------------

    def _split_into_units(self, text: str) -> List[str]:
        """
        Split text into logical units:
        - First split on 2+ blank lines (paragraph boundaries).
        - Then split each paragraph further whenever a section header
          appears at the start of a line within the paragraph.
        """
        raw_paragraphs = re.split(r"\n{2,}", text)
        units: List[str] = []

        for para in raw_paragraphs:
            # Find positions of section headers within this paragraph
            header_positions = [m.start() for m in _SECTION_RE.finditer(para)]

            if len(header_positions) <= 1:
                # 0 or 1 header — treat the whole paragraph as one unit
                if para.strip():
                    units.append(para)
                continue

            # Multiple headers — split on each header start
            prev = 0
            for pos in header_positions:
                if pos > prev:
                    segment = para[prev:pos]
                    if segment.strip():
                        units.append(segment)
                prev = pos
            # Tail after last header
            tail = para[prev:]
            if tail.strip():
                units.append(tail)

        return units

    def _sub_chunk(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
        source: str,
        doc_id: str,
        domain: str,
        section_title: str,
        enc,
        start_index: int,
    ) -> Tuple[List[str], List[Dict]]:
        """
        Token/word split a single oversized paragraph.
        Injects ``section_title`` into each sub-chunk metadata.
        """
        if enc is not None:
            sub_texts, sub_metas = self._chunk_by_tokens(
                text, chunk_size, overlap, source, doc_id, domain, enc
            )
        else:
            sub_texts, sub_metas = self._chunk_by_words(
                text, chunk_size, overlap, source, doc_id, domain
            )

        for i, meta in enumerate(sub_metas):
            meta["section_title"] = section_title
            meta["chunk_index"] = start_index + i

        return sub_texts, sub_metas

    # ------------------------------------------------------------------
    # Original token / word chunking (unchanged, used by "token" strategy
    # and as sub-chunk fallback inside contextual)
    # ------------------------------------------------------------------

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
                "indexed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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
                "indexed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            })
        return chunks, metadatas
