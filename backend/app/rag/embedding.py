"""Chunking + embedding.

Documents are split with RecursiveCharacterTextSplitter (1000 / 200)
and embedded with all-MiniLM-L6-v2 (384-dim).
"""

from typing import List, Any, TYPE_CHECKING

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter

# NOTE: sentence-transformers is imported lazily in __init__ below,
# not at module level. It pulls in scipy, whose compiled wheels can
# fail to load on some macOS / Python combos — that must not prevent
# `uvicorn app.main:app` from starting; it should only fail on first
# ingest/query, with a clear error.
if TYPE_CHECKING:  # pragma: no cover
    from sentence_transformers import SentenceTransformer


class EmbeddingPipeline:
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)
        print(f"[INFO] Loaded embedding model: {model_name}") 

    def chunk_documents(self, documents: List[Any]) -> List[Any]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", " ", ""],
        )
        chunks = splitter.split_documents(documents)
        print(f"[INFO] Split {len(documents)} documents into {len(chunks)} chunks.")
        return chunks

    def embed_chunks(self, chunks: List[Any]) -> np.ndarray:
        texts = [chunk.page_content for chunk in chunks]
        print(f"[INFO] Generating embeddings for {len(texts)} chunks...")
        embeddings = self.model.encode(texts, show_progress_bar=True)
        print(f"[INFO] Embeddings shape: {embeddings.shape}")
        return np.asarray(embeddings)
