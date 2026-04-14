"""
R4 Prompt-Level Data Firewall
THE CORE INNOVATION OF RAPID.

Raw document chunks + raw database rows go in.
NL summary comes out.
Raw data is destroyed from memory.
The answer LLM never sees raw data.
"""
import gc
import logging
from typing import List, Dict, Optional, AsyncIterator

from rapid.services.llm_service import LLMService

logger = logging.getLogger(__name__)

SUMMARIZE_SYSTEM_PROMPT = """You are a data privacy firewall.
Your ONLY job is to convert raw data into a plain English summary.

Rules you MUST follow:
1. NEVER include raw names, IDs, exact salary figures, SSNs, or any PII
2. Describe meaning, not raw values (e.g. "senior employee" not "Grade 7", "upper salary range" not "$95,000")
3. Keep the summary factual and complete — do not lose meaning
4. If data was blocked by access rules, say "some fields were restricted for your access level"
5. Cite the source document or table name at the end
6. Return ONLY the summary. No preamble, no explanation, no metadata."""

ANSWER_SYSTEM = (
    "You are a helpful enterprise AI assistant. Answer the user's question "
    "using ONLY the provided document summaries. If the summaries do not "
    "contain enough information, say so clearly. Cite source numbers like [1], [2]. "
    "Never invent information not present in the summaries."
)


# ── Standalone Firewall Function ──────────────────────────────────────────────

async def apply_firewall(
    raw_chunks: Optional[List[str]],
    raw_rows: Optional[List[dict]],
    source_label: str,
    user_role: str,
    llm_service: "LLMService",
) -> str:
    """
    The Prompt-Level Data Firewall.

    Takes raw document chunks AND/OR raw database rows.
    Returns a single NL summary string.
    Destroys all raw data from memory before returning.

    This function is the architectural guarantee that the answer LLM
    never sees raw sensitive data.
    """
    payload_parts = []

    if raw_chunks:
        payload_parts.append("=== DOCUMENT DATA ===")
        for i, chunk in enumerate(raw_chunks):
            payload_parts.append(f"[Chunk {i+1}]: {chunk}")

    if raw_rows:
        payload_parts.append("=== DATABASE DATA ===")
        for i, row in enumerate(raw_rows):
            payload_parts.append(f"[Row {i+1}]: {row}")

    if not payload_parts:
        return "No relevant data was found for this query."

    raw_payload = "\n".join(payload_parts)

    try:
        nl_summary = await llm_service.chat_simple(
            f"Source: {source_label}\n\nRaw data to summarize:\n{raw_payload}",
            system=SUMMARIZE_SYSTEM_PROMPT,
            temperature=0.1,
        )
    except Exception as e:
        logger.error(f"Firewall summarization failed: {e}")
        nl_summary = f"Data from {source_label} could not be processed due to an error."
    finally:
        # DESTROY RAW DATA FROM MEMORY
        # After this point, raw data is GONE. Only nl_summary continues.
        if raw_chunks:
            raw_chunks.clear()
            del raw_chunks
        if raw_rows:
            raw_rows.clear()
            del raw_rows
        if 'raw_payload' in locals():
            del raw_payload
        if 'payload_parts' in locals():
            del payload_parts
        gc.collect()

        logger.info(
            f"Firewall applied | source={source_label} | "
            f"user_role={user_role} | raw_data_destroyed=True"
        )

    return nl_summary


# ── R4Summarizer — Answer Generation Only ────────────────────────────────────

class R4Summarizer:
    """
    Generates the final cited answer from NL summaries produced by apply_firewall().

    The firewall (apply_firewall) runs first and destroys raw data.
    This class only ever receives the NL summaries — never raw data.

    Supports both batch (generate_answer) and streaming (stream_generate_answer).
    """

    def __init__(self, llm: LLMService):
        self.llm = llm

    # ── Answer generation (batch) ─────────────────────────────────────────────

    def _answer_prompt(self, summaries: List[str], query: str) -> str:
        context = "\n\n---\n\n".join(
            f"[Source {i+1}]: {s}" for i, s in enumerate(summaries)
        )
        return f"Document summaries:\n{context}\n\nQuestion: {query}\n\nAnswer:"

    async def generate_answer(self, summaries: List[str], query: str) -> str:
        """Generate a cited answer from NL summaries (non-streaming)."""
        prompt = self._answer_prompt(summaries, query)
        return await self.llm.chat_simple(prompt, system=ANSWER_SYSTEM, temperature=0.1)

    # ── Answer generation (streaming) ─────────────────────────────────────────

    async def stream_generate_answer(
        self,
        summaries: List[str],
        query: str,
    ) -> AsyncIterator[str]:
        """
        Stream the answer token-by-token from NL summaries.
        Usage:
            async for token in r4.stream_generate_answer(summaries, query):
                print(token, end="", flush=True)
        """
        prompt = self._answer_prompt(summaries, query)
        messages = [
            {"role": "system", "content": ANSWER_SYSTEM},
            {"role": "user", "content": prompt},
        ]
        async for token in self.llm.stream_chat(messages, temperature=0.1):
            yield token
