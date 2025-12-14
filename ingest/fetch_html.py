"""Download HTML pages with retries (robust decoding)."""
import asyncio
import re
from typing import List

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â¬")


def _detect_encoding(resp: httpx.Response) -> str:
    # 1) Content-Type header
    ct = resp.headers.get("content-type", "")
    m = re.search(r"charset=([^\s;]+)", ct, flags=re.I)
    if m:
        return m.group(1).strip("\"'").lower()

    # 2) <meta charset="..."> inside head
    head = resp.content[:4096].decode("ascii", errors="ignore")
    m = re.search(r'charset=["\']?\s*([a-zA-Z0-9_\-]+)', head, flags=re.I)
    if m:
        return m.group(1).lower()

    # 3) default
    return "utf-8"


def _decode_html(resp: httpx.Response) -> str:
    raw = resp.content
    enc = _detect_encoding(resp)

    # decode with detected encoding
    try:
        text = raw.decode(enc, errors="replace")
    except LookupError:
        text = raw.decode("utf-8", errors="replace")

    # Heuristic: if it *looks* like mojibake, try UTF-8 strict and prefer it if cleaner
    if enc != "utf-8" and any(m in text for m in _MOJIBAKE_MARKERS):
        try:
            utf8 = raw.decode("utf-8", errors="strict")
            if not any(m in utf8 for m in _MOJIBAKE_MARKERS):
                text = utf8
        except UnicodeDecodeError:
            pass

    return text


async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            return _decode_html(resp)


async def fetch_all(urls: List[str]) -> List[str]:
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, headers=DEFAULT_HEADERS) as client:
        tasks = [fetch_url(client, url) for url in urls]
        return await asyncio.gather(*tasks)
