import asyncio
import logging
from openai import AsyncOpenAI
from typing import List
from rapid.config import EMBEDDING_PROVIDERS

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Multi-provider embedding abstraction.
    Supported: openai, ollama, local (sentence-transformers all-MiniLM-L6-v2)
    """

    def __init__(self, provider: str = "openai", api_key: str = None):
        self.provider = provider
        cfg = EMBEDDING_PROVIDERS[provider]
        self.model = cfg["model"]
        self.dimensions = cfg["dimensions"]

        if provider == "local":
            # Lazy-load sentence-transformers to avoid slow startup if unused
            from sentence_transformers import SentenceTransformer
            self._st_model = SentenceTransformer(self.model)
            self._client = None
            logger.info(f"EmbeddingService: local SentenceTransformer '{self.model}' loaded")
        else:
            base_url = "http://localhost:11434/v1" if provider == "ollama" else None
            self._client = AsyncOpenAI(
                api_key=api_key or "none",
                base_url=base_url,
            )
            self._st_model = None

    async def embed(self, text: str) -> List[float]:
        text = text.replace("\n", " ").strip()
        if self.provider == "local":
            loop = asyncio.get_event_loop()
            embedding = await loop.run_in_executor(
                None, lambda: self._st_model.encode(text).tolist()
            )
            return embedding
        resp = await self._client.embeddings.create(input=[text], model=self.model)
        return resp.data[0].embedding

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        texts = [t.replace("\n", " ").strip() for t in texts]
        if self.provider == "local":
            loop = asyncio.get_event_loop()
            embeddings = await loop.run_in_executor(
                None, lambda: self._st_model.encode(texts).tolist()
            )
            return embeddings
        resp = await self._client.embeddings.create(input=texts, model=self.model)
        return [item.embedding for item in sorted(resp.data, key=lambda x: x.index)]
