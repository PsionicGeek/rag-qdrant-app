# rag-qdrant-app

A complete RAG pipeline with a FastAPI backend, Qdrant vector store, and a React (Vite) frontend.

Ask questions over your own documents (PDF, TXT, CSV, DOCX, JSON, Markdown). Documents are chunked and embedded locally with `all-MiniLM-L6-v2`, stored in Qdrant, retrieved by similarity, and summarised by an LLM.

**Multi-chat:** create as many chats as you like — each chat has its own documents and its own Qdrant collection (`rag-<first 8 chars of the chat id>`), so questions in one chat never see another chat's documents. Chat history, chat titles and ingested-document records live in a local SQLite database at `backend/data/app.db`, so history persists across backend restarts. Open an old chat from the left sidebar and its full history loads back.

## Architecture

```
React (Vite, :5173)  -->  FastAPI (:8000)  -->  Qdrant (:6333)
   Chat list / Chat /         app/rag/               all-MiniLM-L6-v2
   Upload / Sources           data_loader ->           384-dim, COSINE
                              embedding ->
                              vectorstore ->
                              search (ChatGroq)
                        SQLite (backend/data/app.db)
                          chats / messages / documents
```

One Qdrant collection per chat (`rag-<chat id first 8 chars>`, stored on the chat row in SQLite). The legacy endpoints (`POST /api/query`, `POST /api/ingest`, `DELETE /api/collection`) still work — they use a chat titled `Default`.

- **Ingest:** `app/rag/data_loader.py` loads PDF/TXT/CSV/DOCX/JSON/MD with LangChain loaders (per-file try/except, a bad file never kills the batch).
- **Chunk + embed:** `app/rag/embedding.py` — `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)`, `SentenceTransformer("all-MiniLM-L6-v2")`.
- **Store:** `app/rag/vectorstore.py` — `QdrantVectorStore` (Cosine, 384-dim). Payload preserves `text` + `source` + `page` (+ any other LangChain metadata). Rebuilding recreates the collection, so re-ingesting does not duplicate chunks.
- **Generate:** `app/rag/search.py` — `RAGSearch.search_and_summarize()` retrieves `top_k` chunks and calls Groq with a `HumanMessage`.

## Prerequisites

- Python 3.12+ (PyCharm: open this folder as a project, set the interpreter to a new venv)
- Docker (for Qdrant) — or a Qdrant Cloud account
- Node.js 18+ and npm (frontend)
- A Groq API key: https://console.groq.com/keys

## 1. Qdrant

```bash
docker compose up -d
# or: docker run -p 6333:6333 -p 6334:6334 -v qdrant_storage:/qdrant/storage qdrant/qdrant
```

Dashboard: http://localhost:6333/dashboard

## 2. Backend

```bash
cd backend
cp ../.env.example .env   # then fill in GROQ_API_KEY
python -m venv .venv
source .venv/bin/activate  # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs (Swagger): http://localhost:8000/docs

### Environment variables

| Variable | Default | Description |
|---|---|---|
| `QDRANT_URL` | `http://localhost:6333` | Qdrant HTTP URL |
| `QDRANT_API_KEY` | _(empty)_ | Only needed for Qdrant Cloud / secured Qdrant |
| `QDRANT_COLLECTION` | `rag-documents` | Collection name |
| `GROQ_API_KEY` | _(required)_ | Groq API key |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | Groq chat model |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | SentenceTransformer model |
| `CHUNK_SIZE` | `1000` | Chunk size in characters |
| `CHUNK_OVERLAP` | `200` | Chunk overlap in characters |

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — the Vite dev server proxies `/api` and `/health` to `http://localhost:8000`.

## Usage

1. Start Qdrant, the backend, and the frontend (above).
2. Click **+ New chat** (or use the chat created for you), open **Documents**, and upload documents (PDF/TXT/CSV/DOCX/JSON/MD) — or type a server folder path — and click **Ingest**. This rebuilds *that chat's* Qdrant collection only.
3. Ask a question, pick `top_k` (1–10), and read the structured answer with its sources (file, page, similarity score). A chat titled `New chat` is auto-renamed to your first question.
4. Switch chats from the left sidebar — each chat's history and documents are separate. **Clear chat** deletes only the messages; **Clear collection** empties that chat's Qdrant collection and its document records. Deleting a chat (🗑) deletes its messages, documents and its Qdrant collection.
5. Restart the backend any time — chats and history are reloaded from `backend/data/app.db`.

