"""Qdrant vector store.

Cosine distance, 384-dim all-MiniLM-L6-v2, payload preserves
text + source + page, rebuild recreates the collection (no duplicates),
embedding model loaded lazily and only once for query().

Qdrant persists the collection itself — there are no local index
files to manage, and no save() / load() step.
"""

import uuid
from typing import List, Any, Optional, TYPE_CHECKING

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

# NOTE: sentence-transformers is imported lazily in `model` below,
# not at module level — see embedding.py. It pulls in scipy, whose
# compiled wheels can fail to load on some macOS / Python combos.
if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer

from app.config import settings
from app.rag.embedding import EmbeddingPipeline

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: Optional[str] = None,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_model: Optional[str] = None,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
    ):
        self.collection_name = collection_name or settings.qdrant_collection
        self.url = url or settings.qdrant_url
        self.api_key = api_key if api_key is not None else (settings.qdrant_api_key or None)
        self.embedding_model = embedding_model or settings.embedding_model
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self._model = None  # SentenceTransformer, loaded lazily in `model`
        self.client = QdrantClient(url=self.url, api_key=self.api_key)
        print(f"[INFO] Qdrant client -> {self.url}, collection '{self.collection_name}'")

    @property
    def model(self):  # -> SentenceTransformer, imported lazily
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.embedding_model)
            print(f"[INFO] Loaded embedding model: {self.embedding_model}")
        return self._model

    def is_available(self) -> bool:
        try:
            self.client.get_collections()
            return True
        except Exception as e:  # noqa: BLE001 - health check must not raise
            print(f"[WARN] Qdrant unavailable: {e}")
            return False

    def ensure_collection(self, dim: int = EMBEDDING_DIM) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[INFO] Created Qdrant collection '{self.collection_name}' (dim={dim}, COSINE)")

    def delete_collection(self) -> None:
        """Delete this chat's Qdrant collection entirely (chat deletion)."""
        self.client.delete_collection(collection_name=self.collection_name)
        print(f"[INFO] Deleted Qdrant collection '{self.collection_name}'")

    def recreate_empty(self, dim: int = EMBEDDING_DIM) -> None:
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        print(f"[INFO] Recreated empty Qdrant collection '{self.collection_name}'")

    def count(self) -> int:
        if not self.client.collection_exists(self.collection_name):
            return 0
        return self.client.count(self.collection_name).count

    def build_from_documents(self, documents: List[Any]) -> int:
        """Chunk + embed documents and (re)create the collection from them.
        Returns the number of chunks ingested."""
        print(f"[INFO] Building Qdrant store from {len(documents)} raw documents...")
        emb_pipe = EmbeddingPipeline(
            model_name=self.embedding_model,
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks = emb_pipe.chunk_documents(documents)
        embeddings = emb_pipe.embed_chunks(chunks)
        metadatas = [
            {"text": chunk.page_content, **(chunk.metadata or {})}
            for chunk in chunks
        ]
        dim = int(np.asarray(embeddings).shape[1])
        self.client.recreate_collection(
            collection_name=self.collection_name,
            vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
        )
        self.add_embeddings(np.array(embeddings).astype("float32"), metadatas)
        print(f"[INFO] Qdrant store built: {len(chunks)} points in '{self.collection_name}'")
        return len(chunks)

    def add_embeddings(self, embeddings: np.ndarray, metadatas: Optional[List[Any]] = None) -> None:
        embeddings = np.asarray(embeddings, dtype="float32")
        if embeddings.ndim == 1:
            embeddings = embeddings.reshape(1, -1)
        self.ensure_collection(dim=int(embeddings.shape[1]))
        points = [
            PointStruct(id=str(uuid.uuid4()), vector=vec.tolist(), payload=meta or {})
            for vec, meta in zip(embeddings, metadatas or [{}] * len(embeddings))
        ]
        self.client.upsert(collection_name=self.collection_name, points=points, wait=True)
        print(f"[INFO] Upserted {len(points)} vectors to Qdrant.")

    def search(self, query_embedding: np.ndarray, top_k: int = 5):
        """Return [{"id", "score", "metadata"}] — metadata is the payload
        dict (with "text"). Score is COSINE similarity (higher = better).
        """
        query = np.asarray(query_embedding, dtype="float32").reshape(-1)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query.tolist(),
            limit=top_k,
            with_payload=True,
        ).points
        return [
            {
                "id": str(point.id),
                "score": float(point.score),
                "distance": 1.0 - float(point.score),
                "metadata": dict(point.payload or {}),
            }
            for point in results
        ]

    def query(self, query_text: str, top_k: int = 5):
        print(f"[INFO] Querying Qdrant for: '{query_text}'")
        query_emb = self.model.encode([query_text]).astype("float32")
        return self.search(query_emb, top_k=top_k)


if __name__ == "__main__":
    from app.rag.data_loader import load_all_documents

    docs = load_all_documents("data")
    store = QdrantVectorStore()
    store.build_from_documents(docs)
    print(f"Points in collection: {store.count()}")
    print(store.query("What is the leading cause of cancer related death?", top_k=3))
