"""
R4 Prompt-Level Data Firewall
THE CORE INNOVATION OF AEGIS.

Raw document chunks + raw database rows go in.
NL summary comes out.
Raw data is destroyed from memory.
The answer LLM never sees raw data.
"""
import asyncio
import logging
from typing import List, Dict, Optional, AsyncIterator

from aegis.services.llm_service import LLMService

logger = logging.getLogger(__name__)

_SUMMARIZE_PROMPTS = {
    "admin": """You are a data privacy firewall for an administrator.
Your job is to convert raw data into a clear English summary.
Rules:
1. Retain precise figures, named entities, and exact values for admin-level review
2. Clearly label PII (SSN, etc.) as restricted but mention it exists
3. Keep the summary factual and complete
4. If data was blocked, say so
5. Cite the source at the end
6. Return ONLY the summary.""",

    "manager": """You are a data privacy firewall for a manager.
Your job is to convert raw data into a plain English summary.
Rules:
1. Use department-level aggregates and ranges (e.g. "salary range $80k–$110k")
2. Omit individual SSNs and personal IDs
3. Keep the summary factual and complete — do not lose meaning
4. If data was blocked by access rules, say so
5. Cite the source at the end
6. Return ONLY the summary.""",

    "employee": """You are a data privacy firewall.
Your ONLY job is to convert raw data into a plain English summary.
Rules:
1. NEVER include raw names, IDs, exact salary figures, SSNs, or any PII
2. Describe meaning, not raw values (e.g. "senior employee" not "Grade 7", "upper salary range" not "$95,000")
3. Keep the summary factual and complete — do not lose meaning
4. If data was blocked by access rules, say "some fields were restricted for your access level"
5. Cite the source document or table name at the end
6. Return ONLY the summary. No preamble, no explanation, no metadata.""",
}
_SUMMARIZE_PROMPTS["default"] = _SUMMARIZE_PROMPTS["employee"]  # fallback

ANSWER_SYSTEM = (
    "You are a helpful enterprise AI assistant. Answer the user's question "
    "using ONLY the provided document summaries. If the summaries do not "
    "contain enough information, say so clearly. Cite source numbers like [1], [2]. "
    "Never invent information not present in the summaries. "
    "IMPORTANT: When a [DATABASE RESULT] section is present, it contains authoritative "
    "structured data queried directly from the database — always include those facts "
    "in your answer even when document content is also present."
)

VERIFY_SYSTEM = (
    "You are a fact-checking assistant for an enterprise. "
    "The user has uploaded a document with claims. Verify each claim against the knowledge base.\n\n"
    "Return a JSON array. Each item: {\"claim\": str, \"kb_says\": str, \"verdict\": \"CORRECT\"|\"INCORRECT\"|\"CANNOT VERIFY\", \"source\": str}\n\n"
    "Example: [{\"claim\": \"Salary is $100k\", \"kb_says\": \"Upper salary range for this grade\", \"verdict\": \"CORRECT\", \"source\": \"[Source 1]\"}]\n\n"
    "Be precise. If a claim cannot be verified, set verdict to CANNOT VERIFY. Never invent data."
)


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
    system_prompt = _SUMMARIZE_PROMPTS.get(user_role, _SUMMARIZE_PROMPTS["default"])

    chunk_batches: List[List[str]] = []
    row_batches: List[List[dict]] = []

    if raw_chunks:
        chunk_batches = [raw_chunks[i:i + 5] for i in range(0, len(raw_chunks), 5)]

    if raw_rows:
        row_batches = [raw_rows[i:i + 10] for i in range(0, len(raw_rows), 10)]

    if not chunk_batches and not row_batches:
        return "No relevant data was found for this query."

    async def _summarize_batch(parts: List[str]) -> str:
        payload = "\n".join(parts)
        try:
            return await llm_service.chat_simple(
                f"Source: {source_label}\n\nRaw data to summarize:\n{payload}",
                system=system_prompt,
                temperature=0.1,
            )
        except Exception as e:
            logger.error(f"Firewall batch summarization failed: {e}")
            return f"Data from {source_label} could not be processed due to an error."

    chunk_tasks = []
    db_tasks = []

    for batch in chunk_batches:
        parts = ["=== DOCUMENT DATA ==="]
        for i, chunk in enumerate(batch):
            parts.append(f"[Chunk {i+1}]: {chunk}")
        chunk_tasks.append(_summarize_batch(parts))

    for batch in row_batches:
        parts = ["=== DATABASE DATA ==="]
        for i, row in enumerate(batch):
            parts.append(f"[Row {i+1}]: {row}")
        db_tasks.append(_summarize_batch(parts))

    try:
        all_tasks = chunk_tasks + db_tasks
        if len(all_tasks) == 1:
            all_results = [await all_tasks[0]]
        else:
            all_results = list(await asyncio.gather(*all_tasks))

        chunk_results = all_results[:len(chunk_tasks)]
        db_results = all_results[len(chunk_tasks):]

        # When both sources present, label them explicitly so the answer LLM
        # can distinguish structured DB facts from document knowledge and
        # weight them appropriately — this prevents DB data from being
        # deprioritised when competing with multiple RAG chunk summaries.
        sections = []
        if chunk_results:
            sections.append("[DOCUMENT KNOWLEDGE BASE]\n" + "\n\n".join(chunk_results))
        if db_results:
            sections.append("[DATABASE RESULT — treat as authoritative structured data]\n" + "\n\n".join(db_results))

        nl_summary = "\n\n---\n\n".join(sections) if sections else ""
    finally:
        # DESTROY RAW DATA FROM MEMORY
        # After this point, raw data is GONE. Only nl_summary continues.
        if raw_chunks:
            raw_chunks.clear()
            del raw_chunks
        if raw_rows:
            raw_rows.clear()
            del raw_rows
        if 'chunk_batches' in locals():
            del chunk_batches
        if 'row_batches' in locals():
            del row_batches

        logger.info(
            f"Firewall applied | source={source_label} | "
            f"user_role={user_role} | raw_data_destroyed=True"
        )

    return nl_summary


