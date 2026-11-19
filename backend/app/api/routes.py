"""FastAPI routes — multi-chat.

  GET    /health                              -> {status, qdrant, points, chats}
  GET    /api/stats                           -> health + documents/chunks
  POST   /api/chats                           -> create a chat
  GET    /api/chats                           -> list chats, newest first
  GET    /api/chats/{id}                      -> single chat + counts
  PATCH  /api/chats/{id}                      -> rename
  DELETE /api/chats/{id}                      -> delete chat + its Qdrant collection
  GET    /api/chats/{id}/messages             -> history, oldest first
  DELETE /api/chats/{id}/messages             -> clear history only
  POST   /api/chats/{id}/query                -> ask, persists both messages
  POST   /api/chats/{id}/ingest               -> multipart files OR JSON {"data_dir"}
  DELETE /api/chats/{id}/collection           -> empty only that chat's collection
  POST   /api/query   (legacy)                -> same as Default chat's query
  POST   /api/ingest  (legacy)                -> same as Default chat's ingest
  DELETE /api/collection (legacy)             -> same as Default chat's collection

One Qdrant collection per chat (Chat.collection_name, e.g. rag-a1b2c3d4).
SQLite (app/db.py) holds chats, messages and documents; Qdrant holds
only the vectors. RAG objects are per-collection (see app.main).
"""

import shutil
from collections import defaultdict
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.db import (
    Chat,
    Document,
    Message,
    auto_rename_chat,
    create_chat,
    get_db,
    get_or_create_default_chat,
    save_message,
)
from app.main import drop_cached_rag, get_rag, get_store
from app.rag.data_loader import load_all_documents, load_documents_from_files

router = APIRouter()

ALLOWED_SUFFIXES = {".pdf", ".txt", ".md", ".csv", ".docx", ".xlsx", ".json"}


# -- request bodies ---------------------------------------------------------

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=20)


class CreateChatRequest(BaseModel):
    title: Optional[str] = None


class RenameChatRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


# -- helpers ----------------------------------------------------------------

def _chat_or_404(db: Session, chat_id: str) -> Chat:
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat is None:
        raise HTTPException(status_code=404, detail=f"Chat not found: {chat_id}")
    return chat


def _points_for(chat: Chat) -> int:
    """Points in this chat's Qdrant collection (0 if Qdrant is down)."""
    try:
        store = get_store(chat.collection_name)
        if not store.is_available():
            return 0
        return store.count()
    except Exception:  # noqa: BLE001 - health/counts must never raise
        return 0


def _chat_summary(db: Session, chat: Chat) -> dict:
    message_count = db.query(Message).filter(Message.chat_id == chat.id).count()
    document_count = db.query(Document).filter(Document.chat_id == chat.id).count()
    last = (
        db.query(Message)
        .filter(Message.chat_id == chat.id)
        .order_by(Message.created_at.desc())
        .first()
    )
    return {
        "id": chat.id,
        "title": chat.title,
        "collection_name": chat.collection_name,
        "created_at": chat.created_at,
        "updated_at": chat.updated_at,
        "points": _points_for(chat),
        "documents": document_count,
        "messages": message_count,
        "last_message_at": last.created_at if last else None,
    }


def _message_out(msg: Message) -> dict:
    return {
        "id": msg.id,
        "role": msg.role,
        "content": msg.content,
        "sources": msg.sources,
        "created_at": msg.created_at,
    }


def _do_query(db: Session, chat: Chat, req: QueryRequest) -> dict:
    """Ask a question in one chat: persist user + assistant messages."""
    save_message(db, chat.id, "user", req.query)
    auto_rename_chat(db, chat, req.query)
    try:
        rag = get_rag(chat.collection_name)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"RAG service unavailable: {e}")
    try:
        result = rag.search_and_summarize(req.query, top_k=req.top_k)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Query failed: {e}")
    save_message(db, chat.id, "assistant", result["answer"], sources=result.get("sources") or [])
    return {"answer": result["answer"], "sources": result.get("sources") or [], "chat_id": chat.id}


