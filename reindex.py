import logging
import os
import sys
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

from rag import _embed, iter_chunks

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _request(method: str, path: str, **kwargs: Any) -> requests.Response:
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/" + path
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    response = requests.request(
        method,
        url,
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        timeout=60,
        **kwargs,
    )
    response.raise_for_status()
    return response


def main() -> None:
    required = ("OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
    if any(not os.getenv(name, "").strip() for name in required):
        raise SystemExit("Для reindex.py нужны OPENAI_API_KEY, SUPABASE_URL и SUPABASE_SERVICE_ROLE_KEY")

    chunks = list(iter_chunks())
    current_files = {chunk["source_file"] for chunk in chunks}
    existing = _request("GET", "document_chunks?select=source_file,content_hash").json()
    existing_files = {row["source_file"] for row in existing}
    hashes_by_file: Dict[str, set] = {}
    for chunk in chunks:
        hashes_by_file.setdefault(chunk["source_file"], set()).add(chunk["content_hash"])
    existing_hashes: Dict[str, set] = {}
    for row in existing:
        existing_hashes.setdefault(row["source_file"], set()).add(row["content_hash"])

    changed_files = {
        source for source in current_files
        if existing_hashes.get(source, set()) != hashes_by_file[source]
    }
    changed_files |= existing_files - current_files
    for source_file in sorted(changed_files):
        _request("DELETE", "document_chunks", params={"source_file": f"eq.{source_file}"})

    to_insert = [
        chunk for chunk in chunks
        if chunk["source_file"] not in existing_files or chunk["source_file"] in changed_files
    ]
    rows: List[Dict[str, Any]] = []
    for chunk in to_insert:
        row = dict(chunk)
        row["embedding"] = _embed(chunk["content"])
        rows.append(row)
        if len(rows) == 50:
            _request("POST", "document_chunks", json=rows)
            rows.clear()
    if rows:
        _request("POST", "document_chunks", json=rows)
    logger.info("Индексация завершена: %s чанков обработано, %s файлов изменено", len(to_insert), len(changed_files))


if __name__ == "__main__":
    try:
        main()
    except requests.HTTPError as error:
        logger.error("Supabase API error: %s", error)
        sys.exit(1)