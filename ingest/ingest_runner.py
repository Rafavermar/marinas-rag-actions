"""Entry point for ingestion pipeline."""
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Optional

from api.storage_mongo import MongoStorage
from ingest.chunking import build_chunks
from ingest.extract_blocks import ContentBlock, extract_blocks
from ingest.fetch_html import fetch_all


async def load_sources(marina_id: Optional[str] = None) -> List[Dict[str, object]]:
    with open("ingest/sources.yaml", "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    marinas = data.get("marinas", [])
    if marina_id:
        marinas = [m for m in marinas if m.get("id") == marina_id]
    return marinas


async def run_ingest(storage: MongoStorage, marina_id: Optional[str] = None) -> None:
    marinas = await load_sources(marina_id)
    if not marinas:
        return

    for marina in marinas:
        marina_doc = {
            "id": marina["id"],
            "name": marina["name"],
            "urls": marina.get("urls", []),
        }
        await storage.upsert_marina(marina_doc)
        html_pages = await fetch_all(marina_doc["urls"])
        blocks: List[ContentBlock] = []
        for html, url in zip(html_pages, marina_doc["urls"]):
            extracted = extract_blocks(html, source_url=url)
            blocks.extend(extracted)
        chunks = build_chunks(blocks)
        for chunk in chunks:
            source_url = chunk.source_url or marina_doc["urls"][0]
            content_hash = storage.hash_content(f"{marina_doc['id']}::{source_url}::{chunk.content}")
            record = {
                "marina_id": marina_doc["id"],
                "source_url": source_url,
                "kind": chunk.kind,
                "title": chunk.title,
                "order": chunk.order,
                "content": chunk.content,
                "content_hash": content_hash,
                "created_at": datetime.now(timezone.utc),
            }
            await storage.upsert_chunk(record)
