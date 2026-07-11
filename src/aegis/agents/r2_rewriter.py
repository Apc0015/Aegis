import asyncio
import json
import logging
from typing import List

from aegis.services.llm_service import LLMService

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """You are a search query optimizer. Rewrite the user's question
to improve document retrieval. Add synonyms, expand abbreviations, and make
implicit context explicit. Return ONLY the rewritten query, no explanation."""

DECOMPOSE_PROMPT = """You are a query decomposer. Split the following compound question into 2-3 simple, focused sub-questions that can each be answered independently. Return ONLY a JSON array of strings. Example: ["sub-question 1", "sub-question 2"]. No explanation."""

_COMPOUND_DETECTION_SYSTEM = (
    "Reply YES if this question asks about multiple distinct topics or requires "
    "multiple independent lookups. Reply NO if it is a single focused question. "
    "Reply ONLY YES or NO."
)

_COMPOUND_SIGNALS = {
    "and",
    "also",
    "as well as",
    "both",
    "compare",
    "versus",
    "vs",
    "difference between",
}


def _is_compound(query: str) -> bool:
    """Heuristic: returns True if the query likely asks about multiple things."""
    lower = query.lower()
    return any(signal in lower for signal in _COMPOUND_SIGNALS)


class R2Rewriter:
    def __init__(self, llm: LLMService):
        self.llm = llm

    async def rewrite(self, query: str, domain: str = "") -> str:
        """
        Rewrite *query* to improve retrieval quality.

        Args:
            query:  The raw user query.
            domain: Optional domain hint (e.g. "legal", "financial").  When
                    provided, domain-specific terminology guidance is prepended
                    to the rewrite prompt.

        Returns the rewritten query string, or *query* unchanged on error or
        when the query is too short (< 4 words).
        """
        # Short-query guard: nothing meaningful to expand
        if len(query.split()) < 4:
            return query

        # Build prompt — prepend domain context when available
        if domain:
            prompt = (
                f"Domain context: {domain}. Expand this query using "
                f"{domain}-specific terminology and synonyms.\n\n"
                + REWRITE_PROMPT
            )
        else:
            prompt = REWRITE_PROMPT

        try:
            return await self.llm.chat_simple(query, system=prompt, temperature=0.1)
        except Exception as e:
            logger.warning("R2 query rewrite failed, using original query: %s", e)
            return query

    async def _is_compound_llm(self, query: str) -> bool:
        """
        Use the LLM to determine whether *query* is a compound question.

        Returns True if the LLM responds with "YES", False for "NO".
        Falls back to the heuristic :func:`_is_compound` on any error.
        """
        try:
            response = await self.llm.chat_simple(
                query, system=_COMPOUND_DETECTION_SYSTEM, temperature=0.0
            )
            return response.strip().upper().startswith("Y")
        except Exception as e:
            logger.warning(
                "R2 LLM compound detection failed, falling back to heuristic: %s", e
            )
            return _is_compound(query)

    async def decompose(self, query: str) -> List[str]:
        """
        Detect compound queries and split them into focused sub-queries.

        Strategy: heuristic-first, LLM only when compound signals detected.
        - If fast keyword heuristic finds no compound signals → return [query]
          immediately (zero LLM calls saved on the majority of simple queries).
        - If heuristic signals compound → confirm with LLM before decomposing.
        Returns a list of sub-queries (2-3 items, capped at 3) for compound
        input, or [query] for simple queries.  Falls back to [query] on error.
        """
        # Fast path: no compound signals → skip LLM call entirely
        if not _is_compound(query):
            return [query]

        # Compound signals detected — confirm with LLM before splitting
        if not await self._is_compound_llm(query):
            return [query]

        try:
            raw = await self.llm.chat_simple(
                query, system=DECOMPOSE_PROMPT, temperature=0.1
            )
            sub_queries = json.loads(raw)
            if isinstance(sub_queries, list) and all(
                isinstance(q, str) for q in sub_queries
            ):
                filtered = [q.strip() for q in sub_queries if q.strip()]
                # Hard cap at 3 sub-questions
                filtered = filtered[:3]
                if filtered:
                    return filtered
            logger.warning(
                "R2 decompose: LLM returned unexpected structure, "
                "falling back to original query"
            )
        except Exception as e:
            logger.warning(
                "R2 query decomposition failed, using original query: %s", e
            )

        return [query]

    async def rewrite_all(
        self,
        queries: List[str],
        original_query: str = "",
        domain: str = "",
    ) -> List[str]:
        """
        Rewrite each query concurrently and return the results in order.

        Args:
            queries:        List of queries to rewrite (typically sub-queries
                            produced by :meth:`decompose`).
            original_query: The parent query.  When provided and there is more
                            than one sub-query, each query is prefixed with
                            ``[Context: <original_query[:80]>] `` so the
                            rewriter has full context.
            domain:         Optional domain hint forwarded to each
                            :meth:`rewrite` call.
        """
        if original_query and len(queries) > 1:
            context_prefix = f"[Context: {original_query[:80]}] "
            prefixed = [context_prefix + q for q in queries]
        else:
            prefixed = queries

        return list(
            await asyncio.gather(*[self.rewrite(q, domain=domain) for q in prefixed])
        )
