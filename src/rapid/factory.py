from typing import Optional
from rapid.services.llm_service import LLMService
from rapid.services.embedding_service import EmbeddingService
from rapid.services.vector_store_service import VectorStoreService
from rapid.services.bm25_engine import BM25Engine
from rapid.rbac.rbac_module import RBACModule
from rapid.rbac.audit_log import AuditLog
from rapid.core.master_agent import MasterAgent


def build_agent(
    llm_provider: str = "openai",
    llm_model: str = "gpt-4o-mini",
    api_key: str = "",
    embed_provider: str = "openai",
    web_enabled: bool = True,
    evaluator_provider: Optional[str] = None,
    evaluator_model: Optional[str] = None,
    evaluator_api_key: Optional[str] = None,
) -> MasterAgent:
    """
    Build and wire a MasterAgent.

    Args:
        llm_provider / llm_model / api_key:
            Main LLM used for query rewriting, summarization, and answer generation.
        embed_provider:
            Embedding provider for vector search.
        web_enabled:
            Whether to allow DuckDuckGo web fallback on low-confidence external queries.
        evaluator_provider / evaluator_model / evaluator_api_key:
            Optional cross-model evaluator for faithfulness scoring.
            Should differ from the main LLM to avoid self-preference bias.
            If evaluator_api_key is None, falls back to api_key.

    Returns:
        Configured MasterAgent instance.
    """
    llm  = LLMService(llm_provider, llm_model, api_key)
    emb  = EmbeddingService(embed_provider, api_key)
    vs   = VectorStoreService()
    bm25 = BM25Engine()
    rbac = RBACModule()
    audit = AuditLog()

    evaluator_llm: Optional[LLMService] = None
    if evaluator_provider and evaluator_model:
        ev_key = evaluator_api_key or api_key
        evaluator_llm = LLMService(evaluator_provider, evaluator_model, ev_key)

    return MasterAgent(
        llm, emb, vs, bm25, rbac, audit,
        web_enabled=web_enabled,
        evaluator_llm=evaluator_llm,
    )
