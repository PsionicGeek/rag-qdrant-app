"""FastAPI entry point. Run from backend/:

    uvicorn app.main:app --reload --port 8000

Multi-chat: one Qdrant collection per chat, SQLite for chats /
messages / documents (see app/db.py). RAG objects are created lazily
and cached per collection (get_rag / get_store), so the app can start
and /health can report honestly even if Qdrant is down or
GROQ_API_KEY is missing. The embedding model is also loaded lazily
inside QdrantVectorStore, on first query/ingest.
"""

from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db import init_db
from app.rag.search import RAGSearch
from app.rag.vectorstore import QdrantVectorStore

_stores: Dict[str, QdrantVectorStore] = {}
_rags: Dict[str, RAGSearch] = {}


def get_store(collection_name: Optional[str] = None) -> QdrantVectorStore:
    """Per-collection Qdrant store (cached). A query/ingest for chat A
    must never touch chat B's collection, so callers always pass the
    chat's stored collection_name."""
    name = collection_name or settings.qdrant_collection
    if name not in _stores:
        _stores[name] = QdrantVectorStore(collection_name=name)
    return _stores[name]


def get_rag(collection_name: Optional[str] = None, store: Optional[QdrantVectorStore] = None) -> RAGSearch:
    name = collection_name or settings.qdrant_collection
    if name not in _rags:
        _rags[name] = RAGSearch(store=store or get_store(name))
    return _rags[name]


def drop_cached_rag(collection_name: str) -> None:
    """Drop cached store/RAG for a collection (e.g. after it is deleted)."""
    _stores.pop(collection_name, None)
    _rags.pop(collection_name, None)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create backend/data/app.db + tables if needed. Intentionally
    # light otherwise: do not connect to Qdrant or load the embedding
    # model at startup — both happen lazily on first use.
    init_db()
    print("[INFO] rag-qdrant-app starting (multi-chat, SQLite + Qdrant + Groq wired lazily)")
    yield
    print("[INFO] rag-qdrant-app stopping")


app = FastAPI(title="rag-qdrant-app", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes live in app.api.routes; importing here registers them.
# (Circular import is avoided: routes imports get_rag/get_store
#  from this module, and this module imports routes last.)
from app.api.routes import router  # noqa: E402

app.include_router(router)


@app.get("/")
def root():
    return {"status": "ok", "docs": "/docs", "health": "/health"}
