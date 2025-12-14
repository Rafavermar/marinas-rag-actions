"""Extract ordered content blocks from HTML."""
from typing import List, Optional

import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO

BLOCK_TAGS = {"p", "li"}
HEADING_TAGS = {"h1", "h2", "h3"}
TABLE_TAGS = {"table"}


class ContentBlock:
    def __init__(self, kind: str, content: str, title: str = "", order: int = 0, source_url: Optional[str] = None) -> None:
        self.kind = kind
        self.content = content.strip()
        self.title = title
        self.order = order
        self.source_url = source_url

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "content": self.content,
            "title": self.title,
            "order": self.order,
            "source_url": self.source_url,
        }


def clean_soup(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "svg"]):
        tag.decompose()


def table_to_markdown(table_tag) -> List[str]:
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
    soup = BeautifulSoup(html, "lxml")
    clean_soup(soup)
    blocks: List[ContentBlock] = []
    order = 0
    for element in soup.body.descendants if soup.body else []:
        if element.name in HEADING_TAGS:
            text = element.get_text(strip=True)
            blocks.append(ContentBlock("heading", text, title=text, order=order, source_url=source_url))
            order += 1
        elif element.name in BLOCK_TAGS:
            text = element.get_text(" ", strip=True)
            if text:
                blocks.append(ContentBlock("text", text, order=order, source_url=source_url))
                order += 1
        elif element.name in TABLE_TAGS:
            tables_md = table_to_markdown(element)
            for md in tables_md:
                blocks.append(ContentBlock("table", md, title="Tabla", order=order, source_url=source_url))
                order += 1
    return blocks
