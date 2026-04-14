"""
RAGTrack — sequential R2 → R3 → R4 pipeline.
Provided as a standalone pipeline component; MasterAgent can use it directly
or call the agents individually.
"""
from typing import List, Dict, Optional

from rapid.agents.r2_rewriter import R2Rewriter
from rapid.agents.r3_retriever import R3Retriever
from rapid.agents.r4_summarizer import R4Summarizer
from rapid.services.embedding_service import EmbeddingService

class RAGTrack:
    def __init__(
        self,
        r2: R2Rewriter,
        r3: R3Retriever,
        r4: R4Summarizer,
        embeddings: EmbeddingService,
    ):
        self.r2 = r2
        self.r3 = r3
        self.r4 = r4
        self.embeddings = embeddings

    async def run(
        self,
        query: str,
        project_id: str,
        top_k: int = 5,
        vector_weight: float = 0.6,
    ) -> Dict:
        """Run the full R2→R3→R4 pipeline. Returns dict with chunks, summaries, answer."""
        rewritten = await self.r2.rewrite(query)

        chunks = await self.r3.retrieve(
            project_id=project_id,
            query=rewritten,
            top_k=top_k,
            vector_weight=vector_weight,
        )

        summaries = await self.r4.summarize(chunks, query)
        answer    = await self.r4.generate_answer(summaries, query)

        return {
            "rewritten_query": rewritten,
            "chunks": chunks,
            "summaries": summaries,
            "answer": answer,
        }
