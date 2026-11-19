"""Load documents from a folder or from uploaded files.

Supported: PDF, TXT, MD, CSV, DOCX, XLSX, JSON. Each file is loaded
in its own try/except, so one bad file never kills the whole batch.
Returns LangChain Documents (page_content + metadata with source/page).
"""

from pathlib import Path
from typing import List, Any, Iterable

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    CSVLoader,
    Docx2txtLoader,
    JSONLoader,
)
from langchain_community.document_loaders.excel import UnstructuredExcelLoader

_SUFFIX_LOADERS = {".pdf", ".txt", ".md", ".csv", ".docx", ".xlsx", ".json"}


def _load_one(path: Path):
    """Load a single file with the matching LangChain loader."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return PyPDFLoader(str(path)).load()
    if suffix in {".txt", ".md"}:
        return TextLoader(str(path), encoding="utf-8").load()
    if suffix == ".csv":
        return CSVLoader(str(path)).load()
    if suffix == ".docx":
        return Docx2txtLoader(str(path)).load()
    if suffix == ".xlsx":
        return UnstructuredExcelLoader(str(path)).load()
    if suffix == ".json":
        # jq_schema="." loads the whole JSON value as one document;
        # text_content=True keeps it as readable text.
        return JSONLoader(str(path), jq_schema=".", text_content=True).load()
    raise ValueError(f"Unsupported file type: {suffix}")


def load_documents_from_files(paths: Iterable[Path]) -> List[Any]:
    documents: List[Any] = []
    for path in paths:
        path = Path(path)
        if path.suffix.lower() not in _SUFFIX_LOADERS:
            print(f"[WARN] Skipping unsupported file: {path}")
            continue
        try:
            loaded = _load_one(path)
            print(f"[INFO] Loaded {len(loaded)} docs from {path.name}")
            documents.extend(loaded)
        except Exception as e:  # noqa: BLE001 - keep ingesting the rest
            print(f"[ERROR] Failed to load {path}: {e}")
    print(f"[INFO] Total loaded documents: {len(documents)}")
    return documents


def load_all_documents(data_dir: str) -> List[Any]:
    """Recursively load every supported file under data_dir."""
    data_path = Path(data_dir).resolve()
    print(f"[INFO] Data path: {data_path}")
    if not data_path.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_path}")
    files = sorted(
        p for p in data_path.rglob("*")
        if p.is_file() and p.suffix.lower() in _SUFFIX_LOADERS
    )
    print(f"[INFO] Found {len(files)} supported files")
    return load_documents_from_files(files)
