import asyncio
import logging
from typing import Any, Callable

from config import MAX_RETRIES, RETRY_BACKOFF_BASE
from orchestrator.progress import ProgressTracker

logger = logging.getLogger(__name__)


class BatchProcessor:
    def __init__(self, concurrency: int, name: str):
        self._semaphore = asyncio.Semaphore(concurrency)
        self.name = name

    async def process_batch(
        self,
        items: list[dict],
        processor_fn: Callable,
        progress: ProgressTracker,
    ) -> dict[str, Any]:
        """Process all items with concurrency control, retry, and resume."""
        pending = [item for item in items if item["slug"] not in progress.completed]
        logger.info(
            f"[{self.name}] Processing {len(pending)} items "
            f"({progress.completed_count} already done, {len(items)} total)"
        )

        results = {}
        tasks = [
            self._process_one(item, processor_fn, progress, results)
            for item in pending
        ]
        await asyncio.gather(*tasks)

        progress.finish()
        logger.info(
            f"[{self.name}] Done. {progress.completed_count} succeeded, "
            f"{progress.failed_count} failed."
        )
        return results

    async def _process_one(
        self,
        item: dict,
        processor_fn: Callable,
        progress: ProgressTracker,
        results: dict,
    ):
        slug = item["slug"]
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                async with self._semaphore:
                    result = await processor_fn(item)
                results[slug] = result
                progress.mark_completed(slug)
                logger.info(
                    f"[{self.name}] ✓ {slug} ({progress.completed_count}/{progress.data['total']})"
                )
                return
            except Exception as e:
                if attempt == MAX_RETRIES:
                    logger.error(f"[{self.name}] ✗ {slug} failed after {attempt} attempts: {e}")
                    progress.mark_failed(slug, str(e), attempt)
                    return
                wait = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"[{self.name}] {slug} attempt {attempt} failed: {e}. Retrying in {wait}s..."
                )
                await asyncio.sleep(wait)
