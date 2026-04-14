"""
Orchestrates a complete query end-to-end.
Flow:
  RBAC check → Intent detect → R2 rewrite →
  [RAG pipeline] + [DB pipeline in parallel] →
  Unified Firewall (apply_firewall) → LLM answer →
  Confidence score → Route → Audit log

Supports both batch (query) and streaming (query_stream) modes.
Cross-model evaluation: pass evaluator_llm to score faithfulness with a
different model, eliminating self-preference bias.
"""
import time
import queue
import asyncio
import threading
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Iterator

from rapid.services.llm_service import LLMService
from rapid.services.embedding_service import EmbeddingService
from rapid.services.vector_store_service import VectorStoreService
from rapid.services.bm25_engine import BM25Engine
from rapid.agents.r1_classifier import R1Classifier
from rapid.agents.r2_rewriter import R2Rewriter
from rapid.agents.r3_retriever import R3Retriever
from rapid.agents.r4_summarizer import R4Summarizer, apply_firewall
from rapid.agents.confidence_scorer import ConfidenceScorer, ConfidenceResult
from rapid.agents.intent_detector import detect_intent, detect_intent_llm
from rapid.agents.web_agent import WebAgent
from rapid.agents.fusion_agent import FusionAgent
from rapid.core.db_pipeline import run_db_pipeline
from rapid.rbac.rbac_module import RBACModule, AccessDecision, load_column_rules
from rapid.rbac.audit_log import AuditLog
from rapid.config import RAG_MODES

logger = logging.getLogger(__name__)

ACCESS_RULES_PATH = "config/access_rules.yaml"


@dataclass
class QueryResult:
    answer: str
    confidence: float
    verdict: str               # "high" | "medium" | "low"
    should_refuse: bool
    is_external: bool
    sources: List[Dict]
    chunks_used: int
    routing_path: str          # "direct" | "disclaimer" | "web" | "refuse" | "denied"
    access_decision: AccessDecision
    model_used: str
    latency_ms: int
    web_used: bool = False
    cross_model_eval: bool = False
    reranker_used: bool = False
    db_triggered: bool = False
    columns_blocked: list = field(default_factory=list)
    columns_anonymized: list = field(default_factory=list)


