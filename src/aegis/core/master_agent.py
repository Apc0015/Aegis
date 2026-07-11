"""
Orchestrates a complete query end-to-end.
Flow:
  RBAC check → Intent detect → R2 rewrite →
  [RAG pipeline] + [DB pipeline in parallel] →
  Unified Firewall (apply_firewall) → LLM answer →
  Confidence score → Route → Audit log

Supports both batch (query) and streaming (query_stream_events) modes — the
streaming mode delegates to the batch pipeline so behavior can never diverge.
Cross-model evaluation: pass evaluator_llm to score faithfulness with a
different model, eliminating self-preference bias.
"""
import os
import time
import json
import hashlib
import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict

REDIS_URL = os.getenv("AEGIS_REDIS_URL", "")

from aegis.services.llm_service import LLMService
from aegis.services.embedding_service import EmbeddingService
from aegis.services.vector_store_service import VectorStoreService
from aegis.services.bm25_engine import BM25Engine
from aegis.agents.r1_classifier import R1Classifier
from aegis.agents.r2_rewriter import R2Rewriter
from aegis.agents.r3_retriever import R3Retriever
from aegis.agents.r4_summarizer import R4Summarizer, apply_firewall
from aegis.agents.confidence_scorer import ConfidenceScorer, ConfidenceResult
from aegis.agents.intent_detector import detect_intent_llm
from aegis.agents.web_agent import WebAgent
from aegis.agents.fusion_agent import FusionAgent
from aegis.core.db_pipeline import run_db_pipeline
from aegis.core.department_router import route_multi
from aegis.core.agent_memory import AgentMemoryStore
from aegis.core.user_memory import UserMemoryStore
from aegis.rbac.rbac_module import RBACModule, AccessDecision, load_column_rules
from aegis.rbac.audit_log import AuditLog
from aegis.services.session_file_store import SessionFileStore
from aegis.services.document_processor import DocumentProcessor
from aegis.config import RAG_MODES, rag_mode_for

