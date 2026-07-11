import asyncio
import logging
from typing import List, Dict

# duckduckgo_search was renamed to ddgs upstream; prefer the maintained package,
# fall back to the legacy name so older environments keep working.
try:
    from ddgs import DDGS
except ImportError:  # pragma: no cover - depends on installed package
    from duckduckgo_search import DDGS

logger = logging.getLogger(__name__)

class WebAgent:
    def __init__(self, max_results: int = 5):
        self.max_results = max_results

    async def search(self, query: str) -> List[Dict]:
        try:
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                None,
                lambda: list(DDGS().text(query, max_results=self.max_results))
            )
            return results
        except Exception as e:
            logger.warning(f"Web search failed for query '{query[:60]}': {e}")
            return []
