from typing import List, Dict
from aegis.services.llm_service import LLMService

FUSION_SYSTEM = """You are a research assistant. You have both internal document
summaries and web search results. Synthesize them into a single clear answer.
Always prefer the internal documents when they conflict with web results.
Cite sources as [DOC] for internal documents and [WEB] for web results."""

class FusionAgent:
    def __init__(self, llm: LLMService):
        self.llm = llm

    async def fuse(
        self,
        query: str,
        rag_answer: str,
        web_results: List[Dict],
    ) -> str:
        web_text = "\n\n".join(
            f"[WEB {i+1}] {r.get('title','')}: {r.get('body','')}"
            for i, r in enumerate(web_results[:3])
        )
        prompt = (
            f"Question: {query}\n\n"
            f"Internal document answer:\n{rag_answer}\n\n"
            f"Web search results:\n{web_text}\n\n"
            f"Synthesize a final answer:"
        )
        return await self.llm.chat_simple(prompt, system=FUSION_SYSTEM)