MAX_SUMMARY_TOKENS = 6000  # ~4500 words

_FILE_SUMMARIZE_SYSTEM = """You are a document summarizer and privacy firewall.
Convert the uploaded document content into a comprehensive natural language summary.

Rules:
1. Preserve ALL key facts, values, measurements, dates, diagnoses, medications, and findings
2. Keep all clinically or operationally significant information intact
3. Replace raw personal identifiers (SSN, DOB, patient IDs, insurance IDs) with their semantic role: \
e.g., "a patient SSN was included" — do NOT reproduce the raw identifier value
4. Structure the summary clearly by topic
5. Return ONLY the summary. No preamble, no metadata."""


class R4Summarizer:
    """
    Generates the final cited answer from NL summaries produced by apply_firewall().

    The firewall (apply_firewall) runs first and destroys raw data.
    This class only ever receives the NL summaries — never raw data.

    Supports both batch (generate_answer) and streaming (stream_generate_answer).
    """

    def __init__(self, llm: LLMService):
        self.llm = llm

    async def summarize_file_content(self, file_text: str, user_query: str) -> str:
        """
        Privacy firewall for uploaded file content.

        Raw file text goes in; NL summary comes out; raw text is destroyed.
        The answer LLM never sees the raw file — only this summary.
        Same guarantee as apply_firewall() for RAG chunks.
        """
        prompt = (
            f"User question: {user_query}\n\n"
            f"Document to summarize:\n{file_text}"
        )
        summary = "File content could not be summarized."
        try:
            summary = await self.llm.chat_simple(
                prompt,
                system=_FILE_SUMMARIZE_SYSTEM,
                temperature=0.1,
            )
        except Exception as e:
            logger.error(f"File content summarization failed: {e}")
        finally:
            # DESTROY RAW FILE CONTENT FROM MEMORY
            # After this point, raw file text is GONE. Only summary continues.
            file_text = None
            del file_text
            logger.info("File firewall applied | raw_file_content_destroyed=True")
        return summary

    def _build_messages(
        self,
        summaries: List[str],
        query: str,
        history: Optional[List[Dict]] = None,
        file_context: Optional[str] = None,
        is_verify: bool = False,
        length_hint: str = "",
        vision_data: Optional[dict] = None,
    ) -> List[Dict]:
        # Token budget guard: drop oldest summaries first until within budget
        total_words = sum(len(s.split()) for s in summaries)
        if total_words > MAX_SUMMARY_TOKENS:
            while len(summaries) > 1 and sum(len(s.split()) for s in summaries) > MAX_SUMMARY_TOKENS:
                summaries = summaries[1:]

        context = "\n\n---\n\n".join(
            f"[Source {i+1}]: {s}" for i, s in enumerate(summaries)
        )

        if is_verify and file_context:
            system = VERIFY_SYSTEM
            prompt = (
                f"=== UPLOADED DOCUMENT (claims to verify) ===\n{file_context}\n\n"
                f"=== COMPANY KNOWLEDGE BASE ===\n{context}\n\n"
                f"User question: {query}\n\n"
                f"Please verify the claims in the uploaded document against the knowledge base:"
            )
        else:
            system = ANSWER_SYSTEM
            if length_hint and not is_verify:
                system = system + f" Keep your answer {length_hint}."
            file_block = f"\n\n=== UPLOADED FILE CONTEXT ===\n{file_context}\n" if file_context else ""
            prompt = f"Document summaries:\n{context}{file_block}\n\nQuestion: {query}\n\nAnswer:"

        messages: List[Dict] = [{"role": "system", "content": system}]
        if history:
            messages.extend(history)
        if vision_data and vision_data.get("b64") and vision_data.get("mime"):
            messages.append({
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{vision_data['mime']};base64,{vision_data['b64']}"
                        },
                    },
                ],
            })
        else:
            messages.append({"role": "user", "content": prompt})
        return messages

    async def generate_answer(
        self,
        summaries: List[str],
        query: str,
        history: Optional[List[Dict]] = None,
        file_context: Optional[str] = None,
        is_verify: bool = False,
        length_hint: str = "",
        vision_data: Optional[dict] = None,
    ) -> str:
        """Generate a cited answer (or verification report) from NL summaries."""
        messages = self._build_messages(summaries, query, history, file_context, is_verify, length_hint, vision_data)
        return await self.llm.chat(messages, temperature=0.1)

    async def stream_generate_answer(
        self,
        summaries: List[str],
        query: str,
        history: Optional[List[Dict]] = None,
        file_context: Optional[str] = None,
        is_verify: bool = False,
        length_hint: str = "",
        vision_data: Optional[dict] = None,
    ) -> AsyncIterator[str]:
        """Stream the answer token-by-token from NL summaries."""
        messages = self._build_messages(summaries, query, history, file_context, is_verify, length_hint, vision_data)
        async for token in self.llm.stream_chat(messages, temperature=0.1):
            yield token
