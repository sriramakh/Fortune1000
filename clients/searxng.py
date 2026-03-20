import asyncio
import logging
from typing import Optional

import aiohttp

from config import SEARXNG_BASE_URL, SEARXNG_CONCURRENCY, SEARXNG_DELAY

logger = logging.getLogger(__name__)


class SearXNGClient:
    def __init__(self):
        self._semaphore = asyncio.Semaphore(SEARXNG_CONCURRENCY)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def search(
        self,
        query: str,
        categories: str = "general",
        time_range: Optional[str] = None,
        max_results: int = 10,
    ) -> list[dict]:
        """Search SearXNG and return normalized results.

        Args:
            query: Search query string
            categories: SearXNG categories (general, news, etc.)
            time_range: Time filter - day, week, month, year
            max_results: Max results to return
        """
        params = {
            "q": query,
            "format": "json",
            "categories": categories,
        }
        if time_range:
            params["time_range"] = time_range

        async with self._semaphore:
            await asyncio.sleep(SEARXNG_DELAY)
            session = await self._get_session()
            try:
                async with session.get(SEARXNG_BASE_URL, params=params) as resp:
                    if resp.status != 200:
                        logger.warning(f"SearXNG returned {resp.status} for query: {query}")
                        return []
                    data = await resp.json()
            except Exception as e:
                logger.error(f"SearXNG error for query '{query}': {e}")
                return []

        results = []
        for item in data.get("results", [])[:max_results]:
            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "date": item.get("publishedDate", ""),
                "source": item.get("engine", ""),
            })
        return results

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
