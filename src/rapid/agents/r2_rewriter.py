import logging
from rapid.services.llm_service import LLMService

logger = logging.getLogger(__name__)

REWRITE_PROMPT = """You are a search query optimizer. Rewrite the user's question
to improve document retrieval. Add synonyms, expand abbreviations, and make
implicit context explicit. Return ONLY the rewritten query, no explanation."""

class R2Rewriter:
    def __init__(self, llm: LLMService):
        self.llm = llm

    async def rewrite(self, query: str) -> str:
        try:
            return await self.llm.chat_simple(query, system=REWRITE_PROMPT, temperature=0.1)
        except Exception as e:
            logger.warning(f"R2 query rewrite failed, using original query: {e}")
            return query
