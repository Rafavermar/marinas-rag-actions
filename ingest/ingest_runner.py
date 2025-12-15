"""Entry point for ingestion pipeline.

Strategy (robust + minimal):
- Treat marinas.urls as stable landing pages (HTML) whenever possible.
- From each landing HTML:
  - extract headings/paragraphs/tables (HTML)
  - discover linked PDFs (tariffs/prices)
- Also support direct PDF URLs listed in sources.yaml (optional fallback).
- Fetch PDFs and extract text.
- Chunk everything and upsert to MongoDB with source_url for traceability.
"""
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Optional

from api.storage_mongo import MongoStorage
from ingest.chunking import build_chunks
from ingest.extract_blocks import ContentBlock, extract_blocks, extract_blocks_from_text
from ingest.fetch_html import fetch_all
from ingest.fetch_docs import fetch_all_docs
from ingest.url_discovery import discover_pdf_links, dedup_keep_order


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

        seed_urls = marina_doc["urls"]
        if not seed_urls:
            continue

        html_seed_urls = [u for u in seed_urls if not u.lower().endswith(".pdf")]
        direct_pdf_urls = [u for u in seed_urls if u.lower().endswith(".pdf")]

        blocks: List[ContentBlock] = []
        discovered_pdf_urls: List[str] = []

        # 1) Fetch + extract from HTML landings
        if html_seed_urls:
            html_pages = await fetch_all(html_seed_urls)
            for html, url in zip(html_pages, html_seed_urls):
                blocks.extend(extract_blocks(html, source_url=url))
                discovered_pdf_urls.extend(discover_pdf_links(html, base_url=url, limit=5))

        # 2) Fetch PDFs (direct + discovered)
        pdf_urls = dedup_keep_order([*direct_pdf_urls, *discovered_pdf_urls])
        if pdf_urls:
            docs = await fetch_all_docs(pdf_urls)
            for doc in docs:
                if doc.kind == "text" and doc.content:
                    blocks.extend(extract_blocks_from_text(doc.content, source_url=doc.url))

        # 3) Chunk + persist
        chunks = build_chunks(blocks)
        for chunk in chunks:
            source_url = chunk.source_url or seed_urls[0]
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