REFUSAL_MESSAGE = (
    "I don't have enough reliable information in the knowledge base to answer that "
    "confidently. Please rephrase, add more detail, or contact the relevant department."
)

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
    query_source: str = "faiss"  # "faiss" | "database" | "file_upload" | "web" | "trivial"


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
        self.r3       = R3Retriever(vector_store, bm25, embeddings, llm=llm)
        self.r4       = R4Summarizer(llm)
        self.scorer   = ConfidenceScorer(llm, evaluator_llm=evaluator_llm)
        self.web      = WebAgent()
        self.fusion   = FusionAgent(llm)
        self.rbac     = rbac
        self.audit    = audit
        self.web_enabled  = web_enabled
        self.evaluator_llm = evaluator_llm
        self.agent_memory = AgentMemoryStore()
        self.user_memory = UserMemoryStore()
        self.session_files = SessionFileStore()
        self._doc_processor = DocumentProcessor()


    # ------------------------------------------------------------------
    # Redis query cache helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cache_key(user_query: str, project_id: str, user_role: str, user_id: str) -> str:
        """
        Return a 16-char hex cache key for the (query, project, role, user) tuple.

        user_id MUST be part of the key: answers are row-filtered per user (an employee
        only sees their own records), so two users sharing role+query still have
        different correct answers. Omitting user_id caused cross-user data leakage.
        """
        raw = f"{user_query}:{project_id}:{user_role}:{user_id}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    async def _redis_get(self, key: str) -> Optional["QueryResult"]:
        """
        Try to fetch a cached QueryResult from Redis.
        Returns None on any error or cache miss.
        """
        if not REDIS_URL:
            return None
        try:
            import redis.asyncio as aioredis
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            async with client:
                raw = await client.get(key)
            if raw is None:
                return None
            data = json.loads(raw)
            # Re-hydrate the access_decision field (stored as dict)
            from aegis.rbac.rbac_module import AccessDecision
            ad_data = data.pop("access_decision", {})
            ad = AccessDecision(**ad_data) if ad_data else AccessDecision(
                permitted=True, user_role="", user_id="", query="", permitted_departments=[]
            )
            return QueryResult(access_decision=ad, **data)
        except Exception as e:
            logger.debug(f"Redis cache get failed (key={key}): {e}")
            return None

    async def _redis_set(self, key: str, result: "QueryResult", ttl: int = 300) -> None:
        """
        Store a QueryResult in Redis with the given TTL (seconds).
        Silently ignores any errors.
        """
        if not REDIS_URL:
            return
        try:
            import redis.asyncio as aioredis
            data = result.__dict__.copy()
            # Serialize access_decision dataclass
            ad = data.get("access_decision")
            if ad is not None:
                data["access_decision"] = ad.__dict__
            client = aioredis.from_url(REDIS_URL, decode_responses=True)
            async with client:
                await client.setex(key, ttl, json.dumps(data))
        except Exception as e:
            logger.debug(f"Redis cache set failed (key={key}): {e}")

    # ------------------------------------------------------------------

    def _load_column_rules(self, user_role: str) -> dict:
        try:
            return load_column_rules(ACCESS_RULES_PATH, user_role)
        except FileNotFoundError as e:
            logger.error(f"Critical: access_rules.yaml not found for role '{user_role}': {e}")
            raise RuntimeError(f"Access rules file missing — cannot process role '{user_role}'") from e
        except Exception as e:
            logger.error(f"Critical: column rules could not be loaded for role '{user_role}': {e}")
            raise RuntimeError(f"Access rules unavailable for role '{user_role}'") from e


    async def ingest_session_file(
        self,
        file_bytes: bytes,
        filename: str,
        user_id: str,
    ) -> str:
        """
        Extract → chunk → embed → store in a temp FAISS + BM25 index.

        This is Pipeline 3's proper ingest step. The returned project_id
        is passed to query() as file_project_id so R3 retrieves from it
        just like any department index.

        The temp index expires after 2 hours (SessionFileStore TTL).
        Same user uploading the same file within the TTL reuses the index.
        """
        # Lazy cleanup of expired session indexes
        self.session_files.cleanup_expired(self.r3.vector, self.r3.bm25)

        project_id = self.session_files.make_project_id(user_id, file_bytes)

        # Reuse existing index if still fresh (same user, same file, within TTL)
        if self.session_files.is_fresh(project_id):
            logger.info(
                f"ingest_session_file: reusing fresh index '{project_id}' "
                f"for user={user_id}, file='{filename}'"
            )
            return project_id

        # Extract text
        text = self._doc_processor.extract_text(file_bytes, filename)
        if not text.strip():
            raise ValueError(f"No extractable text in '{filename}'")

        # Chunk — use contextual strategy, general mode sizing
        mode = RAG_MODES.get("general", RAG_MODES["general"])
        texts, metas = self._doc_processor.chunk(
            text,
            chunk_size=mode["chunk_size"],
            overlap=mode.get("chunk_overlap", 77),
            source=filename,
            doc_id=project_id,
            domain="session_file",
            strategy="contextual",
        )

        if not texts:
            raise ValueError(f"File '{filename}' produced no chunks after processing")

        # Embed all chunks in one batch
        embeddings = await self.r3.embeddings.embed_batch(texts)

        # Store in FAISS — defer disk writes, flush once after all chunks
        for i, (chunk_text, meta, emb) in enumerate(zip(texts, metas, embeddings)):
            self.r3.vector.upsert(
                project_id=project_id,
                doc_id=project_id,
                chunk_index=i,
                text=chunk_text,
                embedding=emb,
                metadata={**meta, "project_id": project_id, "is_session_file": True},
                persist=False,
            )
        self.r3.vector.flush(project_id)

        # Store in BM25
        self.r3.bm25.add_documents(project_id, texts, metas)

        # Register in session store
        self.session_files.register(project_id, user_id, filename)

        logger.info(
            f"ingest_session_file: indexed '{filename}' → {len(texts)} chunks "
            f"under project_id='{project_id}'"
        )
        return project_id

    async def _run_pipeline_pre_answer(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        file_project_id: Optional[str] = None,
        is_verify: bool = False,
        employee_id: str = "",
    ):
        """
        Full pre-answer pipeline:
          RBAC → intent detect → dept routing → R2 rewrite →
          [RAG multi-dept] || [DB query] in parallel →
          Unified R4 firewall → NL summary

        file_project_id: when set, the session file index is prepended to
          dept_ids so R3 retrieves from it alongside the regular project index.
          DB pipeline is suppressed (file queries don't need live DB unless
          is_verify=True, which cross-references file claims against DB).

        System decides all routing — no user overrides.
        Returns 10-tuple including dept_ids for audit + memory.

        employee_id: the caller's HR identity (may differ from the login user_id).
          Used as the row-level-security identity for the DB pipeline so
          "employees see only their own records" actually matches DB rows.
        """
        # Default mode for denial/short-circuit paths; reassigned to the routed
        # department's mode once authorization succeeds (so per-domain retrieval
        # and confidence tuning actually apply instead of always using "general").
        mode = RAG_MODES["general"]
        row_identity = employee_id or user_id

        # Department routing — single or multi-dept depending on keyword scores.
        # NOTE: the session file index is NOT folded in here; it is added back only
        # after department authorization, since an uploaded file is always readable
        # by the user who uploaded it regardless of department permissions.
        routed_depts = route_multi(user_query, project_id, top_k=2)

        # R1 classifier — adds domain signal and confidence; widens retrieval when borderline
        r1_domain, _, r1_confidence = self.r1.classify(user_query, project_id=project_id)
        if r1_confidence < 0.55 and project_id in ("general", ""):
            # Low-confidence classification: fold R1's suggestion into routed_depts
            if r1_domain not in ("multi", "general") and r1_domain not in routed_depts:
                routed_depts = routed_depts[:1] + [r1_domain]
                logger.info(f"R1 low-confidence ({r1_confidence:.2f}): widened routed_depts to {routed_depts}")
            elif r1_domain == "multi":
                # R1 sees no clear domain — keep top-2 from router
                logger.info(f"R1 returned 'multi' ({r1_confidence:.2f}): keeping router depts {routed_depts}")
        # When R1 returns "multi" AND router also found multiple depts, try up to 3 departments
        if r1_domain == "multi" and len(routed_depts) < 3:
            # Expand to top-3 from keyword router for maximum coverage
            routed_expanded = route_multi(user_query, project_id, top_k=3)
            if len(routed_expanded) > len(routed_depts):
                routed_depts = routed_expanded
                logger.info(f"R1 'multi': expanded to 3-dept retrieval {routed_depts}")

        # Base role validity check (denies unknown roles before any retrieval)
        access = self.rbac.check_access(user_id, user_role, user_query)
        if not access.permitted:
            return access, mode, None, None, None, False, [], [], False, [], ""

        # Department-level authorization — THE enforcement point. Retrieval is
        # restricted to the departments this role may actually read; anything the
        # keyword router picked that the role cannot access is dropped.
        allowed_depts, denied_depts = self.rbac.authorize_departments(user_role, routed_depts)
        if not allowed_depts and not file_project_id:
            denial = AccessDecision(
                permitted=False,
                user_role=user_role,
                user_id=user_id,
                query=user_query,
                permitted_departments=[],
                denial_reason=(
                    "Your role does not have access to the requested department(s): "
                    + ", ".join(denied_depts or routed_depts) + "."
                ),
            )
            logger.warning(
                f"Department access denied: user={user_id} role={user_role} "
                f"routed={routed_depts} denied={denied_depts}"
            )
            return denial, mode, None, None, None, False, [], [], False, [], ""

        # Final retrieval targets: session file index (always allowed) + authorized depts
        dept_ids = ([file_project_id] if file_project_id else []) + allowed_depts
        if not dept_ids:
            dept_ids = ["general"]
        # Reflect the departments actually authorized/accessed for an accurate audit trail
        access.permitted_departments = allowed_depts

        # Select the RAG mode from the primary AUTHORIZED department (not the session
        # file index), so per-domain chunking/weights/confidence thresholds apply.
        mode = rag_mode_for(allowed_depts[0] if allowed_depts else "general")

        primary_dept = dept_ids[0] if dept_ids else project_id
        domain = r1_domain if r1_domain not in ("multi", "general") else primary_dept

        is_cross_dept = len(dept_ids) > 1
        if is_cross_dept:
            logger.info(f"Cross-dept query: routing to {dept_ids}")
        else:
            logger.info(f"Single-dept query: routing to '{dept_ids[0]}'")

        # Intent detection — LLM-based with keyword fallback; system decides, no user override
        intent = await detect_intent_llm(user_query, self.llm)
        needs_documents = intent["needs_documents"]
        needs_database  = intent["needs_database"]

        # File upload queries target the uploaded file, not live DB.
        # Only cross-reference DB when user is verifying file claims (is_verify=True).
        if file_project_id and not is_verify:
            needs_database = False
            needs_documents = True  # session index was created — always retrieve from it

        column_rules = self._load_column_rules(user_role)

        # R2: decompose compound queries, then rewrite each sub-query with domain context
        sub_queries = await self.r2.decompose(user_query)
        rewritten_queries = await self.r2.rewrite_all(
            sub_queries, original_query=user_query, domain=domain
        )
        # Use the first rewritten sub-query as the canonical rewritten query for callers
        rewritten = rewritten_queries[0] if rewritten_queries else user_query

        # Answer length hint — derived from query complexity, passed to R4
        query_words = len(user_query.split())
        if len(sub_queries) > 1:
            length_hint = "up to 300 words"
        elif query_words <= 5:
            length_hint = "1-2 sentences"
        else:
            length_hint = "3-5 sentences"

        # Memory-based vector weight tuning — adjust per primary department's historical performance
        vector_weight = mode["vector_weight"]
        experience = self.agent_memory.get_experience(primary_dept)
        total_queries = experience.get("total_queries", 0)
        if total_queries >= 10:
            high_count = experience.get("high_confidence_count", 0)
            ratio = high_count / total_queries
            if ratio > 0.7:
                # RAG performs well for this dept — trust vectors more
                vector_weight = min(0.85, vector_weight + 0.05)
                logger.debug(f"Memory tuning: dept '{primary_dept}' ratio={ratio:.2f} → vector_weight={vector_weight}")
            elif ratio < 0.3:
                # RAG performs poorly — lean toward BM25
                vector_weight = max(0.30, vector_weight - 0.05)
                logger.debug(f"Memory tuning: dept '{primary_dept}' ratio={ratio:.2f} → vector_weight={vector_weight}")

        # Query-variant generation (an LLM call per sub-query) is department-agnostic,
        # so generate variants ONCE per sub-query and reuse them across every
        # department index — instead of regenerating them for every (dept × sub-query)
        # pair, which multiplied LLM calls by the number of routed departments.
        variants_by_sq: Dict[int, List[str]] = {}
        if needs_documents:
            variant_lists = await asyncio.gather(
                *[self.r3.generate_variants(sq) for sq in rewritten_queries]
            )
            variants_by_sq = {i: v for i, v in enumerate(variant_lists)}

        # RAG: retrieve from ALL matched departments × ALL rewritten sub-queries in parallel
        rag_tasks = []
        rag_task_keys = []  # (dept_id, sub_query_idx) for result assembly
        if needs_documents:
            for dept_id in dept_ids:
                for sq_idx, sq in enumerate(rewritten_queries):
                    rag_tasks.append(asyncio.create_task(
                        self.r3.retrieve(
                            project_id=dept_id,
                            query=sq,
                            top_k=mode["top_k"],
                            vector_weight=vector_weight,
                            variants=variants_by_sq.get(sq_idx, []),
                        )
                    ))
                    rag_task_keys.append((dept_id, sq_idx))

        # DB: single query (common DB, SQL handles cross-dept via JOINs)
        # Pass llm_service so text-to-SQL fallback runs when keyword matching finds nothing.
        # row_identity (employee_id) is the row-level-security identity.
        db_task = None
        if needs_database:
            db_task = asyncio.create_task(
                run_db_pipeline(query=user_query, column_rules=column_rules, llm_service=self.llm, user_id=row_identity, user_role=user_role)
            )

        # Gather RAG results — merge chunks from all departments
        chunks: List[Dict] = []
        raw_rows: List[dict] = []
        sources: List[str] = []
        columns_blocked: List[str] = []
        columns_anonymized: List[str] = []
        db_triggered = False

        if rag_tasks:
            all_task_results = await asyncio.gather(*rag_tasks, return_exceptions=True)
            seen_chunk_ids: set = set()
            for (dept_id, _sq_idx), dept_chunks in zip(rag_task_keys, all_task_results):
                if isinstance(dept_chunks, Exception):
                    logger.warning(f"RAG retrieve failed for dept '{dept_id}': {dept_chunks}")
                    continue
                # Tag each chunk with its source department; deduplicate by chunk text
                for c in dept_chunks:
                    c.setdefault("metadata", {})["department"] = dept_id
                    chunk_sig = (dept_id, c.get("text", "")[:120])
                    if chunk_sig in seen_chunk_ids:
                        continue
                    seen_chunk_ids.add(chunk_sig)
                    chunks.append(c)
                    sources.append(
                        f"[{dept_id.upper()}] {c.get('metadata', {}).get('source', 'document')}"
                    )

        if db_task:
            db_result = await db_task
            raw_rows = db_result.get("rows", [])
            columns_blocked = db_result.get("columns_blocked", [])
            columns_anonymized = db_result.get("columns_anonymized", [])
            sources += db_result.get("sources", [])
            db_triggered = len(raw_rows) > 0

        # Unified Firewall — raw data in, NL summary out, raw data DESTROYED
        raw_chunk_texts = [c.get("text", "") for c in chunks] if chunks else None
        source_label = " + ".join(d.upper() for d in dept_ids)
        firewall_ok = False
        try:
            nl_summary = await apply_firewall(
                raw_chunks=raw_chunk_texts,
                raw_rows=raw_rows if raw_rows else None,
                source_label=source_label,
                user_role=user_role,
                llm_service=self.llm,
            )
            firewall_ok = True
        except Exception as e:
            logger.error(f"Firewall apply_firewall failed for role '{user_role}': {e}")
            nl_summary = "Error: data could not be processed through the privacy firewall."

        summaries = [nl_summary]

        return (
            access, mode, rewritten, chunks, summaries,
            db_triggered, columns_blocked, columns_anonymized, firewall_ok, dept_ids, length_hint
        )


    async def query(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        history: Optional[List[Dict]] = None,
        file_context: Optional[str] = None,
        is_verify: bool = False,
        vision_data: Optional[dict] = None,
        file_firewall_applied: bool = False,
        file_project_id: Optional[str] = None,
        employee_id: str = "",
    ) -> QueryResult:
        t0 = time.time()
        model_used = f"{self.llm.provider}/{self.llm.model}"

        # The answer cache is keyed only by (query, project, role, user) and does NOT
        # capture conversation history or an attached file — so it must be bypassed for
        # conversational / file / vision turns, otherwise an identically-worded follow-up
        # returns a stale, context-free answer.
        cacheable = not history and not file_context and not vision_data and not file_project_id
        _cache_key = self._cache_key(user_query, project_id, user_role, user_id)
        if cacheable:
            cached = await self._redis_get(_cache_key)
            if cached is not None:
                logger.info(f"Redis cache hit for key={_cache_key}")
                return cached

        # Pre-answer pipeline — system decides everything
        (access, mode, rewritten, chunks, summaries,
         db_triggered, columns_blocked, columns_anonymized, firewall_ok, dept_ids, length_hint) = await self._run_pipeline_pre_answer(
            user_query, project_id, user_id, user_role,
            file_project_id=file_project_id, is_verify=is_verify,
            employee_id=employee_id,
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

        # Inject user context hint into history for personalized answer generation
        user_hint = self.user_memory.get_context_hint(user_id)
        if user_hint:
            hint_msg = {"role": "system", "content": f"User context: {user_hint}"}
            history = [hint_msg] + history if history else [hint_msg]

        # Generate answer from NL summaries only — never from raw data
        answer = await self.r4.generate_answer(
            summaries, user_query,
            history=history,
            file_context=file_context,
            is_verify=is_verify,
            length_hint=length_hint or "",
            vision_data=vision_data,
        )

        # Determine query source for confidence scoring and audit
        if file_project_id or file_firewall_applied or (file_context is not None and not vision_data):
            query_source = "file_upload"
        elif db_triggered and not chunks:
            query_source = "database"
        else:
            query_source = "faiss"

        # Confidence scoring — for file upload, include the file summary in scoring context
        # so faithfulness is judged against the actual source material, not empty RAG summaries
        scoring_summaries = summaries
        if query_source == "file_upload" and file_context:
            scoring_summaries = [file_context] + summaries

        primary_dept_for_scoring = dept_ids[0] if dept_ids else project_id
        conf: ConfidenceResult = await self.scorer.score(
            query=user_query, chunks=chunks, summaries=scoring_summaries, answer=answer,
            confidence_high=mode["confidence_high"],
            confidence_medium=mode["confidence_medium"],
            db_triggered=db_triggered,
            columns_blocked=columns_blocked,
            dept_experience=self.agent_memory.get_experience(primary_dept_for_scoring),
            query_source=query_source,
        )

        # Routing
        routing_path, web_used = "direct", False
        if conf.should_refuse:
            # Actually refuse: the low-confidence answer is suppressed and replaced,
            # not merely tagged. (Previously the answer was returned verbatim with a
            # "refuse" label the client had to voluntarily honor.)
            routing_path = "refuse"
            answer = REFUSAL_MESSAGE
        elif conf.verdict == "medium":
            routing_path = "disclaimer"
        elif conf.verdict == "low" and conf.is_external and self.web_enabled and mode["web_fallback"]:
            web_results = await self.web.search(user_query)
            if web_results:
                answer = await self.fusion.fuse(user_query, answer, web_results)
            routing_path, web_used = "web", True

        # Audit — file_firewall_applied ensures raw_data_destroyed=1 for file upload path
        effective_firewall = firewall_ok or file_firewall_applied
        primary_dept = dept_ids[0] if dept_ids else project_id
        latency = int((time.time() - t0) * 1000)
        self.audit.log(
            user_id=user_id, user_role=user_role, query_text=user_query,
            access_verdict="PERMITTED", project_id="+".join(dept_ids),
            departments_accessed=access.permitted_departments,
            confidence_score=conf.score, confidence_verdict=conf.verdict,
            routing_path=routing_path, model_used=model_used, latency_ms=latency,
            db_triggered=db_triggered, rag_triggered=bool(chunks),
            firewall_applied=effective_firewall, raw_data_destroyed=effective_firewall,
            columns_blocked=columns_blocked, columns_anonymized=columns_anonymized,
        )

        # Agent memory — record learning per matched department
        for dept_id in dept_ids:
            self.agent_memory.record_learning(
                project_id=dept_id,
                query=user_query,
            confidence_verdict=conf.verdict,
            routing_path=routing_path,
            chunks_used=len(chunks),
        )

        # User memory — record query for personalization
        self.user_memory.record_query(user_id, user_query, project_id, routing_path)

        final_result = QueryResult(
            answer=answer, confidence=conf.score, verdict=conf.verdict,
            should_refuse=conf.should_refuse, is_external=conf.is_external,
            sources=self._build_sources(chunks, primary_dept, user_role),
            chunks_used=len(chunks), routing_path=routing_path,
            access_decision=access, model_used=model_used,
            latency_ms=latency, web_used=web_used,
            cross_model_eval=conf.cross_model_eval,
            reranker_used=self.r3._reranker_available,
            db_triggered=db_triggered,
            columns_blocked=columns_blocked,
            columns_anonymized=columns_anonymized,
            query_source=query_source,
        )

        # Store in Redis cache — only cacheable (history/file-free), non-denied,
        # non-refused results. Caching a refusal would pin a transient low-confidence
        # outcome for the TTL.
        if cacheable and final_result.routing_path not in ("denied", "refuse"):
            await self._redis_set(_cache_key, final_result, ttl=300)

        return final_result

    @staticmethod
    def _build_sources(chunks: List[Dict], default_dept: str, user_role: str) -> List[Dict]:
        """
        Build the client-facing sources list from retrieved chunks.

        Raw chunk text is included only for admins. For other roles the whole
        pipeline promise is that clients receive LLM-summarized content, not raw
        document text — returning excerpts here contradicted the firewall design.
        Non-admins still get full provenance (source, department, chunk index).
        """
        include_text = user_role == "admin"
        return [{
            "text": c.get("text", "")[:200] if include_text else "",
            "source": c.get("metadata", {}).get("source", "Unknown"),
            "department": c.get("metadata", {}).get("department", default_dept),
            "chunk_index": c.get("metadata", {}).get("chunk_index", 0),
        } for c in chunks]


    async def query_stream_events(
        self,
        user_query: str,
        project_id: str,
        user_id: str,
        user_role: str,
        history: Optional[List[Dict]] = None,
        file_context: Optional[str] = None,
        is_verify: bool = False,
        vision_data: Optional[dict] = None,
        file_project_id: Optional[str] = None,
        employee_id: str = "",
        chunk_chars: int = 48,
    ):
        """
        Async generator yielding answer text chunks (str), then the QueryResult
        metadata dict as the final item.

        Delegates entirely to query() — one pipeline for batch and streaming, so
        the two paths can never diverge again. The full answer is produced and
        confidence-scored BEFORE the first chunk is emitted: a refused answer is
        never shown to the user, even partially (previously tokens streamed out
        prior to scoring, making the refusal gate cosmetic). The trade-off is a
        longer time-to-first-token; once emission starts it is effectively instant.

        Runs natively on the caller's event loop — replaces the previous design
        that spawned a thread + a fresh asyncio loop + a queue bridge per request.
        """
        result = await self.query(
            user_query=user_query,
            project_id=project_id,
            user_id=user_id,
            user_role=user_role,
            history=history,
            file_context=file_context,
            is_verify=is_verify,
            vision_data=vision_data,
            file_project_id=file_project_id,
            employee_id=employee_id,
        )

        answer = result.answer or ""
        for i in range(0, len(answer), chunk_chars):
            yield answer[i:i + chunk_chars]

        yield result.__dict__


    async def maybe_compress_history(self, conv_store, user_id: str, conversation_id: str) -> None:
        """
        Check whether the conversation history is long enough to warrant summarization,
        and trigger compression if so. Intended to be called by the API layer after
        appending new messages to the conversation store.

        Compression is delegated to ConversationStore.summarize_and_compress, which
        uses the LLM to collapse the oldest turns into a single summary message,
        keeping the most recent turns intact.
        """
        history = conv_store.get_history(user_id, conversation_id)
        if len(history) >= 16:  # >= 8 turns
            await conv_store.summarize_and_compress(user_id, conversation_id, self.llm)

