"""Retrieval + generation over Qdrant, answered by Groq.

Uses ChatGroq, model openai/gpt-oss-20b by default, key from
GROQ_API_KEY.
"""

import os
from typing import List, Dict, Any

from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq

from app.config import settings
from app.rag.vectorstore import QdrantVectorStore


class RAGSearch:
    def __init__(self, store: QdrantVectorStore | None = None):
        self.vectorstore = store or QdrantVectorStore()
        groq_api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY", "")
        if not groq_api_key:
            raise ValueError(
                "GROQ_API_KEY environment variable is not set. "
                "Copy .env.example to backend/.env and fill it in."
            )
        self.llm = ChatGroq(groq_api_key=groq_api_key, model_name=settings.groq_model)
        print(f"[INFO] Groq LLM initialized: {settings.groq_model}")

    @staticmethod
    def _to_sources(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sources = []
        for r in results:
            meta = r.get("metadata") or {}
            sources.append({
                "text": meta.get("text", ""),
                "source": meta.get("source", ""),
                "page": meta.get("page"),
                "score": r.get("score"),
            })
        return sources

    def search_and_summarize(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """Return {"answer": str, "sources": [{text, source, page, score}]}."""
        results = self.vectorstore.query(query, top_k=top_k)
        sources = self._to_sources(results)
        texts = [s["text"] for s in sources if s["text"]]
        if not texts:
            return {
                "answer": "No relevant documents found. Ingest some documents first.",
                "sources": [],
            }
        # Number the chunks so the model can cite them as [1], [2], ...
        numbered = "\n\n".join(
            f"[{i + 1}] {s['text']}"
            f" (source: {s.get('source') or 'unknown'}"
            f"{', page ' + str(s['page']) if s.get('page') is not None else ''})"
            for i, s in enumerate(sources) if s['text']
        )
        context = numbered
        prompt = (
            "Answer the question using ONLY the context below. "
            "If the context does not contain the answer, say so explicitly.\n\n"
            "Return the answer in this exact structured Markdown format, "
            "omitting any section that has nothing to say:\n\n"
            "## Summary\n"
            "One or two sentences answering the question directly.\n\n"
            "## Key points\n"
            "- One bullet per key fact, each ending with its source citation like [1] or [2].\n\n"
            "## Details\n"
            "A short paragraph (or bullets) with the supporting detail, "
            "numbers and names from the context, with citations like [1].\n\n"
            "## Limitations\n"
            "What the context does NOT cover, or where it is uncertain — "
            "one or two bullets, or 'None' if nothing is missing.\n\n"
            f"Question: {query}\n\nContext:\n{context}\n\nAnswer:"
        )
        response = self.llm.invoke([HumanMessage(content=prompt)])
        return {"answer": response.content, "sources": sources}
