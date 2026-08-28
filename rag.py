import asyncio
import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import requests
import yaml

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge"
RAG_TOP_K = max(1, min(int(os.getenv("RAG_TOP_K", "5")), 10))

# Глобальный кэш для модели (загружается один раз при первом вызове)
_embedding_model = None

def _embed(text: str) -> List[float]:
    """Создаёт эмбеддинг текста с помощью локальной модели sentence-transformers."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # Загружаем модель (первый раз скачается ~80 МБ)
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    # Возвращаем список обычных float (явное приведение)
    return _embedding_model.encode(text, normalize_embeddings=True).tolist()

def is_configured() -> bool:
    # Для работы нужны только ключи Supabase (OpenAI больше не требуется)
    return all(
        os.getenv(name, "").strip() and not os.getenv(name, "").strip().startswith("your_")
        for name in ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    )

def _metadata_filter(query: str) -> Optional[Dict[str, str]]:
    lower = query.lower()
    aliases = {
        "city": {
            "москва": "москва", "спб": "спб", "санкт-петербург": "санкт-петербург",
            "санкт петербург": "санкт-петербург", "казань": "казань",
            "новосибирск": "новосибирск", "екатеринбург": "екатеринбург",
        },
        "grade": {
            "junior": "junior", "middle": "middle", "senior": "senior", "lead": "lead",
            "джун": "junior", "мидл": "middle", "сеньор": "senior",
        },
        "category": {
            "зарплат": "salary", "переговор": "negotiation", "испытательн": "legal",
            "закон": "legal", "резюме": "resume", "ats": "resume",
        },
        "stack": {
            "backend": "backend", "бекенд": "backend", "frontend": "frontend",
            "devops": "devops", "python": "python", "java": "java", "go": "go",
        },
    }
    result: Dict[str, str] = {}
    for key, values in aliases.items():
        match = next((value for term, value in values.items() if term in lower), None)
        if match:
            result[key] = match
    return result or None

def search(query: str, top_k: int = RAG_TOP_K) -> List[Dict[str, Any]]:
    if not is_configured():
        return []
    vector = _embed(query)
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/rpc/match_document_chunks"
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    response = requests.post(
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={"query_embedding": vector, "match_count": top_k, "filter": _metadata_filter(query)},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

async def search_async(query: str) -> List[Dict[str, Any]]:
    return await asyncio.to_thread(search, query)

def format_context(chunks: Iterable[Dict[str, Any]]) -> str:
    formatted = []
    for chunk in chunks:
        source = chunk.get("source_file") or chunk.get("metadata", {}).get("source_file", "unknown")
        content = chunk.get("content", "").strip()
        if content:
            formatted.append(f"---\nИсточник: {source}\n{content}")
    return "\n".join(formatted)

def build_query(history: List[Dict[str, str]]) -> str:
    return "\n".join(f"{item['role']}: {item['content']}" for item in history[-3:])

def _parse_document(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    metadata: Dict[str, Any] = {}
    body = raw
    if raw.startswith("---"):
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", raw, re.DOTALL)
        if not match:
            raise ValueError(f"Некорректный frontmatter: {path}")
        metadata = yaml.safe_load(match.group(1)) or {}
        body = match.group(2).strip()
    metadata["source_file"] = str(path.relative_to(BASE_DIR)).replace("\\", "/")
    return {"metadata": metadata, "body": body}

def _split_document(body: str, chunk_size: int = 1800, overlap: int = 280) -> List[str]:
    sections = re.split(r"(?=^##\s+)", body, flags=re.MULTILINE)
    chunks: List[str] = []
    for section in (part.strip() for part in sections if part.strip()):
        start = 0
        while start < len(section):
            end = min(start + chunk_size, len(section))
            if end < len(section):
                boundary = section.rfind(" ", start, end)
                if boundary > start + chunk_size // 2:
                    end = boundary
            chunks.append(section[start:end].strip())
            if end == len(section):
                break
            start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]

def iter_chunks() -> Iterable[Dict[str, Any]]:
    for path in sorted(KNOWLEDGE_DIR.rglob("*.md")):
        document = _parse_document(path)
        for index, content in enumerate(_split_document(document["body"])):
            metadata = dict(document["metadata"])
            metadata["chunk_index"] = index
            yield {
                "source_file": metadata["source_file"],
                "content": content,
                "metadata": metadata,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            }