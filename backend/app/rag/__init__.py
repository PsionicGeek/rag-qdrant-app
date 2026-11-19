"""RAG pipeline: data_loader -> embedding -> vectorstore -> search.

Intentionally empty: importing this package must NOT import
sentence-transformers / scipy. Those are loaded lazily inside
EmbeddingPipeline / QdrantVectorStore.model, on first ingest/query,
so `uvicorn app.main:app` can start even if the embedding stack
is broken or still downloading. Import the classes directly, e.g.
`from app.rag.vectorstore import QdrantVectorStore`.
""" 
