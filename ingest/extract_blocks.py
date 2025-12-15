"""Extract ordered content blocks from HTML (and plain text).

- HTML: parse headings, paragraphs/lists, and tables (converted to markdown)
- TEXT: split into paragraphs and return ContentBlock("text", ...)
"""
from __future__ import annotations

from typing import List, Optional
from io import StringIO

import pandas as pd
from bs4 import BeautifulSoup


BLOCK_TAGS = {"p", "li"}
HEADING_TAGS = {"h1", "h2", "h3"}
TABLE_TAGS = {"table"}


class ContentBlock:
    def __init__(
        self,
        kind: str,
        content: str,
        title: str = "",
        order: int = 0,
        source_url: Optional[str] = None,
    ) -> None:
        self.kind = kind
        self.content = (content or "").strip()
        self.title = title
        self.order = order
        self.source_url = source_url


def clean_soup(soup: BeautifulSoup) -> None:
    """Remove noisy tags from HTML."""
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()


def table_to_markdown(table_tag) -> List[str]:
    """Convert an HTML <table> to one or more markdown chunks."""
    table_html = str(table_tag)
    dataframes = pd.read_html(StringIO(table_html))
    if not dataframes:
        return []
    df = dataframes[0]
    markdown = df.to_markdown(index=False)
    lines = markdown.split("\n")
    header = lines[:2]
    body = lines[2:]
    chunks: List[List[str]] = []
    current: List[str] = []
    limit = 8000
    for row in body:
        trial = header + current + [row]
        if len("\n".join(trial)) > limit and current:
            chunks.append(header + current)
            current = [row]
        else:
            current.append(row)
    if current:
        chunks.append(header + current)
    return ["\n".join(part) for part in chunks]


def extract_blocks(html: str, source_url: Optional[str] = None) -> List[ContentBlock]:
    """Extract blocks from HTML."""
    soup = BeautifulSoup(html or "", "lxml")
    clean_soup(soup)
    blocks: List[ContentBlock] = []
    order = 0
    for element in soup.body.descendants if soup.body else []:
        if getattr(element, "name", None) in HEADING_TAGS:
            text = element.get_text(strip=True)
            if text:
                blocks.append(ContentBlock("heading", text, title=text, order=order, source_url=source_url))
                order += 1
        elif getattr(element, "name", None) in BLOCK_TAGS:
            text = element.get_text(" ", strip=True)
            if text:
                blocks.append(ContentBlock("text", text, order=order, source_url=source_url))
                order += 1
        elif getattr(element, "name", None) in TABLE_TAGS:
            tables_md = table_to_markdown(element)
            for md in tables_md:
                blocks.append(ContentBlock("table", md, title="Tabla", order=order, source_url=source_url))
                order += 1
    return blocks


def extract_blocks_from_text(text: str, source_url: Optional[str] = None) -> List[ContentBlock]:
    """Extract blocks from plain text (e.g., extracted from PDF).

    Minimal heuristic:
    - split by blank lines into paragraphs
    - keep each paragraph as a text block
    """
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    parts = [p.strip() for p in raw.split("\n\n") if p.strip()]
    blocks: List[ContentBlock] = []
    order = 0
    for p in parts:
        # collapse internal newlines to spaces for better search
        norm = " ".join([line.strip() for line in p.split("\n") if line.strip()])
        if not norm:
            continue
        blocks.append(ContentBlock("text", norm, order=order, source_url=source_url))
        order += 1
    return blocks
