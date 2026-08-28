"""Manually index Markdown knowledge documents in Supabase pgvector."""

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

import yaml
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter
from openai import RateLimitError
from supabase import Client, create_client

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
EMBED_BATCH_SIZE = 100


def require_environment() -> None:
    required = ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    missing = [
        name for name in required
        if not os.getenv(name, "").strip() or os.getenv(name, "").strip().startswith("your_")
    ]
    if missing:
        raise SystemExit(f"Не заданы переменные окружения: {', '.join(missing)}")
    supabase_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"].strip()
    if supabase_key.startswith("sb_publishable_") or supabase_key.startswith("sb_anon_"):
        raise SystemExit(
            "SUPABASE_SERVICE_ROLE_KEY содержит публичный ключ. "
            "Укажите серверный service_role JWT или secret sb_secret_ ключ из Supabase Dashboard."
        )


def load_chunks() -> List[Dict[str, Any]]:
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=[("##", "section")],
        strip_headers=False,
    )
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1800,
        chunk_overlap=280,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks: List[Dict[str, Any]] = []

    for path in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        raw = path.read_text(encoding="utf-8")
        metadata: Dict[str, Any] = {}
        body = raw
        if raw.startswith("---"):
            match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
            if not match:
                raise ValueError(f"Некорректный YAML frontmatter: {path}")
            metadata = yaml.safe_load(match.group(1)) or {}
            body = match.group(2).strip()

        source_file = str(path.relative_to(BASE_DIR)).replace("\\", "/")
        metadata["source_file"] = source_file
        sections = header_splitter.split_text(body)
        documents = text_splitter.split_documents(sections)
        for chunk_index, document in enumerate(documents):
            content = document.page_content.strip()
            if not content:
                continue
            chunk_metadata = {**metadata, **document.metadata, "chunk_index": chunk_index}
            chunks.append({
                "source_file": source_file,
                "content": content,
                "metadata": chunk_metadata,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            })
    return chunks


def get_existing(supabase: Client) -> List[Dict[str, Any]]:
    response = supabase.table("document_chunks").select("source_file,content_hash").execute()
    return response.data or []


def reindex() -> int:
    require_environment()
    try:
        supabase = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])
    except Exception as error:
        raise SystemExit(f"Не удалось подключиться к Supabase: {error}") from error

    embeddings = OpenAIEmbeddings(model=os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small"))
    chunks = load_chunks()
    existing = get_existing(supabase)

    current_hashes: Dict[str, set[str]] = {}
    for chunk in chunks:
        current_hashes.setdefault(chunk["source_file"], set()).add(chunk["content_hash"])
    existing_hashes: Dict[str, set[str]] = {}
    for row in existing:
        existing_hashes.setdefault(row["source_file"], set()).add(row["content_hash"])

    current_files = set(current_hashes)
    existing_files = set(existing_hashes)
    changed_files = {
        source_file for source_file in current_files
        if current_hashes[source_file] != existing_hashes.get(source_file, set())
    }
    changed_files.update(existing_files - current_files)
    pending = [
        chunk for chunk in chunks
        if chunk["source_file"] not in existing_files or chunk["source_file"] in changed_files
    ]
    rows: List[Dict[str, Any]] = []
    for start in range(0, len(pending), EMBED_BATCH_SIZE):
        batch = pending[start:start + EMBED_BATCH_SIZE]
        try:
            vectors = embeddings.embed_documents([chunk["content"] for chunk in batch])
        except RateLimitError as error:
            if "insufficient_quota" in str(error) or "credit_balance_exhausted" in str(error):
                raise SystemExit(
                    "У OpenAI закончилась квота. Пополните баланс или замените OPENAI_API_KEY "
                    "на ключ с доступным балансом."
                ) from error
            raise
        rows.extend({**chunk, "embedding": vector} for chunk, vector in zip(batch, vectors))

    # Удаляем изменённые файлы из базы
    for source_file in sorted(changed_files):
        supabase.table("document_chunks").delete().eq("source_file", source_file).execute()

    if rows:
        supabase.table("document_chunks").insert(rows).execute()

    uploaded = len(rows)
    logger.info("Изменено файлов: %s", len(changed_files))
    print(f"Загружено фрагментов: {uploaded}")
    return uploaded


if __name__ == "__main__":
    reindex()