## API

| Method | Endpoint | Body | Response |
|---|---|---|---|
| `GET` | `/health` | — | `{"status": "ok", "qdrant": true, "points": 123, "chats": 2}` (points summed across all chats) |
| `GET` | `/api/stats` | — | Same as `/health`, plus `documents`/`chunks` counts |
| `POST` | `/api/chats` | `{"title": "..."}` (optional) | Chat object with `points`, `documents`, `messages`, `last_message_at` |
| `GET` | `/api/chats` | — | List of chats, newest first |
| `GET` | `/api/chats/{id}` | — | Single chat + counts |
| `PATCH` | `/api/chats/{id}` | `{"title": "..."}` | Renamed chat |
| `DELETE` | `/api/chats/{id}` | — | Deletes chat, its messages/documents and its Qdrant collection |
| `GET` | `/api/chats/{id}/messages` | — | History, oldest first |
| `DELETE` | `/api/chats/{id}/messages` | — | Clears history only (documents kept) |
| `POST` | `/api/chats/{id}/query` | `{"query": "...", "top_k": 5}` | `{"answer": "...", "sources": [...], "chat_id": "..."}` |
| `POST` | `/api/chats/{id}/ingest` | Multipart `files` **or** JSON `{"data_dir": "..."}` | `{"ingested_chunks": N, "documents": M, "chat_id": "..."}` |
| `DELETE` | `/api/chats/{id}/collection` | — | Empties only that chat's collection |
| `POST` | `/api/query` (legacy) | `{"query": "...", "top_k": 5}` | Same as the Default chat's query |
| `POST` | `/api/ingest` (legacy) | Multipart `files` **or** JSON `{"data_dir": "..."}` | Same as the Default chat's ingest |
| `DELETE` | `/api/collection` (legacy) | — | Empties the Default chat's collection |

Notes:
- `POST /api/query` returns HTTP 503 with a clear message if `GROQ_API_KEY` is missing or Qdrant is unreachable, and a plain "No relevant documents found" answer if the collection is empty.
- `POST /api/ingest` **rebuilds** the collection from the supplied documents (old chunks are replaced, not appended).

## Project structure

```
rag-qdrant-app/
  README.md  .env.example  .gitignore  docker-compose.yml
  backend/
    pyproject.toml  requirements.txt
    data/app.db              # SQLite: chats / messages / documents (git-ignored)
    data/uploads/            # uploaded files land here (git-ignored)
    app/
      __init__.py  config.py  main.py  db.py
      api/__init__.py  api/routes.py
      rag/__init__.py  rag/data_loader.py  rag/embedding.py
      rag/vectorstore.py  rag/search.py
  frontend/
    package.json  vite.config.js  index.html
    src/main.jsx  src/App.jsx  src/api.js  src/App.css
    src/components/Chat.jsx  src/components/ChatList.jsx
    src/components/Upload.jsx  src/components/Sources.jsx  src/components/Answer.jsx
```

## Swapping to xAI Grok

To use **xAI Grok** instead of Groq:

1. Get a key at https://console.x.ai and set `XAI_API_KEY` (keep `GROQ_API_KEY` unset or ignore it).
2. In `backend/app/rag/search.py`, replace the `ChatGroq` construction with an OpenAI-compatible client pointed at `https://api.x.ai/v1`, e.g. `ChatOpenAI(base_url="https://api.x.ai/v1", api_key=os.getenv("XAI_API_KEY"), model="grok-4")` (requires `langchain-openai`).
3. No other file needs to change — chunking, embeddings, Qdrant, the API contract, and the frontend are provider-agnostic.

## Troubleshooting

- **Backend says Qdrant is down (`"qdrant": false`):** check `docker compose ps` and that port 6333 is free; the backend starts anyway and reports health instead of crashing.
- **`GROQ_API_KEY environment variable is not set`:** copy `.env.example` to `backend/.env` and fill it in, then restart uvicorn.
- **First query is slow:** the embedding model downloads on first use (~90 MB) and loads into memory; subsequent queries are fast.
- **Ingest fails on one file:** the loader logs the error and continues with the other files; check the backend console for `[ERROR] Failed to load ...`.
