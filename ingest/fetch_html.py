"""Download HTML pages with retries."""
import asyncio
from typing import List

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
}


def _decode_response(resp: httpx.Response) -> str:
    raw = resp.content  # bytes

    # 1) si el servidor declara encoding, úsalo
    if resp.encoding:
        return raw.decode(resp.encoding, errors="replace")

    # 2) intenta utf-8 primero
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # 3) fallback típico en webs viejas
        return raw.decode("latin-1", errors="replace")


async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        reraise=True,
    ):
        with attempt:
            resp = await client.get(url)
            resp.raise_for_status()
            return _decode_response(resp)


async def fetch_all(urls: List[str]) -> List[str]:
    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(
        timeout=timeout,
        headers=DEFAULT_HEADERS,
        follow_redirects=True,
    ) as client:
        tasks = [fetch_url(client, url) for url in urls]
        return await asyncio.gather(*tasks)