class MasterAgent:
    def __init__(
        self,
        llm: LLMService,
        embeddings: EmbeddingService,
        vector_store: VectorStoreService,
        bm25: BM25Engine,
        rbac: RBACModule,
        audit: AuditLog,
        web_enabled: bool = True,
        evaluator_llm: Optional[LLMService] = None,
    ):
        self.llm      = llm
        self.r1       = R1Classifier()
        self.r2       = R2Rewriter(llm)
        self.r3       = R3Retriever(vector_store, bm25, embeddings)
        self.r4       = R4Summarizer(llm)
        self.scorer   = ConfidenceScorer(llm, evaluator_llm=evaluator_llm)
        self.web      = WebAgent()
        self.fusion   = FusionAgent(llm)
        self.rbac     = rbac
        self.audit    = audit
        self.web_enabled  = web_enabled
        self.evaluator_llm = evaluator_llm

    # ── Load column rules safely ───────────────────────────────────────────────

    def _load_column_rules(self, user_role: str) -> dict:
        try:
            return load_column_rules(ACCESS_RULES_PATH, user_role)
        except FileNotFoundError as e:
            logger.error(f"Critical: access_rules.yaml not found for role '{user_role}': {e}")
            raise RuntimeError(f"Access rules file missing — cannot process role '{user_role}'") from e
        except Exception as e:
            logger.error(f"Critical: column rules could not be loaded for role '{user_role}': {e}")
            raise RuntimeError(f"Access rules unavailable for role '{user_role}'") from e

    # ── Internal shared pipeline ───────────────────────────────────────────────

    async def _run_pipeline_pre_answer(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        rag_mode: str,
        force_db: bool = False,
        llm_intent: bool = False,
    ):
        """
        Full pre-answer pipeline:
          RBAC → Intent detect → R2 rewrite →
          [RAG retrieve] || [DB query] →
          Unified firewall → NL summary

        Args:
            force_db:   When True, always queries the HR database regardless of
                        intent detection. Guarantees combined response.
            llm_intent: When True, uses LLM to classify intent instead of
                        keyword matching. More accurate, ~500ms extra latency.

        Returns:
            (access, mode, rewritten, chunks, summaries,
             db_triggered, columns_blocked, columns_anonymized)

        If access denied, returns (access, mode, None, None, None, False, [], [])
        """
        mode = RAG_MODES.get(rag_mode, RAG_MODES["general"])
        access = self.rbac.check_access(user_id, user_role, user_query)

        if not access.permitted:
            return access, mode, None, None, None, False, [], [], False

        # Intent detection — determines which pipelines to run
        # Priority: force_db overrides everything → llm_intent → keyword heuristic
        if llm_intent:
            intent = await detect_intent_llm(user_query, self.llm)
        else:
            intent = detect_intent(user_query)

        needs_documents = intent["needs_documents"]
        needs_database  = force_db or intent["needs_database"]

        # Column rules for DB pipeline (loaded from access_rules.yaml)
        column_rules = self._load_column_rules(user_role)

        # R2 query rewriting
        rewritten = await self.r2.rewrite(user_query)

        # Run RAG and DB pipelines in parallel
        rag_task = None
        db_task  = None

        if needs_documents:
            rag_task = asyncio.create_task(
                self.r3.retrieve(
                    project_id=project_id,
                    query=rewritten,
                    top_k=mode["top_k"],
                    vector_weight=mode["vector_weight"],
                )
            )

        if needs_database:
            db_task = asyncio.create_task(
                run_db_pipeline(query=user_query, column_rules=column_rules)
            )

        # Gather results
        chunks: List[Dict] = []
        raw_rows: List[dict] = []
        sources: List[str] = []
        columns_blocked: List[str] = []
        columns_anonymized: List[str] = []
        db_triggered = False

        if rag_task:
            chunks = await rag_task
            sources += [c.get("metadata", {}).get("source", "document") for c in chunks]

        if db_task:
            db_result = await db_task
            raw_rows = db_result.get("rows", [])
            columns_blocked = db_result.get("columns_blocked", [])
            columns_anonymized = db_result.get("columns_anonymized", [])
            sources += db_result.get("sources", [])
            db_triggered = len(raw_rows) > 0

        # Unified Firewall — raw data in, NL summary out, raw data DESTROYED
        raw_chunk_texts = [c.get("text", "") for c in chunks] if chunks else None
        firewall_ok = False
        try:
            nl_summary = await apply_firewall(
                raw_chunks=raw_chunk_texts,
                raw_rows=raw_rows if raw_rows else None,
                source_label="RAPID",
                user_role=user_role,
                llm_service=self.llm,
            )
            firewall_ok = True
        except Exception as e:
            logger.error(f"Firewall apply_firewall failed for role '{user_role}': {e}")
            nl_summary = "Error: data could not be processed through the privacy firewall."

        # Wrap in list for compatibility with generate_answer / stream_generate_answer
        summaries = [nl_summary]

        return (
            access, mode, rewritten, chunks, summaries,
            db_triggered, columns_blocked, columns_anonymized, firewall_ok
        )

    # ── Batch query ────────────────────────────────────────────────────────────

    async def query(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        rag_mode: str = "general",
        force_db: bool = False,
        llm_intent: bool = False,
    ) -> QueryResult:
        t0 = time.time()
        model_used = f"{self.llm.provider}/{self.llm.model}"

        # Pre-answer pipeline
        (access, mode, rewritten, chunks, summaries,
         db_triggered, columns_blocked, columns_anonymized, firewall_ok) = await self._run_pipeline_pre_answer(
            user_query, project_id, user_id, user_role, rag_mode,
            force_db=force_db, llm_intent=llm_intent
        )

        if not access.permitted:
            latency = int((time.time() - t0) * 1000)
            self.audit.log(
                user_id=user_id, user_role=user_role, query_text=user_query,
                access_verdict="DENIED", project_id=project_id,
                denial_reason=access.denial_reason,
                routing_path="denied", model_used=model_used, latency_ms=latency,
            )
            return QueryResult(
                answer=access.denial_reason or "Access denied.",
                confidence=0.0, verdict="low", should_refuse=True, is_external=False,
                sources=[], chunks_used=0, routing_path="denied",
                access_decision=access, model_used=model_used, latency_ms=latency,
            )

        # Generate answer from NL summaries only — never from raw data
        answer = await self.r4.generate_answer(summaries, user_query)

        # Confidence scoring
        conf: ConfidenceResult = await self.scorer.score(
            query=user_query, chunks=chunks, summaries=summaries, answer=answer,
            confidence_high=mode["confidence_high"],
            confidence_medium=mode["confidence_medium"],
            db_triggered=db_triggered,
            columns_blocked=columns_blocked,
        )

        # Routing
        routing_path, web_used = "direct", False
        if conf.should_refuse:
            routing_path = "refuse"
        elif conf.verdict == "medium":
            routing_path = "disclaimer"
        elif conf.verdict == "low" and conf.is_external and self.web_enabled and mode["web_fallback"]:
            web_results = await self.web.search(user_query)
            if web_results:
                answer = await self.fusion.fuse(user_query, answer, web_results)
            routing_path, web_used = "web", True

        # Audit
        latency = int((time.time() - t0) * 1000)
        self.audit.log(
            user_id=user_id, user_role=user_role, query_text=user_query,
            access_verdict="PERMITTED", project_id=project_id,
            departments_accessed=access.permitted_departments,
            confidence_score=conf.score, confidence_verdict=conf.verdict,
            routing_path=routing_path, model_used=model_used, latency_ms=latency,
            db_triggered=db_triggered, rag_triggered=bool(chunks),
            firewall_applied=firewall_ok, raw_data_destroyed=firewall_ok,
            columns_blocked=columns_blocked, columns_anonymized=columns_anonymized,
        )

        return QueryResult(
            answer=answer, confidence=conf.score, verdict=conf.verdict,
            should_refuse=conf.should_refuse, is_external=conf.is_external,
            sources=[{
                "text": c.get("text", "")[:200],
                "source": c.get("metadata", {}).get("source", "Unknown"),
                "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
            } for c in chunks],
            chunks_used=len(chunks), routing_path=routing_path,
            access_decision=access, model_used=model_used,
            latency_ms=latency, web_used=web_used,
            cross_model_eval=conf.cross_model_eval,
            reranker_used=self.r3._reranker_available,
            db_triggered=db_triggered,
            columns_blocked=columns_blocked,
            columns_anonymized=columns_anonymized,
        )

    # ── Streaming query ────────────────────────────────────────────────────────

    def query_stream(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        rag_mode: str = "general",
        force_db: bool = False,
        llm_intent: bool = False,
    ) -> Iterator[str]:
        """
        Synchronous generator that yields answer tokens, then a sentinel dict
        with the full QueryResult metadata as the last item.

        Usage in Streamlit:
            for item in agent.query_stream(...):
                if isinstance(item, dict):
                    result_meta = item   # final metadata
                else:
                    print(item, end="")  # token

        Thread-safety: uses queue.Queue to bridge async → sync streaming.
        """
        token_queue: queue.Queue = queue.Queue()
        _DONE = object()

        async def _run():
            t0 = time.time()
            model_used = f"{self.llm.provider}/{self.llm.model}"

            # Pre-answer pipeline
            (access, mode, rewritten, chunks, summaries,
             db_triggered, columns_blocked, columns_anonymized, firewall_ok) = await self._run_pipeline_pre_answer(
                user_query, project_id, user_id, user_role, rag_mode,
                force_db=force_db, llm_intent=llm_intent
            )

            if not access.permitted:
                latency = int((time.time() - t0) * 1000)
                self.audit.log(
                    user_id=user_id, user_role=user_role, query_text=user_query,
                    access_verdict="DENIED", project_id=project_id,
                    denial_reason=access.denial_reason,
                    routing_path="denied", model_used=model_used, latency_ms=latency,
                )
                result = QueryResult(
                    answer=access.denial_reason or "Access denied.",
                    confidence=0.0, verdict="low", should_refuse=True, is_external=False,
                    sources=[], chunks_used=0, routing_path="denied",
                    access_decision=access, model_used=model_used, latency_ms=latency,
                )
                token_queue.put(result.__dict__)
                token_queue.put(_DONE)
                return

            # Stream answer tokens — answer LLM sees only NL summaries
            full_answer_parts = []
            async for token in self.r4.stream_generate_answer(summaries, user_query):
                full_answer_parts.append(token)
                token_queue.put(token)

            answer = "".join(full_answer_parts)

            # Confidence + routing after streaming completes
            conf: ConfidenceResult = await self.scorer.score(
                query=user_query, chunks=chunks, summaries=summaries, answer=answer,
                confidence_high=mode["confidence_high"],
                confidence_medium=mode["confidence_medium"],
                db_triggered=db_triggered,
                columns_blocked=columns_blocked,
            )

            routing_path, web_used = "direct", False
            if conf.should_refuse:
                routing_path = "refuse"
            elif conf.verdict == "medium":
                routing_path = "disclaimer"
            elif conf.verdict == "low" and conf.is_external and self.web_enabled and mode["web_fallback"]:
                web_results = await self.web.search(user_query)
                if web_results:
                    answer = await self.fusion.fuse(user_query, answer, web_results)
                routing_path, web_used = "web", True

            latency = int((time.time() - t0) * 1000)
            self.audit.log(
                user_id=user_id, user_role=user_role, query_text=user_query,
                access_verdict="PERMITTED", project_id=project_id,
                departments_accessed=access.permitted_departments,
                confidence_score=conf.score, confidence_verdict=conf.verdict,
                routing_path=routing_path, model_used=model_used, latency_ms=latency,
                db_triggered=db_triggered, rag_triggered=bool(chunks),
                firewall_applied=firewall_ok, raw_data_destroyed=firewall_ok,
                columns_blocked=columns_blocked, columns_anonymized=columns_anonymized,
            )

            result = QueryResult(
                answer=answer, confidence=conf.score, verdict=conf.verdict,
                should_refuse=conf.should_refuse, is_external=conf.is_external,
                sources=[{
                    "text": c.get("text", "")[:200],
                    "source": c.get("metadata", {}).get("source", "Unknown"),
                    "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
                } for c in chunks],
                chunks_used=len(chunks), routing_path=routing_path,
                access_decision=access, model_used=model_used,
                latency_ms=latency, web_used=web_used,
                cross_model_eval=conf.cross_model_eval,
                reranker_used=self.r3._reranker_available,
                db_triggered=db_triggered,
                columns_blocked=columns_blocked,
                columns_anonymized=columns_anonymized,
            )
            token_queue.put(result.__dict__)
            token_queue.put(_DONE)

        def _thread_target():
            asyncio.run(_run())

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()

        while True:
            item = token_queue.get()
            if item is _DONE:
                break
            yield item

        t.join()

    # ── Direct LLM chat (no retrieval) ────────────────────────────────────────

    async def chat_direct(
        self,
        user_query: str,
        user_id: str,
        user_role: str,
    ) -> "QueryResult":
        """
        Direct LLM chat — no retrieval, just the LLM.
        For general-purpose chatbot use (mode='chat').
        """
        import time as _time
        from rapid.rbac.rbac_module import AccessDecision

        t0 = _time.time()
        model_used = f"{self.llm.provider}/{self.llm.model}"
        messages = [
            {
                "role": "system",
                "content": (
                    "You are RAPID, an intelligent assistant. "
                    "Answer the user's question helpfully and concisely."
                ),
            },
            {"role": "user", "content": user_query},
        ]
        answer = await self.llm.chat(messages, temperature=0.7, max_tokens=2048)
        latency = int((_time.time() - t0) * 1000)

        access = AccessDecision(
            permitted=True,
            user_role=user_role,
            user_id=user_id,
            query=user_query,
            permitted_departments=[],
        )
        result = QueryResult(
            answer=answer,
            confidence=1.0,
            verdict="high",
            should_refuse=False,
            is_external=False,
            sources=[],
            chunks_used=0,
            routing_path="direct_llm",
            model_used=model_used,
            latency_ms=latency,
            web_used=False,
            cross_model_eval=False,
            reranker_used=False,
            db_triggered=False,
            columns_blocked=[],
            columns_anonymized=[],
            access_decision=access,
        )
        self.audit.log(
            user_id=user_id,
            user_role=user_role,
            query_text=user_query,
            access_verdict="ALLOWED",
            routing_path="direct_llm",
            model_used=model_used,
            latency_ms=latency,
        )
        return result

    def chat_stream_direct(
        self,
        user_query: str,
        user_id: str,
        user_role: str,
    ) -> Iterator[str]:
        """
        Streaming version of chat_direct — yields tokens then a final metadata dict.
        Uses the same thread-queue pattern as query_stream.
        """
        import time as _time
        from rapid.rbac.rbac_module import AccessDecision

        token_queue: queue.Queue = queue.Queue()
        _DONE = object()

        async def _run():
            t0 = _time.time()
            model_used = f"{self.llm.provider}/{self.llm.model}"
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are RAPID, an intelligent assistant. "
                        "Answer the user's question helpfully and concisely."
                    ),
                },
                {"role": "user", "content": user_query},
            ]

            full_answer_parts = []
            async for token in self.llm.stream_chat(
                messages, temperature=0.7, max_tokens=2048
            ):
                full_answer_parts.append(token)
                token_queue.put(token)

            answer = "".join(full_answer_parts)
            latency = int((_time.time() - t0) * 1000)

            access = AccessDecision(
                permitted=True,
                user_role=user_role,
                user_id=user_id,
                query=user_query,
                permitted_departments=[],
            )
            result = QueryResult(
                answer=answer,
                confidence=1.0,
                verdict="high",
                should_refuse=False,
                is_external=False,
                sources=[],
                chunks_used=0,
                routing_path="direct_llm",
                model_used=model_used,
                latency_ms=latency,
                web_used=False,
                cross_model_eval=False,
                reranker_used=False,
                db_triggered=False,
                columns_blocked=[],
                columns_anonymized=[],
                access_decision=access,
            )
            self.audit.log(
                user_id=user_id,
                user_role=user_role,
                query_text=user_query,
                access_verdict="ALLOWED",
                routing_path="direct_llm",
                model_used=model_used,
                latency_ms=latency,
            )
            token_queue.put(result.__dict__)
            token_queue.put(_DONE)

        def _thread_target():
            asyncio.run(_run())

        t = threading.Thread(target=_thread_target, daemon=True)
        t.start()

        while True:
            item = token_queue.get()
            if item is _DONE:
                break
            yield item

        t.join()
