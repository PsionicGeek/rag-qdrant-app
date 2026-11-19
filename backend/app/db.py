"""SQLite storage for all in-app data (multi-chat).

Tables: chats, messages, documents. Qdrant still holds the vectors —
one Qdrant collection per chat — but everything the UI shows (chat
list, history, ingested documents) lives here, so history survives
backend restarts.

SQLite file: backend/data/app.db (see config.database_url). Created
on startup by init_db(), called from main.py's lifespan.
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from app.config import settings

Base = declarative_base()


def _resolve_database_url() -> str:
    """Resolve DATABASE_URL to an absolute sqlite path under backend/.

    A relative sqlite:///./data/app.db would otherwise resolve against
    the process CWD (which varies between `uvicorn` and PyCharm runs).
    """
    url = settings.database_url
    if url.startswith("sqlite:///./"):
        rel = url[len("sqlite:///./"):]
        abs_path = (settings.backend_dir / rel).resolve()
        return f"sqlite:///{abs_path}"
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        rel = url[len("sqlite:///"):]
        if not Path(rel).is_absolute():
            abs_path = (settings.backend_dir / rel).resolve()
            return f"sqlite:///{abs_path}"
    return url


DATABASE_URL = _resolve_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


def collection_name_for(chat_id: str) -> str:
    """Qdrant collection name for a chat. Single source of truth —
    every other module must use the stored Chat.collection_name,
    never recompute this differently."""
    return f"rag-{chat_id[:8]}"


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=new_id)
    title = Column(String, nullable=False, default="New chat")
    collection_name = Column(String, unique=True, nullable=False)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)

    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="chat", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=new_id)
    chat_id = Column(String, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user' | 'assistant'
    content = Column(Text, nullable=False, default="")
    sources_json = Column(Text, nullable=True)  # JSON list of source dicts
    created_at = Column(DateTime, nullable=False, default=utcnow)

    chat = relationship("Chat", back_populates="messages")

    @property
    def sources(self):
        if not self.sources_json:
            return []
        try:
            return json.loads(self.sources_json)
        except (ValueError, TypeError):
            return []


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True, default=new_id)
    chat_id = Column(String, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    source_path = Column(String, nullable=False, default="")
    chunks = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, default=utcnow)

    chat = relationship("Chat", back_populates="documents")


def init_db() -> None:
    """Create backend/data/ and all tables if they do not exist yet."""
    Path(settings.data_dir).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    print(f"[INFO] SQLite ready: {DATABASE_URL}")


def get_db():
    """FastAPI dependency: one session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# -- chat helpers -----------------------------------------------------------

def create_chat(db, title: str | None = None) -> Chat:
    chat_id = new_id()
    chat = Chat(
        id=chat_id,
        title=(title or "New chat").strip() or "New chat",
        collection_name=collection_name_for(chat_id),
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


def get_or_create_default_chat(db) -> Chat:
    """The legacy single-chat endpoints delegate to a chat titled
    'Default', so old clients keep working after the multi-chat move."""
    chat = db.query(Chat).filter(Chat.title == "Default").order_by(Chat.created_at).first()
    if chat is None:
        chat = create_chat(db, title="Default")
    return chat


def save_message(db, chat_id: str, role: str, content: str, sources=None) -> Message:
    msg = Message(
        chat_id=chat_id,
        role=role,
        content=content,
        sources_json=json.dumps(sources) if sources else None,
    )
    db.add(msg)
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if chat is not None:
        chat.updated_at = utcnow()
    db.commit()
    db.refresh(msg)
    return msg


def auto_rename_chat(db, chat: Chat, question: str) -> None:
    """Rename a 'New chat' to its first user question (first 60 chars)."""
    if chat.title == "New chat" and question and question.strip():
        chat.title = question.strip()[:60]
        chat.updated_at = utcnow()
        db.commit()
        db.refresh(chat)
