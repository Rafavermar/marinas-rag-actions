"""URL discovery utilities for ingestion.

Goal: keep sources stable by ingesting a marina "landing" page (HTML) and
auto-discovering linked PDFs (tariffs/prices) from that page at ingest time.

This makes the pipeline resilient to WordPress /uploads/YYYY/MM/ file changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List
from urllib.parse import urljoin

from bs4 import BeautifulSoup


# Keywords that typically indicate tariff/price PDFs
_HINTS = (
    "tarifa", "tarifas",
    "precio", "precios",
    "atraque", "atraques",
    "amarre", "amarres",
    "estadia", "estadía", "estancias",
    "rate", "rates", "pricing", "price",
    "download", "descarg", "pdf",
)


def dedup_keep_order(urls: Iterable[str]) -> List[str]:
    """De-duplicate preserving order."""
    out: List[str] = []
    seen = set()
    for u in urls:
        if not u:
            continue
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


@dataclass(frozen=True)
class PdfCandidate:
    url: str
    score: int


def _score_candidate(href: str, anchor_text: str) -> int:
    h = (href or "").lower()
    t = (anchor_text or "").lower()
    score = 0
    for k in _HINTS:
        if k in h:
            score += 2
        if k in t:
            score += 3
    if "/uploads/" in h:
        score += 1
    return score


def discover_pdf_links(html: str, base_url: str, limit: int = 5) -> List[str]:
    """Return up to `limit` absolute PDF URLs discovered in an HTML page."""
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    candidates: List[PdfCandidate] = []

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        # quick filter: must contain ".pdf" somewhere
        if ".pdf" not in href.lower():
            continue

        abs_url = urljoin(base_url, href)
        text = a.get_text(" ", strip=True) if a else ""
        candidates.append(PdfCandidate(url=abs_url, score=_score_candidate(abs_url, text)))

    if not candidates:
        return []

    candidates.sort(key=lambda c: c.score, reverse=True)
    urls = [c.url for c in candidates]
    urls = dedup_keep_order(urls)
    return urls[: max(0, limit)]
