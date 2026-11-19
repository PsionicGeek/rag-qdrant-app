"""Application settings, loaded from the environment / .env file.

Looks for .env in backend/ first, then in the project root, so both
`cp ../.env.example backend/.env` and a root-level .env work.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(_BACKEND_DIR / ".env", _BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""
    qdrant_collection: str = "rag-documents"

    # Groq
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"

    # Embeddings / chunking
    embedding_model: str = "all-MiniLM-L6-v2"
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # SQLite (multi-chat storage). Default resolves to an absolute path
    # under backend/data/app.db regardless of the process CWD — see
    # app/db.py _resolve_database_url(). Override with DATABASE_URL
    # to point at another sqlite file (or any SQLAlchemy URL).
    database_url: str = f"sqlite:///{_BACKEND_DIR / 'data' / 'app.db'}"

    # Uploads + local data dir
    upload_dir: Path = _BACKEND_DIR / "data" / "uploads"
    data_dir: Path = _BACKEND_DIR / "data"

    # Frontend origin for CORS
    frontend_origin: str = "http://localhost:5173"

    @property
    def backend_dir(self) -> Path:
        return _BACKEND_DIR


settings = Settings()
