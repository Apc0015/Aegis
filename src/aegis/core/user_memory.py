"""
User-level memory — persists per-user preferences and interaction patterns.

Stored in data/user_memory/<user_id>.json (one file per user).
Tracks:
  - preferred_departments: which depts this user queries most
  - query_keywords: common query topics (top keywords with counts)
  - last_active: ISO timestamp
  - total_queries: int
  - preferred_format: "concise" | "detailed" (inferred from answer length feedback)

Thread-safe. Used to personalize answers and retrieval.
"""
import json
import logging
import string
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("data/user_memory")
MAX_DEPARTMENTS = 5
MAX_KEYWORDS = 20

# Common stopwords to skip during keyword extraction
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "what", "how", "why", "when", "where", "who", "which", "whom",
    "this", "that", "these", "those", "there", "here",
    "and", "but", "or", "nor", "so", "yet", "for", "of", "in", "on",
    "at", "by", "up", "to", "as", "if", "it", "its", "from", "with",
    "about", "into", "than", "then", "their", "they", "them", "some",
    "any", "all", "not", "more", "also", "just", "over", "such",
    "tell", "show", "give", "find", "list", "get", "make", "want",
    "know", "like", "use", "used", "using", "please", "help",
})


def _extract_keywords(text: str) -> list[str]:
    """
    Simple keyword extractor: lowercase, strip punctuation, remove stopwords,
    keep words longer than 3 characters.
    """
    translator = str.maketrans("", "", string.punctuation)
    words = text.lower().translate(translator).split()
    return [w for w in words if len(w) > 3 and w not in _STOPWORDS]


class UserMemoryStore:
    """Thread-safe per-user memory stored as JSON files."""

    def __init__(self, memory_dir: str = str(MEMORY_DIR)):
        self._dir = Path(memory_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, user_id: str) -> Path:
        # Sanitize user_id to a safe filename component
        safe_id = "".join(c if c.isalnum() or c in "-_." else "_" for c in user_id)
        return self._dir / f"{safe_id}.json"

    def _load(self, path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            if not isinstance(e, FileNotFoundError):
                logger.warning(f"UserMemory: corrupt JSON at {path}, resetting: {e}")
            return {}
        except Exception as e:
            logger.warning(f"UserMemory: could not load {path}: {e}")
            return {}

    def _save(self, path: Path, data: dict) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning(f"UserMemory: could not save {path}: {e}")

    def get(self, user_id: str) -> dict:
        """Return full memory dict for user, or {} if new user."""
        path = self._path(user_id)
        if not path.exists():
            return {}
        with self._lock:
            return self._load(path)

    def record_query(
        self,
        user_id: str,
        query: str,
        project_id: str,
        routing_path: str,
    ) -> None:
        """
        Called after every successful query. Updates:
        - total_queries counter
        - last_active timestamp
        - preferred_departments: dict of {dept: count}, keep top MAX_DEPARTMENTS
        - query_keywords: accumulate keyword counts, keep top MAX_KEYWORDS
        """
        # Skip denied/refused queries — don't learn from blocked interactions
        if routing_path in ("denied", "refuse"):
            return

        path = self._path(user_id)

        with self._lock:
            data = self._load(path)

            # Total queries and last active
            data["total_queries"] = data.get("total_queries", 0) + 1
            data["last_active"] = datetime.now(timezone.utc).isoformat()

            # Preferred departments
            depts: Dict[str, int] = data.get("preferred_departments", {})
            depts[project_id] = depts.get(project_id, 0) + 1
            # Keep only top MAX_DEPARTMENTS by count
            if len(depts) > MAX_DEPARTMENTS:
                depts = dict(
                    sorted(depts.items(), key=lambda x: x[1], reverse=True)[:MAX_DEPARTMENTS]
                )
            data["preferred_departments"] = depts

            # Query keywords
            keywords: Dict[str, int] = data.get("query_keywords", {})
            for kw in _extract_keywords(query):
                keywords[kw] = keywords.get(kw, 0) + 1
            # Keep only top MAX_KEYWORDS by count
            if len(keywords) > MAX_KEYWORDS:
                keywords = dict(
                    sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:MAX_KEYWORDS]
                )
            data["query_keywords"] = keywords

            self._save(path, data)

    def get_context_hint(self, user_id: str) -> str:
        """
        Return a short string summarizing user preferences for the LLM prompt.
        Example: "User frequently asks about HR policies and legal contracts. Prefers detailed answers."
        Returns "" for new users (< 3 queries).
        """
        data = self.get(user_id)
        total = data.get("total_queries", 0)
        if total < 3:
            return ""

        parts = []

        # Top departments
        depts: Dict[str, int] = data.get("preferred_departments", {})
        if depts:
            top_depts = sorted(depts.items(), key=lambda x: x[1], reverse=True)[:3]
            dept_names = [d.replace("_", " ") for d, _ in top_depts]
            if len(dept_names) == 1:
                parts.append(f"User frequently queries the {dept_names[0]} department.")
            else:
                parts.append(
                    f"User frequently queries the {', '.join(dept_names[:-1])} and "
                    f"{dept_names[-1]} departments."
                )

        # Top keywords
        keywords: Dict[str, int] = data.get("query_keywords", {})
        if keywords:
            top_kws = sorted(keywords.items(), key=lambda x: x[1], reverse=True)[:5]
            kw_list = [k for k, _ in top_kws]
            parts.append(f"Common topics: {', '.join(kw_list)}.")

        # Preferred format
        preferred_format = data.get("preferred_format")
        if preferred_format == "detailed":
            parts.append("Prefers detailed answers.")
        elif preferred_format == "concise":
            parts.append("Prefers concise answers.")

        return " ".join(parts)
