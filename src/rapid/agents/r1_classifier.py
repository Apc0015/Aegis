from rapid.config import DOC_TYPE_KEYWORDS, RAG_MODES
from typing import Tuple

class R1Classifier:
    """
    Heuristic document type classifier. No LLM call. Fast.
    Returns (domain_key, rag_mode_config).
    """

    def classify(self, text: str, filename: str = "") -> Tuple[str, dict]:
        text_lower = (text[:3000] + filename).lower()
        scores = {}
        for domain, keywords in DOC_TYPE_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)
        best = max(scores, key=scores.get)
        if scores[best] == 0:
            best = "general"
        return best, RAG_MODES.get(best, RAG_MODES["general"])
