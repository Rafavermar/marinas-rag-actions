"""Download HTML pages with retries."""
import asyncio
from typing import List

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_fixed

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"


async def fetch_url(client: httpx.AsyncClient, url: str) -> str:
    async for attempt in AsyncRetrying(
        stop=stop_after_attempt(3),
        wait=wait_fixed(1),
        retry=retry_if_exception_type(httpx.HTTPError),
        reraise=True,
    ):
        with attempt:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.text

async def fetch_all(urls: List[str]) -> List[str]:
    timeout = httpx.Timeout(15.0, connect=10.0)
    headers = {"User-Agent": USER_AGENT}
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        tasks = [fetch_url(client, url) for url in urls]
        return await asyncio.gather(*tasks)
