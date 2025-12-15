"""Fetch documents for ingestion (HTML + PDF).

- HTML: return as-is (decoded text)
- PDF: download bytes and extract text with pypdf
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from io import BytesIO
from typing import List

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

# Reuse robust HTML decoding + default headers from fetch_html
from ingest.fetch_html import DEFAULT_HEADERS, _decode_html

try:
    from pypdf import PdfReader
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore


@dataclass
class FetchedDoc:
    url: str
    kind: str  # "html" | "text"
    content: str
    content_type: str


def _is_pdf(url: str, content_type: str) -> bool:
    if "application/pdf" in (content_type or "").lower():
        return True
    return url.lower().endswith(".pdf")


async def _fetch_one(client: httpx.AsyncClient, url: str) -> FetchedDoc:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            ctype = (resp.headers.get("content-type") or "").lower()

            if _is_pdf(url, ctype):
                if PdfReader is None:
                    raise RuntimeError(
                        "pypdf is required to ingest PDFs. Install it with: pip install pypdf"
                    )

                reader = PdfReader(BytesIO(resp.content))
                parts: List[str] = []
                for page in reader.pages:
                    try:
                        txt = page.extract_text() or ""
                    except Exception:
                        txt = ""
                    txt = txt.strip()
                    if txt:
                        parts.append(txt)

                text = "\n\n".join(parts).strip()
                return FetchedDoc(url=url, kind="text", content=text, content_type=ctype)

            # Default: treat as HTML/text
            html = _decode_html(resp)
            return FetchedDoc(url=url, kind="html", content=html, content_type=ctype)

    raise RuntimeError("Failed to fetch document")


async def fetch_all_docs(urls: List[str]) -> List[FetchedDoc]:
    """Fetch a list of URLs concurrently and return their decoded content."""
    headers = dict(DEFAULT_HEADERS)
    headers["Accept"] = "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        tasks = [_fetch_one(client, u) for u in urls]
        return await asyncio.gather(*tasks)