def _chunk_counts_by_source(documents) -> dict:
    """Chunks per source file, using the same splitter as the embedder."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", " ", ""],
    )
    by_source = defaultdict(list)
    for doc in documents:
        by_source[(doc.metadata or {}).get("source") or "unknown"].append(doc)
    return {
        source: len(splitter.split_documents(docs))
        for source, docs in by_source.items()
    }


async def _load_documents_for_ingest(request: Request, files):
    """Shared loader for the per-chat and legacy ingest endpoints.
    Returns (documents, saved_paths)."""
    content_type = request.headers.get("content-type", "")
    data_dir = None
    if content_type.startswith("application/json"):
        body = await request.json()
        data_dir = (body or {}).get("data_dir")
    elif files is None:
        form = await request.form()
        data_dir = form.get("data_dir")

    saved: List[Path] = []
    if data_dir:
        documents = load_all_documents(str(data_dir))
    elif files:
        settings.upload_dir.mkdir(parents=True, exist_ok=True)
        for upload in files:
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in ALLOWED_SUFFIXES:
                raise HTTPException(status_code=400, detail=f"Unsupported file type: {upload.filename}")
            dest = settings.upload_dir / Path(upload.filename).name
            with dest.open("wb") as f:
                shutil.copyfileobj(upload.file, f)
            saved.append(dest)
        documents = load_documents_from_files(saved)
    else:
        raise HTTPException(
            status_code=400,
            detail='Provide files to upload or JSON {"data_dir": "..."}',
        )
    return documents, saved


def _do_ingest(db: Session, chat: Chat, documents, saved: List[Path]) -> dict:
    """Rebuild ONLY this chat's Qdrant collection and replace its
    Document rows. Returns {ingested_chunks, documents, chat_id}."""
    if not documents:
        raise HTTPException(status_code=400, detail="No documents could be loaded.")
    try:
        rag = get_rag(chat.collection_name)
        chunks = rag.vectorstore.build_from_documents(documents)
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Ingest failed: {e}")

    # One Document row per source file, with its chunk count.
    db.query(Document).filter(Document.chat_id == chat.id).delete()
    counts = _chunk_counts_by_source(documents)
    for source, n_chunks in counts.items():
        path = Path(source)
        db.add(Document(
            chat_id=chat.id,
            filename=path.name,
            source_path=str(source),
            chunks=n_chunks,
        ))
    db.commit()
    return {"ingested_chunks": chunks, "documents": len(counts), "chat_id": chat.id}


def _total_points(db: Session) -> tuple:
    """(total points across all chats, chat count, qdrant available)."""
    chats = db.query(Chat).all()
    total = 0
    available = False
    for chat in chats:
        try:
            store = get_store(chat.collection_name)
            if store.is_available():
                available = True
                total += store.count()
        except Exception:  # noqa: BLE001
            continue
    return total, len(chats), available


# -- health / stats ---------------------------------------------------------

@router.get("/health")
def health(db: Session = Depends(get_db)):
    points, n_chats, available = _total_points(db)
    return {
        "status": "ok",
        "qdrant": available,
        "collection": settings.qdrant_collection,
        "points": points,
        "chats": n_chats,
    }


@router.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    payload = health(db)
    payload["documents"] = db.query(Document).count()
    payload["chunks"] = payload["points"]
    return payload


# -- chats ------------------------------------------------------------------

@router.post("/api/chats")
def create_chat_endpoint(body: CreateChatRequest = CreateChatRequest(), db: Session = Depends(get_db)):
    chat = create_chat(db, title=body.title)
    return _chat_summary(db, chat)


@router.get("/api/chats")
def list_chats(db: Session = Depends(get_db)):
    chats = db.query(Chat).order_by(Chat.updated_at.desc(), Chat.created_at.desc()).all()
    return [_chat_summary(db, chat) for chat in chats]


@router.get("/api/chats/{chat_id}")
def get_chat_endpoint(chat_id: str, db: Session = Depends(get_db)):
    return _chat_summary(db, _chat_or_404(db, chat_id))


@router.patch("/api/chats/{chat_id}")
def rename_chat(chat_id: str, body: RenameChatRequest, db: Session = Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    chat.title = body.title.strip()
    db.commit()
    db.refresh(chat)
    return _chat_summary(db, chat)


@router.delete("/api/chats/{chat_id}")
def delete_chat(chat_id: str, db: Session = Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    collection_name = chat.collection_name
    # Delete the Qdrant collection first (best effort), then the rows.
    try:
        store = get_store(collection_name)
        store.delete_collection()
    except Exception as e:  # noqa: BLE001 - still delete the SQLite rows
        print(f"[WARN] Could not delete Qdrant collection {collection_name}: {e}")
    drop_cached_rag(collection_name)
    db.delete(chat)  # messages + documents cascade
    db.commit()
    return {"status": "deleted", "chat_id": chat_id, "collection_name": collection_name}


# -- messages ---------------------------------------------------------------

@router.get("/api/chats/{chat_id}/messages")
def list_messages(chat_id: str, db: Session = Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    msgs = (
        db.query(Message)
        .filter(Message.chat_id == chat.id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )
    return [_message_out(m) for m in msgs]


@router.delete("/api/chats/{chat_id}/messages")
def clear_messages(chat_id: str, db: Session = Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    db.query(Message).filter(Message.chat_id == chat.id).delete()
    db.commit()
    return {"status": "cleared", "chat_id": chat.id, "messages": 0}


# -- per-chat query / ingest / collection -----------------------------------

@router.post("/api/chats/{chat_id}/query")
def query_chat(chat_id: str, req: QueryRequest, db: Session = Depends(get_db)):
    return _do_query(db, _chat_or_404(db, chat_id), req)


@router.post("/api/chats/{chat_id}/ingest")
async def ingest_chat(chat_id: str, request: Request, files: List[UploadFile] = File(default=None), db: Session = Depends(get_db)):
    """Ingest into ONLY this chat's collection (rebuilds it)."""
    chat = _chat_or_404(db, chat_id)
    try:
        documents, saved = await _load_documents_for_ingest(request, files)
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")
    return _do_ingest(db, chat, documents, saved)


