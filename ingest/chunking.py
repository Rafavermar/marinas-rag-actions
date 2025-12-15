"""Chunking helpers for linear content."""
from typing import List, Optional
import os
import re
from urllib.parse import urlparse, unquote

from ingest.extract_blocks import ContentBlock

TARGET_SIZE = 8000
WINDOW_SIZE = 5

def _title_from_source_url(source_url: str) -> str:
    """
    Deriva un título razonable desde la URL (ideal para PDFs).
    Ej: .../Tarifas_MEste.pdf -> 'Tarifas MEste'
    """
    path = urlparse(source_url).path
    name = unquote(os.path.basename(path))
    name = re.sub(r"\.pdf$", "", name, flags=re.IGNORECASE)
    name = name.replace("_", " ").replace("-", " ")
    name = re.sub(r"\s+", " ", name).strip()
    return name or "Documento PDF"

def build_chunks(blocks: List[ContentBlock]) -> List[ContentBlock]:
    chunks: List[ContentBlock] = []
    buffer: List[ContentBlock] = []

    def flush_buffer() -> None:
        if buffer:
            text = "\n\n".join(b.content for b in buffer)
            title = next((b.title for b in buffer if b.title), "")
            source_url: Optional[str] = next((b.source_url for b in buffer if b.source_url), None)

            # Fallback: si no hay título y es PDF, derivarlo del filename
            if not title and source_url and source_url.lower().endswith(".pdf"):
                title = _title_from_source_url(source_url)

            chunks.append(ContentBlock("text", text, title=title, order=len(chunks), source_url=source_url))
            buffer.clear()

    for idx, block in enumerate(blocks):

        # IMPORTANT: do not mix different sources in the same chunk
        current_source_url: Optional[str] = next((b.source_url for b in buffer if b.source_url), None)
        if buffer and current_source_url and block.source_url and block.source_url != current_source_url:
            flush_buffer()

        if block.kind == "table":
            flush_buffer()
            chunks.append(
                ContentBlock(
                    "table", block.content, title=block.title, order=len(chunks), source_url=block.source_url
                )
            )
            context_start = max(0, idx - WINDOW_SIZE)
            context_end = min(len(blocks), idx + WINDOW_SIZE + 1)
            context_blocks = blocks[context_start:idx] + [block] + blocks[idx + 1 : context_end]
            window_text = "\n\n".join(b.content for b in context_blocks)
            chunks.append(
                ContentBlock(
                    "table_window",
                    window_text,
                    title=block.title,
                    order=len(chunks),
                    source_url=block.source_url,
                )
            )
            continue

        projected = "\n\n".join([b.content for b in buffer + [block]])
        if len(projected) > TARGET_SIZE:
            flush_buffer()
        buffer.append(block)
    flush_buffer()
    return chunks
