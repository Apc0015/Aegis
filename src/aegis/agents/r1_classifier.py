import json
import logging
import os
from typing import Optional, Tuple

from aegis.config import DOC_TYPE_KEYWORDS, RAG_MODES

logger = logging.getLogger(__name__)

# Prototype sentences that represent each domain's semantic space.
# Embedded once and cached; used for cosine similarity in stage 2.
DOMAIN_PROTOTYPES = {
    "legal": "contract agreement clause jurisdiction liability arbitration",
    "financial": "revenue profit budget cash flow quarterly fiscal balance sheet",
    "medical": "patient diagnosis treatment clinical prescription healthcare",
    "hr": "employee leave policy benefits onboarding handbook performance",
    "technical": "api endpoint deployment architecture docker kubernetes pipeline",
    "research": "hypothesis methodology findings abstract peer review dataset",
    "compliance": "regulation audit sox gdpr requirement standard regulatory",
    "contracts": "contract party obligation term breach amendment covenant",
    "operations": "procedure workflow sop runbook checklist maintenance incident",
    "general": "company information document report summary",
}

# Path prefix for per-project prototype overrides (relative to repo root).
_PROTOTYPES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "data", "domain_prototypes"
)


class R1Classifier:
    """
    Two-stage document type classifier. No LLM call. Fast.

    Stage 1 — keyword scoring (always runs, O(keywords)).
               Filename keywords are scored separately with a 4x multiplier
               added on top of the body score.
    Stage 2 — embedding cosine similarity (runs only when stage 1 is
               ambiguous: top score <= 2 OR gap between top-two <= 1).
               Falls back gracefully to keyword-only if
               sentence_transformers is not installed.

    Returns (domain_key, rag_mode_config, confidence_score).

    Low-confidence path: if the max blended score < 0.45 (or all keyword
    scores <= 1 when embeddings are unavailable), returns domain="multi"
    with the general RAG mode config and confidence=max_score.
    """

    def __init__(self):
        self._model = None
        # domain -> np.ndarray (unit-normed prototype embedding)
        self._prototype_embeddings: dict = {}
        # None = not yet tried; True/False = availability result
        self._model_available: Optional[bool] = None

    # ------------------------------------------------------------------
    # Lazy model helpers
    # ------------------------------------------------------------------

    def _get_model(self):
        """Lazy-load SentenceTransformer. Returns None if unavailable."""
        if self._model_available is False:
            return None
        if self._model is not None:
            return self._model

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._model_available = True
            logger.debug("R1Classifier: SentenceTransformer loaded.")
        except Exception as exc:
            self._model_available = False
            logger.info(
                "R1Classifier: sentence_transformers unavailable, "
                "using keyword-only classification. (%s)",
                exc,
            )
        return self._model

    def _get_prototype_embeddings(self, model, prototypes: dict) -> dict:
        """Compute and cache unit-normed prototype embeddings for the given prototype dict."""
        # Use cached embeddings only when using the default prototypes (no project override)
        if prototypes is DOMAIN_PROTOTYPES and self._prototype_embeddings:
            return self._prototype_embeddings

        result: dict = {}
        try:
            import numpy as np

            sentences = list(prototypes.values())
            domains = list(prototypes.keys())
            vecs = model.encode(
                sentences, convert_to_numpy=True, show_progress_bar=False
            )
            for domain, vec in zip(domains, vecs):
                norm = float(np.linalg.norm(vec))
                result[domain] = vec / norm if norm > 0 else vec

            # Cache only for the default prototype set
            if prototypes is DOMAIN_PROTOTYPES:
                self._prototype_embeddings = result

        except Exception as exc:
            logger.warning(
                "R1Classifier: failed to build prototype embeddings: %s", exc
            )

        return result

    # ------------------------------------------------------------------
    # Project-aware prototype loader
    # ------------------------------------------------------------------

    def _load_project_prototypes(self, project_id: str) -> dict:
        """
        Try to load per-project domain prototype overrides from
        data/domain_prototypes/{project_id}.json.

        The file should be a JSON object mapping domain names to prototype
        sentences, e.g.::

            {"legal": "bespoke legal terminology for this client ..."}

        Project-level entries override the global DOMAIN_PROTOTYPES; all
        other global entries are preserved.  If the file is missing,
        unreadable, or malformed, falls back silently to DOMAIN_PROTOTYPES.
        """
        if not project_id:
            return DOMAIN_PROTOTYPES

        path = os.path.normpath(
            os.path.join(_PROTOTYPES_DIR, f"{project_id}.json")
        )
        try:
            with open(path, "r", encoding="utf-8") as fh:
                overrides = json.load(fh)
            if not isinstance(overrides, dict):
                raise ValueError("prototype file must be a JSON object")
            merged = {**DOMAIN_PROTOTYPES, **overrides}
            logger.debug(
                "R1Classifier: loaded project prototypes for '%s' (%d overrides)",
                project_id,
                len(overrides),
            )
            return merged
        except FileNotFoundError:
            logger.debug(
                "R1Classifier: no prototype file for project '%s', using defaults",
                project_id,
            )
        except Exception as exc:
            logger.warning(
                "R1Classifier: could not load project prototypes for '%s': %s",
                project_id,
                exc,
            )

        return DOMAIN_PROTOTYPES

    # ------------------------------------------------------------------
    # Math helper
    # ------------------------------------------------------------------

    def _cosine(self, a, b) -> float:
        """Cosine similarity between two numpy vectors (both assumed unit-normed)."""
        try:
            import numpy as np

            return float(np.dot(a, b))
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def classify(
        self, text: str, filename: str = "", project_id: str = ""
    ) -> Tuple[str, dict, float]:
        """
        Classify *text* (+ optional *filename*) into a domain.

        Filename tokens are scored separately with a 4x weight multiplier
        and added on top of the body score.

        Args:
            text:       Document body (or excerpt).
            filename:   Original filename — keyword hits here score 4x.
            project_id: Optional project identifier for per-project prototype
                        overrides loaded from data/domain_prototypes/.

        Returns:
            (domain_key: str, rag_mode_config: dict, confidence_score: float)
            confidence_score is the max blended score in [0.0, 1.0].
            domain_key may be "multi" when confidence is below 0.45 threshold.
        """
        # Resolve prototypes (may be project-specific)
        prototypes = self._load_project_prototypes(project_id)

        # ---- Stage 1: keyword scoring (body + 4x filename) -----------
        body_lower = text[:3000].lower()
        filename_lower = filename.lower()

        scores: dict = {}
        for domain, keywords in DOC_TYPE_KEYWORDS.items():
            body_hits = sum(1 for kw in keywords if kw in body_lower)
            filename_hits = sum(1 for kw in keywords if kw in filename_lower)
            scores[domain] = body_hits + 4 * filename_hits

        sorted_domains = sorted(scores, key=scores.get, reverse=True)
        top_domain = sorted_domains[0]
        top_score = scores[top_domain]
        second_score = scores[sorted_domains[1]] if len(sorted_domains) > 1 else 0

        # Decide whether stage 2 is needed
        ambiguous = (top_score <= 2) or ((top_score - second_score) <= 1)

        if not ambiguous:
            # High-confidence keyword hit — no embedding needed.
            # Compute a pseudo blended score for the confidence return value.
            kw_max = max(top_score, 1)
            confidence = min(scores[top_domain] / kw_max, 1.0)
            best = top_domain
            blended_max = confidence
        else:
            # ---- Stage 2: embedding-based disambiguation -------------
            best, blended_max = self._classify_with_embeddings(
                text, scores, top_score, prototypes
            )

        # ------ Low-confidence multi-route ----------------------------
        model_available = self._get_model() is not None
        if model_available:
            if blended_max < 0.45:
                logger.debug(
                    "R1Classifier: low confidence (%.3f), routing to 'multi'",
                    blended_max,
                )
                return "multi", RAG_MODES.get("general", RAG_MODES["general"]), blended_max
        else:
            # Embeddings unavailable: fall back to keyword-only multi check
            if top_score <= 1:
                logger.debug(
                    "R1Classifier: all keyword scores <= 1, no embeddings, routing to 'multi'"
                )
                return "multi", RAG_MODES.get("general", RAG_MODES["general"]), blended_max

        if best not in RAG_MODES and best != "general":
            best = "general"

        return best, RAG_MODES.get(best, RAG_MODES["general"]), blended_max

    # ------------------------------------------------------------------
    # Stage 2 internals
    # ------------------------------------------------------------------

    def _classify_with_embeddings(
        self,
        text: str,
        kw_scores: dict,
        max_kw_score: int,
        prototypes: dict,
    ) -> Tuple[str, float]:
        """
        Blend keyword scores with embedding cosine similarities and return
        (winning_domain, max_blended_score).

        Falls back to keyword winner if embeddings are unavailable;
        in that case the returned score is a normalised keyword score.
        """
        model = self._get_model()
        if model is None:
            # Graceful fallback: keyword-only
            best = max(kw_scores, key=kw_scores.get)
            if kw_scores[best] <= 0:
                best = "general"
            kw_max = max(max_kw_score, 1)
            score = kw_scores[best] / kw_max
            return best, score

        try:
            import numpy as np

            # Embed the first 500 chars of input text
            query_vec = model.encode(
                [text[:500]], convert_to_numpy=True, show_progress_bar=False
            )[0]
            q_norm = float(np.linalg.norm(query_vec))
            if q_norm > 0:
                query_vec = query_vec / q_norm

            protos = self._get_prototype_embeddings(model, prototypes)
            if not protos:
                raise RuntimeError("no prototype embeddings available")

            # Normalise keyword scores to [0, 1]
            domains = list(kw_scores.keys())
            kw_max = max(max_kw_score, 1)  # avoid divide-by-zero

            blended: dict = {}
            for domain in domains:
                kw_norm = kw_scores[domain] / kw_max
                if domain in protos:
                    emb_sim = self._cosine(query_vec, protos[domain])
                    # Shift cosine from [-1, 1] to [0, 1] for safety
                    emb_sim_scaled = (emb_sim + 1.0) / 2.0
                else:
                    emb_sim_scaled = 0.0

                blended[domain] = 0.6 * kw_norm + 0.4 * emb_sim_scaled

            best = max(blended, key=blended.get)
            return best, blended[best]

        except Exception as exc:
            logger.warning(
                "R1Classifier: embedding stage failed, using keyword winner: %s", exc
            )
            fallback = max(kw_scores, key=kw_scores.get)
            if kw_scores[fallback] <= 0:
                fallback = "general"
            kw_max = max(max_kw_score, 1)
            score = kw_scores[fallback] / kw_max
            return fallback, score
