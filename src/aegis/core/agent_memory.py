"""
Agent memory — reads/writes per-department YAML files in data/agent_memory/.

Each query result can append a learning to the relevant department agent's
YAML file. Learnings are pruned to MAX_LEARNINGS to prevent unbounded growth.

The memory is used by the R4 answer prompt as context about what the agent
has learned from prior queries in this department.
"""

import logging
import threading
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

MEMORY_DIR = Path("data/agent_memory")
MAX_LEARNINGS = 50  # per department agent

# Map project_id / department names → agent YAML filename
DEPT_TO_AGENT: Dict[str, str] = {
    "hr": "hr_agent.yaml",
    "finance": "finance_agent.yaml",
    "engineering": "engineering_agent.yaml",
    "sales": "sales_agent.yaml",
    "marketing": "market_agent.yaml",
    "legal": "legal_agent.yaml",
    "it": "it_agent.yaml",
    "operations": "ops_agent.yaml",
    "product": "product_agent.yaml",
    "customer_success": "general_agent.yaml",
    "general": "general_agent.yaml",
}


class AgentMemoryStore:
    """Thread-safe read/write of department agent YAML memory files."""

    def __init__(self, memory_dir: str = str(MEMORY_DIR)):
        self._dir = Path(memory_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project_id: str) -> Optional[Path]:
        filename = DEPT_TO_AGENT.get(project_id)
        if not filename:
            return None
        return self._dir / filename

    def _load(self, path: Path) -> dict:
        try:
            import yaml
            with open(path, "r") as f:
                data = yaml.safe_load(f) or {}
            return data
        except Exception as e:
            logger.warning(f"AgentMemory: could not load {path}: {e}")
            return {}

    def _save(self, path: Path, data: dict):
        try:
            import yaml
            with open(path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.warning(f"AgentMemory: could not save {path}: {e}")

    def get_learnings(self, project_id: str) -> List[str]:
        """Return the recent learnings list for a department agent."""
        path = self._path(project_id)
        if not path or not path.exists():
            return []
        with self._lock:
            data = self._load(path)
        return data.get("recent_learnings", [])

    def get_experience(self, project_id: str) -> dict:
        """
        Return the experience counters dict for a department agent.
        Keys: total_queries, high_confidence_count, medium_confidence_count.
        Returns an empty dict if the agent file doesn't exist yet.
        """
        path = self._path(project_id)
        if not path or not path.exists():
            return {}
        with self._lock:
            data = self._load(path)
        return data.get("experience", {})

    def record_learning(
        self,
        project_id: str,
        query: str,
        confidence_verdict: str,
        routing_path: str,
        chunks_used: int,
    ) -> None:
        """
        Record a learning after a successful query.
        Only records for high/medium confidence answers to avoid reinforcing bad patterns.
        """
        if confidence_verdict == "low" or routing_path in ("denied", "refuse"):
            return

        path = self._path(project_id)
        if not path:
            return

        learning = (
            f"Q: {query[:120]} | verdict={confidence_verdict} "
            f"| chunks={chunks_used} | path={routing_path}"
        )

        with self._lock:
            data = self._load(path) if path.exists() else {}
            learnings: List[str] = data.get("recent_learnings", [])
            learnings.append(learning)
            # Keep last MAX_LEARNINGS
            if len(learnings) > MAX_LEARNINGS:
                learnings = learnings[-MAX_LEARNINGS:]
            data["recent_learnings"] = learnings

            # Update experience counters
            exp: dict = data.get("experience", {}) or {}
            exp["total_queries"] = exp.get("total_queries", 0) + 1
            if confidence_verdict == "high":
                exp["high_confidence_count"] = exp.get("high_confidence_count", 0) + 1
            elif confidence_verdict == "medium":
                exp["medium_confidence_count"] = exp.get("medium_confidence_count", 0) + 1
            data["experience"] = exp

            self._save(path, data)