@router.delete("/api/chats/{chat_id}/collection")
def clear_chat_collection(chat_id: str, db: Session = Depends(get_db)):
    chat = _chat_or_404(db, chat_id)
    try:
        store = get_store(chat.collection_name)
        store.recreate_empty()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")
    db.query(Document).filter(Document.chat_id == chat.id).delete()
    db.commit()
    return {"status": "cleared", "collection": chat.collection_name, "points": 0, "chat_id": chat.id}


# -- legacy single-chat endpoints (Default chat) ----------------------------

@router.post("/api/query")
def query(req: QueryRequest, db: Session = Depends(get_db)):
    return _do_query(db, get_or_create_default_chat(db), req)


@router.post("/api/ingest")
async def ingest(request: Request, files: List[UploadFile] = File(default=None), db: Session = Depends(get_db)):
    chat = get_or_create_default_chat(db)
    try:
        documents, saved = await _load_documents_for_ingest(request, files)
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Ingest failed: {e}")
    return _do_ingest(db, chat, documents, saved)


@router.delete("/api/collection")
def clear_collection(db: Session = Depends(get_db)):
    chat = get_or_create_default_chat(db)
    try:
        store = get_store(chat.collection_name)
        store.recreate_empty()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"Qdrant unavailable: {e}")
    db.query(Document).filter(Document.chat_id == chat.id).delete()
    db.commit()
    return {"status": "cleared", "collection": chat.collection_name, "points": 0}
