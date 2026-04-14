import logging
import chromadb
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

class VectorStoreService:
    """
    ChromaDB wrapper with per-project collection isolation.
    """

    def __init__(self, persist_dir: str = "data/chroma"):
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)

    def _collection(self, project_id: str):
        name = f"rapid_{project_id}".replace("-", "_")[:63]
        return self._client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert(
        self,
        project_id: str,
        doc_id: str,
        chunk_index: int,
        text: str,
        embedding: List[float],
        metadata: Dict,
    ):
        col = self._collection(project_id)
        uid = f"{doc_id}_chunk_{chunk_index}"
        col.upsert(ids=[uid], embeddings=[embedding], documents=[text], metadatas=[metadata])

    def query(
        self,
        project_id: str,
        query_embedding: List[float],
        top_k: int = 5,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        col = self._collection(project_id)
        kwargs = dict(
            query_embeddings=[query_embedding],
            n_results=min(top_k, col.count() or 1),
            include=["documents", "metadatas", "distances"],
        )
        if where:
            kwargs["where"] = where
        results = col.query(**kwargs)
        out = []
        for i, doc in enumerate(results["documents"][0]):
            out.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "score": 1 - results["distances"][0][i],
            })
        return out

    def delete_by_source(self, project_id: str, source: str):
        try:
            col = self._collection(project_id)
            results = col.get(where={"source": source}, include=["documents"])
            if results["ids"]:
                col.delete(ids=results["ids"])
        except Exception as e:
            logger.error(f"Failed to delete vectors for source '{source}' in project '{project_id}': {e}")
            raise

    def delete_collection(self, project_id: str):
        name = f"rapid_{project_id}".replace("-", "_")[:63]
        try:
            self._client.delete_collection(name=name)
        except Exception as e:
            logger.warning(f"Could not delete collection '{name}': {e}")

    def count(self, project_id: str) -> int:
        try:
            return self._collection(project_id).count()
        except Exception as e:
            logger.warning(f"Could not count vectors for project '{project_id}': {e}")
            raise RuntimeError(f"Vector store count failed for project '{project_id}'") from e
